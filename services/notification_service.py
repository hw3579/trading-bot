"""通知服务统一管理模块"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from services.websocket_server import WebSocketServer
from services.telegram_client import TelegramClient
from config.config_loader import NotificationConfig

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务统一管理"""
    
    def __init__(self, websocket_server: Optional[WebSocketServer] = None, 
                 telegram_client: Optional[TelegramClient] = None,
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
            websocket_msg = self._create_websocket_message(
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
        self.notify(f"ℹ️ {info_msg}", "INFO")
    
    def notify_success(self, success_msg: str):
        """发送成功通知"""
        self.notify(f"✅ {success_msg}", "INFO")
    
    def _format_signal_message(self, signal_type: str, exchange: str, 
                              symbol: str, timeframe: str, price: float) -> str:
        """格式化信号消息"""
        icon = "🟢" if signal_type == "BUY" else "🔴"
        return f"{icon} {signal_type} SIGNAL - {exchange.upper()} {symbol} ({timeframe}) @ {price:.4f}"
    
    def _create_websocket_message(self, msg_type: str, level: str, message: str, 
                                 signal_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建WebSocket消息"""
        return {
            "type": msg_type,
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": signal_data or {},
            "source": "TradingSystem"
        }
