# 🚀 交易监控系统 - 双协议架构

## 📋 系统概述

基于双协议架构的加密货币交易监控系统，采用WebSocket实时信号推送 + gRPC查询服务，支持实时技术分析、智能S/R分析和多交易所数据监控。

### 🎯 架构特点
- **双协议架构**: WebSocket信号推送(10000) + gRPC查询服务(10001)
- **进程分离**: 核心系统与Telegram客户端完全独立运行
- **智能分析**: UTBot策略 + Smart S/R分析增强
- **多交易所支持**: OKX、Hyperliquid
- **实时监控**: 多线程数据监控和信号检测
- **增强信号**: 支撑阻力分析集成到UTBot信号

## 🏗️ 系统架构

```
┌─────────────────────────────────────┐
│           核心监控系统               │
│           (main.py)                │
├─────────────────┬───────────────────┤
│  WebSocket      │     gRPC          │
│  信号推送       │     查询服务       │
│  端口: 10000    │     端口: 10001   │
└─────────────────┼───────────────────┘
                  │
          ┌───────▼───────┐
          │ Telegram客户端 │
          │ (standalone)   │
          ├────────────────┤
          │ • 信号接收     │
          │ • 图表查询     │
          │ • 状态查询     │
          │ • S/R分析显示  │
          └────────────────┘
```

### 📊 信号流程
```
UTBot检测 → SmartSR增强 → 通知服务 → WebSocket推送 → Telegram显示
     ↓           ↓            ↓           ↓            ↓
  价格变化    S/R分析      信号数据    实时推送    增强消息
```

## 🚀 快速启动

### 第一步：启动核心系统
```bash
# 方式1: 使用启动脚本
## 🚀 快速启动

### 第一步：启动核心监控系统
```bash
# 方式1: 使用启动脚本
./start_core.sh

# 方式2: 直接运行
python3 main.py --config config/config_multi.yaml --log-level INFO
```

### 第二步：启动Telegram客户端
```bash
# 1. 设置环境变量
export TELEGRAM_BOT_TOKEN="你的bot_token"
export TELEGRAM_CHAT_ID="你的chat_id"

# 2. 启动Telegram客户端
python3 telegram_standalone.py
```

## 📱 Telegram命令

### 基本命令
- `/start` - 显示帮助信息和系统状态
- `/okx <币种> <时间框架> <数量>` - OKX交易所图表查询 
- `/hype <币种> <时间框架> <数量>` - Hyperliquid交易所图表查询
- `/status <交易所>` - 查看指定交易所状态

### 命令示例
```
/okx ETH 5m 200      # ETH 5分钟图，200根K线
/hype BTC 15m 100    # BTC 15分钟图，100根K线  
/okx SOL 1h 50       # SOL 1小时图，50根K线
/status okx          # 查看OKX交易所状态
/status hyperliquid  # 查看Hyperliquid交易所状态
```

## 📊 智能信号系统

### UTBot + Smart S/R 增强信号
- **基础信号**: UTBot检测买卖点
- **S/R分析**: 多时间框架支撑阻力分析
- **增强消息**: 包含价格位置、关键水平、汇聚度信息
- **实时推送**: WebSocket实时信号推送到Telegram

### 信号格式示例
```
UTBot-BUY | okx-SOL-15m
价格: $188.51 | 时间: 2025-01-27 16:15

📊 支撑阻力分析:
当前位置: $188.51
🔴 上方阻力: $189.96 (汇聚度:2, 反应:0)
🟢 下方支撑: $185.43 (汇聚度:3, 反应:9)
```

## ⚙️ 配置文件

### 主配置: `config/config_multi.yaml`
```yaml
# 监控配置
monitoring:
  trigger_second: 10      # 每分钟xx秒启动
  trigger_minutes: 5      # 触发间隔(分钟)
  
# UTBot策略配置  
strategies:
  utbot:
    enable_sr_analysis: true    # 启用S/R分析
    smart_sr_config:
      timeframes: ["15", "60", "240"]  # 分析时间框架
      cluster_percent: 0.25            # 聚类百分比
      min_confluence: 2                # 最小汇聚度
```
- **HMA**: Hull移动平均线

## 🔧 故障排除

### 核心系统问题
```bash
# 检查端口占用
netstat -tlnp | grep 10000

# 查看日志
tail -f logs/signals.log
```

### Telegram客户端问题
```bash
## 🔧 系统参数

### UTBot指标参数 (默认值)
```python
allow_buy: True          # 允许买入信号
allow_sell: True         # 允许卖出信号  
use_heikin: True         # 使用Heikin-Ashi蜡烛
price_source: "open"     # 价格来源：开盘价
ma_type: "HMA"          # 移动平均类型：Hull MA
ma_period: 2            # 移动平均周期：2
atr_period: 11          # ATR周期：11
a: 1.0                  # ATR倍数：1.0
```

## 🛠️ 故障排除

### 常见问题
```bash
# 1. 检查核心系统状态
ps aux | grep main.py

# 2. 检查WebSocket端口
netstat -tlnp | grep 10000

# 3. 检查gRPC端口  
netstat -tlnp | grep 10001

# 4. 测试WebSocket连接
python3 test/test_websocket_format.py

# 5. 检查环境变量
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

## 📁 项目结构

```
bot/
├── main.py                     # 核心监控系统入口
├── telegram_standalone.py      # 独立Telegram客户端  
├── generate_charts.py          # 图表生成器
├── utils.py                    # 工具函数
├── config/                     # 配置文件目录
│   ├── config_multi.yaml      # 主配置文件
│   └── config_loader.py       # 配置加载器
├── core/                       # 核心监控逻辑
│   ├── monitor_base.py        # 监控基类
│   ├── multi_monitor.py       # 多线程监控
│   └── single_monitor.py      # 单线程监控
├── services/                   # 服务层
│   ├── dual_websocket_server.py  # 双协议WebSocket/gRPC服务器
│   ├── grpc_server.py         # gRPC服务器
│   └── notification_service.py # 通知服务
├── strategies/                 # 交易策略
│   ├── utbot_strategy.py      # UTBot策略
│   └── smart_sr_strategy.py   # 智能S/R分析策略
├── indicators/                 # 技术指标
│   ├── UT_Bot_v5.py           # UTBot指标
│   ├── smart_mtf_sr.py        # Smart MTF S/R指标
│   └── hma.py                 # Hull移动平均
├── proto/                      # gRPC协议定义
├── test/                       # 测试文件
└── docs/                       # 详细文档
```

## 📚 详细文档

- [Smart MTF S/R分析指南](docs/SMART_MTF_SR_GUIDE.md)
- [MTF EMA趋势分析指南](docs/MTF_EMA_TREND_GUIDE.md)

## 🔄 系统状态监控

### 核心系统检查
```bash
# 检查主进程
ps aux | grep main.py

# 检查端口状态
netstat -tlnp | grep -E "(10000|10001)"

# 检查日志
tail -f logs/signals.log
```

### Telegram客户端检查
```bash
# 检查客户端进程
ps aux | grep telegram_standalone.py

# 测试连接
python3 test/test_websocket_format.py
```

## ⚡ 系统特性

- **实时监控**: 12个交易对同时监控 (6个OKX + 6个Hyperliquid)
- **多线程处理**: 并发数据获取和分析
- **智能信号**: UTBot + Smart S/R增强分析
- **双协议架构**: WebSocket推送 + gRPC查询
- **容错机制**: 自动重连和错误恢复

---

**项目架构**: 双协议分离架构 v3.0  
**核心技术**: WebSocket + gRPC + 多线程监控  
**更新时间**: 2025-07-27
