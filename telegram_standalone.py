#!/usr/bin/env python3
"""
独立Telegram客户端 - 连接WebSocket的纯转发客户端
只负责转发命令，不包含任何业务逻辑
"""

import asyncio
import logging
import websockets
import json
import os
import sys
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import io
import base64
import grpc

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入 gRPC 代码
import proto.trading_service_pb2 as trading_service_pb2
import proto.trading_service_pb2_grpc as trading_service_pb2_grpc

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramStandaloneClient:
    """独立Telegram客户端"""
    
    def __init__(self, bot_token: str, admin_chat_ids: list, 
                 signal_uri: str = "ws://localhost:10000",
                 grpc_uri: str = "localhost:10001"):
        self.bot_token = bot_token
        self.admin_chat_ids = admin_chat_ids
        self.signal_uri = signal_uri  # 用于接收信号推送
        self.grpc_uri = grpc_uri      # 用于发送查询命令 (gRPC)
        self.signal_websocket = None  # 专门用于监听信号的WebSocket连接
        self.app = None  # Telegram应用实例
        self.listen_task = None  # 监听任务
        
    async def connect_signal_websocket(self):
        """连接信号推送WebSocket"""
        try:
            self.signal_websocket = await websockets.connect(self.signal_uri)
            logger.info(f"✅ 已连接到信号推送服务器: {self.signal_uri}")
            return True
        except Exception as e:
            logger.error(f"❌ 信号WebSocket连接失败: {e}")
            return False
    
    async def listen_websocket_messages(self):
        """持续监听WebSocket信号推送"""
        while True:
            try:
                if not self.signal_websocket:
                    logger.info("🔄 尝试连接信号推送服务器...")
                    if not await self.connect_signal_websocket():
                        await asyncio.sleep(5)  # 等待5秒后重试
                        continue
                
                # 监听信号推送
                async for message in self.signal_websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_websocket_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"❌ 无法解析WebSocket消息: {message}")
                    except Exception as e:
                        logger.error(f"❌ 处理WebSocket消息失败: {e}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("⚠️ 信号WebSocket连接已断开，尝试重连...")
                self.signal_websocket = None
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ 信号WebSocket监听错误: {e}")
                await asyncio.sleep(5)
    
    async def handle_websocket_message(self, data: dict):
        """处理WebSocket推送的消息"""
        try:
            message_type = data.get("type")
            
            if message_type == "signal":
                # 处理交易信号
                signal_data = data.get("data", {})
                message = f"""
🚨 **交易信号**

📊 **{signal_data.get('exchange', 'Unknown')} {signal_data.get('symbol', 'Unknown')}**
⏰ 时间框架: {signal_data.get('timeframe', 'Unknown')}
🔴 信号类型: {signal_data.get('signal', 'Unknown')}
💰 价格: ${signal_data.get('price', 'Unknown')}
📅 时间: {signal_data.get('timestamp', 'Unknown')}

💡 详情: {signal_data.get('message', '')}
                """
                
                # 向所有授权用户发送消息
                for chat_id in self.admin_chat_ids:
                    try:
                        await self.app.bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"❌ 发送信号到 {chat_id} 失败: {e}")
                        
            elif message_type == "notification":
                # 处理一般通知
                notification_message = data.get("message", "")
                for chat_id in self.admin_chat_ids:
                    try:
                        await self.app.bot.send_message(
                            chat_id=chat_id,
                            text=f"ℹ️ {notification_message}"
                        )
                    except Exception as e:
                        logger.error(f"❌ 发送通知到 {chat_id} 失败: {e}")
                        
            else:
                logger.debug(f"📨 收到未知类型消息: {message_type}")
                
        except Exception as e:
            logger.error(f"❌ 处理WebSocket消息失败: {e}")
    
    async def send_command(self, command: str, parameters: dict = None) -> dict:
        """
        使用gRPC发送命令并获取响应
        """
        try:
            channel = grpc.aio.insecure_channel(self.grpc_uri)
            stub = trading_service_pb2_grpc.TradingServiceStub(channel)
            
            if command == 'chart':
                # 构建图表请求
                request = trading_service_pb2.ChartRequest(
                    exchange=parameters.get('exchange', 'okx'),
                    symbol=parameters.get('symbol', 'BTC'),
                    timeframe=parameters.get('timeframe', '3m'),
                    count=parameters.get('count', 200),
                    include_sr=parameters.get('include_sr', True)
                )
                response = await stub.GetChart(request)
                if response.success:
                    # 将图表数据保存到临时文件
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                        tmp_file.write(response.chart_data)
                        tmp_path = tmp_file.name
                    
                    return {
                        "status": "success",
                        "type": "chart",
                        "path": tmp_path,
                        "message": response.message
                    }
                else:
                    return {"status": "error", "message": response.message}
                    
            elif command == 'status':
                # 构建状态请求
                exchange = parameters.get('exchange', 'okx') if parameters else 'okx'
                request = trading_service_pb2.ExchangeStatusRequest(exchange=exchange)
                response = await stub.GetExchangeStatus(request)
                
                if response.success:
                    return {
                        "status": "success",
                        "type": "status",
                        "data": {
                            "exchange": response.exchange,
                            "online": response.online,
                            "last_update": response.last_update,
                            "symbols": list(response.symbols)
                        }
                    }
                else:
                    return {"status": "error", "message": f"获取{exchange}状态失败"}
                
            elif command == 'sr':
                # 构建S/R数据请求
                request = trading_service_pb2.SRRequest(
                    exchange=parameters.get('exchange', 'okx'),
                    symbol=parameters.get('symbol', 'BTC'),
                    timeframe=parameters.get('timeframe', '3m')
                )
                response = await stub.GetSupportResistance(request)
                if response.success:
                    return {
                        "status": "success",
                        "type": "sr_data",
                        "exchange": response.exchange,
                        "symbol": response.symbol,
                        "timeframe": response.timeframe,
                        "zones": [
                            {
                                "level": zone.level,
                                "strength": zone.strength,
                                "zone_type": zone.zone_type,
                                "touches": zone.touches
                            } for zone in response.zones
                        ]
                    }
                else:
                    return {"status": "error", "message": response.error_message}
            else:
                return {"status": "error", "message": f"未知命令: {command}"}
                
        except Exception as e:
            logger.error(f"❌ 发送gRPC命令失败: {e}")
            return {"status": "error", "message": f"gRPC命令失败: {str(e)}"}
        finally:
            try:
                await channel.close()
            except:
                pass
    
    async def handle_okx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/okx命令"""
        if update.effective_chat.id not in self.admin_chat_ids:
            await update.message.reply_text("❌ 未授权访问")
            return
            
        try:
            args = context.args
            if len(args) != 3:
                await update.message.reply_text("用法: /okx <币种> <时间框架> <数量>\n例如: /okx ETH 5m 200")
                return
            
            symbol, timeframe, count = args
            count = int(count)  # 转换为整数
            
            await update.message.reply_text(f"⏳ 正在获取 {symbol} {timeframe} 图表 (K线数量: {count})...")
            
            # 使用gRPC调用图表生成
            response = await self.send_command('chart', {
                'exchange': 'okx',
                'symbol': symbol,
                'timeframe': timeframe,
                'count': count,
                'include_sr': True
            })
            
            if response.get("status") == "success":
                chart_path = response.get("path")
                if chart_path and os.path.exists(chart_path):
                    # 发送图表文件
                    with open(chart_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=f"✅ OKX {symbol} {timeframe} 图表"
                        )
                else:
                    await update.message.reply_text("❌ 图表文件未找到")
            else:
                await update.message.reply_text(f"❌ {response.get('message', '命令执行失败')}")
                
        except Exception as e:
            logger.error(f"处理OKX命令失败: {e}")
            await update.message.reply_text(f"❌ 错误: {str(e)}")
    
    async def handle_hype_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/hype命令"""
        if update.effective_chat.id not in self.admin_chat_ids:
            await update.message.reply_text("❌ 未授权访问")
            return
            
        try:
            args = context.args
            if len(args) != 3:
                await update.message.reply_text("用法: /hype <币种> <时间框架> <数量>\n例如: /hype BTC 5m 200")
                return
            
            symbol, timeframe, count = args
            count = int(count)  # 转换为整数
            
            await update.message.reply_text(f"⏳ 正在获取 {symbol} {timeframe} 图表 (K线数量: {count})...")
            
            # 使用gRPC调用图表生成
            response = await self.send_command('chart', {
                'exchange': 'hyperliquid',
                'symbol': symbol,
                'timeframe': timeframe,
                'count': count,
                'include_sr': True
            })
            
            if response.get("status") == "success":
                chart_path = response.get("path")
                if chart_path and os.path.exists(chart_path):
                    # 发送图表文件
                    with open(chart_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=f"✅ Hyperliquid {symbol} {timeframe} 图表"
                        )
                else:
                    await update.message.reply_text("❌ 图表文件未找到")
            else:
                await update.message.reply_text(f"❌ {response.get('message', '命令执行失败')}")
                
        except Exception as e:
            logger.error(f"处理Hype命令失败: {e}")
            await update.message.reply_text(f"❌ 错误: {str(e)}")
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/start命令"""
        if update.effective_chat.id not in self.admin_chat_ids:
            await update.message.reply_text("❌ 未授权访问")
            return
            
        message = """
🤖 独立Telegram客户端已启动

📋 可用命令:
• /okx <币种> <时间框架> <数量> - OKX交易所图表查询
• /hype <币种> <时间框架> <数量> - Hyperliquid交易所图表查询
• /status <交易所> - 查看指定交易所状态

📊 示例:
• /okx ETH 5m 200
• /hype BTC 15m 100
• /status okx

💡 此客户端通过双协议连接到核心系统:
  📡 WebSocket (端口10000) - 实时信号推送
  🔗 gRPC (端口10001) - 图表查询和状态获取
        """
        await update.message.reply_text(message)
    
    async def handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/status命令"""
        if update.effective_chat.id not in self.admin_chat_ids:
            await update.message.reply_text("❌ 未授权访问")
            return
            
        try:
            args = context.args
            if len(args) != 1:
                await update.message.reply_text("用法: /status <交易所>\n例如: /status okx 或 /status hyperliquid")
                return
            
            exchange = args[0].lower()
            if exchange not in ['okx', 'hyperliquid']:
                await update.message.reply_text("❌ 支持的交易所: okx, hyperliquid")
                return
            
            await update.message.reply_text(f"⏳ 正在获取 {exchange.upper()} 交易所状态...")
            
            # 使用gRPC调用状态查询
            response = await self.send_command('status', {'exchange': exchange})
            
            if response.get("status") == "success":
                info = response.get("data", {})
                status_icon = "🟢" if info.get("online") else "🔴"
                status_text = f"📊 {exchange.upper()} 交易所状态:\n\n"
                status_text += f"{status_icon} 状态: {'在线' if info.get('online') else '离线'}\n"
                status_text += f"📅 更新时间: {info.get('last_update', 'N/A')}\n"
                symbols = info.get('symbols', [])
                if symbols:
                    status_text += f"💱 交易对数量: {len(symbols)}\n"
                    status_text += f"📋 支持的交易对: {', '.join(symbols[:10])}"
                    if len(symbols) > 10:
                        status_text += f" (+{len(symbols)-10}个)"
                
                await update.message.reply_text(status_text)
            else:
                await update.message.reply_text(f"❌ {response.get('message', '获取状态失败')}")
                
        except Exception as e:
            logger.error(f"处理状态命令失败: {e}")
            await update.message.reply_text(f"❌ 错误: {str(e)}")
    
    async def start(self):
        """异步启动方法"""
        self.app = Application.builder().token(self.bot_token).build()
        
        # 添加命令处理器
        self.app.add_handler(CommandHandler("start", self.handle_start))
        self.app.add_handler(CommandHandler("okx", self.handle_okx_command))
        self.app.add_handler(CommandHandler("hype", self.handle_hype_command))
        self.app.add_handler(CommandHandler("status", self.handle_status_command))
        
        logger.info("🚀 独立Telegram客户端启动中...")
        logger.info(f"📡 WebSocket信号地址: {self.signal_uri}")
        logger.info(f"🔗 gRPC查询地址: {self.grpc_uri}")
        logger.info(f"👥 授权用户: {self.admin_chat_ids}")
        
        # 启动WebSocket监听任务
        self.listen_task = asyncio.create_task(self.listen_websocket_messages())
        logger.info("🎧 WebSocket信号监听已启动")
        
        # 初始化应用
        await self.app.initialize()
        await self.app.start()
        
        logger.info("🤖 Telegram轮询已启动")
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("👋 收到停止信号")
        finally:
            # 清理资源
            if self.listen_task:
                self.listen_task.cancel()
            if self.websocket:
                await self.websocket.close()
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
    
    def run(self):
        """启动客户端"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("👋 独立Telegram客户端已停止")

if __name__ == "__main__":
    # 从环境变量读取配置
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_ids_str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    if not bot_token:
        logger.error("❌ 请设置TELEGRAM_BOT_TOKEN环境变量")
        sys.exit(1)
    
    try:
        admin_chat_ids = [int(x.strip()) for x in chat_ids_str.split(',') if x.strip()]
        if not admin_chat_ids:
            logger.error("❌ 请设置TELEGRAM_CHAT_ID环境变量")
            sys.exit(1)
    except ValueError:
        logger.error("❌ TELEGRAM_CHAT_ID格式错误")
        sys.exit(1)
    
    # 启动客户端
    client = TelegramStandaloneClient(
        bot_token=bot_token,
        admin_chat_ids=admin_chat_ids
    )
    
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("👋 独立Telegram客户端已停止")
