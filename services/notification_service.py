"""通知服务统一管理模块"""

import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime
from utils import DataFrameUtils
from config.config_loader import NotificationConfig

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务统一管理"""
    
    def __init__(self, websocket_server: Optional[Any] = None, 
                 telegram_client: Optional[Any] = None,
                 config: NotificationConfig = None):
        self.websocket_server = websocket_server
        self.telegram_client = telegram_client
        self.config = config or NotificationConfig(enabled=True)
        self.logger = logging.getLogger('NotificationService')
        
    def notify(self, message: str, level: str = "INFO", signal_data: Optional[Dict[str, Any]] = None):
        """发送通知"""
        if not self.config.enabled:
            return
        
        # 控制台输出
        print(message)
        
        # 记录日志
        if hasattr(self.logger, level.lower()):
            getattr(self.logger, level.lower())(message)
        else:
            self.logger.info(message)
        
        # WebSocket推送
        if self.websocket_server:
            websocket_msg = DataFrameUtils.create_websocket_message(
                msg_type="notification",
                level=level,
                message=message,
                signal_data=signal_data
            )
            self.websocket_server.send_message_sync(websocket_msg)
    
    def notify_signal(self, exchange: str, symbol: str, timeframe: str, 
                     price: float, signal_type: str, target_key: str):
        """发送交易信号通知"""
        signal_data = {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "price": price,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "target_key": target_key,
            "signal_type": signal_type
        }
        
        signal_msg = self._format_signal_message(signal_type, exchange, symbol, timeframe, price)
        self.notify(signal_msg, "WARNING", signal_data)
    
    def notify_enhanced_signal(self, signal_data: Dict[str, Any]):
        """发送增强的交易信号通知（包含S/R分析）"""
        # 使用标准的信号消息格式（保持JSON结构一致性）
        signal_msg = self._format_signal_message(
            signal_data.get("signal_type", ""),
            signal_data.get("exchange", ""),
            signal_data.get("symbol", ""),
            signal_data.get("timeframe", ""),
            signal_data.get("price", 0)
        )
        
        # 添加时间戳（如果signal_data中没有）
        if "timestamp" not in signal_data:
            signal_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 将enhanced_message作为单独的字段保留在signal_data中
        # 这样WebSocket客户端可以选择使用enhanced_message或标准message
        enhanced_signal_data = signal_data.copy()
        
        # 确保enhanced_message字段存在
        if "enhanced_message" not in enhanced_signal_data:
            enhanced_signal_data["enhanced_message"] = signal_msg
        
        # 使用标准格式的消息，但在signal_data中包含enhanced_message
        self.notify(signal_msg, "WARNING", enhanced_signal_data)
    
    def notify_error(self, error_msg: str, target_info: str = ""):
        """发送错误通知"""
        if target_info:
            full_msg = f"❌ {target_info} 运行出错: {error_msg}"
        else:
            full_msg = f"❌ 系统错误: {error_msg}"
        
        self.notify(full_msg, "ERROR")
    
    def notify_warning(self, warning_msg: str):
        """发送警告通知"""
        self.notify(f"⚠️ {warning_msg}", "WARNING")
    
    def notify_info(self, info_msg: str):
        """发送信息通知"""
        self.notify(info_msg, "INFO")
    
    def _format_signal_message(self, signal_type: str, exchange: str, 
                              symbol: str, timeframe: str, price: float) -> str:
        """格式化信号消息 - 新的简洁格式"""
        from datetime import datetime
        
        icon = "🟢" if signal_type == "BUY" else "🔴"
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 格式化价格，添加千位分隔符
        formatted_price = f"{price:,.4f}"
        
        # 新的多行格式
        message = (
            f"{icon} {signal_type}\n"
            f"{symbol} ({timeframe})\n"
            f"{formatted_price}\n"
            f"{exchange.upper()}\n"
            f"{current_time}"
        )
        
        return message
