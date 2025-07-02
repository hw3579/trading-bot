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
import logging.handlers
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from indicators.UT_Bot_v5 import compute_ut_bot_v5

# 导入 WebSocket 服务器
from message_server import start_message_server, send_message

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
    fetch_limit: int
    tail_calc: int
    targets: List[MonitorTarget]
    notification_enabled: bool
    websocket_enabled: bool
    websocket_host: str
    websocket_port: int
    logging_enabled: bool
    log_file: str
    log_max_size_mb: int
    log_backup_count: int
    log_level: str
    max_workers: int  # 新增：最大线程数

class CryptoMonitor:
    """加密货币监控器 - 多线程版本"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.signal_states = {}
        self.logger = self._setup_logger()
        self.exchanges = self._init_exchanges()
        self.message_server = None
        
        # 线程安全锁
        self._signal_lock = threading.Lock()
        self._logger_lock = threading.Lock()
        
        # 计算最大线程数
        target_count = len([t for t in self.config.targets if t.enabled])
        self.max_workers = min(target_count, self.config.max_workers, 20)  # 最多20个线程
        
        # 启动 WebSocket 服务器
        if self.config.websocket_enabled:
            self.message_server = start_message_server(
                self.config.websocket_host, 
                self.config.websocket_port
            )
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
            trigger_second=data['monitoring']['trigger_second'],
            fetch_limit=data['monitoring']['fetch_limit'],
            tail_calc=data['monitoring']['tail_calc'],
            targets=targets,
            notification_enabled=data['notification']['enabled'],
            websocket_enabled=websocket_config.get('enabled', False),
            websocket_host=websocket_config.get('host', '0.0.0.0'),
            websocket_port=websocket_config.get('port', 10000),
            logging_enabled=logging_config.get('enabled', True),
            log_file=logging_config.get('log_file', 'logs/signals.log'),
            log_max_size_mb=logging_config.get('max_file_size_mb', 10),
            log_backup_count=logging_config.get('backup_count', 5),
            log_level=logging_config.get('level', 'INFO'),
            max_workers=data['monitoring'].get('max_workers', 8)  # 新增配置项
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
        logger = logging.getLogger('CryptoMonitor')
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # 清除已有的处理器
        logger.handlers.clear()
        
        if self.config.logging_enabled:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(self.config.log_file), exist_ok=True)
            
            # 创建轮转文件处理器
            handler = logging.handlers.RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.log_max_size_mb * 1024 * 1024,
                backupCount=self.config.log_backup_count,
                encoding='utf-8'
            )
            
            # 设置日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'  # 添加线程名
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        # 添加控制台处理器（用于实时显示）
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _get_target_key(self, target: MonitorTarget) -> str:
        """生成目标唯一标识"""
        return f"{target.exchange}_{target.symbol}_{target.timeframe}"
    
    def utc_now(self) -> datetime:
        """获取当前UTC时间"""
        return datetime.utcnow().replace(tzinfo=timezone.utc)
    
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
        
        # WebSocket 推送 - 使用独立的消息服务器
        if self.config.websocket_enabled:
            websocket_msg = {
                "type": "notification",
                "level": level,
                "message": msg,
                "timestamp": self.utc_now().isoformat(),
                "data": signal_data or {},
                "source": "CryptoMonitor",
                "thread": threading.current_thread().name  # 添加线程信息
            }
            send_message(websocket_msg)
    
    def fetch_closed_candles(self, target: MonitorTarget) -> pd.DataFrame:
        """获取封闭K线数据"""
        if target.exchange not in self.exchanges:
            raise Exception(f"交易所 {target.exchange} 未连接")
            
        exchange = self.exchanges[target.exchange]
        
        raw = exchange.fetch_ohlcv(
            target.symbol, 
            target.timeframe, 
            limit=self.config.fetch_limit
        )
        df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)
        return df
    
    def merge_into_csv(self, df_new: pd.DataFrame, path: str) -> pd.DataFrame:
        """合并新数据到CSV文件 - 线程安全版本"""
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # 使用文件锁确保并发写入安全
        lock_file = f"{path}.lock"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 简单的文件锁机制
                if os.path.exists(lock_file):
                    time.sleep(0.1 * (attempt + 1))  # 递增等待时间
                    continue
                
                # 创建锁文件
                with open(lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                try:
                    if os.path.exists(path):
                        df_old = pd.read_csv(path, index_col="datetime", parse_dates=True)
                        df_all = pd.concat([df_old, df_new])
                        df_all = df_all[~df_all.index.duplicated(keep='last')].sort_index()
                    else:
                        df_all = df_new
                    
                    df_all.to_csv(path)
                    return df_all
                    
                finally:
                    # 清理锁文件
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                break
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(0.1)
        
        return df_new
    
    def detect_signal(self, df_utbot: pd.DataFrame, target: MonitorTarget) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """检测信号变化 - 线程安全版本"""
        target_key = self._get_target_key(target)
        
        with self._signal_lock:  # 确保信号状态访问线程安全
            last_state = self.signal_states.get(target_key)
        
        latest = df_utbot.iloc[-1]
        current_time = self.utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 构建信号数据
        signal_data = {
            "exchange": target.exchange,
            "symbol": target.symbol,
            "timeframe": target.timeframe,
            "price": float(latest['close']),
            "timestamp": current_time,
            "target_key": target_key,
            "thread": threading.current_thread().name
        }
        
        if latest["buy"] and last_state != "buy":
            with self._signal_lock:
                self.signal_states[target_key] = "buy"
            signal_msg = f"🟢 BUY SIGNAL - {target.exchange.upper()} {target.symbol} ({target.timeframe}) @ {latest['close']:.4f}"
            signal_data["signal_type"] = "BUY"
            return "buy", signal_msg, signal_data
        
        if latest["sell"] and last_state != "sell":
            with self._signal_lock:
                self.signal_states[target_key] = "sell"
            signal_msg = f"🔴 SELL SIGNAL - {target.exchange.upper()} {target.symbol} ({target.timeframe}) @ {latest['close']:.4f}"
            signal_data["signal_type"] = "SELL"
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
            os.makedirs(os.path.dirname(target.csv_utbot), exist_ok=True)
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
        """批量处理监控目标 - 多线程版本"""
        results = {
            'success_count': 0,
            'error_count': 0,
            'total_time': 0,
            'errors': []
        }
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="Worker") as executor:
            # 提交所有任务
            future_to_target = {
                executor.submit(self.process_target, target): target 
                for target in targets
            }
            
            # 收集结果
            for future in as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                    results['success_count'] += 1
                except Exception as e:
                    results['error_count'] += 1
                    error_info = {
                        'target': f"{target.exchange}_{target.symbol}_{target.timeframe}",
                        'error': str(e)
                    }
                    results['errors'].append(error_info)
                    self.logger.error(f"批处理任务失败: {error_info}")
        
        results['total_time'] = time.time() - start_time
        return results
    
    def seconds_until_trigger(self, now: datetime) -> float:
        """计算距离下次触发的秒数"""
        target = now.replace(second=self.config.trigger_second, microsecond=0)
        if target <= now:
            target += timedelta(minutes=1)
        return (target - now).total_seconds()
    
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
        
        start_msg = f"🚀 多交易所监控启动，每分钟 {self.config.trigger_second}s 触发"
        exchange_msg = f"📊 交易所统计: {dict(exchange_counts)}"
        targets_msg = f"🎯 总监控目标: {len(enabled_targets)} 个"
        thread_msg = f"🧵 多线程处理: {self.max_workers} 个工作线程"
        
        self.notify(start_msg, "INFO")
        self.notify(exchange_msg, "INFO")
        self.notify(targets_msg, "INFO")
        self.notify(thread_msg, "INFO")
        
        while True:
            sleep_sec = self.seconds_until_trigger(self.utc_now())
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            
            # 多线程批量处理所有启用的目标
            cycle_start_time = time.time()
            self.logger.info(f"🔄 开始新一轮监控，处理 {len(enabled_targets)} 个目标")
            
            results = self.process_targets_batch(enabled_targets)
            
            # 输出处理统计
            cycle_time = time.time() - cycle_start_time
            stats_msg = (f"📈 处理完成 - 成功: {results['success_count']}, "
                        f"失败: {results['error_count']}, "
                        f"总耗时: {cycle_time:.2f}s, "
                        f"平均: {cycle_time/len(enabled_targets):.2f}s/目标")
            
            self.notify(stats_msg, "INFO")
            
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