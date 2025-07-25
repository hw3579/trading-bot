#!/usr/bin/env python3
"""
独立的Telegram图表机器人
专门处理 /info 命令生成技术分析图表
"""

import asyncio
import os
import sys
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    print("❌ python-telegram-bot 未安装")
    print("💡 安装方法: pip install python-telegram-bot")
    sys.exit(1)

try:
    from generate_charts import TechnicalAnalysisChart
    CHART_GENERATOR_AVAILABLE = True
except ImportError as e:
    print(f"❌ 图表生成器导入失败: {e}")
    print("💡 请确保依赖已安装: matplotlib, pandas, talib等")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 设置httpx日志等级为DEBUG，减少HTTP请求日志干扰
logging.getLogger("httpx").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

class TelegramChartBot:
    """Telegram图表机器人"""
    
    def __init__(self, bot_token: str, allowed_chat_ids: list):
        self.bot_token = bot_token
        self.allowed_chat_ids = [str(cid) for cid in allowed_chat_ids]
        self.chart_generator = TechnicalAnalysisChart(figsize=(20, 12))
        self.application = None
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id not in self.allowed_chat_ids:
            await update.message.reply_text("❌ 您没有权限使用此机器人")
            return
        
        welcome_msg = "🤖 **技术分析图表机器人**\n\n"
        welcome_msg += "📊 使用 `/info` 命令生成技术分析图表\n\n"
        welcome_msg += "📖 **使用格式:**\n"
        welcome_msg += "`/info [symbol] [timeframe] [candles]`\n\n"
        welcome_msg += "📝 **参数说明:**\n"
        welcome_msg += "• `symbol`: 交易对 (BTC, ETH, SOL等)\n"
        welcome_msg += "• `timeframe`: 时间框架 (5m, 15m, 1h, 4h, 1d)\n"
        welcome_msg += "• `candles`: K线数量 (50-1000)\n\n"
        welcome_msg += "🌟 **示例:**\n"
        welcome_msg += "`/info`                    # ETH 15m 200 (默认)\n"
        welcome_msg += "`/info BTC`                # BTC 15m 200\n"
        welcome_msg += "`/info ETH 5m`             # ETH 5m 200\n"
        welcome_msg += "`/info SOL 1h 100`         # SOL 1h 100\n\n"
        welcome_msg += "💡 **支持的交易对:** BTC, ETH, SOL, DOGE等\n"
        welcome_msg += "💡 **图表包含:** K线图、EMA线、支撑阻力位、成交量"
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /info 命令"""
        try:
            args = context.args
            chat_id = str(update.effective_chat.id)
            
            # 检查权限
            if chat_id not in self.allowed_chat_ids:
                await update.message.reply_text("❌ 您没有权限使用此命令")
                return
            
            # 解析参数
            symbol = "ETH"
            timeframe = "15m"
            candles = 200
            
            if len(args) >= 1:
                symbol = args[0].upper()
            if len(args) >= 2:
                timeframe = args[1].lower()
            if len(args) >= 3:
                try:
                    candles = int(args[2])
                    if candles < 50:
                        candles = 50
                    elif candles > 1000:
                        candles = 1000
                except ValueError:
                    await update.message.reply_text("❌ 无效的K线数量，使用默认值200")
                    candles = 200
            
            # 验证参数
            valid_symbols = ["BTC", "ETH", "SOL", "DOGE"]
            valid_timeframes = ["5m", "15m", "30m", "1h", "4h", "1d"]
            
            if symbol not in valid_symbols:
                error_msg = f"❌ 不支持的交易对: {symbol}\n"
                error_msg += f"💡 支持的交易对: {', '.join(valid_symbols)}"
                await update.message.reply_text(error_msg)
                return
            
            if timeframe not in valid_timeframes:
                error_msg = f"❌ 不支持的时间框架: {timeframe}\n"
                error_msg += f"💡 支持的时间框架: {', '.join(valid_timeframes)}"
                await update.message.reply_text(error_msg)
                return
            
            # 发送处理中消息
            processing_msg = f"🔄 **正在生成 {symbol} 技术分析图表...**\n\n"
            processing_msg += f"📊 交易对: `{symbol}/USDT`\n"
            processing_msg += f"🕐 时间框架: `{timeframe}`\n"
            processing_msg += f"📈 K线数量: `{candles}`\n"
            processing_msg += f"⏳ 预计耗时: 10-30秒\n\n"
            processing_msg += f"📡 正在获取数据..."
            
            status_message = await update.message.reply_text(processing_msg, parse_mode='Markdown')
            
            # 生成图表
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"temp_{symbol.lower()}_{timeframe}_{candles}c_{timestamp}.png"
            
            logger.info(f"📊 开始生成 {symbol} 图表: {timeframe}, {candles} candles")
            
            try:
                # 更新状态
                await status_message.edit_text(
                    processing_msg.replace("📡 正在获取数据...", "🔧 正在计算技术指标..."),
                    parse_mode='Markdown'
                )
                
                # 生成图表
                result = self.chart_generator.generate_chart(symbol, timeframe, candles, filename)
                
                if result and os.path.exists(result):
                    # 更新状态
                    await status_message.edit_text(
                        processing_msg.replace("📡 正在获取数据...", "📤 正在发送图表..."),
                        parse_mode='Markdown'
                    )
                    
                    # 准备图片标题
                    caption = f"📊 **{symbol}/USDT 技术分析**\n"
                    caption += f"🕐 时间框架: `{timeframe}`\n"
                    caption += f"📈 K线数量: `{candles}`\n"
                    caption += f"⏰ 生成时间: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                    caption += f"💡 **图表说明:**\n"
                    caption += f"• 🟢 绿色K线：价格上涨\n"
                    caption += f"• 🔴 红色K线：价格下跌\n"
                    caption += f"• 🔵 彩色线条：支撑阻力位\n"
                    caption += f"• 📈 EMA线：移动平均线\n"
                    caption += f"• ⚪ 白色虚线：当前价格\n\n"
                    caption += f"🔄 使用 `/info {symbol} {timeframe} {candles}` 刷新"
                    
                    # 发送图片
                    with open(result, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                    
                    # 删除状态消息
                    await status_message.delete()
                    
                    # 删除临时文件
                    try:
                        os.remove(result)
                        logger.info(f"🗑️ 已删除临时文件: {result}")
                    except Exception as e:
                        logger.warning(f"⚠️ 删除临时文件失败: {e}")
                    
                    logger.info(f"✅ {symbol} 图表发送成功")
                else:
                    error_msg = f"❌ **生成 {symbol} 图表失败**\n\n"
                    error_msg += f"💡 **可能的原因:**\n"
                    error_msg += f"• 数据源暂时不可用\n"
                    error_msg += f"• 网络连接问题\n"
                    error_msg += f"• 服务器负载过高\n\n"
                    error_msg += f"🔄 请稍后重试"
                    
                    await status_message.edit_text(error_msg, parse_mode='Markdown')
                    logger.error(f"❌ {symbol} 图表生成失败")
                    
            except Exception as e:
                error_msg = f"❌ **生成图表时出错**\n\n"
                error_msg += f"🔍 错误信息: `{str(e)}`\n"
                error_msg += f"🔄 请稍后重试或联系管理员"
                
                await status_message.edit_text(error_msg, parse_mode='Markdown')
                logger.error(f"❌ 生成 {symbol} 图表时出错: {e}")
        
        except Exception as e:
            logger.error(f"❌ 处理 /info 命令时出错: {e}")
            await update.message.reply_text(f"❌ 处理命令时出错: {str(e)}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        await self.start_command(update, context)
    
    def setup_handlers(self):
        """设置命令处理器"""
        self.application = Application.builder().token(self.bot_token).build()
        
        # 添加命令处理器
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        logger.info("✅ 命令处理器设置成功")
    
    async def start_bot(self):
        """启动机器人"""
        logger.info("🤖 启动Telegram图表机器人...")
        
        # 设置处理器
        self.setup_handlers()
        
        # 初始化和启动
        await self.application.initialize()
        await self.application.start()
        
        # 测试连接
        try:
            bot = Bot(self.bot_token)
            me = await bot.get_me()
            logger.info(f"✅ 机器人连接成功: @{me.username}")
            
            # 发送启动通知
            for chat_id in self.allowed_chat_ids:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="🚀 **技术分析图表机器人已启动**\n\n💡 使用 `/start` 查看使用说明\n📊 使用 `/info` 生成图表",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.warning(f"⚠️ 向 {chat_id} 发送启动通知失败: {e}")
        except Exception as e:
            logger.error(f"❌ 机器人连接失败: {e}")
            return False
        
        # 开始轮询
        await self.application.updater.start_polling()
        logger.info("✅ 开始监听命令...")
        
        return True
    
    async def stop_bot(self):
        """停止机器人"""
        if self.application:
            logger.info("👋 正在停止机器人...")
            
            # 发送停止通知
            try:
                bot = Bot(self.bot_token)
                for chat_id in self.allowed_chat_ids:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="🛑 **技术分析图表机器人已停止**\n⏰ 停止时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 向 {chat_id} 发送停止通知失败: {e}")
            except Exception as e:
                logger.warning(f"⚠️ 发送停止通知失败: {e}")
            
            # 停止应用
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("✅ 机器人已停止")

async def main():
    """主函数"""
    print("🤖 Telegram技术分析图表机器人")
    print("="*50)
    
    # 检查环境变量
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids_env = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token:
        print("❌ 请设置环境变量 TELEGRAM_BOT_TOKEN")
        return
    
    if not chat_ids_env:
        print("❌ 请设置环境变量 TELEGRAM_CHAT_ID")
        return
    
    # 解析允许的chat_ids
    allowed_chat_ids = [cid.strip() for cid in chat_ids_env.split(",") if cid.strip()]
    
    print(f"✅ 配置加载成功")
    print(f"🤖 Bot Token: {bot_token[:10]}...")
    print(f"👥 允许的Chat IDs: {', '.join(allowed_chat_ids)}")
    print()
    
    # 创建并启动机器人
    bot = TelegramChartBot(bot_token, allowed_chat_ids)
    
    try:
        if await bot.start_bot():
            print("✅ 机器人启动成功!")
            print("\n💡 可用命令:")
            print("  /start - 查看使用说明")
            print("  /info [symbol] [timeframe] [candles] - 生成技术分析图表")
            print("  /help - 查看帮助")
            print("\n🛑 按 Ctrl+C 停止机器人...")
            
            # 保持运行
            while True:
                await asyncio.sleep(1)
        else:
            print("❌ 机器人启动失败")
    except KeyboardInterrupt:
        print("\n👋 正在停止机器人...")
        await bot.stop_bot()
        print("✅ 机器人已停止")
    except Exception as e:
        print(f"\n❌ 运行异常: {e}")
        await bot.stop_bot()

if __name__ == "__main__":
    # 检查是否在正确的目录
    if not os.path.exists("../generate_charts.py") and not os.path.exists("generate_charts.py"):
        print("❌ 请在项目根目录运行此脚本，或确保generate_charts.py存在")
        sys.exit(1)
    
    # 运行机器人
    asyncio.run(main())
