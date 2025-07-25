#!/bin/bash
# Telegram 配置脚本
# 手动设置 Telegram Bot Token 和 Chat ID

# ========================================
# 🔐 敏感信息配置区域 - 请修改为你的实际值
# ========================================

# Telegram Bot Token (从 @BotFather 获取)
export TELEGRAM_BOT_TOKEN="8047454368:AAGCJT5hUXXHwOds_kIwyqB_aZx_bjVeQUw"

# Telegram Chat ID (支持多个，用逗号分隔)
export TELEGRAM_CHAT_ID="5330798367"

# WebSocket 配置
export WEBSOCKET_HOST="localhost"
export WEBSOCKET_PORT="10000"

# ========================================
# 验证配置
# ========================================

# 检查是否设置了必要的环境变量
if [[ "$TELEGRAM_BOT_TOKEN" == "你的_BOT_TOKEN_这里" ]]; then
    echo "❌ 请在脚本中设置正确的 TELEGRAM_BOT_TOKEN"
    exit 1
fi

if [[ "$TELEGRAM_CHAT_ID" == "你的_CHAT_ID_这里" ]]; then
    echo "❌ 请在脚本中设置正确的 TELEGRAM_CHAT_ID"
    exit 1
fi

# 显示配置信息（隐藏敏感信息）
echo "🤖 Telegram 配置已加载:"
echo "📍 Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}...***"
echo "💬 Chat ID: $TELEGRAM_CHAT_ID"
echo "📡 WebSocket: ws://$WEBSOCKET_HOST:$WEBSOCKET_PORT"
echo ""
echo "✅ 配置验证通过，环境变量已设置"
echo ""

# 如果有参数传入，执行相应的命令
if [[ $# -gt 0 ]]; then
    echo "🚀 执行命令: $*"
    exec "$@"
else
    echo "💡 使用方法:"
    echo "  source ./tg_setup.sh     # 仅加载环境变量"
    echo "  ./start.sh               # 启动多线程监控系统"
fi
