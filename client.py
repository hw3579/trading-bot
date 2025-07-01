#!/usr/bin/env python3
"""
带桌面通知功能的客户端
需要安装: pip install plyer
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    print("⚠️  plyer 未安装，桌面通知功能不可用")
    print("安装命令: pip install plyer")

class NotifyClient:
    """带通知的客户端"""
    
    def __init__(self, uri: str):
        self.uri = uri
        self.running = True
        
    async def connect(self):
        """连接服务器"""
        while self.running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    print(f"✅ 已连接到服务器: {self.uri}")
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self.handle_message(data)
                        except json.JSONDecodeError:
                            print(f"❌ 无效消息: {message}")
                            
            except Exception as e:
                print(f"❌ 连接错误: {e}")
                await asyncio.sleep(5)
    
    async def handle_message(self, data):
        """处理消息"""
        msg_type = data.get('type', '')
        level = data.get('level', '')
        message = data.get('message', '')
        signal_data = data.get('data', {})
        
        # 控制台输出
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
        # 交易信号桌面通知
        if (msg_type == "notification" and 
            level == "WARNING" and 
            "SIGNAL" in message and 
            NOTIFICATIONS_AVAILABLE):
            
            signal_type = signal_data.get('signal_type', 'SIGNAL')
            symbol = signal_data.get('symbol', '')
            price = signal_data.get('price', '')
            
            notification.notify(
                title=f"{signal_type} 信号",
                message=f"{symbol} @ {price}",
                app_name="交易信号监控",
                timeout=10
            )
    
    def stop(self):
        self.running = False

async def main():
    """主函数"""
    server_uri = "ws://localhost:10000"
    client = NotifyClient(server_uri)
    
    print("🔔 带通知功能的客户端启动")
    print("📱 将显示桌面通知（如果支持）")
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        print("\n👋 客户端已停止")
        client.stop()

if __name__ == "__main__":
    asyncio.run(main())