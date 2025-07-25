# Telegram技术分析图表机器人使用指南

## 📖 概述

这是一个集成了技术分析功能的Telegram机器人，可以根据用户命令生成专业的加密货币技术分析图表。

## 🚀 功能特色

- **技术分析图表**: 生成包含K线图、EMA线、支撑阻力位的专业图表
- **多时间框架**: 支持5m、15m、30m、1h、4h、1d等时间框架
- **多交易对**: 支持BTC、ETH、SOL、DOGE等主流加密货币
- **Pine Script风格**: 模仿TradingView的Pine Script图表样式
- **实时数据**: 基于最新的市场数据生成分析

## 📋 环境要求

### Python依赖
```bash
pip install python-telegram-bot matplotlib pandas talib websockets
```

### 系统要求
- Python 3.8+
- Linux/macOS/Windows
- 网络连接

## ⚙️ 配置设置

### 1. 创建Telegram机器人

1. 与 [@BotFather](https://t.me/BotFather) 对话
2. 发送 `/newbot` 创建新机器人
3. 设置机器人名称和用户名
4. 获取Bot Token (格式：`1234567890:ABCdefGHIjklMNOpqrSTUvwxyz`)

### 2. 获取Chat ID

1. 将机器人添加到您的聊天或群组
2. 发送任意消息给机器人
3. 访问：`https://api.telegram.org/bot<YourBotToken>/getUpdates`
4. 找到 `"chat":{"id":12345678}` 中的数字

### 3. 设置环境变量

```bash
# Linux/macOS
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"

# Windows (PowerShell)
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"
$env:TELEGRAM_CHAT_ID="your_chat_id_here"

# Windows (CMD)
set TELEGRAM_BOT_TOKEN=your_bot_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. 多用户支持

如需支持多个用户，Chat ID用逗号分隔：
```bash
export TELEGRAM_CHAT_ID="123456789,987654321,555666777"
```

## 🎯 使用方法

### 启动机器人

#### 方法1: 使用启动脚本
```bash
./start_telegram_bot.sh
```

#### 方法2: 直接运行Python脚本
```bash
python3 telegram_chart_bot.py
```

### Telegram命令

#### `/start` - 查看使用说明
获取机器人的完整使用说明。

#### `/info` - 生成技术分析图表

**基本格式:**
```
/info [symbol] [timeframe] [candles]
```

**参数说明:**
- `symbol`: 交易对符号 (可选，默认: ETH)
- `timeframe`: 时间框架 (可选，默认: 15m)
- `candles`: K线数量 (可选，默认: 200，范围: 50-1000)

**使用示例:**

```bash
# 使用默认参数 (ETH 15m 200根K线)
/info

# 指定交易对
/info BTC                    # BTC 15m 200根K线
/info SOL                    # SOL 15m 200根K线

# 指定时间框架
/info ETH 5m                 # ETH 5分钟 200根K线
/info BTC 1h                 # BTC 1小时 200根K线
/info SOL 4h                 # SOL 4小时 200根K线

# 指定K线数量
/info ETH 15m 100            # ETH 15分钟 100根K线
/info BTC 5m 500             # BTC 5分钟 500根K线

# 完整参数示例
/info DOGE 30m 150           # DOGE 30分钟 150根K线
```

**支持的交易对:**
- BTC (比特币)
- ETH (以太坊)
- SOL (Solana)
- DOGE (狗狗币)

**支持的时间框架:**
- 5m (5分钟)
- 15m (15分钟)
- 30m (30分钟)
- 1h (1小时)
- 4h (4小时)
- 1d (1天)

#### `/help` - 获取帮助
与 `/start` 命令相同，显示详细的使用说明。

## 📊 图表说明

生成的技术分析图表包含以下元素：

### K线图
- 🟢 **绿色K线**: 价格上涨
- 🔴 **红色K线**: 价格下跌

### 技术指标
- 📈 **EMA线**: 指数移动平均线 (20, 30, 40, 50, 60周期)
- 🔵 **支撑阻力位**: 彩色水平线，显示关键价格水平
- ⚪ **当前价格**: 白色虚线
- 📊 **成交量**: 底部子图显示交易量

### Pine Script风格
- 深色背景主题
- TradingView风格的颜色方案
- 渐变填充区域
- 专业的标签和标注

## 🔧 高级配置

### 自定义图表参数

如需修改图表生成参数，可以编辑 `generate_charts.py` 文件：

```python
# 修改默认图表大小
chart_generator = TechnicalAnalysisChart(figsize=(24, 16))

# 修改S/R指标参数
df_with_sr = compute_smart_mtf_sr(
    df,
    timeframes=["15", "60", "240"],  # 时间框架
    show_within_percent=2.5,         # 显示百分比范围
    cluster_percent=0.25,            # 聚类百分比
    top_n=8,                         # 显示前N个区域
    alert_confluence=4,              # 警报汇聚度
    min_confluence=2                 # 最小汇聚度
)
```

### 数据源配置

目前使用OKX交易所的历史数据，数据文件位于：
```
hyperliquid/data_raw/
├── BTC/
├── ETH/
├── SOL/
└── DOGE/
```

## 🚨 故障排除

### 常见问题

#### 1. 机器人无响应
- 检查Bot Token是否正确
- 确认Chat ID是否正确
- 检查网络连接

#### 2. 图表生成失败
- 确认数据文件存在
- 检查Python依赖是否完整安装
- 查看终端错误日志

#### 3. 权限错误
- 确认您的Chat ID在允许列表中
- 检查机器人是否已添加到群组/频道

#### 4. 导入错误
```bash
# 安装缺失的依赖
pip install python-telegram-bot matplotlib pandas talib

# 对于TA-Lib的安装问题
# Ubuntu/Debian:
sudo apt-get install ta-lib
pip install TA-Lib

# macOS:
brew install ta-lib
pip install TA-Lib

# Windows:
# 下载预编译的wheel文件
pip install TA_Lib-0.4.24-cp39-cp39-win_amd64.whl
```

### 日志查看

运行时的详细日志会显示在终端中，包括：
- 机器人启动状态
- 命令处理过程
- 图表生成进度
- 错误信息和警告

### 性能优化

#### 减少图表生成时间
- 使用较少的K线数量 (50-200)
- 选择较长的时间框架 (1h, 4h)
- 确保数据文件是最新的

#### 内存优化
- 定期清理临时图表文件
- 使用适当的图表大小
- 避免同时生成多个图表

## 📱 使用技巧

### 1. 快速查看
```
/info BTC 1h        # 快速查看BTC小时图
/info ETH 5m 100    # 查看ETH短期走势
```

### 2. 深度分析
```
/info BTC 4h 500    # BTC长期趋势分析
/info ETH 15m 300   # ETH中期分析
```

### 3. 多品种监控
依次发送多个命令来比较不同资产：
```
/info BTC 1h
/info ETH 1h
/info SOL 1h
```

## 🔐 安全注意事项

1. **保护Bot Token**: 不要将Token分享给他人或提交到公共代码库
2. **限制访问**: 只将您信任的Chat ID添加到允许列表
3. **定期更新**: 保持依赖库和系统的更新
4. **监控使用**: 注意机器人的使用频率，避免过度请求

## 📞 技术支持

如遇到问题，请检查：
1. 环境变量是否正确设置
2. 所有依赖是否已安装
3. 数据文件是否存在且可访问
4. 网络连接是否正常

## 🔄 更新日志

### v1.0.0 (当前版本)
- ✅ 基础Telegram机器人功能
- ✅ `/info` 命令支持
- ✅ 多交易对支持 (BTC, ETH, SOL, DOGE)
- ✅ 多时间框架支持
- ✅ Pine Script风格图表
- ✅ 支撑阻力位分析
- ✅ EMA技术指标
- ✅ 权限控制系统
