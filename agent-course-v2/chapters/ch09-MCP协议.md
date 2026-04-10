# 第 9 章：MCP 协议 —— 让 AI 连接一切

> **本章目标**：理解 MCP 协议，从零实现 MCP Client，让 Agent 能连接数据库、API 等外部服务
>
> 🎯 **里程碑进度**：▓▓▓▓▓▓▓▓▓░ 90% — Agent 能连接外部世界了

---

## 🧠 核心概念

### MCP 是什么？

MCP（Model Context Protocol）是 Anthropic 提出的**开放协议**，用于标准化 AI 模型与外部数据源和工具的集成。

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   AI Model   │◄───────►│   MCP Host  │◄───────►│  MCP Server  │
│  (Claude)    │  JSON   │  (你的      │  JSON   │  (数据库,    │
│              │  RPC    │   Agent)    │  RPC    │   API, etc.) │
└─────────────┘         └─────────────┘         └─────────────┘
```

### MCP 核心概念

| 概念 | 说明 | 类比 |
|------|------|------|
| **MCP Server** | 提供工具和资源的服务 | 餐厅的厨房 |
| **MCP Client** | 连接到 Server，调用工具 | 顾客（你的 Agent） |
| **Transport** | 通信层（stdio / HTTP） | 服务员（传递消息） |
| **Tool** | 可调用的函数 | 菜单上的菜 |
| **Resource** | 可读取的数据 | 餐厅的环境信息 |

### JSON-RPC 2.0 协议

MCP 基于 JSON-RPC 2.0，消息格式：

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

### MCP 通信流程

```
Client                          Server
  │                               │
  │── initialize ────────────────►│
  │◄── capabilities ──────────────│
  │                               │
  │── tools/list ────────────────►│
  │◄── [tool1, tool2, ...] ──────│
  │                               │
  │── tools/call(tool1, args) ───►│
  │◄── result ────────────────────│
  │                               │
  │── resources/list ────────────►│
  │◄── [resource1, ...] ─────────│
  │                               │
  │── resources/read(uri) ───────►│
  │◄── content ───────────────────│
```

---

## 💻 动手实现

### 项目结构

```
src/
├── agent.py              # ⚠️ 需要更新：集成 MCP 工具
└── mcp/
    ├── __init__.py
    ├── transport.py      # 🆕 通信层（stdio）
    ├── client.py         # 🆕 MCP 客户端
    └── tool.py           # 🆕 MCP 工具适配器
```

### 代码 1：`src/mcp/__init__.py`

```python
"""MCP 模块入口"""
from mcp.transport import StdioTransport
from mcp.client import MCPClient
from mcp.tool import MCPToolAdapter

__all__ = ["StdioTransport", "MCPClient", "MCPToolAdapter"]
```

### 代码 2：`src/mcp/transport.py`

```python
"""
MCP 通信层 —— stdio 传输。

通过子进程的 stdin/stdout 与 MCP Server 通信。
从零手写 AI Agent 课程 · 第 9 章
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any, Optional


class StdioTransport:
    """
    基于 stdio 的 MCP 传输层。
    
    通过启动子进程，用 stdin/stdout 与 MCP Server 通信。
    每条消息是一个 JSON-RPC 2.0 对象，以换行符分隔。
    
    使用示例：
        transport = StdioTransport(
            command=["python", "-m", "my_mcp_server"],
            env={"API_KEY": "xxx"}
        )
        await transport.connect()
        result = await transport.send_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        })
        await transport.close()
    """
    
    def __init__(
        self,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
    ):
        """
        Args:
            command: 启动 MCP Server 的命令
            env: 环境变量
            cwd: 工作目录
        """
        self.command = command
        self.env = env
        self.cwd = cwd
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
    
    async def connect(self) -> None:
        """连接到 MCP Server"""
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
            cwd=self.cwd,
        )
        
        # 启动读取循环
        asyncio.create_task(self._read_loop())
    
    async def _read_loop(self) -> None:
        """持续读取服务器响应"""
        assert self._process and self._process.stdout
        
        while True:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break  # 进程结束
                
                data = json.loads(line.decode('utf-8'))
                
                # 响应消息（有 id）
                if "id" in data:
                    msg_id = data["id"]
                    if msg_id in self._pending:
                        future = self._pending.pop(msg_id)
                        if "error" in data:
                            future.set_exception(
                                Exception(data["error"].get("message", "Unknown error"))
                            )
                        else:
                            future.set_result(data.get("result"))
                
                # 通知消息（没有 id）
                elif "method" in data:
                    # 通知消息，暂时不处理
                    pass
            
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # 跳过无效行
            except Exception:
                break
    
    async def send_request(self, request: dict) -> Any:
        """
        发送请求并等待响应。
        
        Args:
            request: JSON-RPC 请求（不含 id，会自动添加）
            
        Returns:
            响应结果
        """
        if not self._process or not self._process.stdin:
            raise RuntimeError("Transport not connected")
        
        # 生成唯一 ID
        self._request_id += 1
        request_id = self._request_id
        
        # 补全请求
        request["jsonrpc"] = "2.0"
        request["id"] = request_id
        
        # 创建 Future 等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[request_id] = future
        
        # 发送
        line = json.dumps(request) + "\n"
        self._process.stdin.write(line.encode('utf-8'))
        await self._process.stdin.drain()
        
        # 等待响应（超时 30 秒）
        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"Request {request_id} timed out")
    
    async def send_notification(self, method: str, params: dict) -> None:
        """发送通知（不需要响应）"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("Transport not connected")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        line = json.dumps(notification) + "\n"
        self._process.stdin.write(line.encode('utf-8'))
        await self._process.stdin.drain()
    
    async def close(self) -> None:
        """关闭连接"""
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except ProcessLookupError:
                pass
            self._process = None
```

### 代码 3：`src/mcp/client.py`

```python
"""
MCP 客户端 —— 连接和管理 MCP Server。

从零手写 AI Agent 课程 · 第 9 章
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.transport import StdioTransport


class MCPClient:
    """
    MCP 客户端。
    
    封装了与 MCP Server 的完整交互流程：
    1. 连接 → 初始化 → 获取能力
    2. 列出工具 → 调用工具
    3. 列出资源 → 读取资源
    
    使用示例：
        client = MCPClient(
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        )
        await client.connect()
        
        # 列出可用工具
        tools = await client.list_tools()
        
        # 调用工具
        result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
        
        await client.close()
    """
    
    def __init__(
        self,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        name: str = "",
    ):
        """
        Args:
            command: 启动 MCP Server 的命令
            env: 环境变量
            cwd: 工作目录
            name: 客户端名称（用于标识）
        """
        self.name = name or command[0]
        self.transport = StdioTransport(command, env, cwd)
        self._connected = False
        self._server_info: dict = {}
    
    async def connect(self) -> None:
        """连接并初始化 MCP Server"""
        await self.transport.connect()
        
        # 发送初始化请求
        result = await self.transport.send_request({
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "handwritten-agent",
                    "version": "0.1.0",
                },
            },
        })
        
        self._server_info = result or {}
        self._connected = True
        
        # 发送 initialized 通知
        await self.transport.send_notification(
            "notifications/initialized",
            {},
        )
    
    async def list_tools(self) -> list[dict]:
        """
        列出 MCP Server 提供的工具。
        
        Returns:
            工具列表，每个工具包含 name, description, inputSchema
        """
        if not self._connected:
            raise RuntimeError("Not connected")
        
        result = await self.transport.send_request({
            "method": "tools/list",
            "params": {},
        })
        
        return result.get("tools", []) if result else []
    
    async def call_tool(
        self,
        name: str,
        arguments: Optional[dict] = None,
    ) -> list[dict]:
        """
        调用 MCP 工具。
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具返回内容列表
        """
        if not self._connected:
            raise RuntimeError("Not connected")
        
        result = await self.transport.send_request({
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        })
        
        return result.get("content", []) if result else []
    
    async def list_resources(self) -> list[dict]:
        """列出 MCP Server 提供的资源"""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        result = await self.transport.send_request({
            "method": "resources/list",
            "params": {},
        })
        
        return result.get("resources", []) if result else []
    
    async def read_resource(self, uri: str) -> str:
        """读取资源"""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        result = await self.transport.send_request({
            "method": "resources/read",
            "params": {"uri": uri},
        })
        
        if result and result.get("contents"):
            return result["contents"][0].get("text", "")
        return ""
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def close(self) -> None:
        """关闭连接"""
        await self.transport.close()
        self._connected = False
```

### 代码 4：`src/mcp/tool.py`

```python
"""
MCP 工具适配器 —— 将 MCP 工具包装为 Agent 的 Tool。

从零手写 AI Agent 课程 · 第 9 章
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tools.base import Tool
from mcp.client import MCPClient


class MCPToolAdapter:
    """
    MCP 工具适配器。
    
    将 MCP Server 的工具转换为 Agent 可用的 Tool 对象。
    
    使用示例：
        client = MCPClient(command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
        await client.connect()
        
        adapter = MCPToolAdapter(client)
        mcp_tools = await adapter.wrap_all()
        
        agent = Agent(tools=[*builtin_tools, *mcp_tools])
    """
    
    def __init__(self, client: MCPClient):
        self.client = client
        self._tools: list[MCPToolWrapper] = []
    
    async def wrap_all(self) -> list['MCPToolWrapper']:
        """
        将 MCP Server 的所有工具包装为 Tool 对象。
        
        Returns:
            Tool 对象列表
        """
        raw_tools = await self.client.list_tools()
        self._tools = [
            MCPToolWrapper(self.client, tool_def)
            for tool_def in raw_tools
        ]
        return self._tools
    
    async def wrap_one(self, tool_name: str) -> Optional['MCPToolWrapper']:
        """包装单个工具"""
        raw_tools = await self.client.list_tools()
        for tool_def in raw_tools:
            if tool_def.get("name") == tool_name:
                wrapper = MCPToolWrapper(self.client, tool_def)
                self._tools.append(wrapper)
                return wrapper
        return None


class MCPToolWrapper(Tool):
    """
    MCP 工具包装器。
    
    将 MCP 工具的定义转换为 Agent 的 Tool 接口。
    """
    
    def __init__(self, client: MCPClient, tool_def: dict):
        self._client = client
        self._tool_def = tool_def
    
    @property
    def name(self) -> str:
        return self._tool_def.get("name", "unknown")
    
    @property
    def description(self) -> str:
        return self._tool_def.get("description", "")
    
    @property
    def parameters(self) -> dict:
        return self._tool_def.get("inputSchema", {
            "type": "object",
            "properties": {},
        })
    
    def execute(self, **kwargs: Any) -> str:
        """同步执行（在事件循环中运行异步调用）"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self._client.call_tool(self.name, kwargs)
        )
        
        # 格式化结果
        parts = []
        for item in result:
            if item.get("type") == "text":
                parts.append(item["text"])
            elif item.get("type") == "image":
                parts.append(f"[图片: {item.get('mimeType', 'unknown')}]")
        
        return "\n".join(parts) if parts else "[无返回内容]"
```

---

## 🧪 测试验证

```python
"""测试 MCP 客户端"""
import asyncio
from mcp.client import MCPClient


async def test_mcp_client():
    """测试 MCP 客户端（需要一个实际的 MCP Server）"""
    # 示例：使用文件系统 MCP Server
    # 需要先安装：npm install -g @modelcontextprotocol/server-filesystem
    
    try:
        client = MCPClient(
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            name="filesystem",
        )
        
        await client.connect()
        print(f"✅ 连接成功: {client._server_info}")
        
        # 列出工具
        tools = await client.list_tools()
        print(f"✅ 可用工具: {[t['name'] for t in tools]}")
        
        await client.close()
        print("✅ 关闭成功")
        
    except FileNotFoundError:
        print("⚠️  跳过测试（npx 不可用）")
        print("   安装 Node.js 后重试")
    except Exception as e:
        print(f"⚠️  测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_mcp_client())
```

---

## ⚠️ 常见错误

### 错误 1：`FileNotFoundError: npx`
**原因**：没有安装 Node.js。
**解决**：安装 Node.js，或者使用 Python 实现的 MCP Server。

### 错误 2：`TimeoutError: Request timed out`
**原因**：MCP Server 启动太慢或响应超时。
**解决**：增加超时时间，或检查 Server 是否正常启动。

### 错误 3：JSON 解析错误
**原因**：MCP Server 输出了非 JSON 内容（如日志信息到 stdout）。
**解决**：确保 MCP Server 只通过 stdout 输出 JSON-RPC 消息，日志应输出到 stderr。

---

## 📝 本章小结

本章实现了 MCP 协议支持：

| 组件 | 作用 |
|------|------|
| **StdioTransport** | 通过子进程 stdin/stdout 通信 |
| **MCPClient** | 完整的 MCP 客户端（初始化、工具、资源） |
| **MCPToolAdapter** | 将 MCP 工具包装为 Agent 的 Tool |

### 当前局限性

- ❌ 只支持 stdio 传输，不支持 HTTP/SSE
- ❌ 没有 MCP Server 的实现（只有 Client）
- ❌ 错误处理不够完善

**下一章**，我们将实现多智能体协作——让多个 Agent 协同工作。

---

## 🏋️ 课后练习

### 练习 1：实现一个简单的 MCP Server
用 Python 实现一个提供天气查询的 MCP Server：
```python
# weather_server.py
import sys
import json

def handle_request(request):
    method = request.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
    elif method == "tools/list":
        return {"tools": [{"name": "get_weather", "description": "..."}]}
    elif method == "tools/call":
        if request["params"]["name"] == "get_weather":
            return {"content": [{"type": "text", "text": "晴天，25°C"}]}

for line in sys.stdin:
    request = json.loads(line)
    result = handle_request(request)
    response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
    print(json.dumps(response), flush=True)
```

### 练习 2：实现 HTTP Transport
支持通过 HTTP SSE 连接远程 MCP Server。

### 练习 3：实现 MCP 资源订阅
监听资源变化，自动更新。

---

**下一章**：[第 10 章：多智能体协作 —— Team Mode](ch10-多智能体协作.md)
