#!/usr/bin/env python3
"""
Multi-Timeframe EMA Trend Analysis Indicator
Based on BigBeluga's Pine Script indicator
Analyzes EMA trends across multiple timeframes
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class MTFEMATrend:
    """多时间框架EMA趋势分析指标"""
    
    def __init__(self, 
                 timeframes: List[str] = ["60", "120", "180", "240", "300"],  # 使用分钟表示，对应1h,2h,3h,4h,5h
                 ema_periods: List[int] = [20, 30, 40, 50, 60],
                 base_timeframe: str = "5"):  # 基础时间框架，默认5分钟
        """
        初始化MTF EMA趋势分析器
        
        Args:
            timeframes: 时间框架列表，以分钟为单位 (如: ["60", "120", "180", "240", "300"])
            ema_periods: EMA周期列表 (如: [20, 30, 40, 50, 60])
            base_timeframe: 基础时间框架，以分钟为单位
        """
        self.timeframes = timeframes
        self.ema_periods = ema_periods
        self.base_timeframe = base_timeframe
        
        # 存储不同时间框架的数据
        self.mtf_data: Dict[str, pd.DataFrame] = {}
        
        # 存储EMA计算结果
        self.ema_results: Dict[str, Dict[int, pd.Series]] = {}
        
        # 存储趋势状态
        self.trend_states: Dict[str, Dict[int, pd.Series]] = {}
    
    def _convert_timeframe_to_minutes(self, tf: str) -> int:
        """
        将时间框架字符串转换为分钟数
        
        Args:
            tf: 时间框架字符串 (如: "60", "120", "1h", "30m", "1d")
            
        Returns:
            分钟数
        """
        tf = tf.lower()
        
        # 如果是纯数字，直接当作分钟处理
        if tf.isdigit():
            return int(tf)
        
        if tf.endswith('m'):
            return int(tf[:-1])
        elif tf.endswith('h'):
            return int(tf[:-1]) * 60
        elif tf.endswith('d'):
            return int(tf[:-1]) * 1440
        else:
            # 尝试解析为数字
            try:
                return int(tf)
            except ValueError:
                raise ValueError(f"无法解析时间框架: {tf}")
    
    def _convert_to_higher_timeframe(self, df: pd.DataFrame, target_minutes: int, base_minutes: int) -> pd.DataFrame:
        """
        将基础时间框架数据转换为更高时间框架
        类似Pine Script的request.security功能
        
        Args:
            df: 基础时间框架的OHLCV数据
            target_minutes: 目标时间框架（分钟）
            base_minutes: 基础时间框架（分钟）
            
        Returns:
            转换后的数据
        """
        if target_minutes <= base_minutes:
            return df  # 如果目标时间框架不大于基础时间框架，直接返回
        
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        
        # 计算需要聚合的周期数
        multiplier = target_minutes // base_minutes
        
        # 重采样规则
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }
        
        # 如果有volume列
        if 'volume' in df.columns:
            agg_dict['volume'] = 'sum'
        
        # 使用周期聚合而不是时间重采样，更接近Pine Script的逻辑
        freq = f"{target_minutes}min"
        resampled = df.resample(freq).agg(agg_dict).dropna()
        return resampled

    def _resample_data(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        将数据重采样到指定时间框架
        
        Args:
            df: 原始OHLCV数据
            timeframe: 目标时间框架
            
        Returns:
            重采样后的数据
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        
        # 转换时间框架
        minutes = self._convert_timeframe_to_minutes(timeframe)
        freq = f"{minutes}min"  # 使用 'min' 替代已废弃的 'T'
        
        # 重采样规则
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }
        
        # 如果有volume列
        if 'volume' in df.columns:
            agg_dict['volume'] = 'sum'
        
        resampled = df.resample(freq).agg(agg_dict).dropna()
        return resampled
    
    def _calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """
        计算指数移动平均线
        
        Args:
            data: 价格数据
            period: EMA周期
            
        Returns:
            EMA值序列
        """
        return data.ewm(span=period, adjust=False).mean()
    
    def _calculate_trend_state(self, ema_series: pd.Series) -> pd.Series:
        """
        计算趋势状态 (基于EMA是否上升)
        
        Args:
            ema_series: EMA数据序列
            
        Returns:
            趋势状态序列 (True=上升, False=下降)
        """
        # 比较当前EMA与2个周期前的EMA (模仿Pine Script的逻辑)
        trend = ema_series > ema_series.shift(2)
        return trend.fillna(False)
    
    def update_data(self, df: pd.DataFrame, base_timeframe: str = None) -> None:
        """
        更新指定时间框架的数据
        
        Args:
            df: OHLCV数据
            base_timeframe: 数据的基础时间框架，如果为None则使用初始化时的设置
        """
        if base_timeframe is None:
            base_timeframe = self.base_timeframe
            
        base_minutes = self._convert_timeframe_to_minutes(base_timeframe)
        
        # 为每个目标时间框架处理数据
        for tf in self.timeframes:
            target_minutes = self._convert_timeframe_to_minutes(tf)
            
            if tf not in self.mtf_data:
                self.ema_results[tf] = {}
                self.trend_states[tf] = {}
            
            # 转换到目标时间框架
            if target_minutes > base_minutes:
                # 需要聚合到更高时间框架
                tf_data = self._convert_to_higher_timeframe(df, target_minutes, base_minutes)
            else:
                # 目标时间框架小于等于基础时间框架，直接使用原数据
                tf_data = df.copy()
            
            self.mtf_data[tf] = tf_data
            
            # 计算各周期的EMA和趋势
            for period in self.ema_periods:
                ema_values = self._calculate_ema(tf_data['close'], period)
                self.ema_results[tf][period] = ema_values
                
                # 关键：使用Pine Script的趋势判断逻辑 (ema > ema[2])
                trend_state = self._calculate_trend_state(ema_values)
                self.trend_states[tf][period] = trend_state
    
    def get_current_trends(self) -> Dict[str, Dict[int, bool]]:
        """
        获取当前所有时间框架和EMA周期的趋势状态
        
        Returns:
            趋势状态字典 {timeframe: {ema_period: is_uptrend}}
        """
        current_trends = {}
        
        for tf in self.timeframes:
            if tf in self.trend_states:
                current_trends[tf] = {}
                for period in self.ema_periods:
                    if period in self.trend_states[tf]:
                        trend_series = self.trend_states[tf][period]
                        if len(trend_series) > 0:
                            current_trends[tf][period] = bool(trend_series.iloc[-1])
                        else:
                            current_trends[tf][period] = False
                    else:
                        current_trends[tf][period] = False
            else:
                current_trends[tf] = {period: False for period in self.ema_periods}
        
        return current_trends
    
    def get_trend_strength_score(self) -> float:
        """
        计算整体趋势强度得分 (0-100)
        
        Returns:
            趋势强度得分
        """
        trends = self.get_current_trends()
        total_signals = 0
        bullish_signals = 0
        
        for tf in trends:
            for period in trends[tf]:
                total_signals += 1
                if trends[tf][period]:
                    bullish_signals += 1
        
        if total_signals == 0:
            return 50.0  # 中性
        
        return (bullish_signals / total_signals) * 100
    
    def get_trend_consensus(self) -> str:
        """
        获取趋势共识结果
        
        Returns:
            趋势共识字符串
        """
        score = self.get_trend_strength_score()
        
        if score >= 80:
            return "强烈看涨"
        elif score >= 65:
            return "看涨"
        elif score >= 55:
            return "轻微看涨"
        elif score >= 45:
            return "中性"
        elif score >= 35:
            return "轻微看跌"
        elif score >= 20:
            return "看跌"
        else:
            return "强烈看跌"
    
    def detect_trend_change(self) -> Dict[str, List[str]]:
        """
        检测趋势变化信号
        
        Returns:
            趋势变化信号字典
        """
        signals = {
            "bullish_crossovers": [],
            "bearish_crossovers": []
        }
        
        for tf in self.timeframes:
            if tf in self.trend_states:
                for period in self.ema_periods:
                    if period in self.trend_states[tf]:
                        trend_series = self.trend_states[tf][period]
                        if len(trend_series) >= 2:
                            current = trend_series.iloc[-1]
                            previous = trend_series.iloc[-2]
                            
                            # 检测从下降到上升的交叉
                            if current and not previous:
                                signals["bullish_crossovers"].append(f"{tf}_EMA{period}")
                            
                            # 检测从上升到下降的交叉
                            elif not current and previous:
                                signals["bearish_crossovers"].append(f"{tf}_EMA{period}")
        
        return signals
    
    def get_trend_summary(self) -> Dict:
        """
        获取完整的趋势分析摘要
        
        Returns:
            趋势分析摘要字典
        """
        trends = self.get_current_trends()
        strength = self.get_trend_strength_score()
        consensus = self.get_trend_consensus()
        signals = self.detect_trend_change()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "trends": trends,
            "strength_score": strength,
            "consensus": consensus,
            "trend_changes": signals,
            "timeframes": self.timeframes,
            "ema_periods": self.ema_periods
        }
    
    def _convert_tf_display(self, tf_minutes: str) -> str:
        """
        将分钟数转换为显示格式
        模仿Pine Script的convert_tf函数
        """
        minutes = int(tf_minutes)
        if minutes >= 1440:
            days = minutes // 1440
            return f"{days}d"
        elif minutes >= 60:
            hours = minutes // 60
            return f"{hours}h"
        else:
            return f"{minutes}m"

    def format_trend_table(self) -> str:
        """
        格式化趋势表格为字符串 (类似Pine Script的表格显示)
        
        Returns:
            格式化的趋势表格字符串
        """
        trends = self.get_current_trends()
        
        # 构建表格
        lines = []
        lines.append("📊 多时间框架EMA趋势分析")
        lines.append("=" * 50)
        
        # 表头
        header = "时间框架".ljust(8)
        for period in self.ema_periods:
            header += f"EMA{period}".ljust(8)
        lines.append(header)
        lines.append("-" * len(header))
        
        # 数据行
        for tf in self.timeframes:
            tf_display = self._convert_tf_display(tf)
            row = tf_display.ljust(8)
            for period in self.ema_periods:
                if tf in trends and period in trends[tf]:
                    trend_char = "🢁" if trends[tf][period] else "🢃"
                    row += trend_char.ljust(8)
                else:
                    row += "❓".ljust(8)
            lines.append(row)
        
        # 添加摘要信息
        lines.append("-" * 50)
        lines.append(f"趋势强度: {self.get_trend_strength_score():.1f}%")
        lines.append(f"趋势共识: {self.get_trend_consensus()}")
        
        # 添加信号
        signals = self.detect_trend_change()
        if signals["bullish_crossovers"]:
            lines.append(f"🟢 看涨信号: {', '.join(signals['bullish_crossovers'])}")
        if signals["bearish_crossovers"]:
            lines.append(f"🔴 看跌信号: {', '.join(signals['bearish_crossovers'])}")
        
        return "\n".join(lines)


# 便捷函数
def create_mtf_ema_trend(
    timeframes: List[str] = ["60", "120", "180", "240", "300"],  # Pine Script默认的时间框架
    ema_periods: List[int] = [20, 30, 40, 50, 60],
    base_timeframe: str = "5"
) -> MTFEMATrend:
    """
    创建MTF EMA趋势分析器实例
    
    Args:
        timeframes: 时间框架列表（分钟表示）
        ema_periods: EMA周期列表
        base_timeframe: 基础时间框架（分钟表示）
        
    Returns:
        MTFEMATrend实例
    """
    return MTFEMATrend(timeframes, ema_periods, base_timeframe)


def analyze_mtf_trend(df: pd.DataFrame, 
                     timeframes: List[str] = ["60", "120", "180", "240", "300"],
                     ema_periods: List[int] = [20, 30, 40, 50, 60],
                     base_timeframe: str = "5") -> Dict:
    """
    一键分析多时间框架EMA趋势
    
    Args:
        df: OHLCV数据
        timeframes: 时间框架列表（分钟表示）
        ema_periods: EMA周期列表
        base_timeframe: 基础时间框架（分钟表示）
        
    Returns:
        趋势分析结果字典
    """
    analyzer = create_mtf_ema_trend(timeframes, ema_periods, base_timeframe)
    analyzer.update_data(df, base_timeframe)
    return analyzer.get_trend_summary()


if __name__ == "__main__":
    # 测试代码
    print("MTF EMA Trend Analyzer initialized")
    
    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=1000, freq='1min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(1000) * 0.1)
    
    test_data = pd.DataFrame({
        'open': prices,
        'high': prices + np.random.rand(1000) * 2,
        'low': prices - np.random.rand(1000) * 2,
        'close': prices + np.random.randn(1000) * 0.5,
        'volume': np.random.randint(1000, 10000, 1000)
    }, index=dates)
    
    # 测试分析
    result = analyze_mtf_trend(test_data)
    print("\n测试结果:")
    print(f"趋势强度: {result['strength_score']:.1f}%")
    print(f"趋势共识: {result['consensus']}")
    
    # 创建分析器并显示表格
    analyzer = create_mtf_ema_trend()
    analyzer.update_data(test_data)
    print("\n" + analyzer.format_trend_table())
