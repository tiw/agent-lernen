"""
MCP 示例服务器 —— 天气查询服务
"""

import asyncio
import json
from mcp.server import MCPServer

server = MCPServer("weather-server", "1.0.0")


@server.tool("get_weather", "获取指定城市的天气信息", {
    "type": "object",
    "properties": {
        "city": {"type": "string", "description": "城市名称"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
    },
    "required": ["city"]
})
async def get_weather(city: str, unit: str = "celsius") -> str:
    """模拟天气查询"""
    return json.dumps({
        "city": city,
        "temperature": 22 if unit == "celsius" else 72,
        "unit": unit,
        "condition": "晴天",
        "humidity": 65,
    }, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(server.run_stdio())
