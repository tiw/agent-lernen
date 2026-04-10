# 第 9 章：MCP 协议 —— 让 AI 连接一切

> 如果 Agent 只能读写文件和运行 Shell，那它只是半个智能体。MCP（Model Context Protocol）让 Agent 能连接数据库、API、浏览器、邮件……**一切外部服务**。

---

## 🔍 先看 Claude Code 怎么做

Claude Code 通过 MCP（Model Context Protocol）扩展了 Agent 的能力边界。虽然 Claude Code 本身没有独立的 `src/mcp/` 目录（MCP 集成在工具系统中），但它通过 `mcpSkillBuilders.ts` 和工具注册机制实现了 MCP 客户端功能。

### MCP 在 Claude Code 中的位置

```
src/skills/mcpSkillBuilders.ts     # MCP 技能构建器
src/tools/                         # 工具系统（MCP 工具注册在这里）
```

关键代码片段：

```typescript
// mcpSkillBuilders.ts —— MCP 技能构建器注册
// 暴露 createSkillCommand 和 parseSkillFrontmatterFields 给 MCP 技能发现
registerMCPSkillBuilders({
  createSkillCommand,
  parseSkillFrontmatterFields,
})
```

### MCP 是什么？

MCP（Model Context Protocol）是 Anthropic 提出的**开放协议**，用于标准化 AI 模型与外部数据源和工具的集成方式。

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   AI Model   │◄───────►│   MCP Host  │◄───────►│  MCP Server  │
│  (Claude)    │  JSON   │  (Claude    │  JSON   │  (Database,  │
│              │  RPC    │   Code)     │  RPC    │   API, etc.) │
└─────────────┘         └─────────────┘         └─────────────┘
```

### MCP 核心概念

1. **MCP Server**：提供工具（Tools）和资源（Resources）的服务
2. **MCP Client**：连接到 Server，调用工具和读取资源
3. **Transport**：通信层（stdio、HTTP SSE、HTTP Streamable）
4. **Tool**：可调用的函数（如 `query_database`）
5. **Resource**：可读取的数据（如 `file:///path/to/data.csv`）

### MCP 通信协议（JSON-RPC 2.0）

```json
// 客户端 → 服务器：调用工具
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query_database",
    "arguments": {"sql": "SELECT * FROM users LIMIT 10"}
  }
}

// 服务器 → 客户端：返回结果
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {"type": "text", "text": "[{\"id\": 1, \"name\": \"Alice\"}]"}
    ]
  }
}
```

---

## 🧠 核心概念

### MCP 架构全景

```
┌──────────────────────────────────────────────────────┐
│                   Agent (你的智能体)                   │
│                                                      │
│  ┌─────────────┐    ┌──────────────┐                 │
│  │  内置工具     │    │  MCP Client   │                │
│  │  Read/Write  │    │  ┌──────────┐ │                │
│  │  Bash        │    │  │ Transport │ │                │
│  │  ...         │    │  │ Protocol  │ │                │
│  └─────────────┘    │  └──────────┘ │                 │
│                     └───────┬───────┘                 │
└─────────────────────────────┼─────────────────────────┘
                              │ stdio / HTTP
                    ┌─────────┴─────────┐
                    │   MCP Server(s)    │
                    │                    │
                    │  ┌──────────────┐  │
                    │  │ 数据库 Server │  │
                    │  │  Tools:       │  │
                    │  │  - query      │  │
                    │  │  - insert     │  │
                    │  └──────────────┘  │
                    │  ┌──────────────┐  │
                    │  │ API Server    │  │
                    │  │  Tools:       │  │
                    │  │  - get_weather│  │
                    │  │  - send_email │  │
                    │  └──────────────┘  │
                    └────────────────────┘
```

### MCP 标准方法

| 方法 | 方向 | 说明 |
|------|------|------|
| `initialize` | C→S | 初始化连接，协商能力 |
| `tools/list` | C→S | 获取可用工具列表 |
| `tools/call` | C→S | 调用工具 |
| `resources/list` | C→S | 获取可用资源列表 |
| `resources/read` | C→S | 读取资源内容 |
| `notifications/resources/updated` | S→C | 资源更新通知 |

### Transport 类型

| 类型 | 适用场景 | 特点 |
|------|---------|------|
| **stdio** | 本地进程 | 最简单，通过 stdin/stdout 通信 |
| **HTTP SSE** | 远程服务 | 服务器推送事件 |
| **HTTP Streamable** | 远程服务 | 全双工 HTTP 流 |

---

## 💻 动手实现

### 项目结构

```
mcp/
├── __init__.py
├── protocol.py     # MCP 协议定义（JSON-RPC 消息）
├── transport.py    # 传输层（stdio + HTTP）
├── client.py       # MCP Client
├── server.py       # MCP Server
└── __main__.py     # 命令行入口
```

### 1. MCP 协议定义 `mcp/protocol.py`

```python
"""
mcp/protocol.py —— MCP 协议定义

基于 JSON-RPC 2.0 的 MCP 消息格式。
参考 MCP 官方规范：https://modelcontextprotocol.io
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import json


# ─── JSON-RPC 基础消息 ───

@dataclass
class JsonRpcRequest:
    """JSON-RPC 请求"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str = ""
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            d["id"] = self.id
        if self.params:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcResponse:
    """JSON-RPC 响应"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Any = None
    error: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcNotification:
    """JSON-RPC 通知（无 id）"""
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ─── MCP 特定消息 ───

@dataclass
class MCPInitializeRequest:
    """MCP 初始化请求"""
    protocol_version: str = "2024-11-05"
    capabilities: dict = field(default_factory=lambda: {
        "roots": {"listChanged": True},
    })
    client_info: dict = field(default_factory=lambda: {
        "name": "python-mcp-client",
        "version": "1.0.0",
    })

    def to_request(self, msg_id: int = 1) -> JsonRpcRequest:
        return JsonRpcRequest(
            id=msg_id,
            method="initialize",
            params={
                "protocolVersion": self.protocol_version,
                "capabilities": self.capabilities,
                "clientInfo": self.client_info,
            }
        )


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
    })


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


@dataclass
class MCPToolCallResult:
    """工具调用结果"""
    content: list[dict]  # [{"type": "text", "text": "..."}]
    is_error: bool = False


# ─── 消息解析 ───

def parse_message(raw: str) -> dict:
    """解析 JSON-RPC 消息"""
    return json.loads(raw)


def make_error_response(msg_id: int, code: int, message: str) -> JsonRpcResponse:
    """创建错误响应"""
    return JsonRpcResponse(
        id=msg_id,
        error={"code": code, "message": message},
    )
```

### 2. 传输层 `mcp/transport.py`

```python
"""
mcp/transport.py —— MCP 传输层

支持两种传输方式：
1. StdioTransport：通过 stdin/stdout 通信（本地进程）
2. HttpTransport：通过 HTTP 通信（远程服务）
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

    def __init__(self, send_queue: asyncio.Queue | None = None, recv_queue: asyncio.Queue | None = None):
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
```

### 3. MCP Server `mcp/server.py`

```python
"""
mcp/server.py —— MCP Server 实现

参考 MCP 官方 Python SDK 的 Server 实现，
从零构建一个支持工具和资源的 MCP 服务器。
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

from .protocol import (
    JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
    MCPTool, MCPResource, MCPToolCallResult,
    parse_message, make_error_response,
)
from .transport import Transport, StdioTransport

logger = logging.getLogger(__name__)


@dataclass
class MCPToolHandler:
    """工具处理器"""
    tool: MCPTool
    handler: Callable[[dict], Any]


class MCPServer:
    """
    MCP 服务器

    实现 MCP 协议的核心方法：
    - initialize: 初始化连接
    - tools/list: 列出可用工具
    - tools/call: 调用工具
    - resources/list: 列出资源
    - resources/read: 读取资源
    """

    def __init__(self, name: str = "mcp-server", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, MCPToolHandler] = {}
        self._resources: dict[str, MCPResource] = {}
        self._resource_readers: dict[str, Callable] = {}
        self._initialized = False
        self._message_id = 0

    # ─── 工具注册 ───

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[[dict], Any],
    ) -> None:
        """
        注册一个工具

        Args:
            name: 工具名
            description: 工具描述
            input_schema: JSON Schema 格式的参数定义
            handler: 处理函数，接收 arguments dict，返回结果
        """
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
        )
        self._tools[name] = MCPToolHandler(tool=tool, handler=handler)
        logger.info(f"Registered tool: {name}")

    # ─── 资源注册 ───

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: str = "text/plain",
        reader: Optional[Callable] = None,
    ) -> None:
        """
        注册一个资源

        Args:
            uri: 资源 URI（如 file:///data/report.csv）
            name: 资源名
            reader: 读取函数，返回资源内容
        """
        resource = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )
        self._resources[uri] = resource
        if reader:
            self._resource_readers[uri] = reader
        logger.info(f"Registered resource: {name} ({uri})")

    # ─── 消息处理 ───

    async def handle_message(self, message: dict) -> Optional[JsonRpcResponse]:
        """
        处理一条 JSON-RPC 消息

        返回响应（如果是通知则返回 None）
        """
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                return self._handle_initialize(msg_id, params)
            elif method == "initialized":
                # 客户端通知，无需响应
                self._initialized = True
                return None
            elif method == "tools/list":
                return self._handle_tools_list(msg_id)
            elif method == "tools/call":
                return await self._handle_tools_call(msg_id, params)
            elif method == "resources/list":
                return self._handle_resources_list(msg_id)
            elif method == "resources/read":
                return self._handle_resources_read(msg_id, params)
            elif method == "ping":
                return JsonRpcResponse(id=msg_id, result={})
            else:
                return make_error_response(
                    msg_id, -32601, f"Method not found: {method}"
                )
        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            return make_error_response(msg_id, -32000, str(e))

    def _handle_initialize(self, msg_id: int, params: dict) -> JsonRpcResponse:
        """处理 initialize 请求"""
        return JsonRpcResponse(
            id=msg_id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"listChanged": True},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
        )

    def _handle_tools_list(self, msg_id: int) -> JsonRpcResponse:
        """处理 tools/list 请求"""
        tools = [
            {
                "name": h.tool.name,
                "description": h.tool.description,
                "inputSchema": h.tool.input_schema,
            }
            for h in self._tools.values()
        ]
        return JsonRpcResponse(id=msg_id, result={"tools": tools})

    async def _handle_tools_call(self, msg_id: int, params: dict) -> JsonRpcResponse:
        """处理 tools/call 请求"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = self._tools.get(tool_name)
        if not handler:
            return make_error_response(msg_id, -32602, f"Unknown tool: {tool_name}")

        try:
            result = handler.handler(arguments)
            if asyncio.iscoroutine(result):
                result = await result

            # 格式化结果
            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            elif isinstance(result, dict):
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
            elif isinstance(result, list):
                content = result
            else:
                content = [{"type": "text", "text": str(result)}]

            return JsonRpcResponse(
                id=msg_id,
                result={"content": content, "isError": False},
            )
        except Exception as e:
            return JsonRpcResponse(
                id=msg_id,
                result={
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            )

    def _handle_resources_list(self, msg_id: int) -> JsonRpcResponse:
        """处理 resources/list 请求"""
        resources = [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type,
            }
            for r in self._resources.values()
        ]
        return JsonRpcResponse(id=msg_id, result={"resources": resources})

    def _handle_resources_read(self, msg_id: int, params: dict) -> JsonRpcResponse:
        """处理 resources/read 请求"""
        uri = params.get("uri", "")
        resource = self._resources.get(uri)
        if not resource:
            return make_error_response(msg_id, -32602, f"Unknown resource: {uri}")

        reader = self._resource_readers.get(uri)
        if reader:
            content = reader()
        else:
            content = f"Resource: {resource.name}"

        return JsonRpcResponse(
            id=msg_id,
            result={
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": content,
                    }
                ]
            }
        )

    # ─── 运行 ───

    async def run_stdio(self) -> None:
        """
        通过 stdio 运行服务器

        这是 MCP 标准的运行方式：
        - 从 stdin 读取 JSON 消息
        - 向 stdout 写入 JSON 响应
        """
        transport = StdioTransport()
        await transport.connect()

        logger.info(f"MCP Server '{self.name}' running on stdio")

        while True:
            try:
                message = await transport.receive()
                if message is None:
                    break

                response = await self.handle_message(message)
                if response:
                    await transport.send(response.to_dict())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Server error: {e}")

    async def run_with_transport(self, transport: Transport) -> None:
        """使用指定传输运行服务器"""
        await transport.connect()

        while True:
            try:
                message = await transport.receive()
                if message is None:
                    break
                response = await self.handle_message(message)
                if response:
                    await transport.send(response.to_dict())
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Server error: {e}")
```

### 4. MCP Client `mcp/client.py`

```python
"""
mcp/client.py —— MCP Client 实现

MCP 客户端，用于连接 MCP 服务器、发现工具、调用工具。
这是 Agent 集成 MCP 的关键组件。
"""

import asyncio
import json
import logging
from typing import Optional, Any

from .protocol import (
    JsonRpcRequest, JsonRpcResponse,
    MCPInitializeRequest, MCPTool,
    parse_message,
)
from .transport import Transport, StdioTransport

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 客户端

    参考 Claude Code 的 MCP 集成模式：
    1. 连接到 MCP Server
    2. 初始化握手
    3. 发现工具列表
    4. 调用工具
    """

    def __init__(self, transport: Transport):
        self.transport = transport
        self._next_id = 1
        self._server_info: Optional[dict] = None
        self._capabilities: Optional[dict] = None
        self._tools: list[MCPTool] = []

    async def connect(self) -> None:
        """
        连接并初始化

        完整的 MCP 握手流程：
        1. 建立传输连接
        2. 发送 initialize 请求
        3. 发送 initialized 通知
        4. 获取工具列表
        """
        await self.transport.connect()

        # Step 1: 发送 initialize 请求
        init_req = MCPInitializeRequest()
        response = await self._send_request(init_req.to_request())

        if response and response.result:
            self._server_info = response.result.get("serverInfo", {})
            self._capabilities = response.result.get("capabilities", {})
            logger.info(
                f"Connected to MCP server: "
                f"{self._server_info.get('name', 'unknown')} "
                f"v{self._server_info.get('version', '?')}"
            )

        # Step 2: 发送 initialized 通知
        await self._send_notification("initialized")

        # Step 3: 获取工具列表
        if self._capabilities and "tools" in self._capabilities:
            await self.refresh_tools()

    async def refresh_tools(self) -> list[MCPTool]:
        """获取可用工具列表"""
        response = await self._send_request(
            JsonRpcRequest(id=self._next_id, method="tools/list")
        )
        if response and response.result:
            tools_data = response.result.get("tools", [])
            self._tools = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
                for t in tools_data
            ]
            logger.info(f"Discovered {len(self._tools)} tools")
        return self._tools

    async def call_tool(self, name: str, arguments: dict = None) -> Any:
        """
        调用工具

        Args:
            name: 工具名
            arguments: 工具参数

        Returns:
            工具返回结果
        """
        response = await self._send_request(
            JsonRpcRequest(
                id=self._next_id,
                method="tools/call",
                params={
                    "name": name,
                    "arguments": arguments or {},
                },
            )
        )

        if not response:
            raise RuntimeError(f"No response from tool: {name}")

        if response.error:
            raise RuntimeError(
                f"Tool error: {response.error.get('message', 'unknown')}"
            )

        result = response.result or {}
        if result.get("isError"):
            content = result.get("content", [])
            error_text = "\n".join(
                c.get("text", "") for c in content if c.get("type") == "text"
            )
            raise RuntimeError(f"Tool returned error: {error_text}")

        # 提取文本内容
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        if len(texts) == 1:
            return texts[0]
        return texts

    async def list_resources(self) -> list[dict]:
        """获取可用资源列表"""
        response = await self._send_request(
            JsonRpcRequest(id=self._next_id, method="resources/list")
        )
        if response and response.result:
            return response.result.get("resources", [])
        return []

    async def read_resource(self, uri: str) -> str:
        """读取资源内容"""
        response = await self._send_request(
            JsonRpcRequest(
                id=self._next_id,
                method="resources/read",
                params={"uri": uri},
            )
        )
        if response and response.result:
            contents = response.result.get("contents", [])
            if contents:
                return contents[0].get("text", "")
        return ""

    def get_tools(self) -> list[MCPTool]:
        """获取已发现的工具列表"""
        return list(self._tools)

    async def close(self) -> None:
        """关闭连接"""
        await self.transport.close()

    # ─── 内部方法 ───

    async def _send_request(self, request: JsonRpcRequest) -> Optional[JsonRpcResponse]:
        """发送请求并等待响应"""
        request.id = self._next_id
        self._next_id += 1
        await self.transport.send(request.to_dict())

        # 等待响应（简化实现：只读下一条消息）
        response_data = await self.transport.receive()
        if response_data:
            return JsonRpcResponse(
                id=response_data.get("id"),
                result=response_data.get("result"),
                error=response_data.get("error"),
            )
        return None

    async def _send_notification(self, method: str, params: dict = None) -> None:
        """发送通知（无需响应）"""
        from .protocol import JsonRpcNotification
        notification = JsonRpcNotification(method=method, params=params or {})
        await self.transport.send(notification.to_dict())


# ─── 便捷工厂函数 ───

async def create_stdio_client(command: list[str]) -> MCPClient:
    """
    创建 stdio 客户端

    Args:
        command: 启动 MCP Server 的命令（如 ["python", "server.py"]）

    Returns:
        已连接的 MCPClient
    """
    transport = StdioTransport(command=command)
    client = MCPClient(transport)
    await client.connect()
    return client
```

### 5. 实战：3 个 MCP Server 示例

#### 示例 1：数据库 Server

```python
"""
examples/database_server.py —— 数据库 MCP Server

提供 SQL 查询工具。
"""

import asyncio
import json
import sqlite3
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import MCPServer


def create_database_server(db_path: str = ":memory:") -> MCPServer:
    """创建数据库 MCP Server"""
    server = MCPServer(name="database-server", version="1.0.0")

    # 初始化数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, name, email, age) VALUES
        (1, 'Alice', 'alice@example.com', 30),
        (2, 'Bob', 'bob@example.com', 25),
        (3, 'Charlie', 'charlie@example.com', 35)
    """)
    conn.commit()

    # 注册查询工具
    def query_handler(args: dict) -> str:
        sql = args.get("sql", "SELECT * FROM users")
        try:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Query error: {e}"

    server.register_tool(
        name="query_database",
        description="Execute a SQL query against the database",
        input_schema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL query to execute",
                }
            },
            "required": ["sql"],
        },
        handler=query_handler,
    )

    # 注册表结构工具
    def schema_handler(args: dict) -> str:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        result = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            result[table] = [
                {"name": col[1], "type": col[2], "notnull": bool(col[3])}
                for col in columns
            ]
        return json.dumps(result, ensure_ascii=False, indent=2)

    server.register_tool(
        name="get_schema",
        description="Get database schema information",
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=schema_handler,
    )

    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_database_server()
    asyncio.run(server.run_stdio())
```

#### 示例 2：API Server（天气查询）

```python
"""
examples/weather_server.py —— 天气 API MCP Server

模拟天气查询服务。
"""

import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import MCPServer


# 模拟天气数据
WEATHER_DATA = {
    "beijing": {"temp": 22, "humidity": 45, "condition": "Sunny", "wind": "5 km/h"},
    "shanghai": {"temp": 25, "humidity": 65, "condition": "Cloudy", "wind": "10 km/h"},
    "shenzhen": {"temp": 30, "humidity": 80, "condition": "Rainy", "wind": "15 km/h"},
    "tokyo": {"temp": 18, "humidity": 55, "condition": "Partly Cloudy", "wind": "8 km/h"},
    "new york": {"temp": 15, "humidity": 40, "condition": "Clear", "wind": "12 km/h"},
}


def create_weather_server() -> MCPServer:
    """创建天气 MCP Server"""
    server = MCPServer(name="weather-server", version="1.0.0")

    def get_weather(args: dict) -> str:
        city = args.get("city", "").lower()
        if city in WEATHER_DATA:
            data = WEATHER_DATA[city]
            result = {
                "city": city.title(),
                **data,
                "timestamp": datetime.now().isoformat(),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            available = ", ".join(WEATHER_DATA.keys())
            return f"City not found. Available cities: {available}"

    server.register_tool(
        name="get_weather",
        description="Get current weather for a city",
        input_schema={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (beijing, shanghai, shenzhen, tokyo, new york)",
                }
            },
            "required": ["city"],
        },
        handler=get_weather,
    )

    def get_forecast(args: dict) -> str:
        city = args.get("city", "").lower()
        days = min(args.get("days", 3), 7)
        if city not in WEATHER_DATA:
            return f"City not found: {city}"

        conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Clear"]
        forecast = []
        base_temp = WEATHER_DATA[city]["temp"]
        for i in range(days):
            forecast.append({
                "day": f"Day {i+1}",
                "temp": base_temp + (i - days//2) * 2,
                "condition": conditions[i % len(conditions)],
            })
        return json.dumps({"city": city.title(), "forecast": forecast}, ensure_ascii=False, indent=2)

    server.register_tool(
        name="get_forecast",
        description="Get weather forecast for a city",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "days": {"type": "integer", "description": "Number of days (1-7)", "default": 3},
            },
            "required": ["city"],
        },
        handler=get_forecast,
    )

    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_weather_server()
    asyncio.run(server.run_stdio())
```

#### 示例 3：文件搜索 Server

```python
"""
examples/search_server.py —— 文件搜索 MCP Server

提供文件搜索和内容读取功能。
"""

import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import MCPServer


def create_search_server(root_dir: str = ".") -> MCPServer:
    """创建文件搜索 MCP Server"""
    server = MCPServer(name="search-server", version="1.0.0")
    root = Path(root_dir).resolve()

    def search_files(args: dict) -> str:
        pattern = args.get("pattern", "*")
        file_type = args.get("type", "")  # "file" or "directory"

        results = []
        for path in root.rglob(pattern):
            if path.is_relative_to(root):
                rel = path.relative_to(root)
                if file_type == "file" and path.is_file():
                    results.append(str(rel))
                elif file_type == "directory" and path.is_dir():
                    results.append(str(rel))
                elif not file_type:
                    results.append(str(rel))

        return json.dumps({"root": str(root), "matches": results[:100]}, ensure_ascii=False, indent=2)

    server.register_tool(
        name="search_files",
        description="Search for files in the project directory",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., '*.py')"},
                "type": {"type": "string", "description": "Filter by type: 'file' or 'directory'"},
            },
        },
        handler=search_files,
    )

    def read_file(args: dict) -> str:
        file_path = args.get("path", "")
        full_path = (root / file_path).resolve()

        # 安全检查：确保路径在项目目录内
        if not full_path.is_relative_to(root):
            return "Error: Path outside project directory"
        if not full_path.exists():
            return f"Error: File not found: {file_path}"
        if not full_path.is_file():
            return f"Error: Not a file: {file_path}"

        try:
            content = full_path.read_text(encoding="utf-8")
            # 截断大文件
            if len(content) > 10000:
                content = content[:10000] + f"\n\n... (truncated, total {len(content)} chars)"
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    server.register_tool(
        name="read_file",
        description="Read file contents",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
            },
            "required": ["path"],
        },
        handler=read_file,
    )

    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    server = create_search_server(root)
    asyncio.run(server.run_stdio())
```

---

## 🧪 测试验证

### 测试文件 `tests/test_mcp.py`

```python
"""
tests/test_mcp.py —— MCP 系统测试
"""

import asyncio
import json
import pytest
from mcp.protocol import (
    JsonRpcRequest, JsonRpcResponse,
    MCPInitializeRequest,
)
from mcp.transport import InMemoryTransport
from mcp.server import MCPServer
from mcp.client import MCPClient


class TestMCPServer:
    """测试 MCP Server"""

    @pytest.fixture
    def server(self):
        s = MCPServer(name="test-server", version="1.0.0")

        # 注册一个简单工具
        s.register_tool(
            name="echo",
            description="Echo back the input",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
                "required": ["message"],
            },
            handler=lambda args: f"Echo: {args.get('message', '')}",
        )

        # 注册一个计算工具
        s.register_tool(
            name="add",
            description="Add two numbers",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
            handler=lambda args: str(args.get("a", 0) + args.get("b", 0)),
        )

        # 注册资源
        s.register_resource(
            uri="file:///hello.txt",
            name="Hello",
            description="A greeting file",
            reader=lambda: "Hello from MCP Server!",
        )

        return s

    @pytest.mark.asyncio
    async def test_initialize(self, server):
        """测试初始化握手"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        })
        assert response is not None
        assert response.result["serverInfo"]["name"] == "test-server"
        assert response.result["serverInfo"]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        """测试工具列表"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        })
        assert response is not None
        tools = response.result["tools"]
        assert len(tools) == 2
        assert tools[0]["name"] == "echo"
        assert tools[1]["name"] == "add"

    @pytest.mark.asyncio
    async def test_tools_call(self, server):
        """测试工具调用"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "Hello MCP!"},
            },
        })
        assert response is not None
        assert response.result["isError"] is False
        assert "Echo: Hello MCP!" in response.result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_tools_call_math(self, server):
        """测试数学工具"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "add",
                "arguments": {"a": 42, "b": 58},
            },
        })
        assert response.result["content"][0]["text"] == "100"

    @pytest.mark.asyncio
    async def test_tools_call_unknown(self, server):
        """测试调用不存在的工具"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nonexistent", "arguments": {}},
        })
        assert response.error is not None
        assert "Unknown tool" in response.error["message"]

    @pytest.mark.asyncio
    async def test_resources_list(self, server):
        """测试资源列表"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/list",
        })
        assert len(response.result["resources"]) == 1
        assert response.result["resources"][0]["uri"] == "file:///hello.txt"

    @pytest.mark.asyncio
    async def test_resources_read(self, server):
        """测试资源读取"""
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": "file:///hello.txt"},
        })
        assert "Hello from MCP Server!" in response.result["contents"][0]["text"]


class TestMCPIntegration:
    """集成测试：Client ↔ Server"""

    @pytest.mark.asyncio
    async def test_client_server_communication(self):
        """测试客户端和服务器通信"""
        # 创建服务器
        server = MCPServer(name="integration-test", version="1.0.0")
        server.register_tool(
            name="greet",
            description="Greet someone",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
            },
            handler=lambda args: f"Hello, {args.get('name', 'World')}!",
        )

        # 创建配对的传输
        client_transport = InMemoryTransport()
        server_transport = InMemoryTransport()

        # 手动连接队列
        client_to_server = asyncio.Queue()
        server_to_client = asyncio.Queue()
        client_transport._queue = client_to_server
        server_transport._queue = server_to_server = client_to_server

        # 重写 receive 来模拟
        class PairedTransport:
            def __init__(self, send_queue, recv_queue):
                self.send_queue = send_queue
                self.recv_queue = recv_queue

            async def connect(self): pass
            async def send(self, msg): await self.send_queue.put(msg)
            async def receive(self): return await self.recv_queue.get()
            async def close(self): pass

        c2s = asyncio.Queue()
        s2c = asyncio.Queue()
        client_t = PairedTransport(c2s, s2c)
        server_t = PairedTransport(s2c, c2s)

        # 启动服务器任务
        async def run_server():
            await server_t.connect()
            while True:
                msg = await server_t.receive()
                response = await server.handle_message(msg)
                if response:
                    await server_t.send(response.to_dict())

        server_task = asyncio.create_task(run_server())

        # 创建客户端
        client = MCPClient(client_t)
        await client.connect()

        # 调用工具
        result = await client.call_tool("greet", {"name": "MCP"})
        assert "Hello, MCP!" in result

        # 清理
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        await client.close()

    @pytest.mark.asyncio
    async def test_database_server(self):
        """测试数据库服务器"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

        from examples.database_server import create_database_server

        server = create_database_server()

        # 初始化
        await server.handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        # 查询
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "query_database",
                "arguments": {"sql": "SELECT * FROM users"},
            },
        })
        data = json.loads(response.result["content"][0]["text"])
        assert len(data) == 3
        assert data[0]["name"] == "Alice"

        # 获取 schema
        response = await server.handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_schema",
                "arguments": {},
            },
        })
        schema = json.loads(response.result["content"][0]["text"])
        assert "users" in schema
```

运行测试：

```bash
pip install pytest pytest-asyncio
pytest tests/test_mcp.py -v
```

预期输出：

```
tests/test_mcp.py::TestMCPServer::test_initialize PASSED
tests/test_mcp.py::TestMCPServer::test_tools_list PASSED
tests/test_mcp.py::TestMCPServer::test_tools_call PASSED
tests/test_mcp.py::TestMCPServer::test_tools_call_math PASSED
tests/test_mcp.py::TestMCPServer::test_tools_call_unknown PASSED
tests/test_mcp.py::TestMCPServer::test_resources_list PASSED
tests/test_mcp.py::TestMCPServer::test_resources_read PASSED
tests/test_mcp.py::TestMCPIntegration::test_database_server PASSED
```

### 手动测试：运行 Server

```bash
# 终端 1：启动数据库服务器
python examples/database_server.py

# 终端 2：发送 JSON-RPC 请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python examples/database_server.py
```

---

## 📝 本章小结

本章我们从零实现了完整的 MCP 协议栈：

| 概念 | 说明 | 我们的实现 |
|------|------|-----------|
| JSON-RPC 2.0 | 消息格式标准 | JsonRpcRequest/Response |
| Transport | 传输层 | StdioTransport + InMemoryTransport |
| Server | 提供工具和服务 | MCPServer（注册+处理） |
| Client | 发现和调用工具 | MCPClient（连接+调用） |
| Tools | 可调用的函数 | register_tool + handler |
| Resources | 可读取的数据 | register_resource + reader |
| 握手 | initialize → initialized | 完整的握手流程 |

**实战 Server 示例：**
1. **数据库 Server**：SQLite 查询，支持 `query_database` 和 `get_schema`
2. **天气 Server**：模拟天气 API，支持 `get_weather` 和 `get_forecast`
3. **搜索 Server**：文件搜索和读取，支持 `search_files` 和 `read_file`

**核心收获：**

1. **MCP 本质是 JSON-RPC**——理解 JSON-RPC 2.0 就理解了 MCP 的一半
2. **stdio 是最简单的传输**——一行一个 JSON，天然适合子进程通信
3. **Server 是插件化的**——每个 Server 提供特定领域的工具，Client 统一调用
4. **Agent + MCP = 无限可能**——Agent 只需知道如何调用工具，不需要知道工具的内部实现

---

## 🏋️ 课后练习

### 练习 1：实现 HTTP SSE 传输

> **提示**：参考 MCP 官方的 HTTP SSE 规范，用 `aiohttp` 实现服务端发送事件。客户端用 `httpx` 连接。

### 练习 2：实现 MCP 工具自动发现

> **提示**：在 Agent 中集成 MCP Client，启动时自动发现所有 MCP Server 的工具，合并到 Agent 的工具列表中。参考 Claude Code 的工具注册机制。

### 练习 3：实现 MCP 通知系统

> **提示**：MCP Server 可以主动向 Client 发送通知（如 `notifications/resources/updated`）。实现一个文件监控 Server，当文件变化时通知 Client。

### 练习 4：实现 MCP Server 组合器

> **提示**：编写一个 `CompositeServer`，可以聚合多个 MCP Server 的工具，对外表现为一个统一的 Server。这类似于 API Gateway 的概念。

**答案提示：**
- 练习 1：`aiohttp.web.Response` + `text/event-stream` content type
- 练习 2：在 Agent 初始化时遍历配置的 MCP Server 列表，调用 `tools/list` 合并
- 练习 3：`watchdog` 库监控文件系统变化，通过 `notifications/resources/updated` 推送
- 练习 4：维护多个 Server 实例的 Transport，路由请求到正确的后端

---

> 📖 **上一章**：[第 8 章：技能系统（Skills）—— 让 AI 学会专业本领](ch08-技能系统.md)
>
> 📖 **下一章**：[第 10 章：多智能体协作 —— Team Mode](ch10-多智能体协作.md)
