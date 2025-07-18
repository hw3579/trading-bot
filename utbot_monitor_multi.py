#!/usr/bin/env python3
# utbot_monitor.py
# ---------------------------------------------------------
# 抓 K 线 → 更新 CSV → 计算 UT Bot v5 → 检测 buy/sell
# 支持多币种、多时间框架、多交易所监控 - 多线程版本
# ---------------------------------------------------------

import os
import time
import ccxt
import pandas as pd
import numpy as np
import yaml
import logging
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from indicators.UT_Bot_v5 import compute_ut_bot_v5

# 导入 WebSocket 服务器
from message_server import start_message_server, send_message

# 导入工具函数
from utils import (
    ThreadSafeFileManager, TimeUtils, LoggerFactory, 
    ThreadSafeStateManager, ProcessingStatsTracker,
    DataFrameUtils, MessageFormatter, ConfigValidator
)

@dataclass
class ExchangeConfig:
    """交易所配置"""
    name: str
    enable_rate_limit: bool
    enabled: bool

@dataclass
class MonitorTarget:
    """监控目标配置"""
    exchange: str
    symbol: str
    timeframe: str
    enabled: bool
    csv_raw: str
    csv_utbot: str

@dataclass
class Config:
    """配置类"""
    exchanges: Dict[str, ExchangeConfig]
    trigger_second: int
    trigger_minutes: int  # 新增：触发分钟间隔
    fetch_limit: int
    tail_calc: int
    max_retries: int  # 新增：API请求最大重试次数
    retry_delay: int  # 新增：重试延迟时间（秒）
    targets: List[MonitorTarget]
    notification_enabled: bool
    websocket_enabled: bool
    websocket_host: str
    websocket_port: int
    websocket_ipv6_enabled: bool  # 新增
    websocket_bind_both: bool     # 新增
    logging_enabled: bool
    log_file: str
    log_max_size_mb: int
    log_backup_count: int
    log_level: str
    max_workers: int

class CryptoMonitor:
    """加密货币监控器 - 多线程版本"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.signal_manager = ThreadSafeStateManager()  # 使用工具类管理信号状态
        self.logger = self._setup_logger()
        self.exchanges = self._init_exchanges()
        self.message_server = None
        
        # 线程安全锁（用于日志记录）
        self._logger_lock = threading.Lock()
        
        # 计算最大线程数
        target_count = len([t for t in self.config.targets if t.enabled])
        self.max_workers = min(target_count, self.config.max_workers, 20)  # 最多20个线程
        
        # 启动 WebSocket 服务器
        if self.config.websocket_enabled:
            self.message_server = start_message_server(
                self.config.websocket_host, 
                self.config.websocket_port,
                ipv6_enabled=self.config.websocket_ipv6_enabled,    # 新增参数
                bind_both=self.config.websocket_bind_both           # 新增参数
            )

            # 更新日志信息
            protocol_info = ""
            if self.config.websocket_ipv6_enabled and self.config.websocket_bind_both:
                protocol_info = " (IPv4 + IPv6)"
            elif self.config.websocket_ipv6_enabled:
                protocol_info = " (IPv6)"
            else:
                protocol_info = " (IPv4)"
                
            self.logger.info(f"WebSocket 服务器已启动{protocol_info}: ws://{self.config.websocket_host}:{self.config.websocket_port}")

            self.logger.info(f"WebSocket 服务器已启动: ws://{self.config.websocket_host}:{self.config.websocket_port}")
        
    def _load_config(self, config_path: str) -> Config:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 解析交易所配置
        exchanges = {}
        for exchange_id, exchange_data in data['exchanges'].items():
            exchanges[exchange_id] = ExchangeConfig(
                name=exchange_data['name'],
                enable_rate_limit=exchange_data['enable_rate_limit'],
                enabled=exchange_data['enabled']
            )
        
        # 解析监控目标
        targets = []
        for target_data in data['monitoring']['targets']:
            targets.append(MonitorTarget(
                exchange=target_data['exchange'],
                symbol=target_data['symbol'],
                timeframe=target_data['timeframe'],
                enabled=target_data['enabled'],
                csv_raw=target_data['csv_raw'],
                csv_utbot=target_data['csv_utbot'],
            ))
        
        # WebSocket 配置
        websocket_config = data.get('notification', {}).get('websocket', {})
        
        # 日志配置
        logging_config = data.get('logging', {})
        
        return Config(
            exchanges=exchanges,
            trigger_second=ConfigValidator.validate_positive_integer(
                data['monitoring']['trigger_second'], 'trigger_second', 30
            ),
            trigger_minutes=ConfigValidator.validate_positive_integer(
                data['monitoring'].get('trigger_minutes', 1), 'trigger_minutes', 1
            ),
            fetch_limit=ConfigValidator.validate_positive_integer(
                data['monitoring']['fetch_limit'], 'fetch_limit', 100
            ),
            tail_calc=ConfigValidator.validate_positive_integer(
                data['monitoring']['tail_calc'], 'tail_calc', 50
            ),
            max_retries=ConfigValidator.validate_positive_integer(
                data['monitoring'].get('max_retries', 3), 'max_retries', 3
            ),
            retry_delay=ConfigValidator.validate_positive_integer(
                data['monitoring'].get('retry_delay', 10), 'retry_delay', 10
            ),
            targets=targets,
            notification_enabled=data['notification']['enabled'],
            websocket_enabled=websocket_config.get('enabled', False),
            websocket_host=ConfigValidator.validate_string(
                websocket_config.get('host', '0.0.0.0'), 'websocket_host', '0.0.0.0'
            ),
            websocket_port=ConfigValidator.validate_positive_integer(
                websocket_config.get('port', 10000), 'websocket_port', 10000
            ),
            websocket_ipv6_enabled=websocket_config.get('ipv6_enabled', False),  # 新增
            websocket_bind_both=websocket_config.get('bind_both', True),         # 新增
            logging_enabled=logging_config.get('enabled', True),
            log_file=ConfigValidator.validate_string(
                logging_config.get('log_file', 'logs/signals.log'), 'log_file', 'logs/signals.log'
            ),
            log_max_size_mb=ConfigValidator.validate_positive_integer(
                logging_config.get('max_file_size_mb', 10), 'log_max_size_mb', 10
            ),
            log_backup_count=ConfigValidator.validate_positive_integer(
                logging_config.get('backup_count', 5), 'log_backup_count', 5
            ),
            log_level=ConfigValidator.validate_string(
                logging_config.get('level', 'INFO'), 'log_level', 'INFO'
            ),
            max_workers=ConfigValidator.validate_positive_integer(
                data['monitoring'].get('max_workers', 8), 'max_workers', 8
            )
        )
    
    def _init_exchanges(self) -> Dict[str, ccxt.Exchange]:
        """初始化所有启用的交易所连接"""
        exchanges = {}
        
        for exchange_id, exchange_config in self.config.exchanges.items():
            if not exchange_config.enabled:
                self.logger.info(f"跳过禁用的交易所: {exchange_id}")
                continue
                
            try:
                exchange_class = getattr(ccxt, exchange_config.name)
                exchange = exchange_class({
                    "enableRateLimit": exchange_config.enable_rate_limit
                })
                exchanges[exchange_id] = exchange
                self.logger.info(f"✅ 已连接交易所: {exchange_id} ({exchange_config.name})")
                
            except Exception as e:
                self.logger.error(f"❌ 连接交易所失败: {exchange_id} - {e}")
                
        return exchanges
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        return LoggerFactory.create_logger(
            name='CryptoMonitor',
            log_file=self.config.log_file,
            log_level=self.config.log_level,
            max_size_mb=self.config.log_max_size_mb,
            backup_count=self.config.log_backup_count,
            enable_file_logging=self.config.logging_enabled
        )
    
    def _get_target_key(self, target: MonitorTarget) -> str:
        """生成目标唯一标识"""
        return f"{target.exchange}_{target.symbol}_{target.timeframe}"
    
    def notify(self, msg: str, level: str = "INFO", signal_data: dict = None):
        """发送通知并记录日志 - 线程安全版本"""
        with self._logger_lock:  # 确保日志记录线程安全
            # 控制台输出
            if self.config.notification_enabled:
                print(msg)
            
            # 记录到日志文件
            if hasattr(self.logger, level.lower()):
                getattr(self.logger, level.lower())(msg)
            else:
                self.logger.info(msg)
        
        # WebSocket 推送 - 使用工具函数创建消息
        if self.config.websocket_enabled:
            websocket_msg = MessageFormatter.create_websocket_message(
                msg_type="notification",
                level=level,
                message=msg,
                signal_data=signal_data
            )
            send_message(websocket_msg)
    
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
                thread_name = threading.current_thread().name
                error_msg = f"[{thread_name}] {target.exchange.upper()} {target.symbol} ({target.timeframe}) API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                
                if attempt < max_retries - 1:  # 还有重试机会
                    self.logger.warning(f"⚠️ {error_msg}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:  # 最后一次尝试失败
                    error_msg = f"❌ [{thread_name}] {target.exchange.upper()} {target.symbol} ({target.timeframe}) API请求失败，已重试{max_retries}次: {e}"
                    self.logger.error(error_msg)
                    raise Exception(f"API请求失败，已重试{max_retries}次: {e}")
    
    def merge_into_csv(self, df_new: pd.DataFrame, path: str) -> pd.DataFrame:
        """合并新数据到CSV文件 - 使用工具类"""
        return ThreadSafeFileManager.merge_csv_with_lock(df_new, path)
    
    def detect_signal(self, df_utbot: pd.DataFrame, target: MonitorTarget) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """检测信号变化 - 使用工具类管理状态"""
        target_key = self._get_target_key(target)
        last_state = self.signal_manager.get_state(target_key)
        
        latest = df_utbot.iloc[-1]
        
        # 使用工具函数创建信号数据
        if latest["buy"] and last_state != "buy":
            self.signal_manager.set_state(target_key, "buy")
            signal_msg = MessageFormatter.format_signal_message(
                "BUY", target.exchange, target.symbol, target.timeframe, latest['close']
            )
            signal_data = MessageFormatter.create_signal_data(
                target.exchange, target.symbol, target.timeframe, 
                latest['close'], "BUY", target_key
            )
            return "buy", signal_msg, signal_data
        
        if latest["sell"] and last_state != "sell":
            self.signal_manager.set_state(target_key, "sell")
            signal_msg = MessageFormatter.format_signal_message(
                "SELL", target.exchange, target.symbol, target.timeframe, latest['close']
            )
            signal_data = MessageFormatter.create_signal_data(
                target.exchange, target.symbol, target.timeframe, 
                latest['close'], "SELL", target_key
            )
            return "sell", signal_msg, signal_data
        
        return last_state, None, None
    
    def process_target(self, target: MonitorTarget):
        """处理单个监控目标 - 多线程版本"""
        thread_name = threading.current_thread().name
        start_time = time.time()
        
        try:
            # ① 抓数据并合并到原 CSV
            df_closed = self.fetch_closed_candles(target)
            df_all = self.merge_into_csv(df_closed, target.csv_raw)
            
            # ② 计算 UT Bot v5（截尾提升效率）
            df_tail = df_all.tail(self.config.tail_calc)
            df_ut = compute_ut_bot_v5(df_tail)
            
            # 确保输出目录存在
            DataFrameUtils.ensure_directory_exists(target.csv_utbot)
            df_ut.to_csv(target.csv_utbot)
            
            # ③ 信号检测
            signal_type, display_msg, signal_data = self.detect_signal(df_ut, target)
            if display_msg and signal_data:
                # 发送通知（包含 WebSocket 推送）
                self.notify(display_msg, "WARNING", signal_data)
            
            # 记录处理时间
            process_time = time.time() - start_time
            self.logger.debug(f"✅ [{thread_name}] {target.exchange.upper()} {target.symbol} ({target.timeframe}) 处理完成，耗时: {process_time:.2f}s")
                
        except Exception as e:
            error_msg = f"❌ [{thread_name}] {target.exchange.upper()} {target.symbol} ({target.timeframe}) 运行出错: {e}"
            self.notify(error_msg, "ERROR")
    
    def process_targets_batch(self, targets: List[MonitorTarget]) -> Dict[str, any]:
        """批量处理监控目标 - 使用工具类追踪统计"""
        stats_tracker = ProcessingStatsTracker()
        stats_tracker.start_batch()
        
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="Worker") as executor:
            # 提交所有任务
            future_to_target = {
                executor.submit(self.process_target, target): target 
                for target in targets
            }
            
            # 收集结果
            for future in as_completed(future_to_target):
                target = future_to_target[future]
                target_info = f"{target.exchange}_{target.symbol}_{target.timeframe}"
                
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                    stats_tracker.add_success()
                except Exception as e:
                    stats_tracker.add_error(target_info, str(e))
                    self.logger.error(f"批处理任务失败: {target_info} - {e}")
        
        return stats_tracker.finish_batch()
    
    def main_loop(self):
        """主监控循环 - 多线程版本"""
        enabled_targets = [t for t in self.config.targets if t.enabled and t.exchange in self.exchanges]
        
        if not enabled_targets:
            self.notify("⚠️  没有启用的监控目标，请检查配置文件", "WARNING")
            return
        
        # 统计信息
        exchange_counts = {}
        for target in enabled_targets:
            exchange_counts[target.exchange] = exchange_counts.get(target.exchange, 0) + 1
        
        start_msg = f"🚀 多交易所监控启动，每 {self.config.trigger_minutes} 分钟 {self.config.trigger_second}s 触发"
        exchange_msg = f"📊 交易所统计: {dict(exchange_counts)}"
        targets_msg = f"🎯 总监控目标: {len(enabled_targets)} 个"
        thread_msg = f"🧵 多线程处理: {self.max_workers} 个工作线程"
        
        self.notify(start_msg, "INFO")
        self.notify(exchange_msg, "INFO")
        self.notify(targets_msg, "INFO")
        self.notify(thread_msg, "INFO")
        
        while True:
            sleep_sec = TimeUtils.seconds_until_trigger(TimeUtils.utc_now(), minutes=self.config.trigger_minutes, trigger_second=self.config.trigger_second)
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            
            # 多线程批量处理所有启用的目标
            cycle_start_time = time.time()
            
            results = self.process_targets_batch(enabled_targets)
            
            # 使用工具类生成统计消息
            stats_tracker = ProcessingStatsTracker()
            stats_tracker.success_count = results['success_count']
            stats_tracker.error_count = results['error_count']
            stats_tracker.total_time = results['total_time']
            stats_msg = stats_tracker.get_summary_message(len(enabled_targets))
            
            if results['error_count'] > 0:
                self.logger.warning(f"本轮有 {results['error_count']} 个目标处理失败")

def main():
    """主函数"""
    try:
        monitor = CryptoMonitor("config_multi.yaml")
        monitor.main_loop()
    except KeyboardInterrupt:
        print("\n👋 监控已停止")
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")

if __name__ == "__main__":
    main()