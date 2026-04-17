"""
cli/commands.py —— Slash 命令处理器
参考 Claude Code 的 commands/ 目录（100+ 个命令）
从零手写 AI Agent 课程 · 第 12 章
"""

import logging
from typing import Callable, Any, Union

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
        aliases: Union[list[str], None] = None,
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
            return f"未知命令：{cmd_name}。输入 /help 查看可用命令。"

        try:
            result = cmd["handler"](args, context)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            logger.error(f"Command error: {cmd_name}: {e}")
            return f"命令执行失败：{e}"

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
    registry.register("/reset", cmd_reset, "重置对话", ["/restart"])
    registry.register("/skills", cmd_skills, "列出已加载技能")
    registry.register("/memory", cmd_memory, "查看记忆状态")
    registry.register("/tasks", cmd_tasks, "查看任务列表")
    registry.register("/team", cmd_team, "启动多智能体协作 <描述>")
    registry.register("/security", cmd_security, "查看安全策略")
    registry.register("/hooks", cmd_hooks, "查看已启用 hooks")
    registry.register("/audit", cmd_audit, "查看审计日志")


def cmd_reset(args: str, ctx: dict) -> str:
    """重置对话"""
    agent = ctx.get("agent")
    if agent and hasattr(agent, "reset"):
        agent.reset()
        return "🔄 对话已重置"
    return "重置不可用"


def cmd_skills(args: str, ctx: dict) -> str:
    """列出已加载技能"""
    agent = ctx.get("agent")
    if agent and hasattr(agent, "skill_loader"):
        skills = agent.skill_loader._skills
        if not skills:
            return "📚 没有已加载的技能"
        lines = ["📚 已加载技能：", ""]
        for name, skill in skills.items():
            enabled = "✅" if skill.enabled else "❌"
            lines.append(f"  {enabled} {name}: {skill.description}")
        return "\n".join(lines)
    return "技能系统未启用"


def cmd_memory(args: str, ctx: dict) -> str:
    """查看记忆状态"""
    agent = ctx.get("agent")
    if not agent or not hasattr(agent, "short_term"):
        return "记忆系统未启用"
    lines = ["🧠 记忆状态：", ""]
    st = agent.short_term
    stats = st.get_stats()
    lines.append(f"  消息数：{stats['message_count']}")
    lines.append(f"  Token 使用：{stats['total_tokens']} / {stats['max_context_tokens']}")
    lines.append(f"  需压缩：{stats['should_compress']}")
    lines.append(f"  工具结果截断：{stats['tool_budget']['truncated']}")
    lines.append(f"  工具结果冻结：{stats['tool_budget']['pinned']}")
    if agent.memory_store:
        mem_stats = agent.memory_store.get_stats() if hasattr(agent.memory_store, "get_stats") else {}
        lines.append(f"  长期记忆数：{mem_stats.get('total_memories', 'N/A')}")
    return "\n".join(lines)


def cmd_tasks(args: str, ctx: dict) -> str:
    """查看任务列表"""
    agent = ctx.get("agent")
    if agent and hasattr(agent, "task_registry"):
        tasks = agent.task_registry.list_tasks()
        if not tasks:
            return "📋 没有待办任务"
        lines = ["📋 任务列表：", ""]
        for task in tasks:
            status = "✅" if task.status.value == "completed" else "🔄" if task.status.value == "in_progress" else "⏳"
            lines.append(f"  {status} {task.name}: {task.status.value}")
        return "\n".join(lines)
    return "任务系统未启用"


async def cmd_team(args: str, ctx: dict) -> str:
    """启动多智能体协作"""
    agent = ctx.get("agent")
    if not agent or not hasattr(agent, "coordinator"):
        return "多智能体未启用"
    if not args:
        return "💡 用法：/team <任务描述>（如：/team 分析当前项目的架构）"
    # 显示团队状态
    status = agent.coordinator.get_team_status()
    roles = status.get("members", [])
    idle = sum(1 for r in roles if r.get("status") == "idle")
    header = f"🤝 任务执行中：{args}\n团队状态：{idle}/{len(roles)} 个角色已就绪\n"
    # 调用 plan_and_execute 实际执行任务
    result = await agent.coordinator.plan_and_execute(args)
    lines = [header]
    lines.append(f"✅ 任务完成：{result.get('tasks_completed', 0)}/{result.get('tasks_total', 0)}")
    lines.append("")
    # 展示每个任务的结果
    summary = result.get("summary", "")
    if summary:
        lines.append(summary)
    return "\n".join(lines)


def cmd_security(args: str, ctx: dict) -> str:
    """查看安全策略"""
    agent = ctx.get("agent")
    if not agent or not hasattr(agent, "security_policy") or not agent.security_policy:
        return "安全策略未启用"
    lines = ["🛡️ 安全策略：", ""]
    lines.append(f"  严格模式：{agent.security_policy.strict_mode}")
    if agent.whitelist:
        lines.append(f"  安全规则数：{len(agent.whitelist.safe_patterns)}")
        lines.append(f"  禁止规则数：{len(agent.whitelist.dangerous_patterns)}")
    if hasattr(agent, "auditor") and agent.auditor:
        recent = agent.auditor.get_recent(5)
        lines.append(f"  最近审计记录：{len(recent)} 条")
    return "\n".join(lines)


def cmd_hooks(args: str, ctx: dict) -> str:
    """查看已启用 hooks"""
    agent = ctx.get("agent")
    if not agent or not agent.hook_registry:
        return "Hook 系统未启用"
    hooks = agent.hook_registry.list_hooks()
    if not hooks:
        return "🔗 没有已注册的 hooks"
    lines = ["🔗 已注册 hooks：", ""]
    for h in hooks:
        enabled = "✅" if h.get("enabled", True) else "❌"
        lines.append(f"  {enabled} {h['name']}: {h.get('event', 'N/A')}")
    return "\n".join(lines)


def cmd_audit(args: str, ctx: dict) -> str:
    """查看审计日志"""
    agent = ctx.get("agent")
    if not agent or not hasattr(agent, "auditor") or not agent.auditor:
        return "审计日志未启用"
    recent = agent.auditor.get_recent(10)
    if not recent:
        return "📋 没有审计记录"
    lines = ["📋 最近审计记录：", ""]
    for event in recent:
        lines.append(f"  [{event.timestamp.strftime('%H:%M:%S')}] {event.type}: {event.message}")
    return "\n".join(lines)


# === 测试 ===
if __name__ == "__main__":
    async def test_commands():
        print("=== Slash 命令测试 ===\n")

        import asyncio
        import sys
        import os

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        registry = CommandRegistry()
        register_builtin_commands(registry)

        # 测试 1: 列出命令
        print("测试 1: 列出命令")
        cmds = registry.list_commands()
        for cmd in cmds:
            print(f"  {cmd['name']}: {cmd['description']}\n")

        # 测试 2: 执行 /help
        print("测试 2: 执行 /help")
        result = await registry.execute("/help", {})
        print(f"  {result[:200]}...\n")

        # 测试 3: 执行未知命令
        print("测试 3: 执行未知命令")
        result = await registry.execute("/unknown", {})
        print(f"  {result}\n")

        print("✅ 所有测试完成！")

    import asyncio
    asyncio.run(test_commands())
