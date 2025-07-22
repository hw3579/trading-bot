#!/bin/bash
# 简化启动脚本 - 默认多线程+TG通知

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 启动交易监控系统 (多线程+TG通知)${NC}"
echo "=================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 未安装${NC}"
    exit 1
fi

# 检查依赖包
echo -e "${YELLOW}📦 检查依赖包...${NC}"
if ! python3 -c "import ccxt, pandas, websockets" &> /dev/null; then
    echo -e "${YELLOW}⚠️  正在安装缺失的依赖包...${NC}"
    pip3 install -r requirements.txt
fi

# 检查Telegram配置
echo -e "${YELLOW}🤖 检查Telegram配置...${NC}"
if [[ -z "$TELEGRAM_BOT_TOKEN" || "$TELEGRAM_BOT_TOKEN" == "你的_BOT_TOKEN_这里" ]]; then
    echo -e "${RED}❌ 请先配置Telegram Bot Token${NC}"
    echo -e "${YELLOW}💡 使用方法：${NC}"
    echo "1. 编辑 tg_setup.sh，设置你的BOT_TOKEN和CHAT_ID"
    echo "2. 运行: source ./tg_setup.sh"
    echo "3. 再次运行: ./start.sh"
    exit 1
fi

if [[ -z "$TELEGRAM_CHAT_ID" || "$TELEGRAM_CHAT_ID" == "你的_CHAT_ID_这里" ]]; then
    echo -e "${RED}❌ 请先配置Telegram Chat ID${NC}"
    echo -e "${YELLOW}💡 使用方法：${NC}"
    echo "1. 编辑 tg_setup.sh，设置你的BOT_TOKEN和CHAT_ID"
    echo "2. 运行: source ./tg_setup.sh"
    echo "3. 再次运行: ./start.sh"
    exit 1
fi

echo -e "${GREEN}✅ Telegram配置检查通过${NC}"
echo -e "${BLUE}📍 Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}...***${NC}"
echo -e "${BLUE}💬 Chat ID: $TELEGRAM_CHAT_ID${NC}"

# 启动系统
echo ""
echo -e "${GREEN}🔥 启动多线程监控系统...${NC}"
echo "=================================="

# 启动主程序（多线程模式）
python3 main.py --multi

echo ""
echo -e "${YELLOW}👋 程序已退出${NC}"
