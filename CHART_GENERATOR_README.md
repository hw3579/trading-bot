# 技术分析图表生成器

自动生成结合Smart MTF S/R和MTF EMA指标的专业技术分析图表。

## 功能特点

### 📊 综合指标分析
- **Smart MTF S/R Levels**: 多时间框架支撑阻力位分析
- **MTF EMA Trend**: 多时间框架EMA趋势分析
- **K线图**: 专业的蜡烛图展示
- **成交量**: 成交量柱状图

### 🎨 可视化特色
- **深色主题**: 专业的交易界面风格
- **彩色水平线**: 支撑阻力位按类型和强度着色
- **汇聚度标注**: 数字显示支撑阻力位的可靠性
- **EMA线**: 多周期移动平均线
- **趋势背景**: 整体趋势色块指示

### 💰 支持币种
- BTC (比特币)
- ETH (以太坊)  
- SOL (Solana)
- 可扩展支持更多币种

## 快速开始

### 基本使用

```bash
# 生成所有默认币种的图表（BTC, ETH, SOL）
python generate_charts.py

# 生成单个币种图表
python generate_charts.py -s BTC

# 生成最近7天的数据图表
python generate_charts.py -s ETH -d 7
```

### 命令行参数

| 参数 | 简写 | 说明 | 示例 |
|------|------|------|------|
| `--symbol` | `-s` | 指定单个币种 | `-s BTC` |
| `--days` | `-d` | 回看天数（默认3天） | `-d 7` |
| `--all` | `-a` | 生成所有币种图表 | `-a` |

### 使用示例

```bash
# 基础用法
python generate_charts.py                    # 生成BTC/ETH/SOL图表
python generate_charts.py -s BTC             # 只生成BTC图表
python generate_charts.py -s ETH -d 7        # 生成ETH最近7天图表
python generate_charts.py -a -d 5            # 生成所有币种最近5天图表
```

## 输出文件

生成的图表文件命名格式：
```
{币种}_technical_analysis_{时间戳}.png
```

示例：
- `btc_technical_analysis_20250725_013500.png`
- `eth_technical_analysis_20250725_013401.png`

## 图表说明

### 主图元素
- **绿色K线**: 价格上涨
- **红色K线**: 价格下跌
- **彩色水平线**: 支撑阻力位
- **数字标注**: 汇聚度（越高越可靠）
- **白色虚线**: 当前价格线
- **彩色EMA线**: 移动平均线

### 颜色编码
- 🟢 **绿色**: 支撑位 (Support)
- 🔴 **红色**: 阻力位 (Resistance)
- 🟠 **橙色**: 混合区域 (Mixed)
- 🔵 **蓝色**: 枢轴点 (Pivot)

### 副图
- **成交量柱**: 绿色表示上涨，红色表示下跌

## 技术分析摘要

每次生成图表时，会自动输出技术分析摘要：

```
📊 BTC 技术分析摘要:
==================================================
当前价格: $118,275.30
S/R区域总数: 5
支撑区域: 2
阻力区域: 3
最近支撑: $117,895.78 (距离: 0.32%, 汇聚度: 6)
最近阻力: $118,332.55 (距离: 0.05%, 汇聚度: 16)
```

## 依赖要求

```bash
pip install pandas numpy matplotlib scipy talib
```

## 数据源

使用OKX交易所的真实历史数据，数据路径：
```
okx/data_raw/{SYMBOL}/{symbol}_5m_latest.csv
```

确保运行前已通过 `main.py` 同步最新数据。

## 高级配置

### 修改时间框架
编辑 `generate_charts.py` 中的时间框架设置：

```python
# Smart MTF S/R时间框架
timeframes=["15", "30", "60", "240"]  # 15分钟，30分钟，1小时，4小时

# MTF EMA时间框架  
timeframes=["60", "240"]  # 1小时，4小时
```

### 修改EMA周期
```python
ema_periods=[20, 50, 200]  # EMA周期
```

### 修改图表尺寸
```python
chart_generator = TechnicalAnalysisChart(figsize=(20, 12))  # 宽x高
```

## 故障排除

### 常见问题

1. **找不到数据文件**
   ```
   FileNotFoundError: 找不到数据文件: okx/data_raw/BTC/btc_5m_latest.csv
   ```
   **解决方案**: 运行 `python main.py` 同步数据

2. **MTF EMA计算错误**
   ```
   ⚠️ BTC MTF EMA计算出错
   ```
   **解决方案**: 会自动使用简单EMA作为备选

3. **图表显示不全**
   - 增加图表尺寸：`figsize=(24, 14)`
   - 减少显示的时间范围：`-d 2`

### 性能优化

- 减少数据量：使用 `-d 2` 只分析最近2天
- 关闭某些指标：编辑代码中的 `show_*=False`
- 降低图表分辨率：修改 `dpi=150`

## 集成使用

### 在其他脚本中使用

```python
from generate_charts import TechnicalAnalysisChart

# 创建图表生成器
chart_gen = TechnicalAnalysisChart()

# 生成单个图表
chart_path = chart_gen.generate_chart("BTC", days_back=3)
print(f"图表已保存到: {chart_path}")

# 批量生成
files = chart_gen.generate_multiple_charts(["BTC", "ETH"], days_back=5)
```

### 自动化定时生成

```bash
# 每天生成图表的cron任务
0 9 * * * cd /path/to/bot && python generate_charts.py
```

## 许可证

本项目基于MIT许可证开源。
