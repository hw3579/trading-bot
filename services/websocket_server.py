"""WebSocket服务器模块
基于原有的message_server.py重构
"""

import asyncio
import websockets
from websockets import WebSocketServerProtocol
import json
import logging
from typing import Dict, Any, Set, Optional
import socket
import queue
import threading
from datetime import datetime
import os
import pandas as pd
import base64
import io

# 导入图表生成器
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generate_charts import TechnicalAnalysisChart

logger = logging.getLogger(__name__)

class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 10000):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.running = False
        self.server = None
        # 添加线程安全队列来处理来自工作线程的消息
        self.message_queue = queue.Queue()
        self._queue_processor_task = None
        # 初始化图表生成器
        self.chart_generator = TechnicalAnalysisChart(figsize=(16, 10))
        
    async def register_client(self, websocket: WebSocketServerProtocol):
        """注册客户端连接"""
        self.clients.add(websocket)
        logger.info(f"✅ 客户端已连接，当前连接数: {len(self.clients)}")
        # 移除自动欢迎消息，避免干扰命令响应
    
    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """注销客户端连接"""
        self.clients.discard(websocket)
        logger.info(f"❌ 客户端已断开，当前连接数: {len(self.clients)}")
    
    async def send_to_client(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]):
        """发送消息给单个客户端"""
        try:
            await websocket.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            await self.unregister_client(websocket)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """广播消息给所有客户端"""
        if not self.clients:
            return
        
        # 创建消息副本，避免并发修改
        clients_copy = self.clients.copy()
        
        # 并发发送消息
        tasks = []
        for client in clients_copy:
            # 检查连接状态 - 新版websockets库的兼容性修复
            try:
                # 检查连接是否仍然开放
                if hasattr(client, 'closed'):
                    # 旧版本API
                    if not client.closed:
                        tasks.append(self.send_to_client(client, message))
                elif hasattr(client, 'state'):
                    # 新版本API - 检查连接状态
                    from websockets.protocol import State
                    if client.state == State.OPEN:
                        tasks.append(self.send_to_client(client, message))
                else:
                    # 直接尝试发送，在send_to_client中处理异常
                    tasks.append(self.send_to_client(client, message))
            except Exception as e:
                logger.debug(f"检查客户端状态时出错: {e}")
                # 如果无法检查状态，直接尝试发送
                tasks.append(self.send_to_client(client, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                try:
                    # 首先检查是否是字符串命令
                    if isinstance(message, str) and message.startswith('/'):
                        await self.handle_command_string(websocket, message)
                        continue
                    
                    # 尝试解析JSON
                    data = json.loads(message)
                    # 处理客户端发送的消息
                    logger.debug(f"收到客户端消息: {data}")
                    
                    # 检查是否是Telegram命令
                    if isinstance(data, dict) and data.get('type') == 'telegram_command':
                        await self.handle_telegram_command(websocket, data)
                    # 检查是否是命令消息
                    elif isinstance(data, dict) and 'command' in data:
                        await self.handle_command(websocket, data)
                        
                except json.JSONDecodeError:
                    # 可能是纯字符串命令
                    if isinstance(message, str) and message.startswith('/'):
                        await self.handle_command_string(websocket, message)
                    else:
                        logger.warning(f"收到无效JSON消息: {message}")
                except Exception as e:
                    logger.error(f"处理客户端消息错误: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"客户端处理错误: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def handle_telegram_command(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """处理来自Telegram的命令"""
        try:
            command = data.get('command', '')
            chat_id = data.get('chat_id')
            
            logger.info(f"处理Telegram命令: {command} (chat_id: {chat_id})")
            
            # 执行命令并直接回复给发送方的websocket连接
            if command.startswith('/'):
                await self.handle_command_string(websocket, command)
            
        except Exception as e:
            logger.error(f"处理Telegram命令失败: {e}")
            await self.send_error_message(websocket, f"处理Telegram命令失败: {e}")
    
    async def handle_command(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """处理结构化命令"""
        command = data.get('command', '')
        if command.startswith('/'):
            await self.handle_command_string(websocket, command)
    
    async def handle_command_string(self, websocket: WebSocketServerProtocol, command: str):
        """处理字符串命令"""
        try:
            parts = command.strip().split()
            if len(parts) < 4:
                await self.send_error_message(websocket, "命令格式错误。正确格式: /交易所 币种 时间框架 数量")
                return
            
            exchange = parts[0][1:]  # 去掉前面的 /
            symbol = parts[1].upper()
            timeframe = parts[2]
            count = int(parts[3])
            
            # 支持的交易所
            supported_exchanges = ['okx', 'hype', 'hyperliquid']
            if exchange not in supported_exchanges:
                await self.send_error_message(websocket, f"不支持的交易所: {exchange}。支持的交易所: {', '.join(supported_exchanges)}")
                return
            
            # 执行查询命令
            await self.execute_query_command(websocket, exchange, symbol, timeframe, count)
            
        except ValueError:
            await self.send_error_message(websocket, "数量必须是整数")
        except Exception as e:
            await self.send_error_message(websocket, f"处理命令时出错: {e}")
            logger.error(f"命令处理错误: {e}")
    
    async def execute_query_command(self, websocket: WebSocketServerProtocol, exchange: str, symbol: str, timeframe: str, count: int):
        """执行查询命令，返回图表数据"""
        try:
            # 标准化交易所名称
            if exchange in ['hype', 'hyperliquid']:
                exchange = 'hyperliquid'
            
            # 构建数据文件路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_file = os.path.join(base_dir, exchange, "data_raw", symbol, f"{symbol.lower()}_{timeframe}_latest.csv")
            
            if not os.path.exists(data_file):
                await self.send_error_message(websocket, f"找不到数据文件: {exchange}/{symbol}/{timeframe}")
                return
            
            # 读取数据
            df = pd.read_csv(data_file, index_col=0, parse_dates=True)
            
            if len(df) == 0:
                await self.send_error_message(websocket, "数据文件为空")
                return
            
            # 获取最后N条数据
            chart_data = df.tail(count)
            
            # 构建响应数据
            response = {
                "status": "success",
                "type": "chart_data",
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(chart_data),
                "message": f"✅ {exchange.upper()} {symbol} {timeframe} 数据查询成功 ({len(chart_data)}条)",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "timestamps": [idx.isoformat() if hasattr(idx, 'isoformat') else str(idx) for idx in chart_data.index],
                    "open": chart_data['open'].tolist(),
                    "high": chart_data['high'].tolist(),
                    "low": chart_data['low'].tolist(),
                    "close": chart_data['close'].tolist(),
                    "volume": chart_data['volume'].tolist()
                },
                "current_price": float(chart_data['close'].iloc[-1]),
                "price_change": float(chart_data['close'].iloc[-1] - chart_data['close'].iloc[0]),
                "price_change_percent": float((chart_data['close'].iloc[-1] - chart_data['close'].iloc[0]) / chart_data['close'].iloc[0] * 100)
            }
            
            # 检查是否有 S/R 数据
            sr_file = os.path.join(base_dir, exchange, "data_sr", symbol, f"{symbol.lower()}_{timeframe}_latest_sr.csv")
            if os.path.exists(sr_file):
                try:
                    sr_df = pd.read_csv(sr_file, index_col=0, parse_dates=True)
                    if len(sr_df) > 0 and 'sr_data' in sr_df.columns:
                        latest_sr_data = sr_df['sr_data'].iloc[-1]
                        if latest_sr_data != 'None':
                            sr_json = json.loads(latest_sr_data)
                            response["sr_analysis"] = sr_json
                except Exception as e:
                    logger.warning(f"读取S/R数据失败: {e}")
            
            # 检查是否有 UTBot 数据
            utbot_file = os.path.join(base_dir, exchange, "data_utbot", symbol, f"{symbol.lower()}_{timeframe}_latest_utbotv5.csv")
            if os.path.exists(utbot_file):
                try:
                    utbot_df = pd.read_csv(utbot_file, index_col=0, parse_dates=True)
                    if len(utbot_df) > 0:
                        # 获取最后的信号
                        latest_utbot = utbot_df.tail(count)
                        response["utbot_data"] = {
                            "buy_signals": [],
                            "sell_signals": [],
                            "stop_levels": latest_utbot['stop'].tolist()
                        }
                        
                        # 提取买卖信号
                        for i, (idx, row) in enumerate(latest_utbot.iterrows()):
                            if row.get('buy', False):
                                response["utbot_data"]["buy_signals"].append({
                                    "index": i,
                                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                                    "price": float(row['close'])
                                })
                            if row.get('sell', False):
                                response["utbot_data"]["sell_signals"].append({
                                    "index": i,
                                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                                    "price": float(row['close'])
                                })
                except Exception as e:
                    logger.warning(f"读取UTBot数据失败: {e}")
            
            # 生成图表图像
            try:
                # 直接使用图表生成器，让它处理S/R计算
                chart_buffer = self.chart_generator.generate_chart_from_dataframe(
                    chart_data, 
                    symbol=symbol,
                    timeframe=timeframe,
                    include_sr_analysis=False,  # 让图表生成器自己计算
                    sr_analysis=None,
                    utbot_data=None,
                    return_buffer=True
                )
                
                if chart_buffer:
                    # 转换为base64编码
                    chart_buffer.seek(0)
                    chart_base64 = base64.b64encode(chart_buffer.getvalue()).decode('utf-8')
                    response["chart_data"] = chart_base64
                    logger.info(f"✅ 图表生成成功，大小: {len(chart_base64)} 字符")
                else:
                    logger.warning("图表生成失败，返回空缓冲区")
                    
            except Exception as e:
                logger.error(f"图表生成失败: {e}")
                # 即使图表生成失败，我们仍然发送数据
            
            await self.send_to_client(websocket, response)
            logger.info(f"已发送图表数据: {exchange} {symbol} {timeframe} ({count}条)")
            
        except Exception as e:
            await self.send_error_message(websocket, f"查询数据时出错: {e}")
            logger.error(f"查询命令执行错误: {e}")
    
    async def send_error_message(self, websocket: WebSocketServerProtocol, error_msg: str):
        """发送错误消息"""
        error_response = {
            "status": "error",
            "type": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_to_client(websocket, error_response)
    
    async def start(self):
        """启动WebSocket服务器（兼容接口）"""
        return await self.start_server()

    async def start_server(self):
        """启动WebSocket服务器"""
        try:
            self.running = True
            
            # 启动队列处理器
            self._queue_processor_task = asyncio.create_task(self._process_message_queue())
            
            # 尝试IPv4和IPv6
            try:
                self.server = await websockets.serve(
                    self.handle_client,
                    self.host,
                    self.port,
                    family=socket.AF_UNSPEC  # 支持IPv4和IPv6
                )
                logger.info(f"WebSocket服务器启动在 {self.host}:{self.port}")
            except Exception as e:
                logger.warning(f"无法绑定到 {self.host}:{self.port}: {e}")
                # 尝试只使用IPv4
                self.server = await websockets.serve(
                    self.handle_client,
                    self.host,
                    self.port,
                    family=socket.AF_INET
                )
                logger.info(f"WebSocket服务器启动在 {self.host}:{self.port} (仅IPv4)")
            
            return self.server
        except Exception as e:
            logger.error(f"启动WebSocket服务器失败: {e}")
            self.running = False
            raise

    async def _process_message_queue(self):
        """处理消息队列中的消息"""
        while self.running:
            try:
                # 非阻塞地检查队列
                try:
                    message = self.message_queue.get_nowait()
                    await self.broadcast_message(message)
                    self.message_queue.task_done()
                except queue.Empty:
                    # 队列为空，稍等片刻
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"处理消息队列失败: {e}")
                await asyncio.sleep(0.1)
    
    async def stop(self):
        """停止WebSocket服务器"""
        self.running = False
        
        # 停止队列处理器
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
            # 关闭所有客户端连接
            if self.clients:
                close_tasks = []
                for client in self.clients.copy():
                    try:
                        # 检查客户端是否有close方法
                        if hasattr(client, 'close'):
                            close_tasks.append(client.close())
                        elif hasattr(client, 'wait_closed'):
                            # 如果客户端已经有wait_closed方法，说明已经在关闭
                            pass
                    except Exception as e:
                        logger.debug(f"关闭客户端连接时出错: {e}")
                
                if close_tasks:
                    await asyncio.gather(*close_tasks, return_exceptions=True)
            
            logger.info("WebSocket服务器已停止")
    
    def send_message_sync(self, message: Dict[str, Any]):
        """同步发送消息（用于从其他线程调用）"""
        if not self.running:
            return
        
        try:
            # 将消息放入队列，由主事件循环的队列处理器来处理
            self.message_queue.put(message)
            logger.debug(f"消息已加入队列: {message.get('type', '未知类型')}")
        except Exception as e:
            logger.error(f"同步发送消息失败: {e}")

# 全局WebSocket服务器实例
_websocket_server: WebSocketServer = None

def get_websocket_server() -> WebSocketServer:
    """获取WebSocket服务器实例"""
    return _websocket_server

def set_websocket_server(server: WebSocketServer):
    """设置WebSocket服务器实例"""
    global _websocket_server
    _websocket_server = server

def send_message(message: Dict[str, Any]):
    """发送消息到WebSocket客户端（兼容原有接口）"""
    server = get_websocket_server()
    if server:
        server.send_message_sync(message)

# 兼容原有接口的函数
async def start_message_server(host: str = "0.0.0.0", port: int = 10000, 
                              ipv6_enabled: bool = False, bind_both: bool = True) -> WebSocketServer:
    """启动消息服务器（兼容原有接口）"""
    server = WebSocketServer(host, port)
    await server.start()
    set_websocket_server(server)
    return server
    return server
