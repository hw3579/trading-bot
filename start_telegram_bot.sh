#!/bin/bash
"""
启动Telegram图表机器人
"""

echo "🤖 启动Telegram技术分析图表机器人"
echo "=================================="

# 检查环境变量
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ 错误: 请设置环境变量 TELEGRAM_BOT_TOKEN"
    echo "💡 设置方法: export TELEGRAM_BOT_TOKEN='your_bot_token'"
    exit 1
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "❌ 错误: 请设置环境变量 TELEGRAM_CHAT_ID"
    echo "💡 设置方法: export TELEGRAM_CHAT_ID='your_chat_id'"
    exit 1
fi

echo "✅ 环境变量检查通过"
echo "🤖 Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "👥 Chat ID: $TELEGRAM_CHAT_ID"
echo ""

# 检查Python依赖
echo "🔍 检查依赖..."
python3 -c "
import sys
missing = []

try:
    import telegram
    print('✅ python-telegram-bot')
except ImportError:
    missing.append('python-telegram-bot')
    print('❌ python-telegram-bot')

try:
    import matplotlib
    print('✅ matplotlib')
except ImportError:
    missing.append('matplotlib')
    print('❌ matplotlib')

try:
    import pandas
    print('✅ pandas')
except ImportError:
    missing.append('pandas')
    print('❌ pandas')

try:
    import talib
    print('✅ talib')
except ImportError:
    missing.append('talib')
    print('❌ talib')

if missing:
    print(f'\\n❌ 缺少依赖: {missing}')
    print('💡 安装方法: pip install ' + ' '.join(missing))
    sys.exit(1)
else:
    print('\\n✅ 所有依赖已安装')
"

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo "🚀 启动机器人..."
echo "💡 按 Ctrl+C 停止"
echo ""

# 启动机器人
python3 services/telegram_chart_bot.py
