#!/usr/bin/env python3
"""
工具函数模块
包含可重用的通用功能函数
"""

import os
import time
import logging
import logging.handlers
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import pandas as pd
import socket



class NetworkUtils:
    """网络相关工具函数"""
    
    @staticmethod
    def is_ipv6_available() -> bool:
        """检查系统是否支持 IPv6"""
        try:
            socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            return True
        except (socket.error, OSError):
            return False
    
    @staticmethod
    def normalize_host_for_ipv6(host: str, ipv6_enabled: bool) -> str:
        """
        为 IPv6 规范化主机地址
        
        Args:
            host: 原始主机地址
            ipv6_enabled: 是否启用 IPv6
            
        Returns:
            规范化后的主机地址
        """
        if ipv6_enabled and host == "0.0.0.0":
            return "::"  # IPv6 的全零地址
        return host
    
    @staticmethod
    def get_bind_addresses(host: str, ipv6_enabled: bool, bind_both: bool) -> list:
        """
        获取绑定地址列表
        
        Args:
            host: 主机地址
            ipv6_enabled: 是否启用 IPv6
            bind_both: 是否同时绑定 IPv4 和 IPv6
            
        Returns:
            绑定地址列表
        """
        addresses = []
        
        if bind_both and ipv6_enabled:
            # 添加 IPv4 地址
            addresses.append((host, socket.AF_INET))
            # 添加 IPv6 地址
            ipv6_host = "::" if host == "0.0.0.0" else host
            addresses.append((ipv6_host, socket.AF_INET6))
        elif ipv6_enabled:
            # 仅 IPv6
            ipv6_host = "::" if host == "0.0.0.0" else host
            addresses.append((ipv6_host, socket.AF_INET6))
        else:
            # 仅 IPv4
            addresses.append((host, socket.AF_INET))
            
        return addresses


class ThreadSafeFileManager:
    """线程安全的文件管理器"""
    
    @staticmethod
    def merge_csv_with_lock(df_new: pd.DataFrame, path: str, max_retries: int = 3) -> pd.DataFrame:
        """
        线程安全地合并新数据到CSV文件
        
        Args:
            df_new: 新的DataFrame数据
            path: CSV文件路径
            max_retries: 最大重试次数
            
        Returns:
            合并后的DataFrame
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # 使用文件锁确保并发写入安全
        lock_file = f"{path}.lock"
        
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


class TimeUtils:
    """时间相关工具函数"""
    
    @staticmethod
    def utc_now() -> datetime:
        """获取当前UTC时间"""
        return datetime.utcnow().replace(tzinfo=timezone.utc)
    
    @staticmethod
    def seconds_until_trigger(current_time: datetime, minutes: int, trigger_second: int) -> float:
        """
        计算距离下次触发的秒数
        
        Args:
            current_time: 当前时间
            trigger_second: 触发秒数
            
        Returns:
            距离下次触发的秒数
        """
        target = current_time.replace(second=trigger_second, microsecond=0)
        if target <= current_time:
            target += timedelta(minutes=minutes)
        return (target - current_time).total_seconds()
    
    @staticmethod
    def format_timestamp(dt: Optional[datetime] = None) -> str:
        """
        格式化时间戳
        
        Args:
            dt: 要格式化的时间，如果为None则使用当前UTC时间
            
        Returns:
            格式化后的时间字符串
        """
        if dt is None:
            dt = TimeUtils.utc_now()
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


class LoggerFactory:
    """日志记录器工厂类"""
    
    @staticmethod
    def create_logger(
        name: str,
        log_file: str,
        log_level: str = "INFO",
        max_size_mb: int = 10,
        backup_count: int = 5,
        enable_file_logging: bool = True
    ) -> logging.Logger:
        """
        创建配置好的日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径
            log_level: 日志级别
            max_size_mb: 日志文件最大大小(MB)
            backup_count: 备份文件数量
            enable_file_logging: 是否启用文件日志
            
        Returns:
            配置好的日志记录器
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # 清除已有的处理器
        logger.handlers.clear()
        
        if enable_file_logging:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # 创建轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            
            # 设置日志格式
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        # 添加控制台处理器（用于实时显示）
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger


class ThreadSafeStateManager:
    """线程安全的状态管理器"""
    
    def __init__(self):
        self._states = {}
        self._lock = threading.Lock()
    
    def get_state(self, key: str) -> Any:
        """
        获取状态值
        
        Args:
            key: 状态键
            
        Returns:
            状态值
        """
        with self._lock:
            return self._states.get(key)
    
    def set_state(self, key: str, value: Any) -> None:
        """
        设置状态值
        
        Args:
            key: 状态键
            value: 状态值
        """
        with self._lock:
            self._states[key] = value
    
    def update_state(self, updates: Dict[str, Any]) -> None:
        """
        批量更新状态
        
        Args:
            updates: 要更新的状态字典
        """
        with self._lock:
            self._states.update(updates)
    
    def get_all_states(self) -> Dict[str, Any]:
        """
        获取所有状态的副本
        
        Returns:
            所有状态的字典副本
        """
        with self._lock:
            return self._states.copy()


class ProcessingStatsTracker:
    """处理统计追踪器"""
    
    def __init__(self):
        self.reset()
    
    def reset(self) -> None:
        """重置统计数据"""
        self.success_count = 0
        self.error_count = 0
        self.total_time = 0
        self.errors = []
        self.start_time = None
    
    def start_batch(self) -> None:
        """开始批处理计时"""
        self.start_time = time.time()
    
    def add_success(self) -> None:
        """添加成功计数"""
        self.success_count += 1
    
    def add_error(self, target_info: str, error: str) -> None:
        """
        添加错误记录
        
        Args:
            target_info: 目标信息
            error: 错误信息
        """
        self.error_count += 1
        self.errors.append({
            'target': target_info,
            'error': error
        })
    
    def finish_batch(self) -> Dict[str, Any]:
        """
        完成批处理并返回统计结果
        
        Returns:
            处理统计结果
        """
        if self.start_time:
            self.total_time = time.time() - self.start_time
        
        return {
            'success_count': self.success_count,
            'error_count': self.error_count,
            'total_time': self.total_time,
            'errors': self.errors.copy()
        }
    
    def get_summary_message(self, total_targets: int) -> str:
        """
        获取处理摘要信息
        
        Args:
            total_targets: 总目标数
            
        Returns:
            摘要信息字符串
        """
        avg_time = self.total_time / total_targets if total_targets > 0 else 0
        return (f"📈 处理完成 - 成功: {self.success_count}, "
                f"失败: {self.error_count}, "
                f"总耗时: {self.total_time:.2f}s, "
                f"平均: {avg_time:.2f}s/目标")


class DataFrameUtils:
    """DataFrame工具函数"""
    
    @staticmethod
    def create_ohlcv_dataframe(raw_data: list) -> pd.DataFrame:
        """
        从原始OHLCV数据创建DataFrame
        
        Args:
            raw_data: 原始OHLCV数据列表
            
        Returns:
            格式化的DataFrame
        """
        df = pd.DataFrame(raw_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)
        return df
    
    @staticmethod
    def ensure_directory_exists(file_path: str) -> None:
        """
        确保文件所在目录存在
        
        Args:
            file_path: 文件路径
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)


class MessageFormatter:
    """消息格式化工具"""
    
    @staticmethod
    def format_signal_message(signal_type: str, exchange: str, symbol: str, 
                            timeframe: str, price: float) -> str:
        """
        格式化交易信号消息 - 新的简洁格式
        
        Args:
            signal_type: 信号类型 ("BUY" 或 "SELL")
            exchange: 交易所名称
            symbol: 交易对符号
            timeframe: 时间框架
            price: 价格
            
        Returns:
            格式化的信号消息
        """
        from datetime import datetime
        
        emoji = "🟢" if signal_type.upper() == "BUY" else "🔴"
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 格式化价格，添加千位分隔符
        formatted_price = f"{price:,.4f}"
        
        # 新的多行格式
        message = (
            f"{emoji} {signal_type.upper()}\n"
            f"{symbol} ({timeframe})\n"
            f"{formatted_price}\n"
            f"{exchange.upper()}\n"
            f"{current_time}"
        )
        
        return message
    
    @staticmethod
    def create_signal_data(exchange: str, symbol: str, timeframe: str, 
                          price: float, signal_type: str, target_key: str) -> Dict[str, Any]:
        """
        创建信号数据字典
        
        Args:
            exchange: 交易所
            symbol: 交易对
            timeframe: 时间框架
            price: 价格
            signal_type: 信号类型
            target_key: 目标键
            
        Returns:
            信号数据字典
        """
        return {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "price": float(price),
            "timestamp": TimeUtils.format_timestamp(),
            "target_key": target_key,
            "thread": threading.current_thread().name,
            "signal_type": signal_type
        }
    
    @staticmethod
    def create_websocket_message(msg_type: str, level: str, message: str, 
                               signal_data: Optional[Dict] = None, 
                               source: str = "CryptoMonitor") -> Dict[str, Any]:
        """
        创建WebSocket消息
        
        Args:
            msg_type: 消息类型
            level: 消息级别
            message: 消息内容
            signal_data: 信号数据
            source: 消息源
            
        Returns:
            WebSocket消息字典
        """
        return {
            "type": msg_type,
            "level": level,
            "message": message,
            "timestamp": TimeUtils.utc_now().isoformat(),
            "data": signal_data or {},
            "source": source,
            "thread": threading.current_thread().name
        }


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_positive_integer(value: Any, name: str, default: int = 1) -> int:
        """
        验证正整数配置
        
        Args:
            value: 要验证的值
            name: 配置项名称
            default: 默认值
            
        Returns:
            验证后的整数值
        """
        if not isinstance(value, int) or value <= 0:
            print(f"⚠️  配置项 {name} 值无效，使用默认值 {default}")
            return default
        return value
    
    @staticmethod
    def validate_string(value: Any, name: str, default: str = "") -> str:
        """
        验证字符串配置
        
        Args:
            value: 要验证的值
            name: 配置项名称  
            default: 默认值
            
        Returns:
            验证后的字符串值
        """
        if not isinstance(value, str):
            print(f"⚠️  配置项 {name} 值无效，使用默认值 '{default}'")
            return default
        return value