"""
mcp/server.py —— MCP Server 实现

参考 MCP 官方 Python SDK 的 Server 实现
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
    """

    def __init__(self, name: str = "mcp-server", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict = {}
        self._resources: dict = {}
        self._resource_readers: dict = {}
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

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: str = "text/plain",
        reader: Optional[Callable] = None,
    ) -> None:
        """注册一个资源"""
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

    async def handle_message(self, message: dict) -> Optional[JsonRpcResponse]:
        """处理一条 JSON-RPC 消息"""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        try:
            if method == "initialize":
                return self._handle_initialize(msg_id, params)
            elif method == "initialized":
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

    async def run_stdio(self) -> None:
        """通过 stdio 运行服务器"""
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
