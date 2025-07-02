#!/usr/bin/env python3
"""
增强版带桌面通知功能的客户端
显示交易所、币种、时间周期等详细信息
需要安装: pip install plyer colorama
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Any

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    print("⚠️  plyer 未安装，桌面通知功能不可用")
    print("安装命令: pip install plyer")

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)  # 自动重置颜色
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    print("⚠️  colorama 未安装，彩色输出不可用")
    print("安装命令: pip install colorama")

class EnhancedNotifyClient:
    """增强版带通知的客户端"""
    
    def __init__(self, uri: str):
        self.uri = uri
        self.running = True
        self.connected_count = 0
        self.message_count = 0
        self.signal_count = 0
        self.start_time = datetime.now()
        
    def get_color_text(self, text: str, color: str = "white") -> str:
        """获取彩色文本"""
        if not COLORS_AVAILABLE:
            return text
            
        color_map = {
            "red": Fore.RED,
            "green": Fore.GREEN,
            "yellow": Fore.YELLOW,
            "blue": Fore.BLUE,
            "magenta": Fore.MAGENTA,
            "cyan": Fore.CYAN,
            "white": Fore.WHITE,
            "bright_red": Fore.LIGHTRED_EX,
            "bright_green": Fore.LIGHTGREEN_EX,
            "bright_yellow": Fore.LIGHTYELLOW_EX,
        }
        return f"{color_map.get(color, Fore.WHITE)}{text}{Style.RESET_ALL}"
    
    def format_signal_message(self, data: Dict[str, Any]) -> str:
        """格式化信号消息"""
        signal_type = data.get('signal_type', 'UNKNOWN')
        exchange = data.get('exchange', 'N/A').upper()
        symbol = data.get('symbol', 'N/A')
        timeframe = data.get('timeframe', 'N/A')
        price = data.get('price', 0)
        timestamp = data.get('timestamp', 'N/A')
        thread = data.get('thread', 'N/A')
        
        # 根据信号类型选择颜色和图标
        if signal_type == "BUY":
            color = "bright_green"
            icon = "🟢"
            bg_icon = "📈"
        elif signal_type == "SELL":
            color = "bright_red"
            icon = "🔴"
            bg_icon = "📉"
        else:
            color = "yellow"
            icon = "⚪"
            bg_icon = "📊"
        
        # 格式化价格
        if isinstance(price, (int, float)) and price > 0:
            if price >= 1:
                price_str = f"{price:,.4f}"
            else:
                price_str = f"{price:.8f}"
        else:
            price_str = "N/A"
        
        # 构建详细信息
        header = self.get_color_text(f"{icon} {signal_type} SIGNAL {bg_icon}", color)
        exchange_info = self.get_color_text(f"交易所: {exchange}", "cyan")
        symbol_info = self.get_color_text(f"币种: {symbol}", "magenta")
        timeframe_info = self.get_color_text(f"周期: {timeframe}", "blue")
        price_info = self.get_color_text(f"价格: {price_str}", "yellow")
        time_info = self.get_color_text(f"时间: {timestamp}", "white")
        thread_info = self.get_color_text(f"线程: {thread}", "white")
        
        return (
            f"{header}\n"
            f"  ├─ {exchange_info}\n"
            f"  ├─ {symbol_info}\n"
            f"  ├─ {timeframe_info}\n"
            f"  ├─ {price_info}\n"
            f"  ├─ {time_info}\n"
            f"  └─ {thread_info}"
        )
    
    def format_general_message(self, data: Dict[str, Any]) -> str:
        """格式化一般消息"""
        level = data.get('level', 'INFO')
        message = data.get('message', '')
        timestamp = data.get('timestamp', '')
        source = data.get('source', '')
        thread = data.get('thread', '')
        
        # 根据日志级别选择颜色
        level_colors = {
            "ERROR": "bright_red",
            "WARNING": "bright_yellow", 
            "INFO": "bright_green",
            "DEBUG": "cyan"
        }
        
        level_icons = {
            "ERROR": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
            "DEBUG": "🔍"
        }
        
        color = level_colors.get(level, "white")
        icon = level_icons.get(level, "📝")
        
        level_text = self.get_color_text(f"{icon} [{level}]", color)
        message_text = self.get_color_text(message, "white")
        
        details = []
        if source:
            details.append(self.get_color_text(f"来源: {source}", "cyan"))
        if thread:
            details.append(self.get_color_text(f"线程: {thread}", "cyan"))
        
        result = f"{level_text} {message_text}"
        if details:
            result += f"\n  └─ {' | '.join(details)}"
            
        return result
    
    def show_desktop_notification(self, signal_data: Dict[str, Any]):
        """显示桌面通知"""
        if not NOTIFICATIONS_AVAILABLE:
            return
            
        signal_type = signal_data.get('signal_type', 'SIGNAL')
        exchange = signal_data.get('exchange', '').upper()
        symbol = signal_data.get('symbol', '')
        timeframe = signal_data.get('timeframe', '')
        price = signal_data.get('price', 0)
        
        # 格式化价格
        if isinstance(price, (int, float)) and price > 0:
            if price >= 1:
                price_str = f"{price:,.4f}"
            else:
                price_str = f"{price:.8f}"
        else:
            price_str = "N/A"
        
        # 构建通知内容
        title = f"{signal_type} 信号 - {exchange}"
        message = f"{symbol} ({timeframe})\n价格: {price_str}"
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="交易信号监控",
                timeout=15,  # 延长显示时间
                toast=True   # Windows 上使用 toast 通知
            )
            print(self.get_color_text("🔔 桌面通知已发送", "green"))
        except Exception as e:
            print(self.get_color_text(f"❌ 桌面通知发送失败: {e}", "red"))
    
    def show_statistics(self):
        """显示统计信息"""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]  # 去掉微秒
        
        stats_header = self.get_color_text("📊 客户端统计", "bright_yellow")
        
        stats = [
            f"运行时长: {uptime_str}",
            f"连接次数: {self.connected_count}",
            f"接收消息: {self.message_count}",
            f"交易信号: {self.signal_count}"
        ]
        
        print(f"\n{stats_header}")
        for stat in stats:
            print(f"  ├─ {self.get_color_text(stat, 'cyan')}")
        print()
    
    async def connect(self):
        """连接服务器"""
        while self.running:
            try:
                print(self.get_color_text(f"🔌 正在连接服务器: {self.uri}", "yellow"))
                
                async with websockets.connect(self.uri) as websocket:
                    self.connected_count += 1
                    connect_msg = self.get_color_text(f"✅ 已连接到服务器 (第{self.connected_count}次)", "bright_green")
                    print(connect_msg)
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self.handle_message(data)
                        except json.JSONDecodeError as e:
                            error_msg = self.get_color_text(f"❌ JSON解析错误: {e}", "red")
                            print(error_msg)
                        except Exception as e:
                            error_msg = self.get_color_text(f"❌ 消息处理错误: {e}", "red")
                            print(error_msg)
                            
            except websockets.exceptions.ConnectionClosed:
                print(self.get_color_text("🔌 连接已断开", "yellow"))
            except Exception as e:
                error_msg = self.get_color_text(f"❌ 连接错误: {e}", "red")
                print(error_msg)
            
            if self.running:
                print(self.get_color_text("⏳ 5秒后重新连接...", "yellow"))
                await asyncio.sleep(5)
    
    async def handle_message(self, data: Dict[str, Any]):
        """处理消息"""
        self.message_count += 1
        
        msg_type = data.get('type', '')
        level = data.get('level', '')
        message = data.get('message', '')
        signal_data = data.get('data', {})
        
        # 添加时间戳
        local_time = datetime.now().strftime("%H:%M:%S")
        timestamp_text = self.get_color_text(f"[{local_time}]", "white")
        
        # 检查是否为交易信号
        is_signal = (msg_type == "notification" and 
                    level == "WARNING" and 
                    "SIGNAL" in message and 
                    signal_data.get('signal_type'))
        
        if is_signal:
            self.signal_count += 1
            print(f"\n{timestamp_text}")
            print(self.format_signal_message(signal_data))
            print("─" * 50)
            
            # 显示桌面通知
            self.show_desktop_notification(signal_data)
            
        else:
            # 处理其他类型的消息
            if msg_type == "welcome":
                welcome_msg = self.get_color_text("🎉 " + message, "bright_green")
                print(f"{timestamp_text} {welcome_msg}")
            else:
                print(f"{timestamp_text}")
                print(self.format_general_message(data))
        
        # 每100条消息显示一次统计
        if self.message_count % 100 == 0:
            self.show_statistics()
    
    def stop(self):
        """停止客户端"""
        self.running = False
        print(self.get_color_text("\n👋 正在停止客户端...", "yellow"))
        self.show_statistics()

async def main():
    """主函数"""
    # 可以通过环境变量或参数指定服务器地址
    import os
    server_host = os.getenv("WEBSOCKET_HOST", "localhost")
    server_port = os.getenv("WEBSOCKET_PORT", "10000")
    server_uri = f"ws://{server_host}:{server_port}"
    
    client = EnhancedNotifyClient(server_uri)
    
    # 显示启动信息
    print("=" * 60)
    print(client.get_color_text("🚀 增强版交易信号客户端", "bright_yellow"))
    print("=" * 60)
    print(f"📡 服务器地址: {client.get_color_text(server_uri, 'cyan')}")
    print(f"🔔 桌面通知: {client.get_color_text('启用' if NOTIFICATIONS_AVAILABLE else '禁用', 'green' if NOTIFICATIONS_AVAILABLE else 'red')}")
    print(f"🎨 彩色输出: {client.get_color_text('启用' if COLORS_AVAILABLE else '禁用', 'green' if COLORS_AVAILABLE else 'red')}")
    print("📱 将显示详细的交易信号信息")
    print("⌨️  按 Ctrl+C 停止客户端")
    print("=" * 60)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        client.stop()

if __name__ == "__main__":
    asyncio.run(main())