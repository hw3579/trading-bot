"""单线程监控模块"""

import asyncio
import logging
from typing import List, Any

from core.monitor_base import BaseMonitor
from config.config_loader import MonitoringConfig
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class SingleThreadMonitor(BaseMonitor):
    """单线程监控器"""
    
    def __init__(self, config: MonitoringConfig, strategies: List[Any], 
                 notification_service: NotificationService):
        super().__init__(config, strategies, notification_service)
        self.monitor_task = None
        
    async def start(self):
        """启动单线程监控"""
        enabled_targets = self.get_enabled_targets()
        
        if not enabled_targets:
            self.notification.notify_warning("没有启用的监控目标，请检查配置文件")
            return
        
        # 统计信息
        exchange_counts = {}
        for target in enabled_targets:
            exchange_counts[target.exchange] = exchange_counts.get(target.exchange, 0) + 1
        
        self.notification.notify_info(f"单线程监控启动，每 {self.config.trigger_minutes} 分钟 {self.config.trigger_second}s 触发")
        self.notification.notify_info(f"交易所统计: {dict(exchange_counts)}")
        self.notification.notify_info(f"总监控目标: {len(enabled_targets)} 个")
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(enabled_targets))
        logger.info("✅ 单线程监控已启动")
        
    async def _monitor_loop(self, targets):
        """监控循环"""
        while self.running:
            try:
                # 等待到触发时间
                sleep_sec = self.seconds_until_trigger()
                if sleep_sec > 0:
                    await asyncio.sleep(sleep_sec)
                
                # 顺序处理所有目标
                logger.debug(f"开始处理 {len(targets)} 个监控目标")
                
                for target in targets:
                    if not self.running:
                        break
                    
                    try:
                        # 在异步环境中运行同步的处理函数
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.process_target_with_strategies, target
                        )
                    except Exception as e:
                        logger.error(f"处理目标失败: {target.exchange}_{target.symbol}_{target.timeframe} - {e}")
                
                logger.debug("本轮监控完成")
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                if self.running:
                    await asyncio.sleep(5)  # 错误后等待5秒继续
    
    async def sync_data_once(self):
        """一次性数据同步"""
        enabled_targets = self.get_enabled_targets()
        
        if not enabled_targets:
            logger.warning("没有启用的监控目标")
            return
        
        logger.info(f"🔄 开始初始数据同步: {len(enabled_targets)} 个目标")
        
        success_count = 0
        error_count = 0
        
        # 顺序处理所有目标进行一次数据同步
        for target in enabled_targets:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.process_target_with_strategies, target
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"初始同步失败: {target.exchange}_{target.symbol}_{target.timeframe} - {e}")
        
        logger.info(f"📊 初始同步完成: 成功 {success_count}, 失败 {error_count}")
        
        if error_count > 0:
            self.notification.notify_warning(f"初始数据同步部分失败: {error_count} 个目标")
        else:
            self.notification.notify_info(f"初始数据同步完成: {success_count} 个目标")
    
    async def stop(self):
        """停止监控"""
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ 单线程监控已停止")
