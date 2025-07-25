#!/usr/bin/env python3
"""
MTF EMA趋势分析 - 带K线图和Pine Script风格渐变
改进版：
1. K线图替代收盘价线图
2. 去掉matrix热图，只保留图表
3. 渐变区域：看涨绿色，看跌紫色 (Pine Script风格)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 服务器环境友好的后端
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 导入MTF EMA趋势指标
from indicators.mtf_ema_trend import MTFEMATrend


def load_okx_data(symbol: str = "ETH", timeframe: str = "5m") -> pd.DataFrame:
    """
    加载OKX数据
    
    Args:
        symbol: 交易对符号 (BTC, ETH, SOL, DOGE)
        timeframe: 时间周期 (3m, 5m, 15m)
        
    Returns:
        OHLCV数据DataFrame
    """
    symbol = symbol.upper()
    data_path = f"okx/data_raw/{symbol}/{symbol.lower()}_{timeframe}_latest.csv"
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"找不到数据文件: {data_path}\n请先运行 main.py 来同步数据")
    
    # 读取CSV数据
    df = pd.read_csv(data_path)
    
    # 处理时间和列
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    
    # 只保留OHLCV列
    ohlcv_cols = ['open', 'high', 'low', 'close']
    if 'volume' in df.columns:
        ohlcv_cols.append('volume')
    df = df[ohlcv_cols]
    
    # 排序确保时间顺序
    df = df.sort_index()
    
    print(f"✅ 成功加载 {symbol} {timeframe} 数据")
    print(f"📅 数据时间范围: {df.index[0]} 至 {df.index[-1]}")
    print(f"📊 数据量: {len(df)} 条{timeframe}K线")
    print(f"💰 最新价格: ${df['close'].iloc[-1]:.4f}")
    
    return df


def plot_candlestick_with_ema_gradient(df: pd.DataFrame, symbol: str, timeframe: str = "5m", candle_count: int = 50):
    """
    绘制K线图 + EMA线条 + Pine Script风格渐变填充
    改进点：
    1. K线图替代简单的收盘价线图
    2. 基于EMA趋势的动态颜色 (绿色看涨/紫色看跌)
    3. 渐变填充区域体现Pine Script的视觉效果
    
    Args:
        df: OHLCV数据
        symbol: 交易对符号
        timeframe: 时间周期 (3m, 5m, 15m)
        candle_count: 绘制K线数量，默认50根
    """
    
    # 取最近指定数量的K线
    if len(df) > candle_count:
        df_plot = df.tail(candle_count).copy()
    else:
        df_plot = df.copy()
    
    print(f"📊 绘制最近 {len(df_plot)} 根{timeframe}K线")
    
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
    fig, ax = plt.subplots(figsize=(18, 12))
    fig.suptitle(f'{symbol.upper()} - {timeframe.upper()} Candlestick Chart + MTF EMA Analysis (Pine Script Style)', 
                fontsize=16, fontweight='bold')
    
    # === 绘制K线图 ===
    def draw_candlestick(ax, df_data, bar_width=0.6):
        """绘制专业K线图"""
        for idx, (timestamp, candle) in enumerate(df_data.iterrows()):
            o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
            
            # K线颜色判断
            is_bullish = c >= o
            candle_color = '#26a69a' if is_bullish else '#ef5350'  # 绿涨红跌
            
            # 绘制上下影线
            ax.plot([idx, idx], [l, h], color=candle_color, linewidth=1.2, alpha=0.9)
            
            # 绘制K线实体
            body_height = abs(c - o)
            body_bottom = min(o, c)
            
            if body_height > 0:
                # 有实体的K线
                rect = Rectangle((idx - bar_width/2, body_bottom), bar_width, body_height,
                               facecolor=candle_color, edgecolor=candle_color, 
                               alpha=0.8, linewidth=0.5)
                ax.add_patch(rect)
            else:
                # 十字星 (开盘价=收盘价)
                ax.plot([idx - bar_width/2, idx + bar_width/2], [c, c], 
                       color=candle_color, linewidth=2.5, alpha=0.9)
    
    # 绘制K线
    draw_candlestick(ax, df_plot)
    
    # === Pine Script风格的EMA线条和渐变 ===
    
    # 颜色定义 (完全仿照Pine Script)
    bullish_color = '#00ff00'  # col_1 = color.lime (看涨绿)  
    bearish_color = '#800080'  # col_2 = color.purple (看跌紫)
    
    # EMA透明度层级 (对应Pine Script中的不同透明度)
    ema_alphas = [0.85, 0.70, 0.55, 0.40, 1.0]  # EMA20到EMA60递减透明度
    
    # 绘制EMA线条 (颜色基于当前趋势状态)
    ema_lines = []
    for i, period in enumerate(ema_periods):
        # 当前EMA趋势决定线条颜色
        current_trend = ema_trends[period].iloc[-1] if len(ema_trends[period]) > 0 else True
        line_color = bullish_color if current_trend else bearish_color
        
        # 绘制EMA线
        line = ax.plot(range(len(df_plot)), emas[period], 
                      color=line_color, linewidth=2.5, alpha=ema_alphas[i],
                      label=f'EMA{period} {"↗" if current_trend else "↘"}',
                      zorder=10)  # 确保EMA线在K线之上
        ema_lines.append(line[0])
    
    # === Pine Script风格的渐变填充区域 ===
    fill_alphas = [0.12, 0.10, 0.08, 0.06]  # 填充透明度递减
    
    for i in range(len(ema_periods) - 1):
        period1 = ema_periods[i]
        period2 = ema_periods[i + 1]
        
        # 两个EMA的综合趋势决定填充颜色
        trend1 = ema_trends[period1].iloc[-1] if len(ema_trends[period1]) > 0 else True
        trend2 = ema_trends[period2].iloc[-1] if len(ema_trends[period2]) > 0 else True
        combined_bullish = (trend1 and trend2) or ((trend1 or trend2) and (trend1 + trend2) > 0.5)
        
        fill_color = bullish_color if combined_bullish else bearish_color
        
        # 渐变填充
        ax.fill_between(range(len(df_plot)), emas[period1], emas[period2],
                       color=fill_color, alpha=fill_alphas[i], 
                       zorder=1)  # 填充在最底层，不添加到图例
    
    # === 图表美化和信息展示 ===
    
    # X轴时间标签
    step = max(1, len(df_plot) // 15)  # 显示约15个时间标签
    tick_positions = range(0, len(df_plot), step)
    tick_labels = [df_plot.index[i].strftime('%m-%d %H:%M') for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha='right')
    
    # 标签和网格
    ax.set_ylabel('Price (USD)', fontsize=13, fontweight='bold')
    ax.set_xlabel('Time', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, linewidth=0.5)
    
    # 价格轴移到右侧
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    
    # 图例 - 放在右上角避免重叠
    ax.legend(loc='upper right', bbox_to_anchor=(0.99, 0.99), fontsize=10, 
             frameon=True, fancybox=True, shadow=True, framealpha=0.95,
             ncol=1, borderpad=0.5, columnspacing=0.5)
    
    # === MTF分析信息框 ===
    
    # 运行MTF分析
    mtf_analyzer = MTFEMATrend(
        timeframes=["60", "120", "180", "240", "300"],  # 1h, 2h, 3h, 4h, 5h
        ema_periods=ema_periods,
        base_timeframe=timeframe.replace("m", "")  # 动态设置基础时间框架
    )
    mtf_analyzer.update_data(df_plot, timeframe.replace("m", ""))
    
    # 获取分析结果
    strength = mtf_analyzer.get_trend_strength_score()
    consensus_cn = mtf_analyzer.get_trend_consensus()
    
    # 翻译共识到英文
    consensus_translation = {
        "强烈看涨": "Strong Bullish",
        "看涨": "Bullish", 
        "轻微看涨": "Weak Bullish",
        "中性": "Neutral",
        "轻微看跌": "Weak Bearish", 
        "看跌": "Bearish",
        "强烈看跌": "Strong Bearish"
    }
    consensus = consensus_translation.get(consensus_cn, consensus_cn)
    
    latest_price = df_plot['close'].iloc[-1]
    
    # 信息文本框
    info_text = f"""MTF Trend Analysis
━━━━━━━━━━━━━━━━
Timeframe: {timeframe.upper()}
Candles: {len(df_plot)}
Trend Strength: {strength:.1f}%
Market Consensus: {consensus}
━━━━━━━━━━━━━━━━
Latest Price: ${latest_price:.4f}
Data Time: {df_plot.index[-1].strftime('%m-%d %H:%M')}
Analysis Period: 1h-5h"""
    
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes, 
            verticalalignment='bottom', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                     edgecolor='gray', alpha=0.95, linewidth=1))
    
    plt.tight_layout()
    
    # 保存高质量图片
    filename = f"{symbol.lower()}_mtf_ema_{timeframe}_candlestick_pine.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight', 
               facecolor='white', edgecolor='none')
    print(f"📊 Pine Script Style Candlestick Chart Saved: {filename}")
    
    # 服务器环境友好的显示处理
    try:
        plt.show()
    except:
        print(f"ℹ️  Graphics interface unavailable, chart saved to file")
    finally:
        plt.close()  # 释放内存
    
    return mtf_analyzer


def analyze_mtf_ema(symbol: str, timeframe: str = "5m", candle_count: int = 50):
    """完整的MTF EMA趋势分析
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期 (3m, 5m, 15m)
        candle_count: 绘制K线数量
    """
    print(f"🔍 开始分析 {symbol} {timeframe} 的MTF EMA趋势...")
    print("=" * 70)
    
    try:
        # 加载数据
        df = load_okx_data(symbol, timeframe)
        
        # 创建MTF EMA分析器 (Pine Script配置)
        analyzer = MTFEMATrend(
            timeframes=["60", "120", "180", "240", "300"],  # 1h, 2h, 3h, 4h, 5h  
            ema_periods=[20, 30, 40, 50, 60],
            base_timeframe=timeframe.replace("m", "")  # 动态设置基础时间框架
        )
        
        # 分析数据
        analyzer.update_data(df, timeframe.replace("m", ""))
        analysis = analyzer.get_trend_summary()
        
        # === 显示分析结果 ===
        print(f"\n📊 {symbol} {timeframe} MTF EMA 趋势分析结果")
        print("=" * 70)
        
        # 基本信息
        latest_price = df['close'].iloc[-1]
        latest_time = df.index[-1]
        print(f"💰 当前价格: ${latest_price:.4f}")
        print(f"⏰ 最新时间: {latest_time}")
        print()
        
        # 趋势表格
        print(analyzer.format_trend_table())
        
        # 详细分析
        print(f"\n📈 趋势分析详情:")
        print(f"  📊 趋势强度得分: {analysis['strength_score']:.1f}%")
        print(f"  🎯 趋势共识: {analysis['consensus']}")
        
        # 交叉信号
        if analysis['trend_changes']['bullish_crossovers']:
            print(f"  🟢 看涨交叉: {', '.join(analysis['trend_changes']['bullish_crossovers'])}")
        if analysis['trend_changes']['bearish_crossovers']:
            print(f"  🔴 看跌交叉: {', '.join(analysis['trend_changes']['bearish_crossovers'])}")
        
        # === TradingView对比格式 ===
        print(f"\n🔄 {symbol} TradingView 对比验证")
        print("=" * 60)
        
        trends = analysis['trends']
        tf_display = ["1h", "2h", "3h", "4h", "5h"]
        tf_keys = ["60", "120", "180", "240", "300"]
        emas = [20, 30, 40, 50, 60]
        
        print("时间框架 | EMA20 | EMA30 | EMA40 | EMA50 | EMA60")
        print("-" * 55)
        
        for i, tf_key in enumerate(tf_keys):
            if tf_key in trends:
                row = f"{tf_display[i]:>6}   |"
                for ema in emas:
                    if ema in trends[tf_key]:
                        trend_symbol = " 🢁 " if trends[tf_key][ema] else " 🢃 "
                        row += f"{trend_symbol} |"
                    else:
                        row += "  ? |"
                print(row)
        
        # === 生成可视化图表 ===
        print(f"\n📊 生成Pine Script风格可视化图表...")
        plot_analyzer = plot_candlestick_with_ema_gradient(df, symbol, timeframe, candle_count)
        
        # === TradingView验证指南 ===
        print(f"\n💡 TradingView 验证步骤:")
        print(f"1. 打开: https://www.tradingview.com/")
        print(f"2. 搜索: OKX:{symbol}USDT")
        print(f"3. 设置5分钟图表")
        print(f"4. 添加EMA指标: 20, 30, 40, 50, 60")
        print(f"5. 切换时间框架: 1h → 2h → 3h → 4h → 5h")
        print(f"6. 对比趋势方向: 🢁上升 🢃下降")
        print(f"7. 当前使用: {timeframe} 基础时间框架")
        
        print(f"\n📝 Pine Script风格说明:")
        print(f"🢁 = EMA上升 (当前EMA > 2周期前EMA)")
        print(f"🢃 = EMA下降 (当前EMA < 2周期前EMA)")
        print(f"🟢 绿色渐变 = 看涨区域 (Pine Script col_1 = lime)")
        print(f"🟣 紫色渐变 = 看跌区域 (Pine Script col_2 = purple)")
        
        return analysis
        
    except FileNotFoundError as e:
        print(f"❌ 数据文件错误: {e}")
        print(f"\n🔧 解决方案:")
        print(f"1. 启动数据同步: python3 main.py")
        print(f"2. 等待数据同步完成")
        print(f"3. 重新运行: python3 examples/analyze_mtf_ema.py {symbol} {timeframe} {candle_count}")
        return None
        
    except Exception as e:
        print(f"❌ 分析错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_available_symbols():
    """检查可用数据"""
    print("🔍 检查数据文件可用性...")
    available = {}
    
    for symbol in ["BTC", "ETH", "SOL", "DOGE"]:
        available[symbol] = []
        for timeframe in ["3m", "5m", "15m"]:
            data_path = f"okx/data_raw/{symbol}/{symbol.lower()}_{timeframe}_latest.csv"
            if os.path.exists(data_path):
                size = os.path.getsize(data_path)
                if size > 1000:  # 至少1KB
                    available[symbol].append(timeframe)
                    print(f"  ✅ {symbol} {timeframe}: 可用 ({size/1024:.1f}KB)")
                else:
                    print(f"  ⚠️  {symbol} {timeframe}: 文件过小 ({size}B)")
            else:
                print(f"  ❌ {symbol} {timeframe}: 文件不存在")
    
    return available


def main():
    """主程序入口"""
    print("🚀 MTF EMA 趋势分析器 - Pine Script风格版")
    print("=" * 70)
    print("📊 改进功能:")
    print("   ✅ K线图替代收盘价线图")
    print("   ✅ 去除matrix热图，专注图表分析")  
    print("   ✅ Pine Script风格渐变 (绿色看涨/紫色看跌)")
    print("   ✅ 自定义时间周期 (3m/5m/15m)")
    print("   ✅ 自定义K线数量 (默认50根)")
    print("=" * 70)
    
    # 检查数据可用性
    available = check_available_symbols()
    
    # 扁平化检查是否有任何可用数据
    all_available = []
    for symbol, timeframes in available.items():
        if timeframes:
            all_available.append(symbol)
    
    if not all_available:
        print(f"\n❌ 无可用数据!")
        print(f"🔧 请先运行: python3 main.py")
        return
    
    print(f"\n📋 可用交易对: {all_available}")
    
    # 解析命令行参数
    symbol = "ETH"  # 默认值
    timeframe = "5m"  # 默认值
    candle_count = 50  # 默认值
    
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        if symbol not in all_available:
            print(f"⚠️  {symbol} 数据不可用，使用 {all_available[0]}")
            symbol = all_available[0]
    else:
        symbol = all_available[0]  # 默认第一个
    
    if len(sys.argv) > 2:
        timeframe = sys.argv[2].lower()
        if timeframe not in available.get(symbol, []):
            print(f"⚠️  {symbol} {timeframe} 数据不可用，使用可用的时间周期")
            # 优先使用5m，如果不可用则使用第一个可用的
            if "5m" in available.get(symbol, []):
                timeframe = "5m"
            elif available.get(symbol):
                timeframe = available[symbol][0]
            else:
                timeframe = "5m"
    else:
        # 优先使用默认的5m，如果不可用则使用该符号的第一个可用时间周期
        if "5m" in available.get(symbol, []):
            timeframe = "5m"
        elif available.get(symbol):
            timeframe = available[symbol][0]
        else:
            timeframe = "5m"
    
    if len(sys.argv) > 3:
        try:
            candle_count = int(sys.argv[3])
            if candle_count <= 0:
                candle_count = 50
        except ValueError:
            print(f"⚠️  无效的K线数量，使用默认值50")
            candle_count = 50
    
    print(f"\n🎯 分析参数:")
    print(f"   📈 交易对: {symbol}")
    print(f"   ⏰ 时间周期: {timeframe}")
    print(f"   📊 K线数量: {candle_count}")
    print(f"   📋 可用时间周期: {available.get(symbol, [])}")
    print("=" * 70)
    
    # 执行分析
    result = analyze_mtf_ema(symbol, timeframe, candle_count)
    
    if result:
        print(f"\n✅ 分析完成! ")
        print(f"📊 图表文件: {symbol.lower()}_mtf_ema_{timeframe}_candlestick_pine.png")
        print(f"🔗 可与TradingView进行对比验证")
        print(f"\n💡 使用方法:")
        print(f"   python3 examples/analyze_mtf_ema.py [交易对] [时间周期] [K线数量]")
        print(f"   示例: python3 examples/analyze_mtf_ema.py BTC 15m 100")
    else:
        print(f"\n❌ 分析失败")


if __name__ == "__main__":
    main()
