"""配置加载器模块"""

import yaml
from dataclasses import dataclass
from typing import Dict, List, Any
from pathlib import Path

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
class MonitoringConfig:
    """监控配置"""
    trigger_second: int
    trigger_minutes: int
    fetch_limit: int
    tail_calc: int
    max_retries: int
    retry_delay: int
    max_workers: int
    use_multi_thread: bool
    exchanges: Dict[str, ExchangeConfig]
    targets: List[MonitorTarget]

@dataclass
class WebSocketConfig:
    """WebSocket配置"""
    enabled: bool
    host: str
    port: int
    ipv6_enabled: bool
    bind_both: bool

@dataclass
class TelegramConfig:
    """Telegram配置"""
    enabled: bool
    bot_token: str
    chat_ids: List[str]

@dataclass
class NotificationConfig:
    """通知配置"""
    enabled: bool

@dataclass
class LoggingConfig:
    """日志配置"""
    enabled: bool
    log_file: str
    log_level: str
    max_size_mb: int
    backup_count: int

@dataclass
class StrategyConfig:
    """策略配置"""
    enabled: List[str]
    utbot: Dict[str, Any]

@dataclass
class SystemConfig:
    """系统总配置"""
    monitoring: MonitoringConfig
    websocket: WebSocketConfig
    telegram: TelegramConfig
    notification: NotificationConfig
    logging: LoggingConfig
    strategies: StrategyConfig

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_positive_integer(value: Any, name: str, default: int) -> int:
        """验证正整数"""
        if not isinstance(value, int) or value <= 0:
            print(f"⚠️ 配置 {name} 无效，使用默认值: {default}")
            return default
        return value
    
    @staticmethod
    def validate_string(value: Any, name: str, default: str) -> str:
        """验证字符串"""
        if not isinstance(value, str) or not value.strip():
            print(f"⚠️ 配置 {name} 无效，使用默认值: {default}")
            return default
        return value.strip()

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load(config_path: str) -> SystemConfig:
        """加载配置文件"""
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return ConfigLoader._parse_config(data)
    
    @staticmethod
    def _parse_config(data: Dict[str, Any]) -> SystemConfig:
        """解析配置数据"""
        
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
        
        # 监控配置
        monitoring_data = data['monitoring']
        monitoring = MonitoringConfig(
            trigger_second=ConfigValidator.validate_positive_integer(
                monitoring_data.get('trigger_second', 30), 'trigger_second', 30
            ),
            trigger_minutes=ConfigValidator.validate_positive_integer(
                monitoring_data.get('trigger_minutes', 1), 'trigger_minutes', 1
            ),
            fetch_limit=ConfigValidator.validate_positive_integer(
                monitoring_data.get('fetch_limit', 100), 'fetch_limit', 100
            ),
            tail_calc=ConfigValidator.validate_positive_integer(
                monitoring_data.get('tail_calc', 50), 'tail_calc', 50
            ),
            max_retries=ConfigValidator.validate_positive_integer(
                monitoring_data.get('max_retries', 3), 'max_retries', 3
            ),
            retry_delay=ConfigValidator.validate_positive_integer(
                monitoring_data.get('retry_delay', 10), 'retry_delay', 10
            ),
            max_workers=ConfigValidator.validate_positive_integer(
                monitoring_data.get('max_workers', 8), 'max_workers', 8
            ),
            use_multi_thread=monitoring_data.get('use_multi_thread', False),
            exchanges=exchanges,
            targets=targets
        )
        
        # WebSocket配置
        websocket_data = data.get('notification', {}).get('websocket', {})
        websocket = WebSocketConfig(
            enabled=websocket_data.get('enabled', False),
            host=ConfigValidator.validate_string(
                websocket_data.get('host', '0.0.0.0'), 'websocket_host', '0.0.0.0'
            ),
            port=ConfigValidator.validate_positive_integer(
                websocket_data.get('port', 10000), 'websocket_port', 10000
            ),
            ipv6_enabled=websocket_data.get('ipv6_enabled', False),
            bind_both=websocket_data.get('bind_both', True)
        )
        
        # Telegram配置
        telegram_data = data.get('telegram', {})
        telegram = TelegramConfig(
            enabled=telegram_data.get('enabled', False),
            bot_token=telegram_data.get('bot_token', ''),
            chat_ids=telegram_data.get('chat_ids', [])
        )
        
        # 通知配置
        notification = NotificationConfig(
            enabled=data.get('notification', {}).get('enabled', True)
        )
        
        # 日志配置
        logging_data = data.get('logging', {})
        logging_config = LoggingConfig(
            enabled=logging_data.get('enabled', True),
            log_file=ConfigValidator.validate_string(
                logging_data.get('log_file', 'logs/signals.log'), 'log_file', 'logs/signals.log'
            ),
            log_level=ConfigValidator.validate_string(
                logging_data.get('level', 'INFO'), 'log_level', 'INFO'
            ),
            max_size_mb=ConfigValidator.validate_positive_integer(
                logging_data.get('max_file_size_mb', 10), 'log_max_size_mb', 10
            ),
            backup_count=ConfigValidator.validate_positive_integer(
                logging_data.get('backup_count', 5), 'log_backup_count', 5
            )
        )
        
        # 策略配置
        strategies_data = data.get('strategies', {})
        strategies = StrategyConfig(
            enabled=strategies_data.get('enabled', ['utbot']),
            utbot=strategies_data.get('utbot', {})
        )
        
        return SystemConfig(
            monitoring=monitoring,
            websocket=websocket,
            telegram=telegram,
            notification=notification,
            logging=logging_config,
            strategies=strategies
        )
