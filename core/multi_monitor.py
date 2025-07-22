"""多线程监控模块"""

import asyncio
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List, Any, Dict

from core.monitor_base import BaseMonitor
from config.config_loader import MonitoringConfig
from services.notification_service import NotificationService
from utils import ProcessingStatsTracker

logger = logging.getLogger(__name__)

class MultiThreadMonitor(BaseMonitor):
    """多线程监控器"""
    
    def __init__(self, config: MonitoringConfig, strategies: List[Any], 
                 notification_service: NotificationService):
        super().__init__(config, strategies, notification_service)
        self.monitor_task = None
        
        # 计算最大线程数
        target_count = len([t for t in self.config.targets if t.enabled])
        self.max_workers = min(target_count, self.config.max_workers, 20)  # 最多20个线程
        
    async def start(self):
        """启动多线程监控"""
        enabled_targets = self.get_enabled_targets()
        
        if not enabled_targets:
            self.notification.notify_warning("没有启用的监控目标，请检查配置文件")
            return
        
        # 统计信息
        exchange_counts = {}
        for target in enabled_targets:
            exchange_counts[target.exchange] = exchange_counts.get(target.exchange, 0) + 1
        
        self.notification.notify_info(f"多线程监控启动，每 {self.config.trigger_minutes} 分钟 {self.config.trigger_second}s 触发")
        self.notification.notify_info(f"交易所统计: {dict(exchange_counts)}")
        self.notification.notify_info(f"总监控目标: {len(enabled_targets)} 个")
        self.notification.notify_info(f"多线程处理: {self.max_workers} 个工作线程")
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(enabled_targets))
        logger.info("✅ 多线程监控已启动")
        
    async def _monitor_loop(self, targets):
        """监控循环"""
        while self.running:
            try:
                # 等待到触发时间
                sleep_sec = self.seconds_until_trigger()
                if sleep_sec > 0:
                    await asyncio.sleep(sleep_sec)
                
                # 多线程批量处理所有目标
                results = await self._process_targets_batch(targets)
                
                # 生成统计信息
                if results['error_count'] > 0:
                    logger.warning(f"本轮有 {results['error_count']} 个目标处理失败")
                
                logger.debug(f"本轮监控完成: 成功 {results['success_count']}, 失败 {results['error_count']}, 耗时 {results['total_time']:.2f}s")
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                if self.running:
                    await asyncio.sleep(5)  # 错误后等待5秒继续
    
    async def _process_targets_batch(self, targets) -> Dict[str, any]:
        """批量处理监控目标"""
        stats_tracker = ProcessingStatsTracker()
        stats_tracker.start_batch()
        
        # 使用线程池执行器在异步环境中运行同步任务
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="Worker") as executor:
            # 提交所有任务
            futures = []
            future_to_target = {}
            
            for target in targets:
                future = loop.run_in_executor(executor, self.process_target_with_strategies, target)
                futures.append(future)
                future_to_target[future] = target
            
            # 等待所有任务完成
            for completed_future in asyncio.as_completed(futures):
                try:
                    # 等待协程完成
                    await completed_future
                    stats_tracker.add_success()
                except Exception as e:
                    # 找到对应的target进行错误记录
                    target = future_to_target.get(completed_future, None)
                    target_info = f"{target.exchange}_{target.symbol}_{target.timeframe}" if target else "未知目标"
                    stats_tracker.add_error(target_info, str(e))
                    logger.error(f"批处理任务失败: {target_info} - {e}")
        
        return stats_tracker.finish_batch()
    
    async def sync_data_once(self):
        """一次性数据同步"""
        enabled_targets = self.get_enabled_targets()
        
        if not enabled_targets:
            logger.warning("没有启用的监控目标")
            return
        
        logger.info(f"🔄 开始初始数据同步: {len(enabled_targets)} 个目标")
        
        # 批量处理所有目标进行一次数据同步
        results = await self._process_targets_batch(enabled_targets)
        
        logger.info(f"📊 初始同步完成: 成功 {results['success_count']}, 失败 {results['error_count']}, 耗时 {results['total_time']:.2f}s")
        
        if results['error_count'] > 0:
            self.notification.notify_warning(f"初始数据同步部分失败: {results['error_count']} 个目标")
        else:
            self.notification.notify_info(f"初始数据同步完成: {results['success_count']} 个目标")
    
    async def stop(self):
        """停止监控"""
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ 多线程监控已停止")
