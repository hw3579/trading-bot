"""Telegram客户端服务
基于原有的telegram_bot.py重构
"""

import asyncio
import websockets
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Union

# 添加项目根目录到路径，以便导入图表生成器
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    TelegramError = Exception
    logging.getLogger(__name__).warning("⚠️ python-telegram-bot 未安装，Telegram功能将被禁用")

# 导入图表生成器
try:
    from generate_charts import TechnicalAnalysisChart
    CHART_GENERATOR_AVAILABLE = True
except ImportError as e:
    CHART_GENERATOR_AVAILABLE = False
    logging.getLogger(__name__).warning(f"⚠️ 图表生成器导入失败: {e}")
    TechnicalAnalysisChart = None

logger = logging.getLogger(__name__)

class TelegramClient:
    """Telegram通知客户端"""
    
    def __init__(self, bot_token: str, chat_ids: Union[str, List[str]], websocket_uri: str):
        if not TELEGRAM_AVAILABLE:
            raise ImportError("python-telegram-bot 未安装，无法使用Telegram功能")
            
        self.bot_token = bot_token
        self.websocket_uri = websocket_uri
        
        # 处理chat_ids
        if isinstance(chat_ids, str):
            self.chat_ids = [chat_ids]
        else:
            self.chat_ids = list(chat_ids)
        
        self.running = False
        self.connected_count = 0
        self.message_count = 0
        self.signal_count = 0
        self.start_time = datetime.now()
        
        # 初始化Telegram Bot
        try:
            self.bot = Bot(token=bot_token)
            logger.info("✅ Telegram Bot 初始化成功")
        except Exception as e:
            logger.error(f"❌ Telegram Bot 初始化失败: {e}")
            raise
        
        # 初始化图表生成器
        if CHART_GENERATOR_AVAILABLE:
            self.chart_generator = TechnicalAnalysisChart(figsize=(20, 12))
            logger.info("✅ 图表生成器初始化成功")
        else:
            self.chart_generator = None
            logger.warning("⚠️ 图表生成器不可用")
        
        # 初始化Application (用于处理命令)
        self.application = None
    
    async def test_telegram_connection(self):
        """测试Telegram连接"""
        try:
            me = await self.bot.get_me()
            logger.info(f"🤖 Telegram Bot: @{me.username}")
            
            # 发送测试消息到所有chat_id
            test_msg = "🚀 交易信号监控机器人已启动\n📡 正在监听交易信号...\n\n💡 使用 /info 查看技术分析图表\n📖 格式: /info [symbol] [timeframe] [candles]\n📝 例子: /info ETH 5m 100"
            await self.send_telegram_message(test_msg)
            logger.info("✅ Telegram 测试消息发送成功")
            return True
        except TelegramError as e:
            logger.error(f"❌ Telegram 连接测试失败: {e}")
            return False
    
    def format_signal_for_telegram(self, data: Dict[str, Any]) -> str:
        """格式化交易信号为Telegram消息"""
        signal_type = data.get('signal_type', 'UNKNOWN')
        exchange = data.get('exchange', 'N/A').upper()
        symbol = data.get('symbol', 'N/A')
        price = data.get('price', 0)
        timeframe = data.get('timeframe', '')
        
        # 选择图标
        if signal_type == "BUY":
            icon = "🟢"
        elif signal_type == "SELL":
            icon = "🔴"
        else:
            icon = "⚪"
        
        # 格式化价格
        if isinstance(price, (int, float)) and price > 0:
            if price >= 1:
                price_str = f"{price:,.4f}"
            else:
                price_str = f"{price:.8f}"
        else:
            price_str = "N/A"
        
        # 构建基础消息
        timeframe_str = f" ({timeframe})" if timeframe else ""
        message = f"{icon} **{signal_type}**\n"
        message += f"`{symbol}`{timeframe_str}\n"
        message += f"`{price_str}`\n"
        message += f"`{exchange}`\n"
        message += f"`{datetime.now().strftime('%H:%M:%S')}`"
        
        # 添加S/R增强信息（如果存在）
        enhanced_message = data.get('enhanced_message', '')
        if enhanced_message:
            # 将enhanced_message转换为Telegram Markdown格式
            sr_info = enhanced_message.replace('📊', '📊').replace('🎯', '🎯').replace('📈', '📈').replace('📉', '📉')
            message += f"\n\n{sr_info}"
        
        return message
    
    def format_general_message_for_telegram(self, data: Dict[str, Any]) -> str:
        """格式化一般消息为Telegram消息"""
        level = data.get('level', 'INFO')
        message = data.get('message', '')
        timestamp = data.get('timestamp', '')
        source = data.get('source', '')
        
        # 根据日志级别选择图标
        level_icons = {
            "ERROR": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
            "DEBUG": "🔍"
        }
        
        icon = level_icons.get(level, "📝")
        
        tg_message = f"{icon} **[{level}]**\n"
        tg_message += f"📝 消息: `{message}`\n"
        
        if source:
            tg_message += f"📍 来源: `{source}`\n"
        if timestamp:
            tg_message += f"⏰ 时间: `{timestamp}`"
        
        return tg_message
    
    async def send_telegram_message(self, message: str, parse_mode='Markdown'):
        """发送Telegram消息"""
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id, 
                    text=message,
                    parse_mode=parse_mode
                )
                logger.info(f"✅ Telegram 消息发送成功 (chat_id={chat_id})")
            except TelegramError as e:
                logger.error(f"❌ Telegram 消息发送失败 (chat_id={chat_id}): {e}")
                # 如果Markdown解析失败，尝试发送纯文本
                if parse_mode == 'Markdown':
                    try:
                        plain_text = message.replace('**', '').replace('`', '')
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=plain_text
                        )
                        logger.info(f"✅ Telegram 纯文本消息发送成功 (chat_id={chat_id})")
                    except TelegramError as e2:
                        logger.error(f"❌ Telegram 纯文本消息也发送失败 (chat_id={chat_id}): {e2}")
    
    async def send_telegram_photo(self, photo_path: str, caption: str = ""):
        """发送Telegram图片"""
        for chat_id in self.chat_ids:
            try:
                with open(photo_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption,
                        parse_mode='Markdown'
                    )
                logger.info(f"✅ Telegram 图片发送成功 (chat_id={chat_id})")
            except TelegramError as e:
                logger.error(f"❌ Telegram 图片发送失败 (chat_id={chat_id}): {e}")
            except FileNotFoundError:
                logger.error(f"❌ 图片文件不存在: {photo_path}")
            except Exception as e:
                logger.error(f"❌ 发送图片时出错: {e}")
    
    async def handle_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /info 命令 - 现在通过WebSocket转发"""
        try:
            args = context.args
            chat_id = update.effective_chat.id
            
            # 检查权限 - 只允许配置的chat_id使用
            if str(chat_id) not in self.chat_ids:
                await update.message.reply_text("❌ 您没有权限使用此命令")
                return
            
            # 解析参数，现在支持交易所选择
            # 格式: /info [交易所] [币种] [时间框架] [K线数量]
            # 例如: /info okx ETH 5m 200
            
            # 默认值
            exchange = "okx"  # 默认交易所改为okx
            symbol = "ETH"
            timeframe = "5m"
            candles = 200
            
            if len(args) >= 1:
                # 第一个参数可能是交易所或币种
                first_arg = args[0].lower()
                if first_arg in ['okx', 'hype', 'hyperliquid']:
                    exchange = first_arg
                    if len(args) >= 2:
                        symbol = args[1].upper()
                    if len(args) >= 3:
                        timeframe = args[2].lower()
                    if len(args) >= 4:
                        try:
                            candles = int(args[3])
                        except ValueError:
                            pass
                else:
                    # 第一个参数是币种，使用默认交易所
                    symbol = first_arg.upper()
                    if len(args) >= 2:
                        timeframe = args[1].lower()
                    if len(args) >= 3:
                        try:
                            candles = int(args[2])
                        except ValueError:
                            pass
            
            # 限制K线数量范围
            if candles < 50:
                candles = 50
            elif candles > 1000:
                candles = 1000
            
            # 发送处理中消息
            processing_msg = f"🔄 正在生成 {exchange.upper()} {symbol} 技术分析图表...\n"
            processing_msg += f"📊 时间框架: {timeframe}\n"
            processing_msg += f"📈 K线数量: {candles}\n"
            processing_msg += f"⏳ 请稍候..."
            
            await update.message.reply_text(processing_msg)
            
            # 通过WebSocket发送命令给主服务器
            command = f"/{exchange} {symbol} {timeframe} {candles}"
            await self.send_command_to_websocket(command, chat_id)
            
        except Exception as e:
            logger.error(f"处理info命令时出错: {e}")
            await update.message.reply_text(f"❌ 处理命令时出错: {e}")
    
    async def send_command_to_websocket(self, command: str, chat_id: int):
        """通过WebSocket发送命令到主服务器"""
        try:
            # 连接到WebSocket服务器
            async with websockets.connect(self.websocket_uri) as websocket:
                # 发送命令，包含来源信息
                command_data = {
                    "type": "telegram_command",
                    "command": command,
                    "chat_id": chat_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(command_data))
                logger.info(f"已发送命令到WebSocket: {command}")
                
                # 等待响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    response_data = json.loads(response)
                    
                    if response_data.get('type') == 'chart_data':
                        # 处理图表数据响应
                        await self.handle_chart_data_response(response_data, chat_id)
                    elif response_data.get('type') == 'error':
                        # 处理错误响应
                        await self.send_telegram_message(f"❌ {response_data.get('message', '未知错误')}", [str(chat_id)])
                        
                except asyncio.TimeoutError:
                    await self.send_telegram_message("⏰ 查询超时，请稍后重试", [str(chat_id)])
                    
        except Exception as e:
            logger.error(f"发送命令到WebSocket失败: {e}")
            await self.send_telegram_message(f"❌ 服务器连接失败: {e}", [str(chat_id)])
    
    async def handle_chart_data_response(self, data: Dict[str, Any], chat_id: int):
        """处理图表数据响应"""
        try:
            if not self.chart_generator:
                await self.send_telegram_message("❌ 图表生成器不可用", [str(chat_id)])
                return
            
            # 从响应数据构建DataFrame
            import pandas as pd
            
            chart_data = pd.DataFrame({
                'open': data['data']['open'],
                'high': data['data']['high'],
                'low': data['data']['low'],
                'close': data['data']['close'],
                'volume': data['data']['volume']
            }, index=pd.to_datetime(data['data']['timestamps']))
            
            # 生成图表
            exchange = data['exchange']
            symbol = data['symbol']
            timeframe = data['timeframe']
            
            chart_path = await self.generate_chart_async(
                chart_data, 
                f"{exchange.upper()}:{symbol}",
                timeframe,
                include_sr_analysis=data.get('sr_analysis') is not None,
                sr_analysis=data.get('sr_analysis'),
                utbot_data=data.get('utbot_data')
            )
            
            if chart_path and os.path.exists(chart_path):
                # 构建图表信息
                current_price = data['current_price']
                price_change = data['price_change']
                price_change_percent = data['price_change_percent']
                
                chart_info = f"📊 **{exchange.upper()} {symbol} 技术分析**\n"
                chart_info += f"⏰ {timeframe} • {data['count']}根K线\n"
                chart_info += f"💰 当前价格: `{current_price:.4f}`\n"
                
                if price_change >= 0:
                    chart_info += f"📈 涨跌: `+{price_change:.4f}` (`+{price_change_percent:.2f}%`)"
                else:
                    chart_info += f"� 涨跌: `{price_change:.4f}` (`{price_change_percent:.2f}%`)"
                
                # 添加S/R分析信息
                if data.get('sr_analysis'):
                    sr_data = data['sr_analysis']
                    chart_info += f"\n\n🎯 支撑阻力分析:\n"
                    chart_info += f"📊 发现 {sr_data.get('total_zones', 0)} 个区域\n"
                    chart_info += f"🛡️ 支撑位: {sr_data.get('support_count', 0)} 个\n"
                    chart_info += f"🚧 阻力位: {sr_data.get('resistance_count', 0)} 个"
                
                await self.send_telegram_message(chart_info, [str(chat_id)])
                await self.send_telegram_photo(chart_path, [str(chat_id)])
                
                # 清理临时文件
                try:
                    os.remove(chart_path)
                except:
                    pass
            else:
                await self.send_telegram_message("❌ 图表生成失败", [str(chat_id)])
                
        except Exception as e:
            logger.error(f"处理图表数据响应时出错: {e}")
            await self.send_telegram_message(f"❌ 图表生成失败: {e}", [str(chat_id)])
    
    async def generate_chart_async(self, df, symbol, timeframe, include_sr_analysis=False, sr_analysis=None, utbot_data=None):
        """异步生成图表"""
        try:
            import asyncio
            import concurrent.futures
            
            # 在线程池中运行图表生成（因为图表生成是CPU密集型任务）
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 生成临时文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{symbol.replace(':', '_')}_{timeframe}_{timestamp}.png"
                
                # 在线程中运行图表生成
                loop = asyncio.get_event_loop()
                chart_path = await loop.run_in_executor(
                    executor, 
                    self._generate_chart_sync, 
                    df, symbol, timeframe, filename, include_sr_analysis, sr_analysis, utbot_data
                )
                
                return chart_path
        except Exception as e:
            logger.error(f"异步图表生成失败: {e}")
            return None
    
    def _generate_chart_sync(self, df, symbol, timeframe, filename, include_sr_analysis=False, sr_analysis=None, utbot_data=None):
        """同步生成图表"""
        try:
            if not self.chart_generator:
                return None
            
            # 调用图表生成器
            # 这里需要适配图表生成器的接口
            return self.chart_generator.generate_chart_from_dataframe(
                df, symbol, timeframe, filename,
                include_sr_analysis=include_sr_analysis,
                sr_analysis=sr_analysis,
                utbot_data=utbot_data
            )
        except Exception as e:
            logger.error(f"同步图表生成失败: {e}")
            return None
    
    def setup_command_handlers(self):
        """设置命令处理器"""
        if not TELEGRAM_AVAILABLE:
            return
        
        try:
            # 创建Application
            self.application = Application.builder().token(self.bot_token).build()
            
            # 添加命令处理器
            self.application.add_handler(CommandHandler("info", self.handle_info_command))
            
            logger.info("✅ 命令处理器设置成功")
        except Exception as e:
            logger.error(f"❌ 命令处理器设置失败: {e}")
    
    async def start_command_polling(self):
        """启动命令轮询"""
        if self.application:
            try:
                logger.info("🤖 启动Telegram命令监听...")
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling()
                logger.info("✅ Telegram命令监听已启动")
            except Exception as e:
                logger.error(f"❌ 启动命令监听失败: {e}")
    
    async def stop_command_polling(self):
        """停止命令轮询"""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("👋 Telegram命令监听已停止")
            except Exception as e:
                logger.error(f"❌ 停止命令监听失败: {e}")
    
    async def send_statistics(self):
        """发送统计信息到Telegram"""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        stats_msg = "📊 **监控统计**\n"
        stats_msg += f"⏱️ 运行时长: `{uptime_str}`\n"
        stats_msg += f"🔗 连接次数: `{self.connected_count}`\n"
        stats_msg += f"📨 接收消息: `{self.message_count}`\n"
        stats_msg += f"🎯 交易信号: `{self.signal_count}`"
        
        await self.send_telegram_message(stats_msg)
    
    async def connect(self):
        """连接WebSocket服务器"""
        while self.running:
            try:
                logger.info(f"🔌 正在连接服务器: {self.websocket_uri}")
                
                async with websockets.connect(self.websocket_uri) as websocket:
                    self.connected_count += 1
                    logger.info(f"✅ 已连接到服务器 (第{self.connected_count}次)")
                    
                    # 发送连接成功通知
                    if self.connected_count == 1:
                        connect_msg = f"🔗 **WebSocket 连接成功**\n📡 服务器: `{self.websocket_uri}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
                        await self.send_telegram_message(connect_msg)
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            logger.debug(f"📥 收到消息: {data}")
                            await self.handle_message(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ JSON解析错误: {e}")
                        except Exception as e:
                            logger.error(f"❌ 消息处理错误: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("🔌 WebSocket连接已断开")
                disconnect_msg = f"⚠️ **连接断开**\n📡 服务器: `{self.websocket_uri}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
                await self.send_telegram_message(disconnect_msg)
            except Exception as e:
                logger.error(f"❌ 连接错误: {e}")
            
            if self.running:
                logger.info("⏳ 5秒后重新连接...")
                await asyncio.sleep(5)
    
    async def handle_message(self, data: Dict[str, Any]):
        """处理收到的消息"""
        self.message_count += 1
        
        msg_type = data.get('type', '')
        level = data.get('level', '')
        message = data.get('message', '')
        signal_data = data.get('data', {})
        
        # 检查是否为交易信号
        is_signal = (msg_type == "notification" and 
                    level == "WARNING" and 
                    "SIGNAL" in message and 
                    signal_data.get('signal_type'))
        
        if is_signal:
            self.signal_count += 1
            logger.info(f"🎯 检测到交易信号: {signal_data}")
            
            # 发送交易信号到Telegram
            signal_message = self.format_signal_for_telegram(signal_data)
            await self.send_telegram_message(signal_message)
            
        elif msg_type == "welcome":
            # 欢迎消息
            welcome_msg = f"🎉 **服务器欢迎**\n📝 消息: `{message}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
            await self.send_telegram_message(welcome_msg)
            
        else:
            # 其他类型的消息 - 只记录重要级别
            if level in ["ERROR", "WARNING"]:
                general_message = self.format_general_message_for_telegram(data)
                await self.send_telegram_message(general_message)
        
        # 每100条消息发送一次统计
        if self.message_count % 100 == 0:
            await self.send_statistics()
    
    async def start(self):
        """启动Telegram客户端"""
        self.running = True
        
        # 设置命令处理器
        self.setup_command_handlers()
        
        # 测试Telegram连接
        if not await self.test_telegram_connection():
            logger.error("❌ Telegram连接测试失败")
            return False
        
        # 启动命令监听
        if self.application:
            asyncio.create_task(self.start_command_polling())
        
        # 开始监听WebSocket
        await self.connect()
        return True
    
    async def stop(self):
        """停止Telegram客户端"""
        self.running = False
        logger.info("👋 正在停止Telegram客户端...")
        
        # 停止命令监听
        if self.application:
            await self.stop_command_polling()
        
        # 发送停止通知
        stop_msg = f"🛑 **监控已停止**\n⏰ 停止时间: `{datetime.now().strftime('%H:%M:%S')}`"
        await self.send_telegram_message(stop_msg)
        await self.send_statistics()

def create_telegram_client_from_env(websocket_uri: str) -> TelegramClient:
    """从环境变量创建Telegram客户端"""
    if not TELEGRAM_AVAILABLE:
        raise ImportError("python-telegram-bot 未安装，无法使用Telegram功能")
        
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id_env = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token:
        raise ValueError("请设置环境变量 TELEGRAM_BOT_TOKEN")
    
    if not chat_id_env:
        raise ValueError("请设置环境变量 TELEGRAM_CHAT_ID")
    
    chat_ids = [cid.strip() for cid in chat_id_env.split(",") if cid.strip()]
    
    return TelegramClient(bot_token, chat_ids, websocket_uri)
