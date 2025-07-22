"""UT Bot交易策略模块"""

import pandas as pd
from typing import Dict, Any, Optional, Tuple
from indicators.UT_Bot_v5 import compute_ut_bot_v5
from config.config_loader import MonitorTarget

class UTBotStrategy:
    """UT Bot策略"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "UTBot"
        
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算UT Bot信号"""
        return compute_ut_bot_v5(df)
    
    def detect_signal_change(self, df_signals: pd.DataFrame, last_state: Optional[str], 
                           target: MonitorTarget) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """检测信号变化"""
        if df_signals.empty:
            return last_state, None
            
        latest = df_signals.iloc[-1]
        
        # 构建信号数据基础信息
        signal_data = {
            "exchange": target.exchange,
            "symbol": target.symbol,
            "timeframe": target.timeframe,
            "price": float(latest['close']),
            "target_key": f"{target.exchange}_{target.symbol}_{target.timeframe}",
            "strategy": self.name
        }
        
        # 检测买入信号
        if latest["buy"] and last_state != "buy":
            signal_data["signal_type"] = "BUY"
            return "buy", signal_data
        
        # 检测卖出信号
        if latest["sell"] and last_state != "sell":
            signal_data["signal_type"] = "SELL"
            return "sell", signal_data
        
        return last_state, None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        return {
            "name": self.name,
            "description": "UT Bot v5交易策略",
            "version": "5.0",
            "config": self.config
        }
