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

############# 交易信号示例 #############
'''
{
  "type": "notification",
  "level": "WARNING",
  "message": "🟢 BUY SIGNAL - BINANCE BTC/USDT (1h) @ 45000.0000",
  "timestamp": "2025-01-07T10:30:00.123456",
  "data": {
    "exchange": "binance",
    "symbol": "BTC/USDT", 
    "timeframe": "1h",
    "price": 45000.0,
    "timestamp": "2025-01-07 10:30:00 UTC",
    "target_key": "binance_BTC/USDT_1h",
    "thread": "Worker-1",
    "signal_type": "BUY"
  },
  "source": "CryptoMonitor",
  "thread": "Worker-1",
  "server_timestamp": "2025-01-07T10:30:00.123456",
  "client_count": 3,
  "server_protocols": ["IPv4", "IPv6"]
}



{
  "type": "notification",
  "level": "INFO",
  "message": "🚀 多交易所监控启动，每分钟 30s 触发",
  "timestamp": "2025-01-07T10:30:00.123456",
  "data": {},
  "source": "CryptoMonitor",
  "thread": "MainThread",
  "server_timestamp": "2025-01-07T10:30:00.123456",
  "client_count": 3,
  "server_protocols": ["IPv4", "IPv6"]
}

{
  "type": "welcome",
  "message": "连接成功，开始接收信号推送",
  "timestamp": "2025-01-07T10:30:00.123456",
  "server_version": "v1.1-IPv6",
  "connected_clients": 1,
  "connection_type": "IPv4",
  "server_protocols": ["IPv4", "IPv6"]
}


{
  "type": "pong",
  "timestamp": "2025-01-07T10:30:00.123456",
  "connection_type": "IPv4"
}
'''
#######################################

class MessageBroadcastServer:
    """消息广播服务器 - 支持 IPv4/IPv6"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 10000, 
                 ipv6_enabled: bool = False, bind_both: bool = True):
        """
        初始化消息广播服务器
        
        Args:
            host: 绑定地址，"0.0.0.0" 表示所有网络接口
            port: 监听端口号
            ipv6_enabled: 是否启用 IPv6 支持
            bind_both: 是否同时绑定 IPv4 和 IPv6（仅在 ipv6_enabled=True 时有效）
        """
        self.host = host
        self.port = port
        self.ipv6_enabled = ipv6_enabled
        self.bind_both = bind_both
        self.clients: Set[websockets.WebSocketServerProtocol] = set()  # 连接的客户端集合
        self.servers: List = []  # 支持多个服务器实例（IPv4 + IPv6）
        self.loop = None  # 事件循环
        self.message_queue = queue.Queue()  # 消息队列（预留）
        self.running = False  # 服务器运行状态
        
        # 设置日志
        self.logger = logging.getLogger('WebSocketServer')
        
        # 验证 IPv6 支持
        if self.ipv6_enabled and not self._check_ipv6_support():
            self.logger.warning("系统不支持 IPv6，将禁用 IPv6 功能")
            self.ipv6_enabled = False
    # 初始化函数说明：
    # - 设置服务器基本参数（地址、端口、协议支持）
    # - 初始化客户端管理和服务器状态
    # - 自动检测系统 IPv6 支持能力
    
    def _check_ipv6_support(self) -> bool:
        """
        检查系统是否支持 IPv6
        
        Returns:
            bool: True 表示支持 IPv6，False 表示不支持
        """
        try:
            test_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            test_socket.close()
            return True
        except (socket.error, OSError):
            return False
    # IPv6支持检测说明：
    # - 尝试创建 IPv6 socket 来测试系统支持
    # - 如果系统不支持 IPv6，会自动降级到 IPv4 模式
    
    def _get_bind_addresses(self) -> List[Tuple[str, int, int]]:
        """
        获取绑定地址列表
        返回格式: [(host, port, family), ...]
        
        Returns:
            List[Tuple[str, int, int]]: 绑定地址列表，每个元组包含 (主机地址, 端口, 地址族)
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
    # 地址绑定策略说明：
    # - IPv4 模式：只绑定指定的 IPv4 地址
    # - IPv6 模式：只绑定对应的 IPv6 地址（0.0.0.0 -> ::）
    # - 双栈模式：同时绑定 IPv4 和 IPv6 地址，支持所有客户端
    
    async def handle_client(self, websocket):
        """
        处理客户端连接 - 适配 websockets 13.0+
        
        Args:
            websocket: WebSocket 连接对象
        """
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
    # 客户端处理说明：
    # - 自动识别客户端连接类型（IPv4/IPv6）
    # - 发送包含服务器信息的欢迎消息
    # - 支持心跳检测（ping/pong）保持连接活跃
    # - 异常断开时自动清理客户端记录
    
    def _get_protocol_info(self) -> List[str]:
        """
        获取服务器支持的协议信息
        
        Returns:
            List[str]: 支持的协议列表，如 ["IPv4"], ["IPv6"], ["IPv4", "IPv6"]
        """
        protocols = []
        if self.ipv6_enabled:
            if self.bind_both:
                protocols = ["IPv4", "IPv6"]
            else:
                protocols = ["IPv6"]
        else:
            protocols = ["IPv4"]
        return protocols
    # 协议信息说明：
    # - 用于告知客户端服务器支持的网络协议
    # - 在欢迎消息和广播消息中包含此信息
    
    async def broadcast_message(self, message: dict):
        """
        广播消息给所有连接的客户端
        
        Args:
            message: 要广播的消息字典
        """
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
    # 消息广播说明：
    # - 自动添加服务器时间戳、客户端数量等元信息
    # - 并发发送给所有连接的客户端
    # - 自动检测并清理断开的连接
    # - 支持 UTF-8 编码的消息内容
    
    def send_message_sync(self, message: dict):
        """
        同步发送消息接口（供外部调用）
        
        Args:
            message: 要发送的消息字典
        """
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
    # 同步接口说明：
    # - 提供线程安全的消息发送接口
    # - 将同步调用转换为异步执行
    # - 设置超时保护，避免长时间阻塞
    # - 供主监控程序调用
    
    async def message_processor(self):
        """
        消息队列处理器
        """
        while self.running:
            try:
                # 非阻塞检查队列
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"消息处理器错误: {e}")
    # 消息处理器说明：
    # - 预留的消息队列处理功能
    # - 当前实现为简单的保活循环
    # - 可扩展为处理消息队列、缓存等功能
    
    async def start_server_async(self):
        """
        异步启动服务器 - 支持 IPv4/IPv6
        """
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
    # 异步启动说明：
    # - 根据配置同时启动多个服务器实例（IPv4/IPv6）
    # - 部分服务器启动失败不影响其他服务器
    # - 启动消息处理器并等待服务器关闭
    # - 提供详细的启动状态日志
    
    def start_server(self):
        """
        启动 WebSocket 服务器（在新线程中）
        
        Returns:
            threading.Thread: 服务器线程对象
        """
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
    # 线程启动说明：
    # - 在独立线程中运行服务器，避免阻塞主程序
    # - 创建新的事件循环，与主线程隔离
    # - 设置为守护线程，主程序退出时自动关闭
    # - 等待1秒确保服务器完全启动
    
    def stop_server(self):
        """
        停止服务器
        """
        self.running = False
        for server in self.servers:
            if server:
                server.close()
    # 停止服务器说明：
    # - 设置运行标志为 False
    # - 关闭所有服务器实例
    # - 清理资源和连接
    
    def get_status(self) -> dict:
        """
        获取服务器状态
        
        Returns:
            dict: 包含服务器详细状态信息的字典
        """
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
    # 状态查询说明：
    # - 返回服务器完整运行状态
    # - 包括连接数、协议支持、服务器实例数等
    # - 用于监控和调试

# 全局服务器实例
_global_server = None

def get_message_server(host: str = "0.0.0.0", port: int = 10000, 
                      ipv6_enabled: bool = False, bind_both: bool = True) -> MessageBroadcastServer:
    """
    获取全局消息服务器实例
    
    Args:
        host: 服务器绑定地址
        port: 服务器端口
        ipv6_enabled: 是否启用 IPv6
        bind_both: 是否双栈绑定
        
    Returns:
        MessageBroadcastServer: 全局服务器实例
    """
    global _global_server
    if _global_server is None:
        _global_server = MessageBroadcastServer(host, port, ipv6_enabled, bind_both)
    return _global_server
# 全局实例说明：
# - 实现单例模式，确保只有一个服务器实例
# - 首次调用时创建，后续调用返回同一实例

def start_message_server(host: str = "0.0.0.0", port: int = 10000,
                        ipv6_enabled: bool = False, bind_both: bool = True) -> MessageBroadcastServer:
    """
    启动消息服务器
    
    Args:
        host: 服务器绑定地址
        port: 服务器端口  
        ipv6_enabled: 是否启用 IPv6 支持
        bind_both: 是否同时绑定 IPv4 和 IPv6
        
    Returns:
        MessageBroadcastServer: 启动的服务器实例
    """
    server = get_message_server(host, port, ipv6_enabled, bind_both)
    if not server.running:
        server.start_server()
    return server
# 启动接口说明：
# - 获取或创建服务器实例
# - 如果服务器未运行则启动
# - 避免重复启动

def send_message(message: dict):
    """
    发送消息到所有连接的客户端
    
    Args:
        message: 要发送的消息字典
    """
    global _global_server
    if _global_server and _global_server.running:
        _global_server.send_message_sync(message)
# 消息发送接口说明：
# - 全局消息发送入口
# - 检查服务器状态后发送
# - 供外部模块调用

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
# 独立运行说明：
# - 提供交互式配置选择
# - 支持测试不同的网络协议配置
# - 优雅的关闭处理