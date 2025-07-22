"""监控基类模块"""

import asyncio
import ccxt
import pandas as pd
import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from config.config_loader import MonitoringConfig, MonitorTarget
from services.notification_service import NotificationService
from strategies.utbot_strategy import UTBotStrategy
from utils import ThreadSafeFileManager, DataFrameUtils

logger = logging.getLogger(__name__)

class BaseMonitor(ABC):
    """监控基类"""
    
    def __init__(self, config: MonitoringConfig, strategies: List[Any], 
                 notification_service: NotificationService):
        self.config = config
        self.strategies = strategies
        self.notification = notification_service
        self.signal_states = {}  # 存储信号状态
        self.exchanges = self._init_exchanges()
        self.running = False
        
    def _init_exchanges(self) -> Dict[str, ccxt.Exchange]:
        """初始化所有启用的交易所连接"""
        exchanges = {}
        
        for exchange_id, exchange_config in self.config.exchanges.items():
            if not exchange_config.enabled:
                logger.info(f"跳过禁用的交易所: {exchange_id}")
                continue
                
            try:
                exchange_class = getattr(ccxt, exchange_config.name)
                exchange = exchange_class({
                    "enableRateLimit": exchange_config.enable_rate_limit
                })
                exchanges[exchange_id] = exchange
                logger.info(f"✅ 已连接交易所: {exchange_id} ({exchange_config.name})")
                
            except Exception as e:
                logger.error(f"❌ 连接交易所失败: {exchange_id} - {e}")
                
        return exchanges
    
    def _get_target_key(self, target: MonitorTarget) -> str:
        """生成目标唯一标识"""
        return f"{target.exchange}_{target.symbol}_{target.timeframe}"
    
    def fetch_closed_candles(self, target: MonitorTarget) -> pd.DataFrame:
        """获取封闭K线数据 - 带重试机制"""
        if target.exchange not in self.exchanges:
            raise Exception(f"交易所 {target.exchange} 未连接")
            
        exchange = self.exchanges[target.exchange]
        max_retries = self.config.max_retries
        retry_delay = self.config.retry_delay
        
        for attempt in range(max_retries):
            try:
                raw = exchange.fetch_ohlcv(
                    target.symbol, 
                    target.timeframe, 
                    limit=self.config.fetch_limit
                )
                return DataFrameUtils.create_ohlcv_dataframe(raw)
                
            except Exception as e:
                error_msg = f"{target.exchange.upper()} {target.symbol} ({target.timeframe}) API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                
                if attempt < max_retries - 1:  # 还有重试机会
                    logger.warning(f"⚠️ {error_msg}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:  # 最后一次尝试失败
                    logger.error(f"❌ {error_msg}")
                    raise Exception(f"API请求失败，已重试{max_retries}次: {e}")
    
    def merge_into_csv(self, df_new: pd.DataFrame, path: str) -> pd.DataFrame:
        """合并新数据到CSV文件"""
        return ThreadSafeFileManager.merge_csv_with_lock(df_new, path)
    
    def process_target_with_strategies(self, target: MonitorTarget):
        """使用策略处理单个监控目标"""
        try:
            # ① 抓取数据并合并到原 CSV
            df_closed = self.fetch_closed_candles(target)
            df_all = self.merge_into_csv(df_closed, target.csv_raw)
            
            # ② 截取尾部数据提升效率
            df_tail = df_all.tail(self.config.tail_calc)
            
            # ③ 应用所有策略
            for strategy in self.strategies:
                if isinstance(strategy, UTBotStrategy):
                    # 计算指标
                    df_signals = strategy.calculate_signals(df_tail)
                    
                    # 确保输出目录存在
                    DataFrameUtils.ensure_directory_exists(target.csv_utbot)
                    df_signals.to_csv(target.csv_utbot)
                    
                    # 信号检测
                    target_key = self._get_target_key(target)
                    last_state = self.signal_states.get(target_key)
                    
                    new_state, signal_data = strategy.detect_signal_change(
                        df_signals, last_state, target
                    )
                    
                    # 更新状态
                    if new_state != last_state:
                        self.signal_states[target_key] = new_state
                    
                    # 发送信号通知
                    if signal_data:
                        self.notification.notify_signal(
                            exchange=signal_data["exchange"],
                            symbol=signal_data["symbol"],
                            timeframe=signal_data["timeframe"],
                            price=signal_data["price"],
                            signal_type=signal_data["signal_type"],
                            target_key=signal_data["target_key"]
                        )
                        
        except Exception as e:
            target_info = f"{target.exchange.upper()} {target.symbol} ({target.timeframe})"
            self.notification.notify_error(str(e), target_info)
    
    def get_enabled_targets(self) -> List[MonitorTarget]:
        """获取启用的监控目标"""
        return [t for t in self.config.targets if t.enabled and t.exchange in self.exchanges]
    
    def seconds_until_trigger(self) -> float:
        """计算距离下次触发的秒数"""
        now = datetime.utcnow()
        target = now.replace(second=self.config.trigger_second, microsecond=0)
        
        # 如果当前时间已经过了触发时间，则计算下一个触发周期
        if target <= now:
            target += timedelta(minutes=self.config.trigger_minutes)
        
        return (target - now).total_seconds()
    
    @abstractmethod
    async def start(self):
        """启动监控"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止监控"""
        pass
