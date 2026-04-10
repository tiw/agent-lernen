"""
MCP 示例服务器 —— 搜索服务
"""

import asyncio
import json
from mcp.server import MCPServer

server = MCPServer("search-server", "1.0.0")


@server.tool("search", "搜索指定关键词", {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "搜索关键词"},
        "limit": {"type": "integer", "description": "返回结果数量", "default": 10}
    },
    "required": ["query"]
})
async def search_tool(query: str, limit: int = 10) -> str:
    """模拟搜索"""
    return json.dumps({
        "query": query,
        "results": [
            {"title": f"结果 {i}", "url": f"https://example.com/{i}", "snippet": f"关于 {query} 的信息..."}
            for i in range(1, min(limit + 1, 4))
        ],
        "total": limit,
    }, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(server.run_stdio())
