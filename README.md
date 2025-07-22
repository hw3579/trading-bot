# 🤖 交易监控系统

基于模块化架构的多交易所交易信号监控系统，支持UT Bot v5策略。

## 🚀 快速启动

### 1. 配置Telegram（可选）
```bash
# 编辑配置脚本
nano tg_setup.sh

# 设置你的Bot Token和Chat ID
export TELEGRAM_BOT_TOKEN="你的_BOT_TOKEN"
export TELEGRAM_CHAT_ID="你的_CHAT_ID"
```

### 2. 启动系统
```bash
# 交互式启动（推荐）
./start_multi.sh

# 或者直接启动新架构
source ./tg_setup.sh  # 如果需要Telegram通知
python main.py --multi
```

## 📁 项目结构

```
├── main.py              # 主启动文件
├── start_multi.sh       # 交互式启动脚本  
├── tg_setup.sh         # Telegram配置脚本
├── config/             # 配置文件
├── core/               # 核心监控模块
├── services/           # 服务模块（WebSocket、Telegram）
├── strategies/         # 交易策略模块
├── indicators/         # 技术指标
└── data/              # 数据目录（okx、hyperliquid）
```

## ✨ 核心功能

- 🔄 **模块化架构**：服务解耦，易于维护和扩展
- 🧵 **多线程支持**：高效并发处理多个交易对
- 📡 **WebSocket服务**：实时数据推送
- 📱 **Telegram通知**：交易信号即时推送
- 🔁 **智能重试**：API请求失败自动重试
- 📊 **多交易所**：支持OKX、Hyperliquid等
- 📈 **策略插件**：UT Bot v5策略，易于扩展

## 🔧 配置说明

编辑 `config/config_multi.yaml` 进行配置：

- 交易所设置
- 监控目标（交易对、时间框架）  
- 重试机制参数
- WebSocket和Telegram配置

## 📖 详细文档

查看 [`STARTUP_GUIDE.md`](STARTUP_GUIDE.md) 获取详细的使用说明。

---

🎯 **一键启动：`./start_multi.sh` → 选择模式1 → 完成！**
