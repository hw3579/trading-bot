#!/usr/bin/env python3
"""
综合技术分析图表生成器
结合Smart MTF S/R和MTF EMA指标生成可视化图表
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 服务器环境友好的后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# 设置字体以避免中文显示问题
plt.rcParams['font.family'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10

# 导入指标和示例
from indicators.smart_mtf_sr import compute_smart_mtf_sr
from indicators.mtf_ema_trend import MTFEMATrend
from examples.smart_mtf_sr_example import load_okx_data, analyze_sr_data


class TechnicalAnalysisChart:
    """技术分析图表生成器"""
    
    def __init__(self, figsize=(16, 12)):
        """Initialize chart generator"""
        self.figsize = figsize
        plt.style.use('dark_background')  # 使用深色主题
        
        # Configure font settings to avoid Chinese character display issues
        plt.rcParams['font.family'] = ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = 10
        
    def timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe to minutes"""
        timeframe = timeframe.lower()
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 60 * 24
        else:
            # Default assume minutes
            return int(timeframe)
    
    def load_data(self, symbol: str = "ETH", timeframe: str = "15m", candles: int = 200) -> pd.DataFrame:
        """Load data by timeframe and candle count"""
        df = load_okx_data(symbol)
        
        # Get timeframe interval in minutes
        interval_minutes = self.timeframe_to_minutes(timeframe)
        
        # Calculate required time range
        total_minutes = interval_minutes * candles
        cutoff_time = df.index[-1] - timedelta(minutes=total_minutes)
        recent_data = df[df.index >= cutoff_time].copy()
        
        # If we don't have enough data, take what we have
        if len(recent_data) < candles:
            recent_data = df.tail(min(len(df), candles * 2)).copy()
        
        print(f"Loading {symbol} data: {timeframe} timeframe, {candles} candles, {len(recent_data)} records")
        return recent_data
    
    def plot_candlesticks(self, ax, df):
        """Draw candlestick chart with improved visibility"""
        # 计算涨跌
        up = df['close'] > df['open']
        down = ~up
        
        # 调整线条宽度以提高可视性
        candle_width = 0.8
        wick_width = 0.1
        
        # 上涨K线 (绿色) - 更鲜明的颜色，设置z-order确保在前景
        ax.bar(df.index[up], df['close'][up] - df['open'][up], candle_width, 
               bottom=df['open'][up], color='#00FF7F', alpha=0.9, 
               edgecolor='#00FF7F', linewidth=0.5, zorder=5)
        ax.bar(df.index[up], df['high'][up] - df['close'][up], wick_width, 
               bottom=df['close'][up], color='#00FF7F', alpha=0.9, zorder=5)
        ax.bar(df.index[up], df['low'][up] - df['open'][up], wick_width, 
               bottom=df['open'][up], color='#00FF7F', alpha=0.9, zorder=5)
        
        # 下跌K线 (红色) - 更鲜明的颜色，设置z-order确保在前景
        ax.bar(df.index[down], df['open'][down] - df['close'][down], candle_width, 
               bottom=df['close'][down], color='#FF4500', alpha=0.9,
               edgecolor='#FF4500', linewidth=0.5, zorder=5)
        ax.bar(df.index[down], df['high'][down] - df['open'][down], wick_width, 
               bottom=df['open'][down], color='#FF4500', alpha=0.9, zorder=5)
        ax.bar(df.index[down], df['low'][down] - df['close'][down], wick_width, 
               bottom=df['close'][down], color='#FF4500', alpha=0.9, zorder=5)
    
    def plot_sr_levels(self, ax, df_with_sr, symbol):
        """绘制支撑阻力位"""
        # 获取最新的S/R数据
        latest_sr = None
        for i in range(len(df_with_sr)-1, -1, -1):
            sr_data = df_with_sr.iloc[i]['sr_data']
            if sr_data and sr_data != 'None':
                try:
                    latest_sr = json.loads(sr_data)
                    break
                except:
                    continue
        
        if not latest_sr or not latest_sr.get('all_zones'):
            print(f"⚠️ {symbol} No valid S/R data available")
            print(f"💡 Try increasing candle count (e.g., -c 200) for better S/R detection")
            print(f"💡 Current: {len(df_with_sr)} candles, Recommended: 150+ candles")
            return
        
        zones = latest_sr['all_zones']
        current_price = latest_sr['current_price']
        
        # 绘制S/R区域和水平线
        x_min = df_with_sr.index[0]
        x_max = df_with_sr.index[-1]
        
        colors = {
            'Support': '#00FF7F',      # SpringGreen
            'Resistance': '#FF4500',   # OrangeRed
            'Mixed': '#FFD700',        # Gold
            'Pivot': '#1E90FF'         # DodgerBlue
        }
        
        for i, zone in enumerate(zones[:8]):  # 只显示前8个重要区域
            level = zone['level']
            zone_type = zone['type']
            confluence = zone['confluence']
            
            color = colors.get(zone_type, '#888888')
            alpha = min(0.3 + confluence * 0.1, 0.9)  # 汇聚度越高越不透明
            
            # 绘制水平线 - 更粗更明显
            ax.axhline(y=level, color=color, alpha=alpha, 
                      linewidth=2 + confluence * 0.5, linestyle='-', zorder=3)
            
            # 添加标签 - 改进字体和位置
            label_text = f"{zone_type[:3]} ${level:,.0f} ({confluence})"
            ax.text(x_max, level, f"  {label_text}", 
                   color=color, fontsize=9, alpha=0.95, weight='bold',
                   verticalalignment='center', 
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='black', 
                            edgecolor=color, alpha=0.8, linewidth=1))
        
        # 标记当前价格 - 更明显的样式
        ax.axhline(y=current_price, color='white', alpha=0.9, 
                  linewidth=3, linestyle='--', label=f'Current Price: ${current_price:,.2f}',
                  zorder=4)
    
    def plot_pine_style_chart_with_sr(self, df, df_with_sr, symbol, timeframe, candles):
        """
        Pine Script风格图表 + 支撑阻力位线条
        基于analyze_mtf_ema.py的plot_candlestick_with_ema_gradient函数
        """
        from matplotlib.patches import Rectangle
        
        # 取最近指定数量的K线
        if len(df) > candles:
            df_plot = df.tail(candles).copy()
        else:
            df_plot = df.copy()
        
        print(f"📊 绘制Pine Script风格图表: {len(df_plot)} 根{timeframe}K线")
        
        # 计算EMA和趋势状态
        ema_periods = [20, 30, 40, 50, 60]
        emas = {}
        ema_trends = {}
        
        for period in ema_periods:
            ema = df_plot['close'].ewm(span=period, adjust=False).mean()
            emas[period] = ema
            # Pine Script趋势逻辑: current_ema > ema[2] (当前EMA > 2周期前EMA)
            ema_trends[period] = ema > ema.shift(2)
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figsize, 
                                      gridspec_kw={'height_ratios': [3, 1]})
        
        # === 绘制K线图 ===
        def draw_candlestick(ax, df_data, bar_width=0.6):
            """绘制专业K线图"""
            for idx, (timestamp, candle) in enumerate(df_data.iterrows()):
                o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
                
                # K线颜色判断
                is_bullish = c >= o
                candle_color = '#26a69a' if is_bullish else '#ef5350'  # 绿涨红跌
                
                # 绘制上下影线
                ax.plot([idx, idx], [l, h], color=candle_color, linewidth=1.2, alpha=0.9, zorder=5)
                
                # 绘制K线实体
                body_height = abs(c - o)
                body_bottom = min(o, c)
                
                if body_height > 0:
                    # 有实体的K线
                    rect = Rectangle((idx - bar_width/2, body_bottom), bar_width, body_height,
                                   facecolor=candle_color, edgecolor=candle_color, 
                                   alpha=0.8, linewidth=0.5, zorder=5)
                    ax.add_patch(rect)
                else:
                    # 十字星 (开盘价=收盘价)
                    ax.plot([idx - bar_width/2, idx + bar_width/2], [c, c], 
                           color=candle_color, linewidth=2.5, alpha=0.9, zorder=5)
        
        # 绘制K线
        draw_candlestick(ax1, df_plot)
        
        # === Pine Script风格的EMA线条和渐变 ===
        
        # 颜色定义 (完全仿照Pine Script)
        bullish_color = '#00ff00'  # col_1 = color.lime (看涨绿)  
        bearish_color = '#800080'  # col_2 = color.purple (看跌紫)
        
        # EMA透明度层级 (对应Pine Script中的不同透明度)
        ema_alphas = [0.85, 0.70, 0.55, 0.40, 0.6]  # EMA20到EMA60递减透明度
        
        # 绘制EMA线条 (颜色基于当前趋势状态)
        for i, period in enumerate(ema_periods):
            # 当前EMA趋势决定线条颜色
            current_trend = ema_trends[period].iloc[-1] if len(ema_trends[period]) > 0 else True
            line_color = bullish_color if current_trend else bearish_color
            
            # 绘制EMA线
            ax1.plot(range(len(df_plot)), emas[period], 
                    color=line_color, linewidth=1.5, alpha=ema_alphas[i],
                    label=f'EMA{period} {"↗" if current_trend else "↘"}',
                    zorder=3)
        
        # === Pine Script风格的渐变填充区域 ===
        fill_alphas = [0.08, 0.06, 0.04, 0.02]  # 填充透明度递减，降低干扰
        
        for i in range(len(ema_periods) - 1):
            period1 = ema_periods[i]
            period2 = ema_periods[i + 1]
            
            # 两个EMA的综合趋势决定填充颜色
            trend1 = ema_trends[period1].iloc[-1] if len(ema_trends[period1]) > 0 else True
            trend2 = ema_trends[period2].iloc[-1] if len(ema_trends[period2]) > 0 else True
            combined_bullish = (trend1 and trend2) or ((trend1 or trend2) and (trend1 + trend2) > 0.5)
            
            fill_color = bullish_color if combined_bullish else bearish_color
            
            # 渐变填充
            ax1.fill_between(range(len(df_plot)), emas[period1], emas[period2],
                           color=fill_color, alpha=fill_alphas[i], 
                           zorder=1)  # 填充在最底层
        
        # === 添加支撑阻力位线条 (你最喜欢的部分) ===
        self.plot_sr_levels_pine_style(ax1, df_with_sr, df_plot, symbol)
        
        # === 图表美化和信息展示 ===
        
        # X轴时间标签
        step = max(1, len(df_plot) // 15)  # 显示约15个时间标签
        tick_positions = range(0, len(df_plot), step)
        tick_labels = [df_plot.index[i].strftime('%m-%d %H:%M') for i in tick_positions]
        ax1.set_xticks(tick_positions)
        ax1.set_xticklabels(tick_labels, rotation=45, ha='right')
        
        # 主图标签
        ax1.set_title(f'{symbol}/USDT Pine Script Style + Smart S/R ({timeframe}, {candles} candles)', 
                     fontsize=16, fontweight='bold', color='white')
        ax1.set_ylabel('Price (USD)', fontsize=13, fontweight='bold', color='white')
        ax1.grid(True, alpha=0.3, linewidth=0.5)
        ax1.legend(loc='upper left', fontsize=9, frameon=True, fancybox=True, 
                  shadow=True, framealpha=0.9)
        
        # 将Price Y轴移到右侧 (TradingView风格)
        ax1.yaxis.tick_right()
        ax1.yaxis.set_label_position("right")
        
        # === Volume子图 ===
        volume_colors = ['#26a69a' if df_plot['close'].iloc[i] > df_plot['open'].iloc[i] 
                        else '#ef5350' for i in range(len(df_plot))]
        ax2.bar(range(len(df_plot)), df_plot['volume'], color=volume_colors, alpha=0.6, width=0.8)
        ax2.set_ylabel('Volume', fontsize=12, color='white')
        ax2.grid(True, alpha=0.3)
        
        # 将Volume Y轴也移到右侧 (TradingView风格)
        ax2.yaxis.tick_right()
        ax2.yaxis.set_label_position("right")
        
        # 格式化两个子图的x轴
        for ax in [ax1, ax2]:
            ax.set_facecolor('black')
            for spine in ax.spines.values():
                spine.set_color('white')
            ax.tick_params(colors='white')
        
        return fig, ax1, ax2

    def plot_sr_levels_pine_style(self, ax, df_with_sr, df_plot, symbol):
        """TradingView风格的支撑阻力位线段绘制"""
        import json
        
        # 获取最新的S/R数据
        latest_sr = None
        for i in range(len(df_with_sr)-1, -1, -1):
            sr_data = df_with_sr.iloc[i]['sr_data']
            if sr_data and sr_data != 'None':
                try:
                    latest_sr = json.loads(sr_data)
                    break
                except:
                    continue
        
        if not latest_sr or not latest_sr.get('all_zones'):
            print(f"⚠️ {symbol} No valid S/R data available")
            print(f"💡 Try increasing candle count (e.g., -c 200) for better S/R detection")
            print(f"💡 Current: {len(df_plot)} candles, Recommended: 150+ candles")
            return
        
        zones = latest_sr['all_zones']
        current_price = latest_sr['current_price']
        
        # S/R线条颜色 (TradingView风格)
        colors = {
            'Support': '#00C851',      # TradingView绿色
            'Resistance': '#FF4444',   # TradingView红色  
            'Mixed': '#FF8800',        # TradingView橙色
            'Pivot': '#33B5E5'         # TradingView蓝色
        }
        
        # 图表宽度
        chart_width = len(df_plot)
        
        for i, zone in enumerate(zones[:8]):  # 只显示前8个重要区域
            level = zone['level']
            zone_type = zone['type']
            confluence = zone['confluence']
            
            color = colors.get(zone_type, '#888888')
            alpha = min(0.7 + confluence * 0.1, 0.95)  # 汇聚度越高越不透明
            
            # TradingView风格线段绘制 - 不横跨整个图表
            # 线段从图表的70%位置开始，到95%位置结束
            line_start = int(chart_width * 0.7)
            line_end = int(chart_width * 0.95)
            
            # 绘制线段 (不是完整的水平线)
            ax.plot([line_start, line_end], [level, level], 
                   color=color, alpha=alpha, 
                   linewidth=2.5 + confluence * 0.5, linestyle='-', zorder=6)
            
            # TradingView风格标签框
            # 确定时间框架信息 (模拟TradingView的显示格式)
            timeframe_info = self.get_zone_timeframe_info(zone, confluence)
            label_text = f"{level:,.2f} | {timeframe_info}"
            
            # 标签框位置 (在线段右端)
            label_x = line_end + (chart_width * 0.01)
            
            # 创建TradingView风格的标签框
            bbox_props = dict(
                boxstyle="round,pad=0.3",
                facecolor='#2A2A2A',  # TradingView深灰背景
                edgecolor=color,
                alpha=0.9,
                linewidth=1.5
            )
            
            ax.text(label_x, level, f" {label_text} ", 
                   color='white',  # 白色文字
                   fontsize=9, 
                   weight='bold',
                   verticalalignment='center',
                   horizontalalignment='left',
                   bbox=bbox_props,
                   zorder=8)
            
            # 添加小的扩展线段到标签 (连接线段和标签)
            ax.plot([line_end, label_x], [level, level], 
                   color=color, alpha=alpha*0.7, 
                   linewidth=1, linestyle='-', zorder=6)
        
        # 当前价格线 - 无限长横跨整个图表 (TradingView风格)
        ax.axhline(y=current_price, color='white', alpha=0.9, 
                  linewidth=1.5, linestyle='--', zorder=7)
        
        # 当前价格标签 - 显示在图表右边
        current_label_x = chart_width + (chart_width * 0.02)  # 图表右边位置
        current_bbox = dict(
            boxstyle="round,pad=0.3",
            facecolor='#1E1E1E',  
            edgecolor='white',
            alpha=0.9,
            linewidth=1
        )
        
        ax.text(current_label_x, current_price, f" ${current_price:,.2f} ", 
               color='white',
               fontsize=10, 
               weight='bold',
               verticalalignment='center',
               horizontalalignment='left',
               bbox=current_bbox,
               zorder=8)

    def get_zone_timeframe_info(self, zone, confluence):
        """生成TradingView风格的时间框架信息"""
        # 模拟TradingView的时间框架显示
        # 根据汇聚度显示不同的时间框架组合
        timeframe_map = {
            2: "15m (2 SW)",
            3: "15m (3 SW), 1h (3 SW)", 
            4: "30m (3 SW), 1h (3 SW)",
            5: "15m (3 SW), 30m (3 SW), 1h (3 SW)",
            6: "15m (3 SW), 30m (4 SW), 1h (3 SW)"
        }
        
        return timeframe_map.get(confluence, f"Multi-TF ({confluence} SW)")

    def plot_simple_ema(self, ax, df):
        """绘制简单清洁的EMA线条，无背景干扰"""
        try:
            import talib
            
            # 计算不同周期的EMA
            ema20 = talib.EMA(df['close'].values, timeperiod=20)
            ema50 = talib.EMA(df['close'].values, timeperiod=50) 
            ema200 = talib.EMA(df['close'].values, timeperiod=200)
            
            # 绘制EMA线条 - 清洁无背景
            ax.plot(df.index, ema20, color='#FFD700', alpha=0.8, 
                   linewidth=1.5, label='EMA20', linestyle='-', zorder=2)
            ax.plot(df.index, ema50, color='#1E90FF', alpha=0.8, 
                   linewidth=1.5, label='EMA50', linestyle='-', zorder=2)
            ax.plot(df.index, ema200, color='#FF69B4', alpha=0.8, 
                   linewidth=1.5, label='EMA200', linestyle='-', zorder=2)
                   
        except Exception as e:
            print(f"⚠️ EMA calculation error: {e}")
            pass

    def plot_mtf_ema(self, ax, df, symbol):
        """绘制MTF EMA趋势 - 简化版本避免背景干扰"""
        try:
            # 使用简单的EMA计算，避免复杂的MTF分析器
            import talib
            
            # 计算不同周期的EMA
            ema20 = talib.EMA(df['close'].values, timeperiod=20)
            ema50 = talib.EMA(df['close'].values, timeperiod=50) 
            ema200 = talib.EMA(df['close'].values, timeperiod=200)
            
            # 绘制EMA线条
            ax.plot(df.index, ema20, color='#FFD700', alpha=0.9, 
                   linewidth=2, label='EMA20', linestyle='-', zorder=3)
            ax.plot(df.index, ema50, color='#1E90FF', alpha=0.9, 
                   linewidth=2, label='EMA50', linestyle='-', zorder=3)
            ax.plot(df.index, ema200, color='#FF69B4', alpha=0.9, 
                   linewidth=2, label='EMA200', linestyle='-', zorder=3)
                   
        except Exception as e:
            print(f"⚠️ {symbol} EMA calculation error: {e}")
            pass
    
    def generate_chart(self, symbol: str = "ETH", timeframe: str = "15m", candles: int = 200, save_path: str = None):
        """Generate comprehensive technical analysis chart"""
        print(f"\n🎯 Generating {symbol} technical analysis chart...")
        
        try:
            # Load data
            df = self.load_data(symbol, timeframe, candles)
            
            # Calculate Smart MTF S/R indicators
            print("Computing Smart MTF S/R indicators...")
            
            df_with_sr = compute_smart_mtf_sr(
                df,
                timeframes=["15", "60", "240"],  # 固定时间框架：15min, 1h, 4h
                show_swings=True,  # Pine script default
                show_pivots=False,  # Pine script default
                show_fibonacci=False,  # Pine script default
                show_order_blocks=False,  # Pine script default
                show_volume_profile=False,  # Pine script default
                show_psychological_levels=True,  # Crypto feature
                show_within_percent=2.5,  # As requested
                cluster_percent=0.25,  # As requested
                top_n=8,  # Pine script default
                alert_confluence=4,  # As requested
                min_confluence=2
            )
            
            # Create Pine Script style chart with S/R levels
            print("Drawing Pine Script style chart with S/R levels...")
            fig, ax1, ax2 = self.plot_pine_style_chart_with_sr(df, df_with_sr, symbol, timeframe, candles)
            
            # Chart is already formatted in Pine style function
            plt.tight_layout()
            
            # Save chart
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{symbol.lower()}_technical_analysis_{timeframe}_{candles}c_{timestamp}.png"
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight', 
                       facecolor='black', edgecolor='none')
            plt.close()
            
            print(f"✅ Chart saved: {save_path}")
            
            # Generate analysis summary
            self.generate_analysis_summary(df_with_sr, symbol)
            
            return save_path
            
        except Exception as e:
            print(f"❌ Error generating {symbol} chart: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_chart_from_dataframe(self, df: pd.DataFrame, symbol: str, timeframe: str, 
                                     filename: str = None, include_sr_analysis: bool = False,
                                     sr_analysis: dict = None, utbot_data: dict = None,
                                     return_buffer: bool = False, candles: int = None):
        """从DataFrame生成图表 - 为WebSocket架构设计
        
        Args:
            df: 价格数据DataFrame
            symbol: 交易对符号
            timeframe: 时间框架
            filename: 保存文件名（可选）
            include_sr_analysis: 是否包含S/R分析
            sr_analysis: S/R分析数据
            utbot_data: UTBot数据
            return_buffer: 是否返回图像缓冲区而不是保存文件
            candles: 要显示的K线数量（如果为None，使用全部数据）
        
        Returns:
            filename (if return_buffer=False) or BytesIO buffer (if return_buffer=True)
        """
        print(f"\n🎯 从DataFrame生成 {symbol} 技术分析图表...")
        
        try:
            # 确保有足够的数据
            if len(df) < 50:
                print("❌ 数据量不足，无法生成图表")
                return None
            
            # 如果指定了candles参数，限制数据长度
            df_for_chart = df.copy()
            if candles is not None and candles > 0:
                if len(df_for_chart) > candles:
                    df_for_chart = df_for_chart.tail(candles).copy()
                    print(f"📊 限制显示最近 {candles} 根K线，实际使用 {len(df_for_chart)} 根")
                else:
                    print(f"📊 请求 {candles} 根K线，实际数据 {len(df_for_chart)} 根")
            else:
                print(f"📊 使用全部数据: {len(df_for_chart)} 根K线")
            
            # 专门为图表生成临时计算S/R数据（不保存到文件）
            print(f"📊 为图表生成临时计算S/R数据: {symbol} {timeframe}")
            
            try:
                # 直接调用S/R计算函数，但不保存结果，只用于图表生成
                from indicators.smart_mtf_sr import compute_smart_mtf_sr
                
                # 根据当前时间框架动态调整S/R计算的时间框架
                if timeframe.endswith('m'):
                    base_tf = int(timeframe[:-1])
                    if base_tf <= 5:
                        # 5分钟及以下：使用5m, 15m, 60m
                        timeframes = ["5", "15", "60"]
                    elif base_tf <= 15:
                        # 15分钟：使用15m, 60m, 240m
                        timeframes = ["15", "60", "240"]
                    else:
                        # 更高时间框架：使用当前框架的倍数
                        timeframes = [str(base_tf), str(base_tf*4), str(base_tf*16)]
                else:
                    # 默认时间框架
                    timeframes = ["15", "60", "240"]
                
                print(f"� 使用时间框架进行S/R计算: {timeframes}")
                
                # 临时计算S/R数据（不保存到文件，只用于图表生成）
                df_with_sr = compute_smart_mtf_sr(
                    df_for_chart,
                    timeframes=timeframes,
                    show_swings=True,
                    show_pivots=False,
                    show_fibonacci=False,
                    show_order_blocks=False,
                    show_volume_profile=False,
                    show_psychological_levels=True,
                    show_within_percent=2.5,
                    cluster_percent=0.25,
                    top_n=8,
                    alert_confluence=4,
                    min_confluence=2
                )
                
                # 使用临时计算的S/R数据
                df_for_chart = df_with_sr
                print(f"✅ S/R数据临时计算完成: {len(df_for_chart)}条数据")
                
                # 检查是否生成了有效的S/R数据
                has_sr_data = False
                for i in range(len(df_with_sr)-1, -1, -1):
                    sr_data = df_with_sr.iloc[i]['sr_data']
                    if sr_data and sr_data != 'None':
                        try:
                            sr_json = json.loads(sr_data)
                            if sr_json.get('zones'):
                                has_sr_data = True
                                print(f"✅ 找到S/R区域: {len(sr_json['zones'])}个")
                                break
                        except:
                            continue
                
                if not has_sr_data:
                    print("⚠️ 临时S/R计算未生成有效区域，继续使用计算结果")
                
            except Exception as e:
                print(f"⚠️ S/R临时计算失败: {e}")
                # 如果临时计算失败，继续使用原始数据
            
            # 创建图表 - 使用临时计算的S/R数据
            display_candles = candles if candles is not None else len(df_for_chart)
            fig, ax1, ax2 = self.plot_pine_style_chart_with_sr(df_for_chart, df_for_chart, symbol, timeframe, display_candles)
            
            # 如果有UTBot数据，添加信号标记
            if utbot_data is not None and not utbot_data.empty:
                self.add_utbot_signals(ax1, df_for_chart, utbot_data)
            
            plt.tight_layout()
            
            if return_buffer:
                # 返回图像缓冲区
                from io import BytesIO
                buffer = BytesIO()
                plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight', 
                           facecolor='black', edgecolor='none')
                plt.close()
                buffer.seek(0)
                print(f"✅ 图表已生成到缓冲区")
                return buffer
            else:
                # 保存到文件
                if not filename:
                    filename = f"{symbol.lower()}_chart_{timeframe}.png"
                plt.savefig(filename, dpi=300, bbox_inches='tight', 
                           facecolor='black', edgecolor='none')
                plt.close()
                print(f"✅ 图表已保存: {filename}")
                return filename
            
        except Exception as e:
            print(f"❌ 从DataFrame生成图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        except Exception as e:
            print(f"❌ 从DataFrame生成图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def add_utbot_signals(self, ax, df, utbot_data):
        """在图表上添加UTBot信号标记"""
        try:
            # 添加买信号
            for signal in utbot_data.get('buy_signals', []):
                idx = signal.get('index')
                if idx is not None and idx < len(df):
                    ax.scatter(df.index[idx], signal['price'], 
                             color='lime', marker='^', s=100, 
                             zorder=10, label='UTBot BUY' if signal == utbot_data['buy_signals'][0] else "")
            
            # 添加卖信号
            for signal in utbot_data.get('sell_signals', []):
                idx = signal.get('index')
                if idx is not None and idx < len(df):
                    ax.scatter(df.index[idx], signal['price'], 
                             color='red', marker='v', s=100, 
                             zorder=10, label='UTBot SELL' if signal == utbot_data['sell_signals'][0] else "")
            
            # 添加止损线
            stop_levels = utbot_data.get('stop_levels', [])
            if stop_levels:
                valid_stops = [s for s in stop_levels if not np.isnan(s)]
                if valid_stops:
                    ax.plot(df.index[-len(valid_stops):], valid_stops, 
                           color='orange', linewidth=1, alpha=0.7, 
                           label='UTBot Stop', linestyle='--')
                           
        except Exception as e:
            print(f"⚠️ 添加UTBot信号时出错: {e}")
    
    def generate_analysis_summary(self, df_with_sr, symbol):
        """Generate analysis summary"""
        print(f"\n📊 {symbol} Technical Analysis Summary:")
        print("="*50)
        
        # 获取最新的S/R分析
        for i in range(len(df_with_sr)-1, -1, -1):
            sr_data = df_with_sr.iloc[i]['sr_data']
            if sr_data and sr_data != 'None':
                analysis = analyze_sr_data(sr_data)
                if analysis['status'] == 'success':
                    current_price = analysis['current_price']
                    print(f"Current Price: ${current_price:,.2f}")
                    print(f"Total S/R Zones: {analysis['total_zones']}")
                    print(f"Support Zones: {analysis['support_zones_count']}")
                    print(f"Resistance Zones: {analysis['resistance_zones_count']}")
                    
                    if analysis['nearest_support']:
                        support = analysis['nearest_support']
                        distance = analysis.get('support_distance_pct', 0)
                        print(f"Nearest Support: ${support['level']:,.2f} (Distance: {distance:.2f}%, Confluence: {support['confluence']})")
                    
                    if analysis['nearest_resistance']:
                        resistance = analysis['nearest_resistance']
                        distance = analysis.get('resistance_distance_pct', 0)
                        print(f"Nearest Resistance: ${resistance['level']:,.2f} (Distance: {distance:.2f}%, Confluence: {resistance['confluence']})")
                    
                    break
    
    def generate_multiple_charts(self, symbols: list = ["BTC", "ETH", "SOL"], timeframe: str = "15m", candles: int = 200):
        """Generate charts for multiple symbols"""
        print(f"\n🚀 Starting multi-symbol technical analysis chart generation...")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Timeframe: {timeframe}, Candles: {candles}")
        print("="*60)
        
        generated_files = []
        
        for symbol in symbols:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{symbol.lower()}_technical_analysis_{timeframe}_{candles}c_{timestamp}.png"
                
                result = self.generate_chart(symbol, timeframe, candles, filename)
                if result:
                    generated_files.append(result)
                    
                print()  # Empty line separator
                
            except Exception as e:
                print(f"❌ Failed to generate {symbol} chart: {e}")
                continue
        
        print("="*60)
        print(f"✅ Chart generation completed! Generated {len(generated_files)} files:")
        for file in generated_files:
            print(f"  📄 {file}")
        
        return generated_files


def main():
    """Main function"""
    print("🎨 Technical Analysis Chart Generator")
    print("Combining Smart MTF S/R and MTF EMA indicators")
    print("="*50)
    
    import argparse
    parser = argparse.ArgumentParser(description='Generate technical analysis charts')
    parser.add_argument('--symbol', '-s', type=str, help='Specify single symbol (e.g. BTC, ETH, SOL)')
    parser.add_argument('--timeframe', '-t', type=str, default='15m', 
                       help='Timeframe (e.g. 5m, 15m, 1h, 4h, 1d, default: 15m)')
    parser.add_argument('--candles', '-c', type=int, default=200, 
                       help='Number of candles to analyze (default: 200)')
    parser.add_argument('--days', '-d', type=int, help='Deprecated: Use --timeframe and --candles instead')
    parser.add_argument('--all', '-a', action='store_true', help='Generate all default symbol charts')
    
    args = parser.parse_args()
    
    # Backward compatibility warning
    if args.days:
        print("⚠️  --days parameter is deprecated. Using --timeframe and --candles instead.")
        print(f"   Converting {args.days} days to approximately {args.days * 96} candles on 15m timeframe")
        args.candles = args.days * 96  # Roughly 96 15m candles per day
    
    # Create chart generator
    chart_generator = TechnicalAnalysisChart(figsize=(20, 12))
    
    if args.symbol:
        # Generate single symbol chart
        print(f"Generating {args.symbol.upper()} technical analysis chart...")
        print(f"Timeframe: {args.timeframe}, Candles: {args.candles}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{args.symbol.lower()}_technical_analysis_{args.timeframe}_{args.candles}c_{timestamp}.png"
        
        result = chart_generator.generate_chart(args.symbol.upper(), args.timeframe, args.candles, filename)
        if result:
            print(f"\n🎉 Chart saved: {result}")
        else:
            print("\n❌ Chart generation failed")
    
    elif args.all or True:  # Default behavior
        # Generate multi-symbol charts
        symbols = ["BTC", "ETH", "SOL"]
        generated_files = chart_generator.generate_multiple_charts(symbols, timeframe=args.timeframe, candles=args.candles)
        
        if generated_files:
            print(f"\n🎉 Successfully generated {len(generated_files)} technical analysis charts!")
        else:
            print("❌ Failed to generate any charts, please check data and configuration")
    
    print("\n💡 Chart Elements:")
    print("- Green Candles: Price up")
    print("- Red Candles: Price down") 
    print("- Colored Horizontal Lines: S/R levels (numbers show confluence)")
    print("- Colored EMA Lines: Moving averages")
    print("- Background Colors: Trend indication")
    print("- White Dashed Line: Current price")
    
    print("\n🚀 Usage Examples:")
    print("  python generate_charts.py                           # Generate all symbols, 15m, 200 candles")
    print("  python generate_charts.py -s BTC                    # Generate BTC chart, 15m, 200 candles")
    print("  python generate_charts.py -s ETH -t 1h -c 100       # Generate ETH chart, 1h timeframe, 100 candles")
    print("  python generate_charts.py -t 4h -c 50               # Generate all symbols, 4h timeframe, 50 candles")
    print("  python generate_charts.py -s SOL -t 5m -c 500       # Generate SOL chart, 5m timeframe, 500 candles")


if __name__ == "__main__":
    main()
