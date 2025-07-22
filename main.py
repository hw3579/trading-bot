#!/usr/bin/env python3
"""
交易监控系统主启动文件
支持多种监控策略、多种通知方式的统一管理
"""

import asyncio
import argparse
import sys
import logging
import os
from pathlib import Path

# 添加项目路径到系统路径
sys.path.insert(0, str(Path(__file__).parent))

from config.config_loader import ConfigLoader
from services.websocket_server import WebSocketServer, set_websocket_server
from services.telegram_client import TelegramClient, create_telegram_client_from_env
from services.notification_service import NotificationService
from core.single_monitor import SingleThreadMonitor
from core.multi_monitor import MultiThreadMonitor
from strategies.utbot_strategy import UTBotStrategy

logger = logging.getLogger(__name__)

class TradingSystem:
    """交易监控系统主类"""
    
    def __init__(self, config_path: str):
        self.config = ConfigLoader.load(config_path)
        self.services = {}
        self.monitor = None
        self.running = False
        
        # 设置日志
        self._setup_logging()
        
    def _setup_logging(self):
        """设置系统日志"""
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.config.logging.log_file), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, self.config.logging.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.logging.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
    async def _initial_data_sync(self):
        """启动时进行一次数据同步"""
        logger.info("📊 启动时数据同步...")
        
        if self.monitor:
            try:
                # 手动触发一次数据同步
                await self.monitor.sync_data_once()
                logger.info("✅ 初始数据同步完成")
            except Exception as e:
                logger.warning(f"⚠️ 初始数据同步失败: {e}")
        
    async def start_services(self):
        """启动所有服务"""
        logger.info("🚀 正在启动交易监控系统...")
        
        # 1. 启动WebSocket服务器
        if self.config.websocket.enabled:
            self.services['websocket'] = WebSocketServer(
                host=self.config.websocket.host,
                port=self.config.websocket.port,
                ipv6_enabled=self.config.websocket.ipv6_enabled,
                bind_both=self.config.websocket.bind_both
            )
            await self.services['websocket'].start()
            set_websocket_server(self.services['websocket'])  # 设置全局实例
            
        # 2. 启动Telegram客户端
        if self.config.telegram.enabled:
            try:
                websocket_uri = f"ws://{self.config.websocket.host}:{self.config.websocket.port}"
                if self.config.telegram.bot_token and self.config.telegram.chat_ids:
                    # 从配置文件获取
                    self.services['telegram'] = TelegramClient(
                        bot_token=self.config.telegram.bot_token,
                        chat_ids=self.config.telegram.chat_ids,
                        websocket_uri=websocket_uri
                    )
                else:
                    # 从环境变量获取
                    self.services['telegram'] = create_telegram_client_from_env(websocket_uri)
                
                asyncio.create_task(self.services['telegram'].start())
                logger.info("✅ Telegram客户端启动")
            except Exception as e:
                logger.warning(f"⚠️ Telegram客户端启动失败: {e}")
        
        # 3. 初始化通知服务
        self.services['notification'] = NotificationService(
            websocket_server=self.services.get('websocket'),
            telegram_client=self.services.get('telegram'),
            config=self.config.notification
        )
        
        # 4. 初始化策略
        strategies = []
        if 'utbot' in self.config.strategies.enabled:
            strategies.append(UTBotStrategy(self.config.strategies.utbot))
        
        # 5. 启动监控器 - 默认使用多线程模式
        self.monitor = MultiThreadMonitor(
            config=self.config.monitoring,
            strategies=strategies,
            notification_service=self.services['notification']
        )
        
        # 6. 启动时进行一次数据同步
        await self._initial_data_sync()
        
        # 启动监控
        await self.monitor.start()
        
        self.running = True
        logger.info("🎯 所有服务启动完成")
        
    async def stop_services(self):
        """停止所有服务"""
        logger.info("🛑 正在停止所有服务...")
        self.running = False
        
        # 停止监控器
        if self.monitor:
            await self.monitor.stop()
        
        # 停止Telegram客户端
        if 'telegram' in self.services:
            await self.services['telegram'].stop()
        
        # 停止WebSocket服务器
        if 'websocket' in self.services:
            await self.services['websocket'].stop()
        
        logger.info("👋 系统已完全停止")
        
    async def run(self):
        """运行系统"""
        try:
            await self.start_services()
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("⌨️ 收到停止信号")
        except Exception as e:
            logger.error(f"❌ 系统运行错误: {e}")
        finally:
            await self.stop_services()

async def main():
    """主函数 - 默认启动多线程+TG通知模式"""
    parser = argparse.ArgumentParser(description='交易监控系统 - 多线程+TG通知模式')
    parser.add_argument('--config', '-c', default='config/config_multi.yaml', 
                       help='配置文件路径 (默认多线程配置)')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        sys.exit(1)
    
    print("=" * 60)
    print("🚀 交易监控系统 - 多线程+TG通知模式")
    print("=" * 60)
    print(f"📋 配置文件: {args.config}")
    print(f"🧵 多线程模式: ✅ 启用")
    print(f"📱 Telegram通知: ✅ 启用") 
    print(f"📊 日志级别: {args.log_level}")
    print("⌨️  按 Ctrl+C 停止系统")
    print("=" * 60)
    
    # 启动系统
    system = TradingSystem(args.config)
    await system.run()

if __name__ == "__main__":
    asyncio.run(main())
