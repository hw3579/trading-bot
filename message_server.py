#!/usr/bin/env python3
"""
独立的 WebSocket 消息推送服务器 - 支持 IPv4/IPv6
"""

import asyncio
import websockets
import json
import threading
import logging
import socket
from datetime import datetime
from typing import Set, List, Tuple
import queue

class MessageBroadcastServer:
    """消息广播服务器 - 支持 IPv4/IPv6"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 10000, 
                 ipv6_enabled: bool = False, bind_both: bool = True):
        self.host = host
        self.port = port
        self.ipv6_enabled = ipv6_enabled
        self.bind_both = bind_both
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.servers: List = []  # 支持多个服务器实例（IPv4 + IPv6）
        self.loop = None
        self.message_queue = queue.Queue()
        self.running = False
        
        # 设置日志
        self.logger = logging.getLogger('WebSocketServer')
        
        # 验证 IPv6 支持
        if self.ipv6_enabled and not self._check_ipv6_support():
            self.logger.warning("系统不支持 IPv6，将禁用 IPv6 功能")
            self.ipv6_enabled = False
    
    def _check_ipv6_support(self) -> bool:
        """检查系统是否支持 IPv6"""
        try:
            test_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            test_socket.close()
            return True
        except (socket.error, OSError):
            return False
    
    def _get_bind_addresses(self) -> List[Tuple[str, int, int]]:
        """
        获取绑定地址列表
        返回格式: [(host, port, family), ...]
        """
        addresses = []
        
        if self.ipv6_enabled:
            if self.bind_both:
                # 同时绑定 IPv4 和 IPv6
                addresses.append((self.host, self.port, socket.AF_INET))
                ipv6_host = "::" if self.host == "0.0.0.0" else self.host
                addresses.append((ipv6_host, self.port, socket.AF_INET6))
            else:
                # 仅 IPv6
                ipv6_host = "::" if self.host == "0.0.0.0" else self.host
                addresses.append((ipv6_host, self.port, socket.AF_INET6))
        else:
            # 仅 IPv4
            addresses.append((self.host, self.port, socket.AF_INET))
        
        return addresses
    
    async def handle_client(self, websocket):
        """处理客户端连接 - 适配 websockets 13.0+"""
        self.clients.add(websocket)
        
        # 获取客户端地址信息
        remote_addr = websocket.remote_address
        addr_type = "IPv6" if ":" in str(remote_addr[0]) and "::" in str(remote_addr[0]) else "IPv4"
        self.logger.info(f"✅ 客户端连接 ({addr_type}): {remote_addr}")
        
        try:
            # 发送欢迎消息
            welcome_msg = {
                "type": "welcome",
                "message": "连接成功，开始接收信号推送",
                "timestamp": datetime.utcnow().isoformat(),
                "server_version": "v1.1-IPv6",
                "connected_clients": len(self.clients),
                "connection_type": addr_type,
                "server_protocols": self._get_protocol_info()
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
                            "timestamp": datetime.utcnow().isoformat(),
                            "connection_type": addr_type
                        }
                        await websocket.send(json.dumps(pong_msg))
                except:
                    pass  # 忽略无效消息
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"🔌 客户端正常断开 ({addr_type}): {remote_addr}")
        except Exception as e:
            self.logger.error(f"❌ 客户端连接错误 ({addr_type}): {e}")
        finally:
            # 清理客户端
            self.clients.discard(websocket)
            self.logger.info(f"👋 客户端已移除 ({addr_type}): {remote_addr}, 当前连接数: {len(self.clients)}")
    
    def _get_protocol_info(self) -> List[str]:
        """获取服务器支持的协议信息"""
        protocols = []
        if self.ipv6_enabled:
            if self.bind_both:
                protocols = ["IPv4", "IPv6"]
            else:
                protocols = ["IPv6"]
        else:
            protocols = ["IPv4"]
        return protocols
    
    async def broadcast_message(self, message: dict):
        """广播消息给所有连接的客户端"""
        if not self.clients:
            self.logger.debug("没有连接的客户端，跳过广播")
            return
            
        # 添加服务器信息
        message.update({
            "server_timestamp": datetime.utcnow().isoformat(),
            "client_count": len(self.clients),
            "server_protocols": self._get_protocol_info()
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
        """异步启动服务器 - 支持 IPv4/IPv6"""
        try:
            bind_addresses = self._get_bind_addresses()
            started_servers = []
            
            # 为每个地址启动服务器
            for host, port, family in bind_addresses:
                try:
                    server = await websockets.serve(
                        self.handle_client,
                        host,
                        port,
                        family=family
                    )
                    started_servers.append(server)
                    
                    protocol_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
                    self.logger.info(f"🚀 WebSocket 服务器启动成功 ({protocol_name}): ws://{host}:{port}")
                    
                except Exception as e:
                    protocol_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
                    self.logger.error(f"❌ {protocol_name} 服务器启动失败: {e}")
            
            if not started_servers:
                raise Exception("没有成功启动任何服务器")
            
            self.servers = started_servers
            self.running = True
            
            # 启动消息处理器
            message_task = asyncio.create_task(self.message_processor())
            
            # 等待所有服务器关闭
            try:
                await asyncio.gather(*[server.wait_closed() for server in self.servers])
            finally:
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
        for server in self.servers:
            if server:
                server.close()
    
    def get_status(self) -> dict:
        """获取服务器状态"""
        return {
            "running": self.running,
            "client_count": len(self.clients),
            "host": self.host,
            "port": self.port,
            "ipv6_enabled": self.ipv6_enabled,
            "bind_both": self.bind_both,
            "protocols": self._get_protocol_info(),
            "servers_count": len(self.servers),
            "loop_running": self.loop and not self.loop.is_closed() if self.loop else False
        }

# 全局服务器实例
_global_server = None

def get_message_server(host: str = "0.0.0.0", port: int = 10000, 
                      ipv6_enabled: bool = False, bind_both: bool = True) -> MessageBroadcastServer:
    """获取全局消息服务器实例"""
    global _global_server
    if _global_server is None:
        _global_server = MessageBroadcastServer(host, port, ipv6_enabled, bind_both)
    return _global_server

def start_message_server(host: str = "0.0.0.0", port: int = 10000,
                        ipv6_enabled: bool = False, bind_both: bool = True) -> MessageBroadcastServer:
    """启动消息服务器"""
    server = get_message_server(host, port, ipv6_enabled, bind_both)
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
    
    # 测试不同配置
    print("选择服务器配置:")
    print("1. 仅 IPv4 (默认)")
    print("2. 仅 IPv6")
    print("3. IPv4 + IPv6")
    
    choice = input("请输入选择 (1-3): ").strip()
    
    if choice == "2":
        server = start_message_server("0.0.0.0", 10000, ipv6_enabled=True, bind_both=False)
        print("WebSocket 服务器已启动 (仅 IPv6)")
    elif choice == "3":
        server = start_message_server("0.0.0.0", 10000, ipv6_enabled=True, bind_both=True)
        print("WebSocket 服务器已启动 (IPv4 + IPv6)")
    else:
        server = start_message_server("0.0.0.0", 10000, ipv6_enabled=False)
        print("WebSocket 服务器已启动 (仅 IPv4)")
    
    print("按 Ctrl+C 停止服务器")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止服务器...")
        server.stop_server()