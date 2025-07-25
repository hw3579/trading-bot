#!/usr/bin/env python3
"""
Smart Multi-Timeframe Support/Resistance Levels Indicator
Based on BullByte's Pine Script indicator
Analyzes S/R levels across multiple timeframes using various methods
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import talib as ta
from scipy.signal import argrelextrema


class Zone:
    """支撑阻力区域类"""
    def __init__(self, level: float, method: str, timeframe: str, zone_type: str, extra: str = ""):
        self.level = level
        self.top = level
        self.bottom = level
        self.methods = [method]
        self.timeframes = [timeframe]
        self.types = zone_type
        self.extras = [extra] if extra else []
        self.confluence = 1
        self.reactions = 0
    
    def merge_with(self, other_level: float, method: str, timeframe: str, zone_type: str, extra: str = ""):
        """合并其他水平到当前区域"""
        self.top = max(self.top, other_level)
        self.bottom = min(self.bottom, other_level)
        self.level = (self.level + other_level) / 2
        self.confluence += 1
        self.methods.append(method)
        self.timeframes.append(timeframe)
        if zone_type != self.types:
            self.types = "Mixed"
        if extra:
            self.extras.append(extra)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'level': self.level,
            'top': self.top,
            'bottom': self.bottom,
            'methods': self.methods,
            'timeframes': self.timeframes,
            'type': self.types,
            'extras': self.extras,
            'confluence': self.confluence,
            'reactions': self.reactions
        }


class SmartMTFSR:
    """智能多时间框架支撑阻力位指标"""
    
    def __init__(self, 
                 timeframes: List[str] = ["15", "60", "240"],  # 15分钟、1小时、4小时
                 show_swings: bool = True,  # Pine脚本默认值
                 show_pivots: bool = False,  # Pine脚本默认值
                 show_fibonacci: bool = False,  # Pine脚本默认值
                 show_order_blocks: bool = False,  # Pine脚本默认值
                 show_volume_profile: bool = False,  # Pine脚本默认值
                 show_psychological_levels: bool = True,  # 保留加密货币特色
                 show_within_percent: float = 2.5,  # 按要求调整
                 lookback_swings: int = 3,  # Pine脚本默认值
                 cluster_percent: float = 0.25,  # 按要求调整
                 top_n: int = 8,  # Pine脚本默认值
                 reaction_lookback: int = 100,  # Pine脚本默认值
                 sort_by: str = "Confluence",  # Pine脚本默认值
                 alert_confluence: int = 4,  # 按要求调整
                 min_confluence: int = 2):  # 最小汇聚度过滤
        """
        初始化Smart MTF S/R指标
        
        Args:
            timeframes: 时间框架列表，以分钟为单位
            show_swings: 显示摆动高低点
            show_pivots: 显示枢轴点
            show_fibonacci: 显示斐波那契水平
            show_order_blocks: 显示订单块
            show_volume_profile: 显示成交量分析
            show_psychological_levels: 显示心理价位水平（整数价位）
            show_within_percent: 显示价格附近百分比内的水平
            lookback_swings: 摆动点回看数量
            cluster_percent: 聚类百分比
            top_n: 显示前N个区域
            reaction_lookback: 反应计算回看期
            sort_by: 排序方式 ("Confluence", "Reactions", "Distance")
            min_confluence: 最小汇聚度过滤，只显示汇聚度大于等于此值的区域
        """
        self.timeframes = timeframes
        self.show_swings = show_swings
        self.show_pivots = show_pivots
        self.show_fibonacci = show_fibonacci
        self.show_order_blocks = show_order_blocks
        self.show_volume_profile = show_volume_profile
        self.show_psychological_levels = show_psychological_levels
        self.show_within_percent = show_within_percent
        self.lookback_swings = lookback_swings
        self.cluster_percent = cluster_percent
        self.top_n = top_n
        self.reaction_lookback = reaction_lookback
        self.sort_by = sort_by
        self.alert_confluence = alert_confluence
        self.min_confluence = min_confluence
        
        # 存储多时间框架数据
        self.mtf_data: Dict[str, pd.DataFrame] = {}
    
    def _resample_to_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """将数据重采样到指定时间框架"""
        try:
            # 确保索引是datetime类型
            if not isinstance(df.index, pd.DatetimeIndex):
                df = df.set_index('timestamp') if 'timestamp' in df.columns else df
            
            # 转换时间框架
            tf_mapping = {
                '1': '1min', '3': '3min', '5': '5min', '15': '15min', '30': '30min', 
                '60': '1h', '120': '2h', '240': '4h', '1440': '1D'
            }
            
            freq = tf_mapping.get(timeframe, f'{timeframe}min')
            
            # 重采样
            resampled = df.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return resampled
        except Exception as e:
            print(f"重采样错误: {e}")
            return df
    
    def _find_swing_points(self, df: pd.DataFrame, left: int = 3, right: int = 3) -> Tuple[List[float], List[float]]:
        """查找摆动高低点"""
        highs = []
        lows = []
        
        if len(df) < left + right + 1:
            return highs, lows
        
        # 使用scipy找到局部极值
        high_indices = argrelextrema(df['high'].values, np.greater, order=left)[0]
        low_indices = argrelextrema(df['low'].values, np.less, order=left)[0]
        
        # 获取最近的摆动点
        if len(high_indices) > 0:
            recent_highs = df['high'].iloc[high_indices[-self.lookback_swings:]].tolist()
            highs.extend(recent_highs)
        
        if len(low_indices) > 0:
            recent_lows = df['low'].iloc[low_indices[-self.lookback_swings:]].tolist()
            lows.extend(recent_lows)
        
        return highs, lows
    
    def _calculate_pivots(self, df: pd.DataFrame) -> Tuple[float, float, float]:
        """计算枢轴点"""
        if len(df) == 0:
            return np.nan, np.nan, np.nan
        
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        close = df['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        s1 = pivot * 2 - high
        r1 = pivot * 2 - low
        
        return pivot, s1, r1
    
    def _calculate_fibonacci(self, df: pd.DataFrame, period: int = 50) -> List[float]:
        """计算斐波那契回撤水平"""
        if len(df) < period:
            return []
        
        recent_data = df.tail(period)
        high = recent_data['high'].max()
        low = recent_data['low'].min()
        
        if high == low:
            return []
        
        fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
        fib_levels = []
        
        for ratio in fib_ratios:
            level = low + (high - low) * ratio
            fib_levels.append(level)
        
        return fib_levels
    
    def _find_order_blocks(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """查找订单块"""
        if len(df) < 3:
            return None, None
        
        bullish_ob = None
        bearish_ob = None
        
        for i in range(2, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i-1]
            prev2 = df.iloc[i-2]
            
            # 看涨订单块：当前收盘价 > 开盘价，前一根收盘价 < 开盘价，当前收盘价 > 前一根最高价
            if (current['close'] > current['open'] and 
                prev['close'] < prev['open'] and 
                current['close'] > prev['high']):
                bullish_ob = prev['low']
            
            # 看跌订单块：当前收盘价 < 开盘价，前一根收盘价 > 开盘价，当前收盘价 < 前一根最低价
            if (current['close'] < current['open'] and 
                prev['close'] > prev['open'] and 
                current['close'] < prev['low']):
                bearish_ob = prev['high']
        
        return bullish_ob, bearish_ob
    
    def _calculate_volume_profile(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """计算成交量分析"""
        if len(df) < 50:
            return None, None
        
        recent_data = df.tail(50)
        
        # VWAP计算
        vwap = (recent_data['volume'] * (recent_data['high'] + recent_data['low'] + recent_data['close']) / 3).sum() / recent_data['volume'].sum()
        
        # POC (Point of Control) - 成交量最大的价格点
        if recent_data['volume'].sum() > 0:
            max_vol_idx = recent_data['volume'].idxmax()
            poc = (recent_data.loc[max_vol_idx, 'high'] + recent_data.loc[max_vol_idx, 'low']) / 2
        else:
            poc = None
        
        return vwap, poc
    
    def _calculate_psychological_levels(self, current_price: float) -> List[float]:
        """计算心理价位水平（整数价位）"""
        levels = []
        
        # 确定价格范围
        price_range = self.show_within_percent / 100 * current_price
        min_price = current_price - price_range
        max_price = current_price + price_range
        
        # 根据价格大小确定间隔
        if current_price >= 10000:
            # 价格>10000时，使用1000的倍数
            interval = 1000
            start = int(min_price / interval) * interval
            end = int(max_price / interval + 1) * interval
        elif current_price >= 1000:
            # 价格1000-10000时，使用100的倍数
            interval = 100
            start = int(min_price / interval) * interval
            end = int(max_price / interval + 1) * interval
        elif current_price >= 100:
            # 价格100-1000时，使用10的倍数
            interval = 10
            start = int(min_price / interval) * interval
            end = int(max_price / interval + 1) * interval
        elif current_price >= 10:
            # 价格10-100时，使用1的倍数
            interval = 1
            start = int(min_price / interval) * interval
            end = int(max_price / interval + 1) * interval
        else:
            # 价格<10时，使用0.1的倍数
            interval = 0.1
            start = round(min_price / interval) * interval
            end = round(max_price / interval + 1) * interval
        
        # 生成心理价位
        current = start
        while current <= end:
            if current != current_price:  # 避免添加当前价格
                levels.append(current)
            current += interval
        
        return levels
    
    def _calculate_reactions(self, df: pd.DataFrame, top: float, bottom: float) -> int:
        """计算价格对区域的反应次数"""
        if len(df) < self.reaction_lookback:
            return 0
        
        recent_data = df.tail(self.reaction_lookback)
        reactions = 0
        
        for _, row in recent_data.iterrows():
            if bottom <= row['close'] <= top:
                reactions += 1
        
        return reactions
    
    def _cluster_levels(self, levels: List[Tuple[float, str, str, str, str]], current_price: float) -> List[Zone]:
        """将水平聚类为区域"""
        zones = []
        
        for level, method, tf, zone_type, extra in levels:
            if np.isnan(level):
                continue
            
            # 查找是否可以合并到现有区域
            merged = False
            for zone in zones:
                if abs(zone.level - level) / current_price * 100 < self.cluster_percent:
                    zone.merge_with(level, method, tf, zone_type, extra)
                    merged = True
                    break
            
            if not merged:
                zones.append(Zone(level, method, tf, zone_type, extra))
        
        return zones
    
    def _filter_zones_by_distance(self, zones: List[Zone], current_price: float) -> List[Zone]:
        """过滤距离当前价格太远的区域，并按最小汇聚度过滤"""
        filtered_zones = []
        
        for zone in zones:
            # 距离过滤
            distance_percent = abs(zone.level - current_price) / current_price * 100
            if distance_percent <= self.show_within_percent:
                # 汇聚度过滤
                if zone.confluence >= self.min_confluence:
                    filtered_zones.append(zone)
        
        return filtered_zones
    
    def _sort_zones(self, zones: List[Zone], current_price: float) -> List[Zone]:
        """排序区域"""
        if self.sort_by == "Confluence":
            zones.sort(key=lambda z: z.confluence, reverse=True)
        elif self.sort_by == "Reactions":
            zones.sort(key=lambda z: z.reactions, reverse=True)
        elif self.sort_by == "Distance":
            zones.sort(key=lambda z: abs(z.level - current_price))
        
        return zones[:self.top_n]
    
    def compute_sr_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算智能多时间框架支撑阻力位
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            添加了sr_data列的DataFrame
        """
        result_df = df.copy()
        result_df['sr_data'] = None
        
        try:
            # 为每个时间框架准备数据
            for tf in self.timeframes:
                if tf == "5":  # 基础时间框架
                    self.mtf_data[tf] = df
                else:
                    self.mtf_data[tf] = self._resample_to_timeframe(df, tf)
            
            # 处理每一行
            for idx in range(len(df)):
                if idx < self.reaction_lookback:  # 需要足够的历史数据
                    continue
                
                current_data = df.iloc[:idx+1]
                current_price = current_data['close'].iloc[-1]
                all_levels = []
                
                # 为每个时间框架收集水平
                for tf in self.timeframes:
                    tf_data = self.mtf_data[tf]
                    
                    # 确保有足够的数据
                    if len(tf_data) == 0:
                        continue
                    
                    # 找到对应的时间点
                    current_time = current_data.index[-1]
                    tf_current_data = tf_data[tf_data.index <= current_time]
                    
                    if len(tf_current_data) == 0:
                        continue
                    
                    # 摆动点
                    if self.show_swings:
                        highs, lows = self._find_swing_points(tf_current_data)
                        for high in highs:
                            all_levels.append((high, "Swing High", tf, "Resistance", ""))
                        for low in lows:
                            all_levels.append((low, "Swing Low", tf, "Support", ""))
                    
                    # 枢轴点
                    if self.show_pivots:
                        pivot, s1, r1 = self._calculate_pivots(tf_current_data)
                        if not np.isnan(pivot):
                            all_levels.append((pivot, "Pivot", tf, "Pivot", ""))
                            all_levels.append((s1, "S1", tf, "Support", ""))
                            all_levels.append((r1, "R1", tf, "Resistance", ""))
                    
                    # 斐波那契
                    if self.show_fibonacci:
                        fib_levels = self._calculate_fibonacci(tf_current_data)
                        fib_ratios = ["0.236", "0.382", "0.5", "0.618", "0.786"]
                        for i, level in enumerate(fib_levels):
                            ratio = fib_ratios[i] if i < len(fib_ratios) else ""
                            all_levels.append((level, "Fibonacci", tf, "Pivot", ratio))
                    
                    # 订单块
                    if self.show_order_blocks:
                        bullish_ob, bearish_ob = self._find_order_blocks(tf_current_data)
                        if bullish_ob is not None:
                            all_levels.append((bullish_ob, "Bullish OB", tf, "Support", ""))
                        if bearish_ob is not None:
                            all_levels.append((bearish_ob, "Bearish OB", tf, "Resistance", ""))
                    
                    # 成交量分析
                    if self.show_volume_profile:
                        vwap, poc = self._calculate_volume_profile(tf_current_data)
                        if vwap is not None:
                            all_levels.append((vwap, "VWAP", tf, "Pivot", ""))
                        if poc is not None:
                            all_levels.append((poc, "POC", tf, "Pivot", ""))
                
                # 心理价位水平（只需要计算一次，不分时间框架）
                if self.show_psychological_levels and tf == self.timeframes[0]:  # 只在第一个时间框架计算
                    psychological_levels = self._calculate_psychological_levels(current_price)
                    for level in psychological_levels:
                        # 根据与当前价格的关系确定类型
                        level_type = "Resistance" if level > current_price else "Support"
                        all_levels.append((level, "Psychological", "All", level_type, ""))
                
                # 聚类水平为区域
                zones = self._cluster_levels(all_levels, current_price)
                
                # 计算反应次数
                for zone in zones:
                    zone.reactions = self._calculate_reactions(current_data, zone.top, zone.bottom)
                
                # 过滤和排序
                filtered_zones = self._filter_zones_by_distance(zones, current_price)
                sorted_zones = self._sort_zones(filtered_zones, current_price)
                
                # 生成输出数据
                sr_data = {
                    'zones': [zone.to_dict() for zone in sorted_zones],
                    'total_zones': len(sorted_zones),
                    'current_price': current_price,
                    'timestamp': current_data.index[-1].isoformat() if hasattr(current_data.index[-1], 'isoformat') else str(current_data.index[-1])
                }
                
                result_df.iloc[idx, result_df.columns.get_loc('sr_data')] = json.dumps(sr_data)
        
        except Exception as e:
            print(f"计算Smart MTF S/R时出错: {e}")
            import traceback
            traceback.print_exc()
        
        return result_df


# 便捷函数
def compute_smart_mtf_sr(df: pd.DataFrame, 
                        timeframes: List[str] = ["15", "60", "240"],  # 15分钟、1小时、4小时
                        show_swings: bool = True,  # Pine脚本默认值
                        show_pivots: bool = False,  # Pine脚本默认值
                        show_fibonacci: bool = False,  # Pine脚本默认值
                        show_order_blocks: bool = False,  # Pine脚本默认值
                        show_volume_profile: bool = False,  # Pine脚本默认值
                        show_psychological_levels: bool = True,
                        show_within_percent: float = 2.5,  # 按要求调整
                        lookback_swings: int = 3,  # Pine脚本默认值
                        cluster_percent: float = 0.25,  # 按要求调整
                        top_n: int = 8,  # Pine脚本默认值
                        reaction_lookback: int = 100,  # Pine脚本默认值
                        sort_by: str = "Confluence",  # Pine脚本默认值
                        alert_confluence: int = 4,  # 按要求调整
                        min_confluence: int = 2) -> pd.DataFrame:
    """
    计算智能多时间框架支撑阻力位
    
    Args:
        df: OHLCV数据DataFrame
        timeframes: 时间框架列表
        show_swings: 显示摆动点
        show_pivots: 显示枢轴点
        show_fibonacci: 显示斐波那契
        show_order_blocks: 显示订单块
        show_volume_profile: 显示成交量分析
        show_psychological_levels: 显示心理价位水平
        show_within_percent: 显示价格附近百分比
        lookback_swings: 摆动点回看数量
        cluster_percent: 聚类百分比
        top_n: 显示前N个区域
        reaction_lookback: 反应计算回看期
        sort_by: 排序方式
        alert_confluence: 警报汇聚度阈值
        min_confluence: 最小汇聚度过滤
        
    Returns:
        包含sr_data列的DataFrame
    """
    indicator = SmartMTFSR(
        timeframes=timeframes,
        show_swings=show_swings,
        show_pivots=show_pivots,
        show_fibonacci=show_fibonacci,
        show_order_blocks=show_order_blocks,
        show_volume_profile=show_volume_profile,
        show_psychological_levels=show_psychological_levels,
        show_within_percent=show_within_percent,
        lookback_swings=lookback_swings,
        cluster_percent=cluster_percent,
        top_n=top_n,
        reaction_lookback=reaction_lookback,
        sort_by=sort_by,
        alert_confluence=alert_confluence,
        min_confluence=min_confluence
    )
    
    return indicator.compute_sr_levels(df)


if __name__ == "__main__":
    # 测试代码
    print("Smart MTF S/R Levels Indicator - 测试模式")
    
    # 创建测试数据
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='5min')
    np.random.seed(42)
    
    # 生成模拟价格数据
    price = 100
    prices = [price]
    for _ in range(999):
        price += np.random.normal(0, 0.5)
        prices.append(max(price, 50))  # 防止价格过低
    
    # 生成OHLCV数据
    test_data = []
    for i, (date, price) in enumerate(zip(dates, prices)):
        open_price = price + np.random.normal(0, 0.2)
        high_price = max(open_price, price) + abs(np.random.normal(0, 0.3))
        low_price = min(open_price, price) - abs(np.random.normal(0, 0.3))
        close_price = price
        volume = np.random.randint(1000, 10000)
        
        test_data.append({
            'timestamp': date,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(test_data)
    df.set_index('timestamp', inplace=True)
    
    print("测试数据生成完成，开始计算Smart MTF S/R...")
    
    # 计算指标
    result = compute_smart_mtf_sr(
        df, 
        timeframes=["15", "60", "240"],  # Pine脚本时间框架
        show_swings=True,  # Pine脚本默认开启
        show_pivots=False,  # Pine脚本默认关闭
        show_fibonacci=False,  # Pine脚本默认关闭
        show_order_blocks=False,  # Pine脚本默认关闭
        show_volume_profile=False,  # Pine脚本默认关闭
        show_psychological_levels=True,  # 加密货币特色
        top_n=5,
        min_confluence=1  # 测试时降低最小汇聚度
    )
    
    # 显示结果
    print(f"计算完成！数据行数: {len(result)}")
    
    # 显示最后几行的结果
    for i in range(max(0, len(result)-3), len(result)):
        sr_data = result.iloc[i]['sr_data']
        if sr_data and sr_data != 'None':
            try:
                data = json.loads(sr_data)
                print(f"\n时间: {data['timestamp']}")
                print(f"当前价格: {data['current_price']:.2f}")
                print(f"发现 {data['total_zones']} 个S/R区域")
                
                for j, zone in enumerate(data['zones'][:3]):  # 只显示前3个
                    print(f"  区域 {j+1}: 价格={zone['level']:.2f}, 类型={zone['type']}, 汇聚度={zone['confluence']}, 反应次数={zone['reactions']}")
                    print(f"    方法: {', '.join(zone['methods'])}")
                    print(f"    时间框架: {', '.join(zone['timeframes'])}")
            except:
                pass
