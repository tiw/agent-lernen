"""
mcp/client.py —— MCP Client 实现

MCP 客户端，用于连接 MCP 服务器、发现工具、调用工具。
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
    """MCP 客户端"""

    def __init__(self, transport: Transport):
        self.transport = transport
        self._next_id = 1
        self._server_info: Optional[dict] = None
        self._capabilities: Optional[dict] = None
        self._tools: list = []

    async def connect(self) -> None:
        """连接并初始化"""
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

    async def refresh_tools(self) -> list:
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
        """调用工具"""
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

        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        if len(texts) == 1:
            return texts[0]
        return texts

    async def list_resources(self) -> list:
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

    def get_tools(self) -> list:
        """获取已发现的工具列表"""
        return list(self._tools)

    async def close(self) -> None:
        """关闭连接"""
        await self.transport.close()

    async def _send_request(self, request: JsonRpcRequest) -> Optional[JsonRpcResponse]:
        """发送请求并等待响应"""
        request.id = self._next_id
        self._next_id += 1
        await self.transport.send(request.to_dict())

        response_data = await self.transport.receive()
        if response_data:
            return JsonRpcResponse(
                id=response_data.get("id"),
                result=response_data.get("result"),
                error=response_data.get("error"),
            )
        return None

    async def _send_notification(self, method: str, params: dict = None) -> None:
        """发送通知"""
        from .protocol import JsonRpcNotification
        notification = JsonRpcNotification(method=method, params=params or {})
        await self.transport.send(notification.to_dict())


async def create_stdio_client(command: list) -> MCPClient:
    """创建 stdio 客户端"""
    transport = StdioTransport(command=command)
    client = MCPClient(transport)
    await client.connect()
    return client
