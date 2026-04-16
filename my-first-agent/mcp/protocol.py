"""
mcp/protocol.py —— MCP 协议定义
基于 JSON-RPC 2.0 的 MCP 消息格式。
参考 MCP 官方规范：https://modelcontextprotocol.io
从零手写 AI Agent 课程 · 第 9 章
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


# === 测试 ===
if __name__ == "__main__":
    print("=== MCP 协议测试 ===\n")

    # 测试 1: JSON-RPC 请求
    print("测试 1: JSON-RPC 请求")
    req = JsonRpcRequest(id=1, method="tools/list", params={})
    print(f"  请求：{req.to_json()}")

    # 测试 2: JSON-RPC 响应
    print("\n测试 2: JSON-RPC 响应")
    resp = JsonRpcResponse(id=1, result={"tools": []})
    print(f"  响应：{resp.to_json()}")

    # 测试 3: MCP 初始化请求
    print("\n测试 3: MCP 初始化请求")
    init_req = MCPInitializeRequest()
    req = init_req.to_request()
    print(f"  初始化：{req.to_json()}")

    # 测试 4: MCP 工具定义
    print("\n测试 4: MCP 工具定义")
    tool = MCPTool(
        name="query_database",
        description="Execute SQL query",
        input_schema={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL query"}
            },
            "required": ["sql"],
        }
    )
    print(f"  工具名：{tool.name}")
    print(f"  描述：{tool.description}")
    print(f"  Schema: {tool.input_schema}")

    # 测试 5: 错误响应
    print("\n测试 5: 错误响应")
    error_resp = make_error_response(1, -32601, "Method not found")
    print(f"  错误：{error_resp.to_json()}")

    print("\n✅ 所有测试完成！")
