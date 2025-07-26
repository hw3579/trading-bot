# 🚀 交易监控系统 - 进程分离架构

## 📋 系统概述

这是一个基于进程分离架构的加密货币交易监控系统，支持实时技术分析、信号检测和多交易所数据监控。

### 🎯 架构特点
- **进程分离**: 核心系统与Telegram客户端完全独立运行
- **WebSocket通信**: 统一的命令处理和数据传输
- **多交易所支持**: OKX、Hyperliquid
- **实时监控**: 多线程数据监控和信号检测
- **技术分析**: UTBot、Smart MTF S/R、EMA趋势分析

## 🏗️ 系统架构

```
┌─────────────────┐    WebSocket     ┌──────────────────┐
│  核心系统       │ ◄──────────────► │  Telegram客户端  │
│  (main.py)      │   ws://10000     │  (standalone)    │
├─────────────────┤                  ├──────────────────┤
│ • 数据监控      │                  │ • 命令转发       │
│ • 技术分析      │                  │ • 响应处理       │
│ • 信号检测      │                  │ • 图表发送       │
│ • WebSocket服务 │                  │ • 用户交互       │
└─────────────────┘                  └──────────────────┘
```

## 🚀 快速启动

### 第一步：启动核心系统
```bash
# 方式1: 使用启动脚本
./start_core.sh

# 方式2: 直接运行
python3 main.py --config config/config_multi.yaml --log-level INFO
```

### 第二步：配置并启动Telegram客户端
```bash
# 1. 配置token（编辑 tg_setup.sh）
nano tg_setup.sh
# 设置实际的 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID

# 2. 启动Telegram客户端
./start_telegram_standalone.sh
```

## 📱 Telegram命令

通过Telegram机器人发送以下命令：

### 基本命令
- `/start` - 显示帮助信息
- `/okx <币种> <时间框架> <数量>` - 查询OKX交易所数据
- `/hype <币种> <时间框架> <数量>` - 查询Hyperliquid交易所数据

### 示例
```
/okx ETH 5m 200      # 获取ETH 5分钟图200个数据点
/hype BTC 15m 100    # 获取BTC 15分钟图100个数据点
/okx SOL 1h 50       # 获取SOL 1小时图50个数据点
```

## ⚙️ 配置文件

### 主配置: `config/config_multi.yaml`
- 监控目标设置
- 交易所配置
- 策略参数
- WebSocket设置

### Telegram配置: `tg_setup.sh`
```bash
export TELEGRAM_BOT_TOKEN="你的bot_token"
export TELEGRAM_CHAT_ID="你的chat_id"
```

## 📊 支持的技术指标

- **UTBot Alert**: 基于ATR的趋势信号
- **Smart MTF S/R**: 多时间框架支撑阻力分析
- **EMA趋势**: 多周期EMA趋势判断
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
# 测试WebSocket连接
python3 test_websocket_improved.py

# 检查token配置
echo $TELEGRAM_BOT_TOKEN
```

## 📁 项目结构

```
bot/
├── main.py                          # 核心系统入口
├── telegram_standalone.py           # 独立Telegram客户端
├── start_core.sh                   # 核心系统启动脚本
├── start_telegram_standalone.sh    # Telegram客户端启动脚本
├── tg_setup.sh                     # Telegram配置脚本
├── config/                         # 配置文件
├── core/                          # 核心监控逻辑
├── services/                      # 服务层
├── strategies/                    # 交易策略
├── indicators/                    # 技术指标
└── docs/                         # 详细文档
```

## 📚 详细文档

- [进程分离架构指南](PROCESS_SEPARATION_GUIDE.md)
- [图表生成说明](CHART_GENERATOR_README.md)
- [MTF EMA趋势指南](docs/MTF_EMA_TREND_GUIDE.md)
- [Smart MTF S/R指南](docs/SMART_MTF_SR_GUIDE.md)

## 🔄 系统状态检查

### 检查核心系统
- WebSocket服务器运行在端口10000
- 实时监控12个交易对（6个OKX + 6个Hyperliquid）
- 多线程数据处理

### 检查Telegram客户端
- 连接到核心系统WebSocket
- 响应用户命令
- 转发数据并生成图表

## ⚡ 性能优化

- 多线程数据获取
- WebSocket异步通信
- 图表数据缓存
- 智能重连机制

---

**维护者**: hw3579  
**更新时间**: 2025-07-26  
**架构版本**: 进程分离 v2.0
