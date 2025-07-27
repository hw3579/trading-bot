#!/usr/bin/env python3
"""
交易监控系统主启动文件 - 双协议架构
端口 10000: WebSocket 信号推送服务
端口 10001: gRPC 查询请求服务
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
from services.dual_websocket_server import DualPortWebSocketServer
from services.notification_service import NotificationService
from core.single_monitor import SingleThreadMonitor
from core.multi_monitor import MultiThreadMonitor
from strategies.utbot_strategy import UTBotStrategy

logger = logging.getLogger(__name__)

class TradingSystem:
    """交易监控系统主类 - 双协议架构"""
    
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
        
        # 配置日志格式
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.logging.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # 设置第三方库的日志级别
        logging.getLogger('websockets').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('grpc').setLevel(logging.WARNING)
        
    async def _initial_data_sync(self):
        """启动时进行一次数据同步 - 现在集成到监控启动中"""
        # 数据同步现在集成到监控器的启动过程中
        # 这个方法保留用于向后兼容
        logger.info("📊 数据同步已集成到监控启动流程")
        
    async def init_data_sync(self):
        """初始化数据同步 - 向后兼容方法"""
        await self._initial_data_sync()
        
    async def start_services(self):
        """启动双协议架构服务"""
        logger.info("🚀 正在启动交易监控双协议系统...")
        
        # 1. 启动WebSocket信号推送服务器 (端口10000)
        self.services['websocket'] = DualPortWebSocketServer(
            signal_host=self.config.websocket.host,
            signal_port=self.config.websocket.port,
            query_host=self.config.websocket.host,
            query_port=self.config.websocket.port + 1  # 这个端口不会被使用，因为我们用gRPC
        )
        
        # 只启动信号推送服务器部分
        await self.services['websocket'].start_signal_server_only()
        logger.info(f"✅ WebSocket信号推送服务器启动")
        logger.info(f"📡 信号推送端口: {self.config.websocket.host}:{self.config.websocket.port}")
        
        # 2. 启动gRPC查询服务器 (端口10001)
        try:
            from services.grpc_server import start_grpc_server
            self.services['grpc_task'] = asyncio.create_task(
                start_grpc_server(
                    host=self.config.websocket.host,
                    port=self.config.websocket.port + 1
                )
            )
            logger.info(f"✅ gRPC查询服务器启动")
            logger.info(f"🔗 gRPC查询端口: {self.config.websocket.host}:{self.config.websocket.port + 1}")
        except Exception as e:
            logger.error(f"❌ gRPC服务器启动失败: {e}")
            raise
        
        # 3. 初始化通知服务 (仅使用WebSocket信号推送)
        self.services['notification'] = NotificationService(
            websocket_server=self.services['websocket'],
            telegram_client=None,  # 核心系统不包含Telegram集成
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
        
        logger.info("✅ 所有服务启动完成")
        
        # 5. 启动时进行一次数据同步
        await self._initial_data_sync()
        
        # 启动监控
        await self.monitor.start()
        
        logger.info("🎯 核心系统启动完成")
        
    async def stop_services(self):
        """停止所有服务"""
        logger.info("🛑 正在停止核心系统...")
        
        # 停止监控
        if self.monitor:
            await self.monitor.stop()
        
        # 停止 WebSocket 服务器
        if 'websocket' in self.services:
            await self.services['websocket'].stop()
        
        # 停止 gRPC 服务器
        if 'grpc_task' in self.services:
            self.services['grpc_task'].cancel()
            try:
                await self.services['grpc_task']
            except asyncio.CancelledError:
                pass
        
        logger.info("👋 核心系统已完全停止")
        
    async def run(self):
        """运行系统"""
        try:
            self.running = True
            
            # 启动服务
            await self.start_services()
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("👋 收到停止信号")
        except Exception as e:
            logger.error(f"❌ 系统运行错误: {e}")
        finally:
            self.running = False
            await self.stop_services()

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='交易监控系统 - 双协议架构')
    parser.add_argument(
        '--config', '-c',
        default='config/config_multi.yaml',
        help='配置文件路径 (默认: config/config_multi.yaml)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别'
    )
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_args()
    
    # 创建并运行系统
    system = TradingSystem(
        config_path=args.config,
        log_level=args.log_level
    )
    
    await system.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 系统已停止")
