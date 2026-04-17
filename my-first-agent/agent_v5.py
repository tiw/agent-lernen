"""
Agent v5 —— 全集成的 AI Agent（Chapter 1-13）
从零手写 AI Agent 课程 · 集成版本

集成模块：
- Ch01-04: Agent Core + 9 个工具（Bash, Python, File, Web, Search）
- Ch05-06: 记忆系统（短期 + 长期）
- Ch07: 任务系统
- Ch08: 技能系统
- Ch09: MCP Server
- Ch10: 多智能体协作
- Ch11: Hook 系统
- Ch12: CLI 终端界面
- Ch13: 安全与权限
"""

import os
import sys
import json
import asyncio
import time
import uuid
from typing import Optional, List
from pathlib import Path
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

# ============================================================
# Ch01-04: 工具层
# ============================================================
from tools.bash_tool import BashTool
from tools.python_tool import PythonTool
from tools.file_tools import create_file_tools, FileSandbox
from tools.web_tools import WebSearchTool, WebFetchTool
from tools.search_tools import GrepTool, GlobTool

# ============================================================
# Ch05-06: 记忆系统
# ============================================================
from memory.token_counter import TokenEstimator
from memory.long_term import MemoryStore, Memory, MemoryType
from memory.embedding_store import EmbeddingStore, HashEmbeddingProvider, SemanticMemorySearch

# 动态导入（session_memory 依赖 tool_budget 和 micro_compact）
from memory.session_memory import ShortTermMemory, SessionMemory

# ============================================================
# Ch07: 任务系统
# ============================================================
from tasks.base import TaskRegistry, TaskType, TaskStatus
from tasks.shell_task import ShellTask

# ============================================================
# Ch08: 技能系统
# ============================================================
from skills.skill import Skill
from skills.loader import SkillLoader

# ============================================================
# Ch10: 多智能体协作
# ============================================================
from team.coordinator import Coordinator
from team.roles import RoleType

# ============================================================
# Ch11: Hook 系统
# ============================================================
from hooks.event_bus import EventBus, HookEvent, HookContext
from hooks.registry import HookRegistry

# ============================================================
# Ch13: 安全与权限
# ============================================================
from security.policy import SecurityPolicy, Decision
from security.whitelist import CommandWhitelist, SafetyLevel
from security.filter import SensitiveDataFilter
from security.auditor import Auditor, AuditEvent


class AgentV5:
    """全集成的 AI Agent（Chapter 1-13）"""

    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "qwen-plus",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tool_iterations: int = 10,
        max_context_tokens: int = 100000,
        sandbox_dirs: Optional[List[str]] = None,
        strict_mode: bool = False,
        enable_memory: bool = True,
        enable_skills: bool = True,
        enable_security: bool = True,
        enable_hooks: bool = True,
        enable_team: bool = True,
    ):
        self.console = Console()
        self.session_id = str(uuid.uuid4())[:8]

        # === Ch01: LLM 初始化 ===
        api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未找到 API 密钥！请设置 DASHSCOPE_API_KEY 环境变量")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        self.system_prompt = system_prompt
        self.messages = [{"role": "system", "content": system_prompt}]
        self.max_tool_iterations = max_tool_iterations
        self.max_context_tokens = max_context_tokens

        # === Ch05: Token 估算 ===
        self.token_estimator = TokenEstimator()

        # === Ch05-06: 记忆系统 ===
        self.enable_memory = enable_memory
        if enable_memory:
            self.short_term = ShortTermMemory(
                session_id="v5_default",
                max_context_tokens=max_context_tokens,
            )
            self.memory_store = MemoryStore(db_path=".agent_memory.db")
            emb_store = EmbeddingStore(
                db_path=".agent_memory.db",
                provider=HashEmbeddingProvider(),
            )
            self.semantic_search = SemanticMemorySearch(self.memory_store, emb_store)
        else:
            self.short_term = None
            self.memory_store = None
            self.semantic_search = None

        # === Ch07: 任务系统 ===
        self.task_registry = TaskRegistry()

        # === Ch08: 技能系统 ===
        self.enable_skills = enable_skills
        self.skill_loader = SkillLoader()
        if enable_skills:
            # 加载用户技能和项目技能
            user_skills_dir = Path.home() / ".claude" / "skills"
            project_skills_dir = Path.cwd() / ".claude" / "skills"
            user_skills_alt = Path.cwd() / "my-skills"
            if user_skills_dir.exists():
                self.skill_loader.load_directory(user_skills_dir, source="user")
            if project_skills_dir.exists():
                self.skill_loader.load_directory(project_skills_dir, source="project")
            if user_skills_alt.exists():
                self.skill_loader.load_directory(user_skills_alt, source="user")

        # === Ch13: 安全系统 ===
        self.enable_security = enable_security

        # === Ch11: Hook 系统 ===
        self.enable_hooks = enable_hooks
        if enable_hooks:
            self.event_bus = EventBus()
            self.hook_registry = HookRegistry(event_bus=self.event_bus)
            # 注册内置 hooks
            self._register_builtin_hooks()
        else:
            self.event_bus = None
            self.hook_registry = None
        if enable_security:
            self.whitelist = CommandWhitelist()
            self.sensitive_filter = SensitiveDataFilter()
            self.security_policy = SecurityPolicy(
                whitelist=self.whitelist,
                filter_=self.sensitive_filter,
                strict_mode=strict_mode,
            )
            self.auditor = Auditor(log_dir=".agent_audit")
        else:
            self.whitelist = None
            self.sensitive_filter = None
            self.security_policy = None
            self.auditor = None

        # === Ch10: 多智能体协作 ===
        self.enable_team = enable_team
        if enable_team:
            self.coordinator = Coordinator("v5-team", client=self.client, model=self.model)
            # 默认添加所有预定义角色
            self.coordinator.add_roles(list(RoleType))

        # === Ch01-04: 工具初始化 ===
        sandbox_dirs = sandbox_dirs or [os.getcwd(), "/tmp"]
        self.sandbox_dirs = sandbox_dirs

        self._init_tools(sandbox_dirs)

        # 统计
        self.total_turns = 0
        self.total_tool_calls = 0
        self.session_start = time.time()

    # ============================================================
    # Ch01-04: 工具初始化
    # ============================================================

    def _init_tools(self, sandbox_dirs: List[str]):
        """初始化所有工具"""
        read_tool, write_tool, edit_tool = create_file_tools(
            allowed_dirs=sandbox_dirs
        )

        web_search = WebSearchTool(max_results=8)
        web_fetch = WebFetchTool(timeout=30)
        grep = GrepTool(root_dir=os.getcwd())
        glob_tool = GlobTool(root_dir=os.getcwd())

        self.tools = [
            BashTool(),
            PythonTool(),
            read_tool, write_tool, edit_tool,
            web_search, web_fetch,
            grep, glob_tool,
        ]
        self.tool_map = {tool.name: tool for tool in self.tools}

    def _build_tool_defs(self) -> list:
        """构建工具定义列表"""
        return [tool.to_openai_format() for tool in self.tools]

    # ============================================================
    # Ch11: Hook 注册
    # ============================================================

    def _register_builtin_hooks(self):
        """注册内置 hooks"""
        if not self.hook_registry:
            return

        # Hook: UserPromptSubmit — 记录用户输入
        self.hook_registry.register(
            name="input_logger",
            event=HookEvent.USER_PROMPT_SUBMIT,
            callback=self._hook_log_input,
            priority=100,
        )

        # Hook: ToolResult — 安全扫描
        if self.enable_security:
            self.hook_registry.register(
                name="security_scanner",
                event=HookEvent.TOOL_RESULT,
                callback=self._hook_security_scan,
                priority=100,
            )

        # Hook: AssistantResponse — 审计记录
        if self.enable_security:
            self.hook_registry.register(
                name="audit_logger",
                event=HookEvent.ASSISTANT_RESPONSE,
                callback=self._hook_audit_log,
                priority=100,
            )

    def _hook_log_input(self, ctx: HookContext):
        """记录用户输入到审计日志"""
        if self.auditor:
            self.auditor.log(AuditEvent.create(
                event_type="user_input",
                decision="logged",
                details={"input_length": ctx.get("input_length", 0)},
                session_id=self.session_id,
            ))

    def _hook_security_scan(self, ctx: HookContext):
        """安全扫描工具结果"""
        result = ctx.get("result", "")
        if self.sensitive_filter:
            filtered = self.sensitive_filter.filter_text(result)
            if filtered != result:
                ctx.modify("result", filtered)

    def _hook_audit_log(self, ctx: HookContext):
        """审计助手回复"""
        if self.auditor:
            self.auditor.log(AuditEvent.create(
                event_type="assistant_response",
                decision="logged",
                details={"output_length": ctx.get("output_length", 0)},
                session_id=self.session_id,
            ))

    # ============================================================
    # Ch11: Hook 发布辅助
    # ============================================================

    async def _emit_hook(self, event: HookEvent, data: dict):
        """触发 Hook 事件"""
        if not self.event_bus:
            return
        ctx = HookContext(event=event, data=data, session_id=self.session_id)
        await self.event_bus.emit(event, ctx)
        return ctx

    def _emit_hook_sync(self, event: HookEvent, data: dict):
        """同步触发 Hook 事件（用于同步 chat 循环）"""
        if not self.event_bus:
            return None
        ctx = HookContext(event=event, data=data, session_id=self.session_id)
        # 同步检查 handler（不使用异步 emit，避免需要事件循环）
        handlers = self.event_bus._handlers.get(event, [])
        for callback in handlers:
            try:
                result = callback(ctx)
                if asyncio.iscoroutine(result):
                    # 同步环境下无法 await，跳过异步 handler
                    pass
            except Exception:
                pass
        return ctx

    # ============================================================
    # Ch08: System Prompt 动态构建
    # ============================================================

    def _build_system_prompt(self) -> str:
        """动态构建 system prompt，注入技能、记忆等"""
        parts = [self.system_prompt]

        # 注入技能
        if self.enable_skills and self.skill_loader:
            skills = self.skill_loader.list_skills()
            if skills:
                skill_text = "\n\n".join(
                    f"## Skill: {s['name']}\n{s.get('description', '')}"
                    for s in skills
                )
                parts.append(f"\n[Available Skills]\n{skill_text}")

        # 注入会话记忆摘要
        if self.enable_memory and self.short_term:
            injection = self.short_term.session_memory.get_injection_prompt()
            if injection:
                parts.append(f"\n{injection}")

        return "\n".join(parts)

    # ============================================================
    # Ch05: 消息修剪
    # ============================================================

    def _trim_messages_if_needed(self):
        """如果消息总 token 超过限制，移除最旧的非系统消息"""
        total = self.token_estimator.estimate_messages(self.messages)
        if total <= self.max_context_tokens:
            return

        # 移除最旧的非系统消息（保留 system 和最近 4 条）
        non_system = [i for i, m in enumerate(self.messages) if m.get("role") != "system"]
        keep_recent = 4
        to_remove = non_system[:-keep_recent] if len(non_system) > keep_recent else []

        for i in sorted(to_remove, reverse=True):
            del self.messages[i]

    # ============================================================
    # Ch05: 记忆压缩
    # ============================================================

    def _try_compress_memory(self):
        """尝试压缩记忆"""
        if not self.enable_memory or not self.short_term:
            return

        if self.short_term.should_compress():
            result = self.short_term.compress()
            if result.get("session_memory_injection"):
                # 注入会话记忆摘要
                injection = result["session_memory_injection"]
                # 插入到 system 消息之后
                self.messages.insert(1, {
                    "role": "system",
                    "content": injection,
                })

    # ============================================================
    # Ch01-04 + Ch11/Ch13: 核心 Chat 循环
    # ============================================================

    def chat(self, user_input: str) -> str:
        """与 Agent 对话（支持工具调用、记忆、安全、hooks）"""
        self.total_turns += 1

        # Hook: UserPromptSubmit
        self._emit_hook_sync(HookEvent.USER_PROMPT_SUBMIT, {
            "input": user_input,
            "input_length": len(user_input),
        })

        # 安全检查：敏感信息过滤
        if self.enable_security and self.sensitive_filter:
            filtered = self.sensitive_filter.filter_text(user_input)
            if filtered != user_input:
                self.console.print("[dim][安全] 输入中的敏感信息已被过滤[/dim]")

        # 记录到短期记忆
        user_msg = {"role": "user", "content": user_input}
        if self.enable_memory and self.short_term:
            self.short_term.add_message(user_msg)
        self.messages.append(user_msg)

        # 动态构建 system prompt
        self.messages[0]["content"] = self._build_system_prompt()

        # 记忆压缩检查
        self._try_compress_memory()

        # 消息修剪
        self._trim_messages_if_needed()

        # 调用 LLM
        tool_defs = self._build_tool_defs()
        iteration = 0

        while iteration < self.max_tool_iterations:
            iteration += 1
            self.console.print("\n[dim]🤔 Agent 正在思考...[/dim]")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_defs,
            )

            message = response.choices[0].message

            if message.tool_calls:
                self.console.print(f"[dim]🔧 第 {iteration} 次工具调用...[/dim]")
                self.messages.append(message)

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id
                    self.total_tool_calls += 1

                    self.console.print(f"[dim]   → 调用 {tool_name}[/dim]")

                    # Hook: ToolCall
                    self._emit_hook_sync(HookEvent.TOOL_CALL, {
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    # 安全检查：bash 命令白名单
                    if (self.enable_security and tool_name == "bash"
                            and self.whitelist and self.security_policy):
                        cmd = tool_args.get("command", "")
                        perm = self.security_policy.check_command(cmd)
                        if perm.decision == Decision.DENY:
                            result_str = f"[安全拒绝] {perm.reason}"
                            self.console.print(f"[dim]   ⛔ {result_str}[/dim]")
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": result_str,
                            })
                            if self.auditor:
                                self.auditor.log_command_check(
                                    command=cmd[:200],
                                    decision="denied",
                                    reason=perm.reason,
                                    session_id=self.session_id,
                                )
                            continue

                    # 执行工具
                    if tool_name in self.tool_map:
                        try:
                            tool = self.tool_map[tool_name]
                            if hasattr(tool, 'call'):
                                result = tool.call(**tool_args)
                            else:
                                result = tool.execute(**tool_args)
                            result_str = str(result)
                        except Exception as e:
                            result_str = f"[错误] {str(e)}"
                    else:
                        result_str = f"[错误] 未知工具：{tool_name}"

                    # Hook: ToolResult
                    hook_ctx = self._emit_hook_sync(HookEvent.TOOL_RESULT, {
                        "tool": tool_name,
                        "result": result_str,
                    })
                    if hook_ctx:
                        result_str = hook_ctx.get("result", result_str)

                    # 安全过滤
                    if self.enable_security and self.sensitive_filter:
                        result_str = self.sensitive_filter.filter_text(result_str)

                    # 审计日志
                    if self.auditor:
                        self.auditor.log_command_check(
                            command=f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)[:100]})",
                            decision="allowed",
                            reason="tool execution",
                            session_id=self.session_id,
                        )

                    # 处理工具结果（短期记忆预算）
                    if self.enable_memory and self.short_term:
                        result_str = self.short_term.process_tool_result(
                            tool_name, tool_call_id, result_str
                        )

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_str,
                    })

                    # 记录到短期记忆
                    if self.enable_memory and self.short_term:
                        self.short_term.add_message(self.messages[-1])

                    preview = result_str[:100] + "..." if len(result_str) > 100 else result_str
                    self.console.print(f"[dim]   ← 结果：{preview}[/dim]")

                continue

            # LLM 直接回复
            reply = message.content or ""
            self.messages.append({"role": "assistant", "content": reply})

            # 记录到短期记忆
            if self.enable_memory and self.short_term:
                self.short_term.add_message(self.messages[-1])

            # Hook: AssistantResponse
            self._emit_hook_sync(HookEvent.ASSISTANT_RESPONSE, {
                "content": reply,
                "output_length": len(reply),
            })

            # 审计日志
            if self.auditor:
                self.auditor.log(AuditEvent.create(
                    event_type="assistant_response",
                    decision="completed",
                    details={"output_length": len(reply)},
                    session_id=self.session_id,
                ))

            return reply

        return f"[错误] 工具调用次数过多（超过{self.max_tool_iterations}次），已终止。"

    # ============================================================
    # Async 版本（供 AgentCLI 使用）
    # ============================================================

    async def chat_async(self, user_input: str) -> str:
        """异步版本的 chat()，供 AgentCLI 使用"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat, user_input)

    async def start_session(self):
        """启动会话（供 AgentCLI 使用）"""
        # 触发 session_start Hook
        if self.event_bus:
            await self.event_bus.emit(
                HookEvent.SESSION_START,
                HookContext(event=HookEvent.SESSION_START, data={}, session_id=self.session_id),
            )

        # 初始化长期记忆（如果有）
        if self.enable_memory and self.memory_store:
            try:
                recent = self.memory_store.get_recent(limit=3)
                if recent:
                    self.console.print(f"[dim]💭 已加载 {len(recent)} 条历史记忆[/dim]")
            except Exception:
                pass

    # ============================================================
    # Ch07: 任务管理
    # ============================================================

    async def run_task(self, command: str, description: str = "") -> str:
        """创建并运行一个 ShellTask"""
        task = ShellTask(command=command, description=description or command)
        self.task_registry.register(task)
        asyncio_task = await self.task_registry.start(task.task_id)
        await asyncio_task
        return task.state.output or ""

    # ============================================================
    # Ch10: 多智能体协作
    # ============================================================

    async def run_team(self, project_description: str) -> str:
        """启动多智能体协作"""
        if not self.enable_team:
            return "团队协作功能未启用"

        # 添加标准角色
        self.coordinator.add_roles([
            RoleType.PLANNER,
            RoleType.CODER,
            RoleType.REVIEWER,
            RoleType.TESTER,
            RoleType.WRITER,
        ])

        result = await self.coordinator.plan_and_execute(project_description)
        return result.get("summary", "团队协作完成")

    # ============================================================
    # 状态查询
    # ============================================================

    def reset(self):
        """重置对话历史"""
        self.messages = [self.messages[0]]
        self.messages[0]["content"] = self.system_prompt
        if self.enable_memory and self.short_term:
            self.short_term.reset()
        self.total_turns = 0
        self.console.print("[dim]💭 对话历史已重置[/dim]")

    def list_tools(self):
        """列出所有可用工具"""
        self.console.print("\n[bold]=== 可用工具 ===[/bold]")
        for tool in self.tools:
            desc = tool.description[:60] if tool.description else ""
            self.console.print(f"  • [cyan]{tool.name}[/cyan]: {desc}")

    def get_status(self) -> dict:
        """获取 Agent 完整状态"""
        elapsed = time.time() - self.session_start
        status = {
            "model": self.model,
            "total_turns": self.total_turns,
            "total_tool_calls": self.total_tool_calls,
            "session_duration": f"{elapsed:.0f}s",
            "message_count": len(self.messages),
            "modules": {
                "memory": "enabled" if self.enable_memory else "disabled",
                "skills": "enabled" if self.enable_skills else "disabled",
                "security": "enabled" if self.enable_security else "disabled",
                "hooks": "enabled" if self.enable_hooks else "disabled",
                "team": "enabled" if self.enable_team else "disabled",
            },
        }

        if self.enable_memory and self.short_term:
            status["memory_stats"] = self.short_term.get_stats()

        if self.enable_skills and self.skill_loader:
            skills = self.skill_loader.list_skills()
            status["skills_count"] = len(skills)
            status["skills"] = skills

        if self.enable_security and self.security_policy:
            status["security_report"] = self.security_policy.get_security_report()

        if self.enable_hooks and self.hook_registry:
            status["hooks"] = [
                {"name": h.name, "event": h.event.value, "enabled": h.enabled}
                for h in self.hook_registry._hooks
            ]

        if self.enable_team and self.coordinator:
            status["team_status"] = self.coordinator.get_team_status()

        if self.auditor:
            status["audit_log_path"] = str(self.auditor.log_dir)
            status["audit_events"] = len(self.auditor._events)

        return status

    def get_tools_status(self) -> str:
        """工具状态文本"""
        lines = [f"🔧 可用工具（{len(self.tools)} 个）：", ""]
        for tool in self.tools:
            desc = tool.description[:50] if tool.description else ""
            lines.append(f"  • {tool.name}: {desc}")
        return "\n".join(lines)

    def get_memory_status(self) -> str:
        """记忆状态文本"""
        if not self.enable_memory:
            return "记忆系统：未启用"

        lines = ["💭 记忆系统状态：", ""]

        if self.short_term:
            stats = self.short_term.get_stats()
            lines.append("  短期记忆：")
            lines.append(f"    消息数：{stats.get('message_count', 0)}")
            lines.append(f"    Token 数：{stats.get('total_tokens', 0)}")
            lines.append(f"    需压缩：{stats.get('should_compress', False)}")

        if self.memory_store:
            count = self.memory_store.count()
            lines.append("\n  长期记忆：")
            lines.append(f"    记忆条数：{count}")

        return "\n".join(lines)

    def get_tasks_status(self) -> str:
        """任务状态文本"""
        tasks = self.task_registry.list_tasks()
        if not tasks:
            return "📋 暂无任务"

        lines = ["📋 任务列表：", ""]
        for t in tasks:
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "killed": "⏹️",
                "running": "🔄",
                "pending": "⏳",
            }.get(t.get("status", ""), "❓")
            lines.append(f"  {status_icon} {t.get('id', '?')}: {t.get('description', '')} ({t.get('status', '')})")
        return "\n".join(lines)

    def get_security_status(self) -> str:
        """安全状态文本"""
        if not self.enable_security:
            return "安全系统：未启用"

        report = self.security_policy.get_security_report()
        lines = ["🛡️ 安全状态：", ""]
        lines.append(f"  严格模式：{report['strict_mode']}")
        lines.append(f"  永久允许：{report['permanent_allows']}")
        lines.append(f"  永久禁止：{report['permanent_denies']}")
        lines.append(f"  已过滤：{report['redacted_count']}")
        lines.append(f"  白名单规则：{report['whitelist_rules']}")
        lines.append(f"  黑名单规则：{report['blacklist_rules']}")
        return "\n".join(lines)

    def get_hooks_status(self) -> str:
        """Hooks 状态文本"""
        if not self.enable_hooks or not self.hook_registry:
            return "Hook 系统：未启用"

        lines = ["🪝 已注册 Hooks：", ""]
        for h in self.hook_registry._hooks:
            lines.append(f"  • {h.name} → {h.event.value} (enabled={h.enabled})")
        return "\n".join(lines)

    def get_audit_status(self) -> str:
        """审计日志状态文本"""
        if not self.auditor:
            return "审计日志：未启用"

        log_dir = str(self.auditor.log_dir)
        lines = ["📝 审计日志：", ""]
        lines.append(f"  日志目录：{log_dir}")
        lines.append(f"  内存事件数：{len(self.auditor._events)}")
        return "\n".join(lines)


# ============================================================
# __main__: 使用 AgentCLI 启动
# ============================================================

if __name__ == "__main__":
    # 添加项目根目录到 path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 导入 CLI（延迟导入避免循环依赖）
    from cli.interface import AgentCLI
    from rich.console import Console as RichConsole

    sandbox_dirs = [os.getcwd(), "/tmp"]

    agent = AgentV5(
        system_prompt=(
            "你是一个全功能的 AI 助手，集成了工具调用、记忆系统、技能系统、"
            "安全系统、Hook 系统、多智能体协作等功能。"
            "回答要简洁明了。"
        ),
        sandbox_dirs=sandbox_dirs,
    )

    console = RichConsole()

    # 打印启动信息
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]🤖 Agent v5 已启动（全集成版本）！[/bold green]\n"
        "[dim]集成模块：Memory, Tasks, Skills, Team, Hooks, Security, CLI[/dim]\n"
        "[dim]输入 /help 查看命令，输入 /quit 退出[/dim]",
        border_style="green"
    ))
    console.print()

    # 打印模块状态
    status = agent.get_status()
    modules = status.get("modules", {})
    console.print("[bold]=== 模块状态 ===[/bold]")
    for mod, state in modules.items():
        icon = "✅" if state == "enabled" else "⏸️"
        console.print(f"  {icon} {mod}: {state}")
    console.print()

    # 使用 AgentCLI 启动
    cli = AgentCLI(agent=agent)
    asyncio.run(cli.run())
