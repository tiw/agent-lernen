"""
mcp/transport.py —— MCP 传输层
支持两种传输方式：
1. StdioTransport：通过 stdin/stdout 通信（本地进程）
2. HttpTransport：通过 HTTP 通信（远程服务）
从零手写 AI Agent 课程 · 第 9 章
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class Transport(ABC):
    """传输层抽象基类"""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        ...

    @abstractmethod
    async def send(self, message: dict) -> None:
        """发送消息"""
        ...

    @abstractmethod
    async def receive(self) -> Optional[dict]:
        """接收消息"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        ...


class StdioTransport(Transport):
    """
    Stdio 传输：通过 stdin/stdout 通信

    这是 MCP 最简单的传输方式，适合本地子进程通信。
    每行一个 JSON 消息。
    """

    def __init__(self, command: list[str] = None):
        """
        如果 command 不为空，则启动子进程；
        否则使用当前进程的 stdin/stdout（作为服务器端）。
        """
        self.command = command
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer = None

    async def connect(self) -> None:
        if self.command:
            # 启动子进程
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            logger.info(f"Started MCP server: {' '.join(self.command)}")
        else:
            # 使用当前进程的 stdin/stdout（服务器模式）
            loop = asyncio.get_event_loop()
            self._reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, asyncio.get_event_loop()._stdin)
            self._writer = asyncio.get_event_loop()._stdout

    async def send(self, message: dict) -> None:
        """发送 JSON 消息（一行一条）"""
        line = json.dumps(message) + "\n"
        if self._writer:
            if hasattr(self._writer, 'write'):
                self._writer.write(line.encode("utf-8"))
                if hasattr(self._writer, 'drain'):
                    await self._writer.drain()
            else:
                # 服务器模式：直接写 stdout
                import sys
                sys.stdout.write(line)
                sys.stdout.flush()

    async def receive(self) -> Optional[dict]:
        """接收一行 JSON 消息"""
        if not self._reader:
            return None
        line = await self._reader.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return None

    async def close(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()


class InMemoryTransport(Transport):
    """
    内存传输：用于测试

    两个 InMemoryTransport 实例可以配对，模拟客户端和服务端通信。
    原理：client.send() → server.receive()，server.send() → client.receive()
    """

    def __init__(self, send_queue: asyncio.Queue = None, recv_queue: asyncio.Queue = None):
        self._send_queue = send_queue  # 我发送消息到这个队列
        self._recv_queue = recv_queue  # 我从这个队列接收消息
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def send(self, message: dict) -> None:
        if self._send_queue is None:
            raise RuntimeError("Transport not paired — no send queue")
        await self._send_queue.put(message)

    async def receive(self) -> Optional[dict]:
        if self._recv_queue is None:
            raise RuntimeError("Transport not paired — no receive queue")
        return await self._recv_queue.get()

    async def close(self) -> None:
        self._connected = False

    @staticmethod
    def paired() -> tuple["InMemoryTransport", "InMemoryTransport"]:
        """
        创建一对配对的传输。

        原理：
        - client_to_server: client.send() 放入此队列 → server.receive() 从此队列取
        - server_to_client: server.send() 放入此队列 → client.receive() 从此队列取
        """
        client_to_server: asyncio.Queue = asyncio.Queue()
        server_to_client: asyncio.Queue = asyncio.Queue()

        client = InMemoryTransport(
            send_queue=client_to_server,   # client 发送到 server
            recv_queue=server_to_client,   # client 从 server 接收
        )
        server = InMemoryTransport(
            send_queue=server_to_client,   # server 发送到 client
            recv_queue=client_to_server,   # server 从 client 接收
        )
        return client, server


# === 测试 ===
if __name__ == "__main__":
    async def test_in_memory_transport():
        print("=== 内存传输测试 ===\n")

        # 测试 1: 配对传输
        print("测试 1: 配对传输")
        client, server = InMemoryTransport.paired()
        await client.connect()
        await server.connect()
        print(f"  客户端已连接：{client._connected}")
        print(f"  服务端已连接：{server._connected}\n")

        # 测试 2: 客户端发送，服务端接收
        print("测试 2: 客户端发送 → 服务端接收")
        await client.send({"method": "tools/list", "id": 1})
        msg = await server.receive()
        print(f"  服务端收到：{msg}\n")

        # 测试 3: 服务端发送，客户端接收
        print("测试 3: 服务端发送 → 客户端接收")
        await server.send({"result": {"tools": []}, "id": 1})
        msg = await client.receive()
        print(f"  客户端收到：{msg}\n")

        # 清理
        await client.close()
        await server.close()

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_in_memory_transport())
