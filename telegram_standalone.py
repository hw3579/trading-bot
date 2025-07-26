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

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramStandaloneClient:
    """独立Telegram客户端"""
    
    def __init__(self, bot_token: str, admin_chat_ids: list, websocket_uri: str = "ws://localhost:10000"):
        self.bot_token = bot_token
        self.admin_chat_ids = admin_chat_ids
        self.websocket_uri = websocket_uri
        self.websocket = None
        
    async def connect_websocket(self):
        """连接WebSocket"""
        try:
            self.websocket = await websockets.connect(self.websocket_uri)
            logger.info(f"✅ 已连接到WebSocket: {self.websocket_uri}")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            return False
    
    async def send_command(self, command: str) -> dict:
        """发送命令到WebSocket"""
        if not self.websocket:
            if not await self.connect_websocket():
                return {"status": "error", "message": "无法连接到WebSocket服务器"}
        
        try:
            await self.websocket.send(command)
            response = await self.websocket.recv()
            return json.loads(response)
        except Exception as e:
            logger.error(f"❌ 发送命令失败: {e}")
            # 尝试重新连接
            self.websocket = None
            if await self.connect_websocket():
                try:
                    await self.websocket.send(command)
                    response = await self.websocket.recv()
                    return json.loads(response)
                except:
                    pass
            return {"status": "error", "message": str(e)}
    
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
            command = f"/okx {symbol} {timeframe} {count}"
            
            await update.message.reply_text(f"⏳ 正在获取 {symbol} {timeframe} 数据...")
            
            response = await self.send_command(command)
            
            if response.get("status") == "success":
                if "chart_data" in response:
                    # 发送图表
                    chart_data = base64.b64decode(response["chart_data"])
                    await update.message.reply_photo(
                        photo=io.BytesIO(chart_data),
                        caption=response.get("message", f"✅ {symbol} {timeframe} 图表")
                    )
                else:
                    await update.message.reply_text(response.get("message", "✅ 命令执行成功"))
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
            command = f"/hype {symbol} {timeframe} {count}"
            
            await update.message.reply_text(f"⏳ 正在获取 {symbol} {timeframe} 数据...")
            
            response = await self.send_command(command)
            
            if response.get("status") == "success":
                if "chart_data" in response:
                    # 发送图表
                    chart_data = base64.b64decode(response["chart_data"])
                    await update.message.reply_photo(
                        photo=io.BytesIO(chart_data),
                        caption=response.get("message", f"✅ {symbol} {timeframe} 图表")
                    )
                else:
                    await update.message.reply_text(response.get("message", "✅ 命令执行成功"))
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
• /okx <币种> <时间框架> <数量> - OKX交易所数据查询
• /hype <币种> <时间框架> <数量> - Hyperliquid交易所数据查询

📊 示例:
• /okx ETH 5m 200
• /hype BTC 15m 100

💡 此客户端通过WebSocket连接到核心系统
        """
        await update.message.reply_text(message)
    
    def run(self):
        """启动客户端"""
        app = Application.builder().token(self.bot_token).build()
        
        # 添加命令处理器
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("okx", self.handle_okx_command))
        app.add_handler(CommandHandler("hype", self.handle_hype_command))
        
        logger.info("🚀 独立Telegram客户端启动中...")
        logger.info(f"🌐 WebSocket地址: {self.websocket_uri}")
        logger.info(f"👥 授权用户: {self.admin_chat_ids}")
        
        # 启动应用
        app.run_polling(drop_pending_updates=True)

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
