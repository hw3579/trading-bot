"""WebSocket服务器模块
基于原有的message_server.py重构
"""

import asyncio
import websockets
from websockets import WebSocketServerProtocol
import json
import logging
from typing import Dict, Any, Set
import socket
import queue
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 10000):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.running = False
        self.server = None
        # 添加线程安全队列来处理来自工作线程的消息
        self.message_queue = queue.Queue()
        self._queue_processor_task = None
        
    async def register_client(self, websocket: WebSocketServerProtocol):
        """注册客户端连接"""
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
        """启动WebSocket服务器（兼容接口）"""
        return await self.start_server()

    async def start_server(self):
        """启动WebSocket服务器"""
        try:
            self.running = True
            
            # 启动队列处理器
            self._queue_processor_task = asyncio.create_task(self._process_message_queue())
            
            # 尝试IPv4和IPv6
            try:
                self.server = await websockets.serve(
                    self.handle_client,
                    self.host,
                    self.port,
                    family=socket.AF_UNSPEC  # 支持IPv4和IPv6
                )
                logger.info(f"WebSocket服务器启动在 {self.host}:{self.port}")
            except Exception as e:
                logger.warning(f"无法绑定到 {self.host}:{self.port}: {e}")
                # 尝试只使用IPv4
                self.server = await websockets.serve(
                    self.handle_client,
                    self.host,
                    self.port,
                    family=socket.AF_INET
                )
                logger.info(f"WebSocket服务器启动在 {self.host}:{self.port} (仅IPv4)")
            
            return self.server
        except Exception as e:
            logger.error(f"启动WebSocket服务器失败: {e}")
            self.running = False
            raise

    async def _process_message_queue(self):
        """处理消息队列中的消息"""
        while self.running:
            try:
                # 非阻塞地检查队列
                try:
                    message = self.message_queue.get_nowait()
                    await self.broadcast_message(message)
                    self.message_queue.task_done()
                except queue.Empty:
                    # 队列为空，稍等片刻
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"处理消息队列失败: {e}")
                await asyncio.sleep(0.1)
    
    async def stop(self):
        """停止WebSocket服务器"""
        self.running = False
        
        # 停止队列处理器
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
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
            # 将消息放入队列，由主事件循环的队列处理器来处理
            self.message_queue.put(message)
            logger.debug(f"消息已加入队列: {message.get('type', '未知类型')}")
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
    server = WebSocketServer(host, port)
    await server.start()
    set_websocket_server(server)
    return server
    return server
