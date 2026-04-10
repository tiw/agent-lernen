"""
MCP 示例服务器 —— 数据库查询服务

演示如何注册资源和工具。
"""

import asyncio
import json
from mcp.server import MCPServer

server = MCPServer("database-server", "1.0.0")


@server.tool("query", "执行 SQL 查询", {
    "type": "object",
    "properties": {
        "sql": {"type": "string", "description": "SQL 查询语句"},
        "database": {"type": "string", "description": "数据库名称"}
    },
    "required": ["sql"]
})
async def query_tool(sql: str, database: str = "default") -> str:
    """模拟数据库查询"""
    return json.dumps({
        "database": database,
        "query": sql,
        "rows": [{"id": 1, "name": "示例数据"}],
        "count": 1,
    }, ensure_ascii=False)


@server.resource("db://schema", "数据库 Schema", "application/json")
async def get_schema() -> str:
    """返回数据库 schema 信息"""
    return json.dumps({
        "tables": ["users", "orders", "products"],
        "version": "1.0",
    }, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(server.run_stdio())
