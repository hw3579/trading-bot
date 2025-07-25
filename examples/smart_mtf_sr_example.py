#!/usr/bin/env python3
"""
Smart MTF S/R Levels Indicator 使用示例 - OKX真实数据
使用真实的OKX数据测试Smart MTF S/R指标
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from indicators.smart_mtf_sr import compute_smart_mtf_sr


def analyze_sr_data(sr_json_data: str) -> dict:
    """
    分析支撑阻力数据
    
    Args:
        sr_json_data: JSON格式的S/R数据
        
    Returns:
        分析结果字典
    """
    if not sr_json_data or sr_json_data == 'None':
        return {'status': 'no_data'}
    
    try:
        data = json.loads(sr_json_data)
        zones = data.get('zones', [])
        current_price = data.get('current_price', 0)
        
        if not zones:
            return {'status': 'no_zones'}
        
        # 分析最强的支撑和阻力
        support_zones = [z for z in zones if z['type'] in ['Support', 'Mixed'] and z['level'] < current_price]
        resistance_zones = [z for z in zones if z['type'] in ['Resistance', 'Mixed'] and z['level'] > current_price]
        
        # 按汇聚度排序
        support_zones.sort(key=lambda x: x['confluence'], reverse=True)
        resistance_zones.sort(key=lambda x: x['confluence'], reverse=True)
        
        # 找到最近的强支撑和阻力
        nearest_support = None
        nearest_resistance = None
        
        if support_zones:
            nearest_support = max(support_zones, key=lambda x: x['level'])  # 最高的支撑位
        
        if resistance_zones:
            nearest_resistance = min(resistance_zones, key=lambda x: x['level'])  # 最低的阻力位
        
        analysis = {
            'status': 'success',
            'current_price': current_price,
            'total_zones': len(zones),
            'support_zones_count': len(support_zones),
            'resistance_zones_count': len(resistance_zones),
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'strongest_zone': max(zones, key=lambda x: x['confluence']) if zones else None
        }
        
        # 计算距离百分比
        if nearest_support:
            analysis['support_distance_pct'] = abs(current_price - nearest_support['level']) / current_price * 100
        
        if nearest_resistance:
            analysis['resistance_distance_pct'] = abs(nearest_resistance['level'] - current_price) / current_price * 100
        
        return analysis
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def generate_trading_signals(analysis: dict) -> dict:
    """
    基于S/R分析生成交易信号
    
    Args:
        analysis: S/R分析结果
        
    Returns:
        交易信号字典
    """
    if analysis.get('status') != 'success':
        return {'signal': 'none', 'reason': 'no_valid_analysis'}
    
    signals = {
        'signal': 'none',
        'confidence': 0,
        'reasons': [],
        'levels': {}
    }
    
    current_price = analysis['current_price']
    nearest_support = analysis.get('nearest_support')
    nearest_resistance = analysis.get('nearest_resistance')
    strongest_zone = analysis.get('strongest_zone')
    
    # 支撑位买入信号
    if nearest_support and analysis.get('support_distance_pct', 0) <= 1.0:  # 距离支撑位1%以内
        confidence = min(nearest_support['confluence'] * 10, 100)
        if confidence >= 30:  # 汇聚度足够高
            signals['signal'] = 'buy'
            signals['confidence'] = confidence
            signals['reasons'].append(f"接近强支撑位 {nearest_support['level']:.2f}")
            signals['reasons'].append(f"汇聚度: {nearest_support['confluence']}")
            signals['levels']['support'] = nearest_support['level']
    
    # 阻力位卖出信号
    if nearest_resistance and analysis.get('resistance_distance_pct', 0) <= 1.0:  # 距离阻力位1%以内
        confidence = min(nearest_resistance['confluence'] * 10, 100)
        if confidence >= 30:  # 汇聚度足够高
            signals['signal'] = 'sell'
            signals['confidence'] = confidence
            signals['reasons'].append(f"接近强阻力位 {nearest_resistance['level']:.2f}")
            signals['reasons'].append(f"汇聚度: {nearest_resistance['confluence']}")
            signals['levels']['resistance'] = nearest_resistance['level']
    
    # 如果最强区域的汇聚度很高，增加信号强度
    if strongest_zone and strongest_zone['confluence'] >= 5:
        if signals['signal'] != 'none':
            signals['confidence'] = min(signals['confidence'] + 20, 100)
            signals['reasons'].append(f"发现高汇聚度区域: {strongest_zone['confluence']}")
    
    return signals


def load_okx_data(symbol: str = "ETH") -> pd.DataFrame:
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
    df.set_index('datetime', inplace=True)
    
    # 确保数据按时间排序
    df.sort_index(inplace=True)
    
    # 重命名列以匹配标准格式
    if 'o' in df.columns:
        df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'vol': 'volume'}, inplace=True)
    
    print(f"加载 {symbol} 数据: {len(df)} 条记录")
    print(f"时间范围: {df.index[0]} 到 {df.index[-1]}")
    print(f"价格范围: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")
    
    return df


def example_usage():
    """使用示例"""
    print("=== Smart MTF S/R Levels - OKX真实数据测试 ===\n")
    
    # 测试多个币种
    symbols = ["BTC", "ETH", "SOL"]
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"测试币种: {symbol}")
        print(f"{'='*50}")
        
        try:
            # 加载OKX真实数据
            df = load_okx_data(symbol)
            
            # 只使用最近的数据（提高计算速度）
            recent_data = df.tail(300)  # 最近300条5分钟数据（约25小时）
            
            print(f"\n1. 计算Smart MTF S/R指标...")
            print(f"使用最近 {len(recent_data)} 条数据进行分析")
            
            # 计算指标（使用Pine脚本的默认参数）
            result = compute_smart_mtf_sr(
                recent_data, 
                timeframes=["15", "60", "240"],  # 15分钟，1小时，4小时
                show_swings=True,  # Pine脚本默认开启
                show_pivots=False,  # Pine脚本默认关闭
                show_fibonacci=False,  # Pine脚本默认关闭
                show_order_blocks=False,  # Pine脚本默认关闭
                show_volume_profile=False,  # Pine脚本默认关闭
                show_psychological_levels=True,  # 加密货币特色功能
                show_within_percent=2.5,  # 按要求设置
                cluster_percent=0.25,  # 按要求设置
                top_n=8,  # Pine脚本默认值
                alert_confluence=4,  # 按要求设置
                min_confluence=2  # 最小汇聚度
            )
            
            print(f"计算完成！处理了 {len(result)} 条数据")
            
            # 分析最后几条数据
            print(f"\n2. {symbol} 最近的S/R分析:")
            
            # 只分析最后一条有效数据
            for i in range(len(result)-1, max(len(result)-4, -1), -1):
                sr_data = result.iloc[i]['sr_data']
                
                if sr_data and sr_data != 'None':
                    analysis = analyze_sr_data(sr_data)
                    
                    if analysis['status'] == 'success':
                        timestamp = result.index[i]
                        current_price = analysis['current_price']
                        
                        print(f"\n时间: {timestamp}")
                        print(f"当前价格: ${current_price:,.2f}")
                        print(f"发现 {analysis['total_zones']} 个S/R区域 (支撑: {analysis['support_zones_count']}, 阻力: {analysis['resistance_zones_count']})")
                        
                        # 显示最近的支撑和阻力
                        if analysis['nearest_support']:
                            support = analysis['nearest_support']
                            distance = analysis.get('support_distance_pct', 0)
                            methods = ', '.join(support['methods'][:3])  # 只显示前3个方法
                            print(f"最近支撑位: ${support['level']:,.2f} (汇聚度: {support['confluence']}, 距离: {distance:.2f}%)")
                            print(f"  方法: {methods}{'...' if len(support['methods']) > 3 else ''}")
                        
                        if analysis['nearest_resistance']:
                            resistance = analysis['nearest_resistance']
                            distance = analysis.get('resistance_distance_pct', 0)
                            methods = ', '.join(resistance['methods'][:3])  # 只显示前3个方法
                            print(f"最近阻力位: ${resistance['level']:,.2f} (汇聚度: {resistance['confluence']}, 距离: {distance:.2f}%)")
                            print(f"  方法: {methods}{'...' if len(resistance['methods']) > 3 else ''}")
                        
                        # 显示最强区域
                        if analysis['strongest_zone']:
                            strongest = analysis['strongest_zone']
                            print(f"最强区域: ${strongest['level']:,.2f} (汇聚度: {strongest['confluence']}, 类型: {strongest['type']})")
                        
                        # 生成交易信号
                        signals = generate_trading_signals(analysis)
                        if signals['signal'] != 'none':
                            print(f"🚨 交易信号: {signals['signal'].upper()} (置信度: {signals['confidence']}%)")
                            for reason in signals['reasons']:
                                print(f"   - {reason}")
                        else:
                            print("📊 当前无明确交易信号")
                        
                        break  # 只分析最新的有效数据
            
            # 显示统计信息
            print(f"\n3. {symbol} 统计信息:")
            valid_count = len([x for x in result['sr_data'] if x and x != 'None'])
            print(f"有效S/R数据: {valid_count}/{len(result)} 条")
            
            if valid_count > 0:
                # 统计平均区域数量
                total_zones = 0
                for sr_data in result['sr_data']:
                    if sr_data and sr_data != 'None':
                        try:
                            data = json.loads(sr_data)
                            total_zones += data.get('total_zones', 0)
                        except:
                            pass
                
                avg_zones = total_zones / valid_count if valid_count > 0 else 0
                print(f"平均S/R区域数量: {avg_zones:.1f}")
        
        except FileNotFoundError as e:
            print(f"❌ 无法加载 {symbol} 数据: {e}")
            continue
        except Exception as e:
            print(f"❌ 分析 {symbol} 时出错: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*50}")
    print("=== 测试完成 ===")
    print("\n💡 提示:")
    print("- 支撑位汇聚度越高，支撑越强")
    print("- 阻力位汇聚度越高，阻力越强")
    print("- 心理价位(Psychological)在加密货币中特别重要")
    print("- 多时间框架确认的水平更可靠")


if __name__ == "__main__":
    example_usage()
