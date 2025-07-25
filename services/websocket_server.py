"""WebSocket服务器模块
基于原有的message_server.py重构
"""

import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Set, Dict, Any
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketServer:
    """WebSocket服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 10000, 
                 ipv6_enabled: bool = False, bind_both: bool = True):
        self.host = host
        self.port = port
        self.ipv6_enabled = ipv6_enabled
        self.bind_both = bind_both
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None
        self.running = False
        self._lock = threading.Lock()
        
    async def register_client(self, websocket: WebSocketServerProtocol):
        """注册客户端连接"""
        with self._lock:
            self.clients.add(websocket)
        
        # 发送欢迎消息
        welcome_msg = {
            "type": "welcome",
            "message": f"WebSocket连接成功，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "timestamp": datetime.now().isoformat(),
            "client_count": len(self.clients)
        }
        await self.send_to_client(websocket, welcome_msg)
        logger.info(f"✅ 客户端已连接，当前连接数: {len(self.clients)}")
    
    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """注销客户端连接"""
        with self._lock:
            self.clients.discard(websocket)
        logger.info(f"❌ 客户端已断开，当前连接数: {len(self.clients)}")
    
    async def send_to_client(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]):
        """发送消息给单个客户端"""
        try:
            await websocket.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            await self.unregister_client(websocket)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """广播消息给所有客户端"""
        if not self.clients:
            return
        
        # 创建消息副本，避免并发修改
        clients_copy = self.clients.copy()
        
        # 并发发送消息
        tasks = []
        for client in clients_copy:
            # 检查连接状态 - 新版websockets库的兼容性修复
            try:
                # 检查连接是否仍然开放
                if hasattr(client, 'closed'):
                    # 旧版本API
                    if not client.closed:
                        tasks.append(self.send_to_client(client, message))
                elif hasattr(client, 'state'):
                    # 新版本API - 检查连接状态
                    from websockets.protocol import State
                    if client.state == State.OPEN:
                        tasks.append(self.send_to_client(client, message))
                else:
                    # 直接尝试发送，在send_to_client中处理异常
                    tasks.append(self.send_to_client(client, message))
            except Exception as e:
                logger.debug(f"检查客户端状态时出错: {e}")
                # 如果无法检查状态，直接尝试发送
                tasks.append(self.send_to_client(client, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    # 这里可以处理客户端发送的消息
                    logger.debug(f"收到客户端消息: {data}")
                except json.JSONDecodeError:
                    logger.warning(f"收到无效JSON消息: {message}")
                except Exception as e:
                    logger.error(f"处理客户端消息错误: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"客户端处理错误: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def start(self):
        """启动WebSocket服务器"""
        try:
            if self.ipv6_enabled:
                if self.bind_both:
                    # 同时绑定IPv4和IPv6
                    self.server = await websockets.serve(
                        self.handle_client, 
                        self.host, 
                        self.port,
                        family=0  # 让系统自动选择
                    )
                else:
                    # 只绑定IPv6
                    import socket
                    self.server = await websockets.serve(
                        self.handle_client, 
                        self.host, 
                        self.port,
                        family=socket.AF_INET6
                    )
            else:
                # 只绑定IPv4
                import socket
                self.server = await websockets.serve(
                    self.handle_client, 
                    self.host, 
                    self.port,
                    family=socket.AF_INET
                )
            
            self.running = True
            
            protocol_info = ""
            if self.ipv6_enabled and self.bind_both:
                protocol_info = " (IPv4 + IPv6)"
            elif self.ipv6_enabled:
                protocol_info = " (IPv6)"
            else:
                protocol_info = " (IPv4)"
            
            logger.info(f"✅ WebSocket服务器已启动{protocol_info}: ws://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"❌ WebSocket服务器启动失败: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket服务器"""
        if self.server:
            self.running = False
            self.server.close()
            await self.server.wait_closed()
            
            # 关闭所有客户端连接
            if self.clients:
                close_tasks = []
                for client in self.clients.copy():
                    try:
                        # 检查客户端是否有close方法
                        if hasattr(client, 'close'):
                            close_tasks.append(client.close())
                        elif hasattr(client, 'wait_closed'):
                            # 如果客户端已经有wait_closed方法，说明已经在关闭
                            pass
                    except Exception as e:
                        logger.debug(f"关闭客户端连接时出错: {e}")
                
                if close_tasks:
                    await asyncio.gather(*close_tasks, return_exceptions=True)
            
            logger.info("WebSocket服务器已停止")
    
    def send_message_sync(self, message: Dict[str, Any]):
        """同步发送消息（用于从其他线程调用）"""
        if not self.running:
            return
        
        try:
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环正在运行，创建任务
                asyncio.create_task(self.broadcast_message(message))
            else:
                # 如果循环未运行，直接运行
                loop.run_until_complete(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"同步发送消息失败: {e}")

# 全局WebSocket服务器实例
_websocket_server: WebSocketServer = None

def get_websocket_server() -> WebSocketServer:
    """获取WebSocket服务器实例"""
    return _websocket_server

def set_websocket_server(server: WebSocketServer):
    """设置WebSocket服务器实例"""
    global _websocket_server
    _websocket_server = server

def send_message(message: Dict[str, Any]):
    """发送消息到WebSocket客户端（兼容原有接口）"""
    server = get_websocket_server()
    if server:
        server.send_message_sync(message)

# 兼容原有接口的函数
async def start_message_server(host: str = "0.0.0.0", port: int = 10000, 
                              ipv6_enabled: bool = False, bind_both: bool = True) -> WebSocketServer:
    """启动消息服务器（兼容原有接口）"""
    server = WebSocketServer(host, port, ipv6_enabled, bind_both)
    await server.start()
    set_websocket_server(server)
    return server
