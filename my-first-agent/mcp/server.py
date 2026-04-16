"""
mcp/server.py —— MCP Server 实现（简化版）
从零手写 AI Agent 课程 · 第 9 章
"""

import asyncio
import json
import logging
import sys
import os
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from mcp.protocol import (
        JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
        MCPTool, MCPResource, MCPToolCallResult,
        parse_message, make_error_response,
    )
    from mcp.transport import Transport, StdioTransport
else:
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
    """

    def __init__(self, name: str = "mcp-server", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, MCPToolHandler] = {}
        self._resources: dict[str, MCPResource] = {}
        self._resource_readers: dict[str, Callable] = {}
        self._initialized = False
        self._message_id = 0

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[[dict], Any],
    ) -> None:
        """注册一个工具"""
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
        )
        self._tools[name] = MCPToolHandler(tool=tool, handler=handler)
        logger.info(f"Registered tool: {name}")

    async def handle_message(self, message: dict) -> Optional[JsonRpcResponse]:
        """处理一条 JSON-RPC 消息"""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                return self._handle_initialize(msg_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(msg_id)
            elif method == "tools/call":
                return await self._handle_tools_call(msg_id, params)
            elif method == "ping":
                return JsonRpcResponse(id=msg_id, result={})
            else:
                return make_error_response(
                    msg_id, -32601, f"Method not found: {method}"
                )
        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            return make_error_response(msg_id, -32600, str(e))

    def _handle_initialize(self, msg_id: int, params: dict) -> JsonRpcResponse:
        """处理初始化请求"""
        self._initialized = True
        return JsonRpcResponse(
            id=msg_id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
        )

    def _handle_tools_list(self, msg_id: int) -> JsonRpcResponse:
        """处理工具列表请求"""
        tools = [
            {
                "name": t.tool.name,
                "description": t.tool.description,
                "inputSchema": t.tool.input_schema,
            }
            for t in self._tools.values()
        ]
        return JsonRpcResponse(id=msg_id, result={"tools": tools})

    async def _handle_tools_call(self, msg_id: int, params: dict) -> JsonRpcResponse:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self._tools:
            return make_error_response(msg_id, -32602, f"Tool not found: {tool_name}")

        handler = self._tools[tool_name].handler
        try:
            result = handler(arguments)
            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            else:
                content = [{"type": "text", "text": json.dumps(result)}]
            return JsonRpcResponse(id=msg_id, result={"content": content})
        except Exception as e:
            return make_error_response(msg_id, -32000, str(e))

    async def run_stdio(self) -> None:
        """通过 stdio 运行服务器"""
        transport = StdioTransport()
        await transport.connect()

        logger.info(f"MCP Server '{self.name}' started (stdio mode)")

        try:
            while True:
                message = await transport.receive()
                if not message:
                    break

                response = await self.handle_message(message)
                if response:
                    await transport.send(response.to_dict())
        except asyncio.CancelledError:
            pass
        finally:
            await transport.close()


# === 测试 ===
if __name__ == "__main__":
    async def test_server():
        print("=== MCP Server 测试 ===\n")

        # 创建服务器
        server = MCPServer(name="test-server", version="1.0.0")

        # 注册测试工具
        def echo_handler(args: dict) -> str:
            return f"Echo: {args.get('message', '')}"

        server.register_tool(
            name="echo",
            description="Echo a message",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"}
                },
                "required": ["message"],
            },
            handler=echo_handler,
        )

        # 测试工具列表
        print("测试 1: 工具列表")
        resp = server._handle_tools_list(1)
        print(f"  响应：{json.dumps(resp.to_dict(), indent=2)}\n")

        # 测试工具调用
        print("测试 2: 工具调用")
        resp = await server._handle_tools_call(
            2,
            {"name": "echo", "arguments": {"message": "Hello World"}}
        )
        print(f"  响应：{json.dumps(resp.to_dict(), indent=2)}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_server())
