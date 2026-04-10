"""
mcp/transport.py —— MCP 传输层

支持两种传输方式：
1. StdioTransport：通过 stdin/stdout 通信（本地进程）
2. InMemoryTransport：内存传输（用于测试）
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
        ...

    @abstractmethod
    async def send(self, message: dict) -> None:
        ...

    @abstractmethod
    async def receive(self) -> Optional[dict]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class StdioTransport(Transport):
    """Stdio 传输：通过 stdin/stdout 通信"""

    def __init__(self, command: list = None):
        self.command = command
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer = None

    async def connect(self) -> None:
        if self.command:
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
            import sys
            self._reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            self._writer = sys.stdout

    async def send(self, message: dict) -> None:
        """发送 JSON 消息（一行一条）"""
        line = json.dumps(message) + "\n"
        if self._writer:
            if hasattr(self._writer, 'write'):
                self._writer.write(line.encode("utf-8"))
                if hasattr(self._writer, 'drain'):
                    await self._writer.drain()
            else:
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
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def send(self, message: dict) -> None:
        await self._queue.put(message)

    async def receive(self) -> Optional[dict]:
        return await self._queue.get()

    async def close(self) -> None:
        self._connected = False
