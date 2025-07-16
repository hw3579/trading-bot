#!/bin/bash
# Telegram机器人配置文件
# 使用方法: source telegram_config.sh

# Telegram Bot Token (从 @BotFather 获取)
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

# Telegram Chat ID (可以是个人ID或群组ID)
export TELEGRAM_CHAT_ID="YOUR_CHAT_ID_HERE"

# WebSocket 服务器配置
export WEBSOCKET_HOST="localhost"
export WEBSOCKET_PORT="10000"

echo "✅ Telegram配置已加载"
echo "📱 Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "💬 Chat ID: $TELEGRAM_CHAT_ID"
echo "📡 WebSocket: ws://$WEBSOCKET_HOST:$WEBSOCKET_PORT"