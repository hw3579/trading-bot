"""双端口WebSocket服务器
端口 10000: 信号推送服务器（只推送交易信号和通知）
端口 10001: 查询请求服务器（处理用户命令和图表请求）
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

class DualPortWebSocketServer:
    def __init__(self, signal_host: str = "localhost", signal_port: int = 10000,
                 query_host: str = "localhost", query_port: int = 10001):
        # 信号推送服务器配置
        self.signal_host = signal_host
        self.signal_port = signal_port
        self.signal_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # 查询请求服务器配置
        self.query_host = query_host
        self.query_port = query_port
        self.query_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        self.running = False
        self.signal_server = None
        self.query_server = None
        
        # 添加线程安全队列来处理来自工作线程的消息（仅用于信号推送）
        self.message_queue = queue.Queue()
        self._queue_processor_task = None
        
        # 初始化图表生成器（仅用于查询服务器）
        self.chart_generator = TechnicalAnalysisChart(figsize=(16, 10))
        
    # ===========================================
    # 信号推送服务器 (端口 10000)
    # ===========================================
    
    async def register_signal_client(self, websocket: WebSocketServerProtocol):
        """注册信号推送客户端连接"""
        self.signal_clients.add(websocket)
        logger.info(f"✅ 信号客户端已连接，当前连接数: {len(self.signal_clients)}")
        
        # 发送欢迎消息给新连接的客户端
        welcome_message = {
            "type": "welcome",
            "level": "INFO",
            "message": (
                "🎉 连接成功\n"
                "交易信号推送服务\n"
                "实时监控中...\n"
                f"端口: {self.signal_port}\n"
                f"{datetime.now().strftime('%H:%M:%S')}"
            ),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "server": "signal_server",
                "port": self.signal_port,
                "status": "connected",
                "total_connections": len(self.signal_clients)
            }
        }
        
        try:
            await websocket.send(json.dumps(welcome_message, ensure_ascii=False))
            logger.info(f"📤 已发送欢迎消息给新客户端")
        except Exception as e:
            logger.error(f"❌ 发送欢迎消息失败: {e}")
    
    async def unregister_signal_client(self, websocket: WebSocketServerProtocol):
        """注销信号推送客户端连接"""
        self.signal_clients.discard(websocket)
        logger.info(f"❌ 信号客户端已断开，当前连接数: {len(self.signal_clients)}")
    
    async def handle_signal_connection(self, websocket: WebSocketServerProtocol):
        """处理信号推送连接（只接收连接，不处理命令）"""
        await self.register_signal_client(websocket)
        try:
            # 信号服务器只推送，不接收命令
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"❌ 信号连接处理错误: {e}")
        finally:
            await self.unregister_signal_client(websocket)
    
    # ===========================================
    # 查询请求服务器 (端口 10001)
    # ===========================================
    
    async def register_query_client(self, websocket: WebSocketServerProtocol):
        """注册查询请求客户端连接"""
        self.query_clients.add(websocket)
        logger.info(f"✅ 查询客户端已连接，当前连接数: {len(self.query_clients)}")
    
    async def unregister_query_client(self, websocket: WebSocketServerProtocol):
        """注销查询请求客户端连接"""
        self.query_clients.discard(websocket)
        logger.info(f"❌ 查询客户端已断开，当前连接数: {len(self.query_clients)}")
    
    async def handle_query_connection(self, websocket: WebSocketServerProtocol):
        """处理查询请求连接"""
        await self.register_query_client(websocket)
        try:
            async for message in websocket:
                try:
                    # 解析并执行查询命令
                    response = await self.execute_query_command(message)
                    await websocket.send(json.dumps(response, ensure_ascii=False))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": "无效的JSON格式"
                    }, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"❌ 处理查询命令错误: {e}")
                    await websocket.send(json.dumps({
                        "status": "error", 
                        "message": str(e)
                    }, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"❌ 查询连接处理错误: {e}")
        finally:
            await self.unregister_query_client(websocket)
    
    async def execute_query_command(self, message: str) -> dict:
        """执行查询命令（从原WebSocket服务器迁移）"""
        # 解析命令
        parts = message.strip().split()
        if len(parts) < 4:
            return {
                "status": "error",
                "message": "命令格式错误。使用: /okx <symbol> <timeframe> <count> 或 /hype <symbol> <timeframe> <count>"
            }
        
        command = parts[0].lower()
        symbol = parts[1].upper()
        timeframe = parts[2]
        count = int(parts[3])
        
        logger.info(f"📊 处理查询命令: {command} {symbol} {timeframe} {count}")
        
        try:
            if command == "/okx":
                return await self.generate_okx_chart(symbol, timeframe, count)
            elif command == "/hype":
                return await self.generate_hype_chart(symbol, timeframe, count) 
            else:
                return {
                    "status": "error",
                    "message": f"未知命令: {command}"
                }
        except Exception as e:
            logger.error(f"❌ 执行查询命令失败: {e}")
            return {
                "status": "error",
                "message": f"命令执行失败: {str(e)}"
            }
    
    async def generate_okx_chart(self, symbol: str, timeframe: str, count: int) -> dict:
        """生成OKX图表"""
        try:
            from examples.smart_mtf_sr_example import load_okx_data
            
            # 加载数据
            df = load_okx_data(symbol)
            if df is None or len(df) == 0:
                return {
                    "status": "error",
                    "message": f"无法加载 {symbol} 数据"
                }
            
            # 获取指定数量的数据
            if len(df) > count:
                df = df.tail(count)
            
            # 生成图表
            chart_buffer = self.chart_generator.generate_chart_from_dataframe(
                df=df,
                symbol=symbol,
                timeframe=timeframe,
                return_buffer=True
            )
            
            if chart_buffer:
                # 转换为base64
                chart_data = base64.b64encode(chart_buffer.getvalue()).decode('utf-8')
                logger.info(f"✅ 图表生成成功，大小: {len(chart_data)} 字符")
                
                return {
                    "status": "success",
                    "message": f"✅ OKX {symbol} {timeframe} 图表生成成功",
                    "chart_data": chart_data
                }
            else:
                return {
                    "status": "error",
                    "message": "图表生成失败"
                }
                
        except Exception as e:
            logger.error(f"❌ 生成OKX图表失败: {e}")
            return {
                "status": "error",
                "message": f"生成图表失败: {str(e)}"
            }
    
    async def generate_hype_chart(self, symbol: str, timeframe: str, count: int) -> dict:
        """生成Hyperliquid图表"""
        try:
            # 加载Hyperliquid数据
            data_path = f"hyperliquid/data_raw/{symbol}/{symbol.lower()}_{timeframe}_latest.csv"
            
            if not os.path.exists(data_path):
                return {
                    "status": "error",
                    "message": f"未找到 {symbol} {timeframe} 数据文件"
                }
            
            # 读取数据
            df = pd.read_csv(data_path, index_col=0, parse_dates=True)
            if df is None or len(df) == 0:
                return {
                    "status": "error",
                    "message": f"无法加载 {symbol} 数据"
                }
            
            # 获取指定数量的数据
            if len(df) > count:
                df = df.tail(count)
            
            # 生成图表
            chart_buffer = self.chart_generator.generate_chart_from_dataframe(
                df=df,
                symbol=symbol,
                timeframe=timeframe,
                return_buffer=True
            )
            
            if chart_buffer:
                # 转换为base64
                chart_data = base64.b64encode(chart_buffer.getvalue()).decode('utf-8')
                logger.info(f"✅ 图表生成成功，大小: {len(chart_data)} 字符")
                
                return {
                    "status": "success",
                    "message": f"✅ Hyperliquid {symbol} {timeframe} 图表生成成功",
                    "chart_data": chart_data
                }
            else:
                return {
                    "status": "error",
                    "message": "图表生成失败"
                }
                
        except Exception as e:
            logger.error(f"❌ 生成Hyperliquid图表失败: {e}")
            return {
                "status": "error",
                "message": f"生成图表失败: {str(e)}"
            }
    
    # ===========================================
    # 信号推送功能（仅用于端口 10000）
    # ===========================================
    
    async def broadcast_to_signal_clients(self, message: dict):
        """向所有信号客户端广播消息"""
        if not self.signal_clients:
            return
        
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected_clients = set()
        
        for client in self.signal_clients:
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ 向信号客户端发送消息失败: {e}")
                disconnected_clients.add(client)
        
        # 清理断开的连接
        for client in disconnected_clients:
            self.signal_clients.discard(client)
    
    def send_signal_sync(self, message: dict):
        """线程安全的信号发送方法"""
        self.message_queue.put(message)
    
    def send_message_sync(self, message: dict):
        """向后兼容的方法名"""
        self.send_signal_sync(message)
    
    async def _process_signal_queue(self):
        """处理信号队列"""
        while self.running:
            try:
                # 非阻塞获取消息
                try:
                    message = self.message_queue.get_nowait()
                    await self.broadcast_to_signal_clients(message)
                except queue.Empty:
                    pass
                
                # 短暂休眠，避免CPU占用过高
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ 处理信号队列错误: {e}")
                await asyncio.sleep(1)
    
    # ===========================================
    # 服务器启动和管理
    # ===========================================
    
    async def start(self):
        """启动双端口WebSocket服务器"""
        try:
            self.running = True
            
            # 启动信号推送服务器 (端口 10000)
            self.signal_server = await websockets.serve(
                self.handle_signal_connection,
                self.signal_host,
                self.signal_port
            )
            logger.info(f"📡 信号推送服务器启动在 {self.signal_host}:{self.signal_port}")
            
            # 启动查询请求服务器 (端口 10001)
            self.query_server = await websockets.serve(
                self.handle_query_connection,
                self.query_host,
                self.query_port
            )
            logger.info(f"🔍 查询请求服务器启动在 {self.query_host}:{self.query_port}")
            
            # 启动信号队列处理器
            self._queue_processor_task = asyncio.create_task(self._process_signal_queue())
            logger.info("📋 信号队列处理器已启动")
            
            logger.info("🚀 双端口WebSocket服务器启动完成")
            
        except Exception as e:
            logger.error(f"❌ 启动双端口WebSocket服务器失败: {e}")
            raise
    
    async def start_signal_server_only(self):
        """只启动信号推送服务器 (端口 10000)"""
        try:
            self.running = True
            
            # 只启动信号推送服务器
            self.signal_server = await websockets.serve(
                self.handle_signal_connection,
                self.signal_host,
                self.signal_port
            )
            logger.info(f"📡 信号推送服务器启动在 {self.signal_host}:{self.signal_port}")
            
            # 启动信号队列处理器
            self._queue_processor_task = asyncio.create_task(self._process_signal_queue())
            logger.info("📋 信号队列处理器已启动")
            
            logger.info("🚀 WebSocket信号推送服务器启动完成")
            
        except Exception as e:
            logger.error(f"❌ 启动WebSocket信号推送服务器失败: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket服务器"""
        logger.info("🛑 正在停止双端口WebSocket服务器...")
        
        self.running = False
        
        # 停止信号队列处理器
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # 关闭信号推送服务器
        if self.signal_server:
            self.signal_server.close()
            await self.signal_server.wait_closed()
            logger.info("📡 信号推送服务器已停止")
        
        # 关闭查询请求服务器
        if self.query_server:
            self.query_server.close()
            await self.query_server.wait_closed()
            logger.info("🔍 查询请求服务器已停止")
        
        logger.info("✅ 双端口WebSocket服务器已完全停止")
    
    def is_port_available(self, host: str, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False
