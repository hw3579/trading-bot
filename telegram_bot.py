#!/usr/bin/env python3
"""
Telegram机器人客户端
监听WebSocket服务器并通过Telegram发送交易信号
需要安装: pip install python-telegram-bot websockets
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Any
import os
from telegram import Bot
from telegram.error import TelegramError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramNotifyClient:
    """Telegram通知客户端"""
    
    def __init__(self, uri: str, bot_token: str, chat_id: str):
        self.uri = uri
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.running = True
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
    
    async def test_telegram_connection(self):
        """测试Telegram连接"""
        try:
            me = await self.bot.get_me()
            logger.info(f"🤖 Telegram Bot: @{me.username}")
            
            # 发送测试消息
            test_msg = "🚀 交易信号监控机器人已启动\n📡 正在监听交易信号..."
            await self.bot.send_message(chat_id=self.chat_id, text=test_msg)
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
        
        # 构建消息
        timeframe_str = f" ({timeframe})" if timeframe else ""
        message = f"{icon} **{signal_type} **\n"
        message += f"`{symbol}`{timeframe_str}\n"
        message += f"`{price_str}`\n"
        message += f"`{exchange}`\n"
        message += f"`{datetime.now().strftime('%H:%M:%S')}`"

        # timeframe_str = f" ({timeframe})" if timeframe else ""
        # message = f"{icon} **{signal_type} 信号**\n"
        # message += f"📊 交易对: `{symbol}`{timeframe_str}\n"
        # message += f"💰 价格: `{price_str}`\n"
        # message += f"🏢 交易所: `{exchange}`\n"
        # message += f"⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
        
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
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=message,
                parse_mode=parse_mode
            )
            logger.info("✅ Telegram 消息发送成功")
        except TelegramError as e:
            logger.error(f"❌ Telegram 消息发送失败: {e}")
            # 如果Markdown解析失败，尝试发送纯文本
            if parse_mode == 'Markdown':
                try:
                    # 移除Markdown格式
                    plain_text = message.replace('**', '').replace('`', '')
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=plain_text
                    )
                    logger.info("✅ Telegram 纯文本消息发送成功")
                except TelegramError as e2:
                    logger.error(f"❌ Telegram 纯文本消息也发送失败: {e2}")
    
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
                logger.info(f"🔌 正在连接服务器: {self.uri}")
                
                async with websockets.connect(self.uri) as websocket:
                    self.connected_count += 1
                    logger.info(f"✅ 已连接到服务器 (第{self.connected_count}次)")
                    
                    # 发送连接成功通知
                    if self.connected_count == 1:
                        connect_msg = f"🔗 **WebSocket 连接成功**\n📡 服务器: `{self.uri}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
                        await self.send_telegram_message(connect_msg)
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            logger.info(f"📥 收到消息: {data}")
                            await self.handle_message(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ JSON解析错误: {e}")
                        except Exception as e:
                            logger.error(f"❌ 消息处理错误: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("🔌 WebSocket连接已断开")
                disconnect_msg = f"⚠️ **连接断开**\n📡 服务器: `{self.uri}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
                await self.send_telegram_message(disconnect_msg)
            except Exception as e:
                logger.error(f"❌ 连接错误: {e}")
                error_msg = f"❌ **连接错误**\n📝 错误: `{str(e)}`\n⏰ 时间: `{datetime.now().strftime('%H:%M:%S')}`"
                await self.send_telegram_message(error_msg)
            
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
    
    async def stop(self):
        """停止客户端"""
        self.running = False
        logger.info("👋 正在停止Telegram客户端...")
        
        # 发送停止通知
        stop_msg = f"🛑 **监控已停止**\n⏰ 停止时间: `{datetime.now().strftime('%H:%M:%S')}`"
        await self.send_telegram_message(stop_msg)
        await self.send_statistics()

async def main():
    """主函数"""
    # 从环境变量获取配置
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    server_host = os.getenv("WEBSOCKET_HOST", "localhost")
    server_port = os.getenv("WEBSOCKET_PORT", "10000")
    
    if not bot_token:
        logger.error("❌ 请设置环境变量 TELEGRAM_BOT_TOKEN")
        return
    
    if not chat_id:
        logger.error("❌ 请设置环境变量 TELEGRAM_CHAT_ID")
        return
    
    server_uri = f"ws://{server_host}:{server_port}"
    
    # 显示启动信息
    print("=" * 60)
    print("🤖 Telegram 交易信号机器人")
    print("=" * 60)
    print(f"📡 WebSocket服务器: {server_uri}")
    print(f"🤖 Bot Token: {bot_token[:10]}...")
    print(f"💬 Chat ID: {chat_id}")
    print("⌨️  按 Ctrl+C 停止机器人")
    print("=" * 60)
    
    try:
        client = TelegramNotifyClient(server_uri, bot_token, chat_id)
        
        # 测试Telegram连接
        if not await client.test_telegram_connection():
            logger.error("❌ Telegram连接测试失败，程序退出")
            return
        
        # 开始监听
        await client.connect()
        
    except KeyboardInterrupt:
        logger.info("⌨️ 收到停止信号")
        if 'client' in locals():
            await client.stop()
    except Exception as e:
        logger.error(f"❌ 程序异常: {e}")

if __name__ == "__main__":
    asyncio.run(main())