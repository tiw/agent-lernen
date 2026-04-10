from __future__ import annotations

"""
Slash 命令处理器

参考 Claude Code 的 commands/ 目录（100+ 个命令）
"""

import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Slash 命令注册表"""

    def __init__(self):
        self._commands: dict[str, dict] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """注册一个命令"""
        self._commands[name] = {
            "handler": handler,
            "description": description,
            "aliases": aliases or [],
        }
        for alias in (aliases or []):
            self._commands[alias] = self._commands[name]

    async def execute(self, command_line: str, context: dict) -> Any:
        """执行命令"""
        parts = command_line.strip().split(maxsplit=1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(cmd_name)
        if not cmd:
            return f"未知命令: {cmd_name}。输入 /help 查看可用命令。"

        try:
            result = cmd["handler"](args, context)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            logger.error(f"Command error: {cmd_name}: {e}")
            return f"命令执行失败: {e}"

    def list_commands(self) -> list[dict]:
        """列出所有命令"""
        seen = set()
        commands = []
        for name, info in self._commands.items():
            if name not in seen:
                seen.add(name)
                commands.append({
                    "name": name,
                    "description": info["description"],
                    "aliases": info["aliases"],
                })
        return sorted(commands, key=lambda x: x["name"])


def register_builtin_commands(registry: CommandRegistry) -> None:
    """注册内置命令"""

    def cmd_help(args: str, ctx: dict) -> str:
        cmds = registry.list_commands()
        lines = ["📋 可用命令：", ""]
        for cmd in cmds:
            aliases = f" ({', '.join(cmd['aliases'])})" if cmd["aliases"] else ""
            lines.append(f"  {cmd['name']:<12} {cmd['description']}{aliases}")
        lines.append("")
        lines.append("💡 直接输入文字即可与 Agent 对话")
        return "\n".join(lines)

    def cmd_clear(args: str, ctx: dict) -> str:
        ctx.get("clear_callback", lambda: None)()
        return ""

    def cmd_quit(args: str, ctx: dict) -> str:
        raise SystemExit(0)

    def cmd_cost(args: str, ctx: dict) -> str:
        agent = ctx.get("agent")
        if agent and hasattr(agent, "cost_tracker"):
            return agent.cost_tracker.summary()
        return "成本追踪未启用"

    def cmd_tools(args: str, ctx: dict) -> str:
        agent = ctx.get("agent")
        if agent and hasattr(agent, "tools"):
            lines = ["🔧 可用工具：", ""]
            for tool in agent.tools:
                lines.append(f"  {tool.name:<15} {tool.description}")
            return "\n".join(lines)
        return "无可用工具"

    registry.register("/help", cmd_help, "显示帮助信息", ["/h", "/?"])
    registry.register("/clear", cmd_clear, "清空对话", ["/cls"])
    registry.register("/quit", cmd_quit, "退出", ["/exit", "/q"])
    registry.register("/cost", cmd_cost, "查看成本")
    registry.register("/tools", cmd_tools, "列出工具")
