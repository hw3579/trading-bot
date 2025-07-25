# Smart MTF S/R Levels Indicator

智能多时间框架支撑阻力位指标，基于BullByte的Pine Script指标转换而来。

## 功能特点

### 📊 多时间框架分析
- 支持多个时间框架同时分析（默认：15分钟、30分钟、1小时、4小时）
- 自动从5分钟基础数据构建更高时间框架
- 多时间框架汇聚提高支撑阻力位可靠性

### 🎯 多种支撑阻力识别方法
1. **摆动高低点 (Swing Highs/Lows)** - 基于局部极值的传统支撑阻力
2. **枢轴点 (Pivot Points)** - 经典技术分析枢轴点计算
3. **斐波那契回撤 (Fibonacci Retracements)** - 23.6%, 38.2%, 50%, 61.8%, 78.6%水平
4. **订单块 (Order Blocks)** - 基于价格行为的机构订单区域
5. **成交量分析 (Volume Profile)** - VWAP和POC（成交量重心）
6. **心理价位 (Psychological Levels)** - 整数价位水平

### 🧠 智能区域聚类
- 将相近的支撑阻力位聚类为区域
- 计算每个区域的汇聚度（多少个方法确认）
- 统计历史价格对区域的反应次数

### 📈 加密货币优化
- 针对加密货币高波动性调整参数
- 心理价位自适应计算（根据价格范围调整间隔）
- 更大的聚类范围以适应加密货币特性

## 安装和使用

### 依赖要求
```bash
pip install pandas numpy scipy talib
```

### 基本使用

```python
from indicators.smart_mtf_sr import compute_smart_mtf_sr
import pandas as pd

# 准备OHLCV数据（需要包含open, high, low, close, volume列）
df = pd.read_csv("your_data.csv")

# 计算指标
result = compute_smart_mtf_sr(
    df, 
    timeframes=["15", "30", "60", "240"],  # 时间框架（分钟）
    show_swings=True,                      # 显示摆动点
    show_pivots=True,                      # 显示枢轴点
    show_fibonacci=True,                   # 显示斐波那契
    show_order_blocks=True,                # 显示订单块
    show_volume_profile=True,              # 显示成交量分析
    show_psychological_levels=True,        # 显示心理价位
    show_within_percent=2.0,               # 只显示价格2%范围内的水平
    cluster_percent=0.3,                   # 0.3%内的水平聚类为一个区域
    top_n=8,                               # 显示前8个区域
    min_confluence=2                       # 最小汇聚度过滤
)

# 结果在sr_data列中，JSON格式
print(result['sr_data'].iloc[-1])
```

### 使用OKX真实数据测试

```bash
cd /home/hw3579/bot
python examples/smart_mtf_sr_example.py
```

## 输出数据格式

每行的`sr_data`列包含JSON格式的数据：

```json
{
  "zones": [
    {
      "level": 118275.30,
      "top": 118280.0,
      "bottom": 118270.0,
      "methods": ["Swing High", "Pivot", "Fibonacci"],
      "timeframes": ["15", "30", "60"],
      "type": "Resistance",
      "extras": ["", "", "0.618"],
      "confluence": 3,
      "reactions": 15
    }
  ],
  "total_zones": 5,
  "current_price": 118275.30,
  "timestamp": "2025-07-24T23:50:00"
}
```

### 字段说明
- `level`: 区域中心价格
- `top/bottom`: 区域上下边界
- `methods`: 确认此区域的方法列表
- `timeframes`: 涉及的时间框架
- `type`: 区域类型（Support/Resistance/Mixed）
- `confluence`: 汇聚度（越高越重要）
- `reactions`: 历史反应次数

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeframes` | List[str] | ["15", "30", "60"] | 分析的时间框架（分钟） |
| `show_swings` | bool | True | 显示摆动高低点 |
| `show_pivots` | bool | True | 显示枢轴点 |
| `show_fibonacci` | bool | True | 显示斐波那契水平 |
| `show_order_blocks` | bool | True | 显示订单块 |
| `show_volume_profile` | bool | True | 显示成交量分析 |
| `show_psychological_levels` | bool | True | 显示心理价位 |
| `show_within_percent` | float | 5.0 | 显示价格附近百分比范围 |
| `lookback_swings` | int | 5 | 摆动点回看数量 |
| `cluster_percent` | float | 0.5 | 聚类百分比阈值 |
| `top_n` | int | 10 | 显示前N个区域 |
| `reaction_lookback` | int | 200 | 反应计算回看期 |
| `sort_by` | str | "Confluence" | 排序方式 |
| `min_confluence` | int | 2 | 最小汇聚度过滤 |

## 交易信号示例

基于输出数据可以生成交易信号：

```python
def analyze_signals(sr_data):
    data = json.loads(sr_data)
    current_price = data['current_price']
    
    for zone in data['zones']:
        distance = abs(zone['level'] - current_price) / current_price * 100
        
        if distance <= 1.0 and zone['confluence'] >= 3:
            if zone['type'] == 'Support' and zone['level'] < current_price:
                print(f"买入信号：接近强支撑位 {zone['level']}")
            elif zone['type'] == 'Resistance' and zone['level'] > current_price:
                print(f"卖出信号：接近强阻力位 {zone['level']}")
```

## 实际应用建议

1. **汇聚度重要性**：汇聚度>=3的区域通常更可靠
2. **距离判断**：价格距离区域1%以内时信号更强
3. **多时间框架确认**：包含更多时间框架的区域更重要
4. **反应次数**：历史反应次数多的区域往往更有效
5. **心理价位**：在加密货币中，整数价位经常成为重要支撑阻力

## 性能优化

- 建议使用最近200-500条数据进行计算
- 可以根据需要禁用某些计算密集型功能
- 调整`min_confluence`参数过滤低质量区域

## 技术原理

本指标基于以下技术分析理论：
- 支撑阻力理论
- 多时间框架分析
- 成交量价格分析
- 市场心理学（心理价位）
- 机构订单流分析（订单块）
