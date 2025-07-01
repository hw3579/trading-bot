#!/usr/bin/env python3
"""
独立的 WebSocket 消息推送服务器
"""

import asyncio
import websockets
import json
import threading
import logging
from datetime import datetime
from typing import Set
import queue

class MessageBroadcastServer:
    """消息广播服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 10000):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.loop = None
        self.message_queue = queue.Queue()
        self.running = False
        
        # 设置日志
        self.logger = logging.getLogger('WebSocketServer')
        
    async def handle_client(self, websocket):
        """处理客户端连接 - 适配 websockets 13.0+"""
        self.clients.add(websocket)
        self.logger.info(f"✅ 客户端连接: {websocket.remote_address}")
        
        try:
            # 发送欢迎消息
            welcome_msg = {
                "type": "welcome",
                "message": "连接成功，开始接收信号推送",
                "timestamp": datetime.utcnow().isoformat(),
                "server_version": "v1.0",
                "connected_clients": len(self.clients)
            }
            await websocket.send(json.dumps(welcome_msg, ensure_ascii=False))
            
            # 保持连接活跃，等待消息或断开
            async for message in websocket:
                # 处理客户端发送的消息（心跳包等）
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        pong_msg = {
                            "type": "pong", 
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        await websocket.send(json.dumps(pong_msg))
                except:
                    pass  # 忽略无效消息
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"🔌 客户端正常断开: {websocket.remote_address}")
        except Exception as e:
            self.logger.error(f"❌ 客户端连接错误: {e}")
        finally:
            # 清理客户端
            self.clients.discard(websocket)
            self.logger.info(f"👋 客户端已移除: {websocket.remote_address}, 当前连接数: {len(self.clients)}")
    
    async def broadcast_message(self, message: dict):
        """广播消息给所有连接的客户端"""
        if not self.clients:
            self.logger.debug("没有连接的客户端，跳过广播")
            return
            
        # 添加服务器信息
        message.update({
            "server_timestamp": datetime.utcnow().isoformat(),
            "client_count": len(self.clients)
        })
        
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected = []
        
        for client in list(self.clients):
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client)
            except Exception as e:
                self.logger.warning(f"发送消息失败: {e}")
                disconnected.append(client)
        
        # 移除断开的连接
        for client in disconnected:
            self.clients.discard(client)
            
        if disconnected:
            self.logger.info(f"清理了 {len(disconnected)} 个断开的连接")
    
    def send_message_sync(self, message: dict):
        """同步发送消息接口（供外部调用）"""
        if not self.running:
            return
            
        if self.loop and not self.loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.broadcast_message(message), 
                    self.loop
                )
                future.result(timeout=2.0)  # 2秒超时
            except asyncio.TimeoutError:
                self.logger.warning("消息发送超时")
            except Exception as e:
                self.logger.error(f"发送消息异常: {e}")
    
    async def message_processor(self):
        """消息队列处理器"""
        while self.running:
            try:
                # 非阻塞检查队列
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"消息处理器错误: {e}")
    
    async def start_server_async(self):
        """异步启动服务器"""
        try:
            # 启动 WebSocket 服务器
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port
            )
            
            self.logger.info(f"🚀 WebSocket 服务器启动成功: ws://{self.host}:{self.port}")
            self.running = True
            
            # 启动消息处理器
            message_task = asyncio.create_task(self.message_processor())
            
            # 等待服务器关闭
            await self.server.wait_closed()
            
            # 清理
            message_task.cancel()
            
        except Exception as e:
            self.logger.error(f"服务器启动失败: {e}")
            raise
    
    def start_server(self):
        """启动 WebSocket 服务器（在新线程中）"""
        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            try:
                self.loop.run_until_complete(self.start_server_async())
            except Exception as e:
                self.logger.error(f"服务器线程异常: {e}")
            finally:
                self.loop.close()
        
        server_thread = threading.Thread(target=run_server, daemon=True, name="WebSocketServer")
        server_thread.start()
        
        # 等待服务器启动
        import time
        time.sleep(1)
        
        return server_thread
    
    def stop_server(self):
        """停止服务器"""
        self.running = False
        if self.server:
            self.server.close()
    
    def get_status(self) -> dict:
        """获取服务器状态"""
        return {
            "running": self.running,
            "client_count": len(self.clients),
            "host": self.host,
            "port": self.port,
            "loop_running": self.loop and not self.loop.is_closed() if self.loop else False
        }

# 全局服务器实例
_global_server = None

def get_message_server(host: str = "0.0.0.0", port: int = 10000) -> MessageBroadcastServer:
    """获取全局消息服务器实例"""
    global _global_server
    if _global_server is None:
        _global_server = MessageBroadcastServer(host, port)
    return _global_server

def start_message_server(host: str = "0.0.0.0", port: int = 10000) -> MessageBroadcastServer:
    """启动消息服务器"""
    server = get_message_server(host, port)
    if not server.running:
        server.start_server()
    return server

def send_message(message: dict):
    """发送消息到所有连接的客户端"""
    global _global_server
    if _global_server and _global_server.running:
        _global_server.send_message_sync(message)

if __name__ == "__main__":
    # 独立运行服务器
    import logging
    logging.basicConfig(level=logging.INFO)
    
    server = start_message_server("0.0.0.0", 10000)
    
    print("WebSocket 消息服务器已启动")
    print("按 Ctrl+C 停止服务器")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止服务器...")
        server.stop_server()