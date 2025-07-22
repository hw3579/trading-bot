#!/usr/bin/env python3
"""
MTF EMA趋势分析 - OKX真实数据示例
使用真实的OKX 5分钟数据进行MTF EMA分析，便于与TradingView对比
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 导入MTF EMA趋势指标
from indicators.mtf_ema_trend import MTFEMATrend, analyze_mtf_trend


class OKXMTFAnalyzer:
    """OKX真实数据的MTF EMA分析器"""
    
    def __init__(self):
        """初始化分析器"""
        # 使用与Pine Script相同的配置
        self.analyzer = MTFEMATrend(
            timeframes=["15m", "30m", "1h", "2h", "4h"],  # 从5m数据构建的时间框架
            ema_periods=[20, 30, 40, 50, 60]              # 与Pine Script相同的EMA周期
        )
    
    def load_okx_data(self, symbol: str = "ETH") -> pd.DataFrame:
        """
        加载OKX数据
        
        Args:
            symbol: 交易对符号 (BTC, ETH, SOL, DOGE)
            
        Returns:
            OHLCV数据DataFrame
        """
        symbol = symbol.upper()
        data_path = f"okx/data_raw/{symbol}/{symbol.lower()}_5m_latest.csv"
        
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"找不到数据文件: {data_path}")
        
        # 读取CSV数据
        df = pd.read_csv(data_path)
        
        # 转换datetime列为索引
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        
        # 排序确保时间顺序
        df = df.sort_index()
        
        print(f"✅ 成功加载 {symbol} 数据")
        print(f"📅 数据时间范围: {df.index[0]} 至 {df.index[-1]}")
        print(f"📊 数据量: {len(df)} 条5分钟K线")
        print(f"💰 最新价格: {df['close'].iloc[-1]:.2f}")
        
        return df
    
    def analyze_with_okx_data(self, symbol: str = "ETH") -> dict:
        """
        使用OKX数据进行MTF EMA分析
        
        Args:
            symbol: 交易对符号
            
        Returns:
            分析结果字典
        """
        print(f"🔍 开始分析 {symbol} 的MTF EMA趋势...")
        print("=" * 60)
        
        # 加载数据
        df = self.load_okx_data(symbol)
        
        # 进行MTF分析
        self.analyzer.update_data(df, "5m")  # 指定原始数据是5分钟
        
        # 获取分析结果
        analysis = self.analyzer.get_trend_summary()
        
        return analysis, df
    
    def display_results(self, symbol: str, analysis: dict, df: pd.DataFrame):
        """
        显示分析结果
        
        Args:
            symbol: 交易对符号
            analysis: 分析结果
            df: 原始数据
        """
        print(f"\n📊 {symbol} MTF EMA趋势分析结果")
        print("=" * 60)
        
        # 显示基本信息
        latest_price = df['close'].iloc[-1]
        latest_time = df.index[-1]
        print(f"💰 当前价格: {latest_price:.2f}")
        print(f"⏰ 最新时间: {latest_time}")
        print()
        
        # 显示趋势表格
        print(self.analyzer.format_trend_table())
        
        # 显示详细分析
        print(f"\n📈 趋势分析详情:")
        print(f"  📊 趋势强度得分: {analysis['strength_score']:.1f}%")
        print(f"  🎯 趋势共识: {analysis['consensus']}")
        print(f"  ⏰ 分析时间: {analysis['timestamp']}")
        
        # 显示信号变化
        if analysis['trend_changes']['bullish_crossovers']:
            print(f"  🟢 看涨交叉信号: {', '.join(analysis['trend_changes']['bullish_crossovers'])}")
        
        if analysis['trend_changes']['bearish_crossovers']:
            print(f"  🔴 看跌交叉信号: {', '.join(analysis['trend_changes']['bearish_crossovers'])}")
        
        # 显示当前趋势详情
        print(f"\n📋 各时间框架趋势状态:")
        trends = analysis['trends']
        for tf in trends:
            trend_summary = []
            for period in trends[tf]:
                status = "🢁" if trends[tf][period] else "🢃"
                trend_summary.append(f"EMA{period}{status}")
            print(f"  {tf:>4}: {' '.join(trend_summary)}")
    
    def compare_with_tradingview_format(self, symbol: str, analysis: dict):
        """
        输出便于与TradingView对比的格式
        
        Args:
            symbol: 交易对符号
            analysis: 分析结果
        """
        print(f"\n🔄 {symbol} TradingView对比格式")
        print("=" * 50)
        
        trends = analysis['trends']
        
        # 按照TradingView常用的时间框架排序
        tv_timeframes = ["15m", "30m", "1h", "2h", "4h"]
        tv_emas = [20, 30, 40, 50, 60]
        
        print("时间框架 | EMA20 | EMA30 | EMA40 | EMA50 | EMA60")
        print("-" * 50)
        
        for tf in tv_timeframes:
            if tf in trends:
                row = f"{tf:>6}   |"
                for ema in tv_emas:
                    if ema in trends[tf]:
                        trend_char = " 🢁 " if trends[tf][ema] else " 🢃 "
                        row += f"{trend_char} |"
                    else:
                        row += " ? |"
                print(row)
        
        print("\n📝 说明:")
        print("🢁 = EMA上升趋势 (当前EMA > 2周期前EMA)")
        print("🢃 = EMA下降趋势 (当前EMA < 2周期前EMA)")
        print("请在TradingView中添加相应EMA并对比趋势方向")


def main():
    """主函数"""
    print("📊 MTF EMA趋势分析 - OKX真实数据")
    print("=" * 60)
    
    # 提示用户先启动数据同步
    print("⚠️  注意: 请确保已运行 main.py 来同步最新数据")
    print("🚀 启动命令: source ./tg_setup.sh && python3 main.py")
    print("💡 或者运行: source ./tg_setup.sh && ./start.sh")
    print("⏹️  数据同步完成后，按 Ctrl+C 停止 main.py，然后再运行本示例")
    print()
    
    # 检查数据文件是否存在
    print("🔍 检查数据文件...")
    available_symbols = []
    
    for symbol in ["BTC", "ETH", "SOL", "DOGE"]:
        data_path = f"okx/data_raw/{symbol}/{symbol.lower()}_5m_latest.csv"
        if os.path.exists(data_path):
            file_size = os.path.getsize(data_path)
            if file_size > 0:
                available_symbols.append(symbol)
                print(f"  ✅ {symbol}: {data_path} ({file_size/1024:.1f}KB)")
            else:
                print(f"  ⚠️  {symbol}: 文件存在但为空")
        else:
            print(f"  ❌ {symbol}: 文件不存在")
    
    if not available_symbols:
        print("\n❌ 没有找到有效的数据文件!")
        print("🔧 解决方案:")
        print("1. 运行: source ./tg_setup.sh")
        print("2. 运行: python3 main.py")
        print("3. 等待数据同步完成")
        print("4. 按 Ctrl+C 停止 main.py")
        print("5. 再次运行本示例")
        return
    
    print(f"\n📋 可用交易对: {available_symbols}")
    
    analyzer = OKXMTFAnalyzer()
    
    # 选择交易对
    if len(available_symbols) == 1:
        symbol = available_symbols[0]
        print(f"\n🎯 自动选择唯一可用的交易对: {symbol}")
    else:
        print("\n📋 可用交易对:")
        for i, symbol in enumerate(available_symbols, 1):
            print(f"  {i}. {symbol}")
        
        try:
            choice = input(f"\n请选择交易对 (1-{len(available_symbols)}, 默认1): ").strip()
            if choice == "":
                choice = "1"
            
            choice = int(choice)
            if 1 <= choice <= len(available_symbols):
                symbol = available_symbols[choice - 1]
            else:
                symbol = available_symbols[0]
        except (ValueError, IndexError):
            symbol = available_symbols[0]
    
    print(f"\n🎯 选择的交易对: {symbol}")
    print("=" * 60)
    
    try:
        # 分析选定的交易对
        analysis, df = analyzer.analyze_with_okx_data(symbol)
        
        # 显示结果
        analyzer.display_results(symbol, analysis, df)
        
        # 显示TradingView对比格式
        analyzer.compare_with_tradingview_format(symbol, analysis)
        
        print(f"\n💡 TradingView验证建议:")
        print(f"1. 在TradingView打开 OKX:{symbol}USDT, 5分钟图")
        print(f"2. 添加EMA指标: 20, 30, 40, 50, 60")
        print(f"3. 切换到不同时间框架: 15m, 30m, 1h, 2h, 4h")
        print(f"4. 对比每个EMA的趋势方向是否一致")
        print(f"5. 注意: 我们的分析基于最新的5分钟数据重采样")
        
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请确保OKX数据文件存在")
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")


if __name__ == "__main__":
    main()
