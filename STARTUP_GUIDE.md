# 🚀 启动脚本使用说明

## 📋 文件说明

### 1. `tg_setup.sh` - Telegram配置脚本
用于设置Telegram环境变量的bash脚本，需要手动配置敏感信息。

### 2. `start.sh` - 简化启动脚本
默认启动多线程监控系统，无需选择选项，一键启动。

### 3. `id.txt` - 测试用文件
保留作为参考，实际使用中不会读取此文件。

## ⚙️ 配置步骤

### 第一步：配置Telegram信息

编辑 `tg_setup.sh` 文件，修改以下内容：

```bash
# 将 "你的_BOT_TOKEN_这里" 替换为实际的Bot Token
export TELEGRAM_BOT_TOKEN="你的实际TOKEN"

# 将 "你的_CHAT_ID_这里" 替换为实际的Chat ID（支持多个，逗号分隔）
export TELEGRAM_CHAT_ID="你的实际CHAT_ID"
```

### 第二步：加载环境变量

```bash
# 仅加载环境变量到当前shell
source ./tg_setup.sh

# 或者加载环境变量并直接运行程序
./tg_setup.sh python main.py --multi
```

## 🚀 启动方式

### 方式一：使用简化启动脚本（推荐）

```bash
./start.sh
```

自动启动多线程+Telegram通知模式，无需选择选项。

### 方式二：直接启动

```bash
# 新架构多线程模式
source ./tg_setup.sh
python main.py --config config/config_multi.yaml --multi

# 新架构单线程模式
source ./tg_setup.sh
python main.py --config config/config.yaml

# 仅WebSocket服务器
python -c "
import asyncio
from services.websocket_server import WebSocketServer

async def main():
    server = WebSocketServer('0.0.0.0', 10000)
    await server.start()
    while True: await asyncio.sleep(1)

asyncio.run(main())
"
```

### 方式三：一键启动（推荐）

```bash
# 配置并启动简化模式
./tg_setup.sh ./start.sh
```

## 🛠️ 高级用法

### 自定义WebSocket配置

编辑 `tg_setup.sh` 中的WebSocket配置：

```bash
export WEBSOCKET_HOST="0.0.0.0"    # 修改监听地址
export WEBSOCKET_PORT="8080"       # 修改监听端口
```

### 多Chat ID配置

支持向多个Telegram用户发送通知：

```bash
export TELEGRAM_CHAT_ID="5330798367,1234567890,9876543210"
```

### 环境变量检查

```bash
# 检查环境变量是否正确设置
echo "Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}...***"
echo "Chat IDs: $TELEGRAM_CHAT_ID"
echo "WebSocket: ws://$WEBSOCKET_HOST:$WEBSOCKET_PORT"
```

## 🔧 故障排除

### 1. 权限问题
```bash
chmod +x tg_setup.sh start_multi.sh
```

### 2. Python依赖问题
```bash
pip3 install ccxt pandas numpy pyyaml websockets python-telegram-bot
```

### 3. 配置文件问题
```bash
# 检查配置文件是否存在
ls -la config/config_multi.yaml
```

### 4. Telegram连接问题
- 检查Bot Token是否正确
- 检查Chat ID是否正确
- 确保Bot已启动（与@BotFather对话）

## 📝 示例工作流

```bash
# 1. 配置Telegram信息（一次性）
nano tg_setup.sh  # 编辑配置

# 2. 加载环境变量
source ./tg_setup.sh

# 3. 启动系统
./start.sh

# 系统自动启动多线程+Telegram通知模式！
```

---

🎯 **快速启动：编辑 `tg_setup.sh` → 运行 `source ./tg_setup.sh` → 运行 `./start.sh` → 完成！**
