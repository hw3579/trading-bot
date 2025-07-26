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
        
        # 初始化智能S/R策略（如果配置中启用）
        self.enable_sr_analysis = config.get("enable_sr_analysis", True)
        self.smart_sr_strategy = None
        
        if self.enable_sr_analysis:
            try:
                from strategies.smart_sr_strategy import SmartSRStrategy
                sr_config = config.get("smart_sr_config", {})
                self.smart_sr_strategy = SmartSRStrategy(sr_config)
                print(f"✅ UTBot策略已启用智能S/R分析")
            except Exception as e:
                print(f"⚠️ 初始化智能S/R分析失败: {e}")
                self.enable_sr_analysis = False
        
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
        
        signal_triggered = False
        
        # 检测买入信号
        if latest["buy"] and last_state != "buy":
            signal_data["signal_type"] = "BUY"
            signal_triggered = True
            new_state = "buy"
        # 检测卖出信号
        elif latest["sell"] and last_state != "sell":
            signal_data["signal_type"] = "SELL"
            signal_triggered = True
            new_state = "sell"
        else:
            return last_state, None
        
        # 如果信号被触发且启用了S/R分析，则增强信号数据
        if signal_triggered and self.enable_sr_analysis and self.smart_sr_strategy:
            try:
                # 获取完整的OHLCV数据用于S/R分析
                source_df = df_signals[['open', 'high', 'low', 'close', 'volume']].copy()
                enhanced_signal_data = self.smart_sr_strategy.enhance_utbot_signal(signal_data, source_df)
                return new_state, enhanced_signal_data
            except Exception as e:
                print(f"⚠️ S/R分析增强失败: {e}")
                # 分析失败时返回原始信号
                return new_state, signal_data
        
        return new_state, signal_data
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        info = {
            "name": self.name,
            "description": "UT Bot v5交易策略",
            "version": "5.0",
            "config": self.config,
            "sr_analysis_enabled": self.enable_sr_analysis
        }
        
        if self.enable_sr_analysis and self.smart_sr_strategy:
            info["sr_strategy_info"] = self.smart_sr_strategy.get_strategy_info()
            
        return info
