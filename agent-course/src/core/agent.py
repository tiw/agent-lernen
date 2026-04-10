from __future__ import annotations

"""
Agent 核心 —— 集成 Hook 系统

将事件总线、Hook 注册表和内置 Hook 整合到一个完整的 Agent 实现中。
参考 Claude Code 的 hooks.ts 和 Agent 主循环。
"""

import asyncio
import logging
import uuid
from typing import Any

from hooks.event_bus import EventBus, HookContext, HookEvent
from hooks.registry import HookRegistry
from hooks.builtin.session_persist import restore_session, save_session
from hooks.builtin.security_scan import security_scan
from hooks.builtin.continuous_learn import continuous_learn

logger = logging.getLogger(__name__)


class AgentWithHooks:
    """集成 Hook 系统的 Agent"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.turn_id = ""
        self.history: list[dict] = []
        self.turn_count = 0

        # 初始化 Hook 系统
        self.event_bus = EventBus()
        self.registry = HookRegistry(self.event_bus)

        # 注册内置 Hook
        self._register_builtin_hooks()

    def _register_builtin_hooks(self) -> None:
        """注册内置 Hook"""
        # 会话持久化
        self.registry.register(
            "session_restore", HookEvent.SESSION_START,
            restore_session, priority=10,
        )
        self.registry.register(
            "session_save", HookEvent.SESSION_END,
            save_session, priority=10,
        )

        # 安全扫描（高优先级，最先执行）
        self.registry.register(
            "security_scan", HookEvent.TOOL_CALL,
            security_scan, priority=1,
        )

        # 持续学习
        self.registry.register(
            "continuous_learn", HookEvent.TURN_END,
            continuous_learn, priority=200,
        )

    async def start_session(self) -> None:
        """开始会话"""
        ctx = HookContext(
            event=HookEvent.SESSION_START,
            data={"session_id": self.session_id},
            session_id=self.session_id,
        )
        await self.event_bus.emit(HookEvent.SESSION_START, ctx)

        # 恢复历史
        restored = ctx.get("history")
        if restored:
            self.history = restored

    async def process_turn(self, user_input: str) -> dict[str, Any]:
        """处理一轮对话"""
        self.turn_id = str(uuid.uuid4())
        self.turn_count += 1

        # --- Turn Start ---
        turn_ctx = HookContext(
            event=HookEvent.TURN_START,
            data={"input": user_input, "turn_id": self.turn_id},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TURN_START, turn_ctx)
        if turn_ctx.should_abort:
            return {"error": turn_ctx.abort_reason}

        # --- User Prompt Submit ---
        prompt_ctx = HookContext(
            event=HookEvent.USER_PROMPT_SUBMIT,
            data={"prompt": user_input},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.USER_PROMPT_SUBMIT, prompt_ctx)
        if prompt_ctx.should_abort:
            return {"error": prompt_ctx.abort_reason}

        # --- 模拟 Agent 思考（实际应调用 LLM）---
        response = f"收到: {user_input}"

        # --- 模拟工具调用 ---
        tool_ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={
                "tool_name": "bash",
                "tool_input": {"command": "echo hello"},
            },
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TOOL_CALL, tool_ctx)
        if tool_ctx.should_abort:
            return {"error": f"工具调用被拦截: {tool_ctx.abort_reason}"}

        # --- Assistant Response ---
        resp_ctx = HookContext(
            event=HookEvent.ASSISTANT_RESPONSE,
            data={"response": response},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.ASSISTANT_RESPONSE, resp_ctx)
        response = resp_ctx.get("response", response)

        # --- Turn End ---
        end_ctx = HookContext(
            event=HookEvent.TURN_END,
            data={
                "input": user_input,
                "response": response,
                "tool_calls": [],
                "errors": [],
            },
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TURN_END, end_ctx)

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": response})

        return {"response": response, "turn_id": self.turn_id}

    async def end_session(self) -> None:
        """结束会话"""
        ctx = HookContext(
            event=HookEvent.SESSION_END,
            data={
                "session_id": self.session_id,
                "history": self.history,
                "turn_count": self.turn_count,
            },
            session_id=self.session_id,
        )
        await self.event_bus.emit(HookEvent.SESSION_END, ctx)
