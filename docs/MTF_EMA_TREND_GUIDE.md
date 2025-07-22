# 📊 多时间框架EMA趋势分析指标 (MTF EMA Trend)

## 🎯 指标简介

MTF EMA趋势分析指标基于BigBeluga的Pine Script指标，用于分析多个时间框架上的EMA（指数移动平均线）趋势。该指标可以帮助识别市场的整体趋势方向和强度。

## ✨ 主要功能

### 🔍 多时间框架分析
- 支持同时分析多个时间框架（如30m, 1h, 2h, 4h, 6h）
- 每个时间框架计算多条EMA线的趋势状态
- 提供整体趋势强度评分（0-100%）

### 📈 趋势状态检测
- **上升趋势** 🢁: EMA当前值 > 2个周期前的值
- **下降趋势** 🢃: EMA当前值 < 2个周期前的值
- 实时检测趋势转变信号

### 🎨 可视化表格
- 类似Pine Script的表格显示
- 直观的趋势方向箭头
- 趋势强度和共识评价

## 🛠️ 使用方法

### 基本用法

```python
from indicators.mtf_ema_trend import MTFEMATrend, analyze_mtf_trend
import pandas as pd

# 方法1: 快速分析
result = analyze_mtf_trend(df)
print(f"趋势强度: {result['strength_score']:.1f}%")
print(f"趋势共识: {result['consensus']}")

# 方法2: 详细分析
analyzer = MTFEMATrend(
    timeframes=["30m", "1h", "2h", "4h"],
    ema_periods=[10, 20, 50, 100, 200]
)
analyzer.update_data(df)
print(analyzer.format_trend_table())
```

### 自定义配置

```python
# 自定义时间框架和EMA周期
analyzer = MTFEMATrend(
    timeframes=["15m", "30m", "1h", "4h", "1d"],  # 自定义时间框架
    ema_periods=[9, 21, 55, 89, 144]              # 斐波那契EMA周期
)
```

## 📋 API参考

### MTFEMATrend类

#### 初始化参数
- `timeframes`: List[str] - 时间框架列表，如["1h", "4h"]
- `ema_periods`: List[int] - EMA周期列表，如[20, 50, 200]

#### 主要方法

```python
# 更新数据
analyzer.update_data(df)

# 获取当前趋势状态
trends = analyzer.get_current_trends()

# 获取趋势强度得分 (0-100)
score = analyzer.get_trend_strength_score()

# 获取趋势共识
consensus = analyzer.get_trend_consensus()

# 检测趋势变化信号
signals = analyzer.detect_trend_change()

# 获取完整分析摘要
summary = analyzer.get_trend_summary()

# 格式化表格显示
table = analyzer.format_trend_table()
```

## 💡 交易信号逻辑

### 信号强度分级

| 趋势强度 | 共识评价 | 建议操作 |
|----------|----------|----------|
| 80-100%  | 强烈看涨 | 考虑买入 |
| 65-79%   | 看涨     | 轻仓买入 |
| 55-64%   | 轻微看涨 | 观望     |
| 45-54%   | 中性     | 观望     |
| 35-44%   | 轻微看跌 | 观望     |
| 20-34%   | 看跌     | 轻仓卖出 |
| 0-19%    | 强烈看跌 | 考虑卖出 |

### 趋势变化信号

```python
# 看涨信号：EMA从下降转为上升
bullish_signals = signals["bullish_crossovers"]
# 例：["1h_EMA20", "4h_EMA50"]

# 看跌信号：EMA从上升转为下降  
bearish_signals = signals["bearish_crossovers"]
# 例：["2h_EMA100", "1d_EMA20"]
```

## 📊 数据格式要求

输入数据必须包含OHLCV格式：

```python
df = pd.DataFrame({
    'open': [...],      # 开盘价
    'high': [...],      # 最高价  
    'low': [...],       # 最低价
    'close': [...],     # 收盘价
    'volume': [...]     # 成交量（可选）
}, index=datetime_index)  # 时间索引
```

## 🔄 与现有系统集成

### 在策略中使用

```python
# 在UTBot策略中集成MTF EMA
from indicators.mtf_ema_trend import MTFEMATrend

class EnhancedUTBotStrategy:
    def __init__(self):
        self.utbot = UTBotStrategy()
        self.mtf_ema = MTFEMATrend()
    
    def calculate_signals(self, df):
        # UTBot信号
        utbot_signals = self.utbot.calculate_signals(df)
        
        # MTF EMA趋势分析
        self.mtf_ema.update_data(df)
        trend_analysis = self.mtf_ema.get_trend_summary()
        
        # 综合信号判断
        if utbot_signals and trend_analysis['strength_score'] > 70:
            return "STRONG_BUY"
        elif utbot_signals and trend_analysis['strength_score'] > 50:
            return "BUY"
        # ... 更多逻辑
```

## 📈 示例输出

```
📊 多时间框架EMA趋势分析
==================================================
时间框架    EMA20   EMA30   EMA40   EMA50   EMA60   
------------------------------------------------
1h      🢁       🢁       🢁       🢁       🢁       
2h      🢁       🢁       🢁       🢃       🢃       
3h      🢁       🢁       🢃       🢃       🢃       
4h      🢁       🢃       🢃       🢃       🢃       
5h      🢃       🢃       🢃       🢃       🢃       
--------------------------------------------------
趋势强度: 60.0%
趋势共识: 轻微看涨
🟢 看涨信号: 1h_EMA20, 2h_EMA30
```

## ⚠️ 注意事项

1. **数据质量**: 确保输入数据的时间戳准确且连续
2. **时间框架**: 高级时间框架需要足够的历史数据
3. **延迟性**: EMA是滞后指标，信号可能有延迟
4. **风险管理**: 指标仅供参考，请结合其他分析工具

## 🔧 故障排除

### 常见问题

1. **数据不足**: 确保有足够的历史数据计算EMA
2. **时间格式**: 确保DataFrame索引是datetime格式
3. **内存使用**: 大量时间框架可能消耗较多内存

### 调试模式

```python
# 启用详细输出
analyzer = MTFEMATrend()
analyzer.update_data(df)

# 检查中间结果
print("EMA Results:", analyzer.ema_results)
print("Trend States:", analyzer.trend_states)
```

---

📚 **更多示例请查看**: `examples/mtf_ema_example.py`
