#!/usr/bin/env python3
"""
交易监控系统主启动文件 - 核心系统
只包含核心业务逻辑和WebSocket服务器，不包含Telegram集成
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
from services.notification_service import NotificationService
from core.single_monitor import SingleThreadMonitor
from core.multi_monitor import MultiThreadMonitor
from strategies.utbot_strategy import UTBotStrategy

logger = logging.getLogger(__name__)

class TradingSystem:
    """交易监控系统主类 - 核心系统"""
    
    def __init__(self, config_path: str, log_level: str = None):
        self.config = ConfigLoader.load(config_path)
        
        # 如果命令行指定了日志级别，覆盖配置文件设置
        if log_level:
            self.config.logging.log_level = log_level
            
        self.services = {}
        self.monitor = None
        self.running = False
        
        # 设置日志
        self._setup_logging()
        
    def _setup_logging(self):
        """设置系统日志"""
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.config.logging.log_file), exist_ok=True)
        
        # 获取日志级别
        log_level = getattr(logging, self.config.logging.log_level.upper())
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.logging.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 设置第三方库的日志级别，减少噪音
        if log_level >= logging.WARNING:
            # 当设置为WARNING或更高级别时，抑制所有模块的INFO日志
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("websockets").setLevel(logging.WARNING)
            
            # 同时设置我们自己的模块也使用WARNING级别
            logging.getLogger("services").setLevel(log_level)
            logging.getLogger("core").setLevel(log_level)
            logging.getLogger("strategies").setLevel(log_level)
            logging.getLogger("__main__").setLevel(log_level)  # 包括主模块
        else:
            # 当设置为DEBUG或INFO时，允许第三方库显示INFO日志
            logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx总是保持WARNING
            logging.getLogger("websockets").setLevel(log_level)
        
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
        """启动核心服务"""
        logger.info("🚀 正在启动交易监控核心系统...")
        
        # 1. 启动WebSocket服务器（必须启用）
        self.services['websocket'] = WebSocketServer(
            host=self.config.websocket.host,
            port=self.config.websocket.port
        )
        await self.services['websocket'].start()
        set_websocket_server(self.services['websocket'])  # 设置全局实例
        logger.info(f"✅ WebSocket服务器启动 - {self.config.websocket.host}:{self.config.websocket.port}")
        
        # 2. 初始化通知服务（只包含WebSocket）
        self.services['notification'] = NotificationService(
            websocket_server=self.services.get('websocket'),
            telegram_client=None,  # 核心系统不包含Telegram
            config=self.config.notification
        )
        
        # 3. 初始化策略
        strategies = []
        if 'utbot' in self.config.strategies.enabled:
            strategies.append(UTBotStrategy(self.config.strategies.utbot))
        
        # 4. 启动监控器 - 默认使用多线程模式
        self.monitor = MultiThreadMonitor(
            config=self.config.monitoring,
            strategies=strategies,
            notification_service=self.services['notification']
        )
        
        # 5. 启动时进行一次数据同步
        await self._initial_data_sync()
        
        # 启动监控
        await self.monitor.start()
        
        self.running = True
        logger.info("🎯 核心系统启动完成")
        
    async def stop_services(self):
        """停止所有服务"""
        logger.info("🛑 正在停止核心系统...")
        self.running = False
        
        # 停止监控器
        if self.monitor:
            await self.monitor.stop()
        
        # 停止WebSocket服务器
        if 'websocket' in self.services:
            await self.services['websocket'].stop()
        
        logger.info("👋 核心系统已完全停止")
        
    async def run(self):
        """运行核心系统"""
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
    """主函数 - 核心系统启动"""
    parser = argparse.ArgumentParser(description='交易监控核心系统 - WebSocket服务器')
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
    print("🚀 交易监控核心系统")
    print("=" * 60)
    print(f"📋 配置文件: {args.config}")
    print(f"🧵 多线程模式: ✅ 启用")
    print(f"🌐 WebSocket服务器: ✅ 启用") 
    print(f"📊 日志级别: {args.log_level}")
    print(f"📱 Telegram集成: ❌ 分离（请单独启动telegram_standalone.py）")
    print("⌨️  按 Ctrl+C 停止系统")
    print("=" * 60)
    
    # 启动核心系统
    system = TradingSystem(args.config, args.log_level)
    await system.run()

if __name__ == "__main__":
    asyncio.run(main())
