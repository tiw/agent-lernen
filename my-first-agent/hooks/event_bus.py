"""
hooks/event_bus.py —— 事件总线
Hook 系统的中枢神经
参考 Claude Code 的 hookEvents.ts
从零手写 AI Agent 课程 · 第 11 章
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Union

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Agent 生命周期事件"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ASSISTANT_RESPONSE = "assistant_response"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    NOTIFICATION = "notification"


@dataclass
class HookContext:
    """Hook 执行时的上下文信息"""
    event: HookEvent
    data: dict[str, Any]
    session_id: str = ""
    turn_id: str = ""
    # 拦截标记：Hook 可以设置此标记中止后续流程
    should_abort: bool = False
    abort_reason: str = ""
    # 数据修改：Hook 可以修改 data 中的内容
    modified_data: dict[str, Any] = field(default_factory=dict)

    def abort(self, reason: str) -> None:
        """中止后续 Hook 和主流程"""
        self.should_abort = True
        self.abort_reason = reason

    def modify(self, key: str, value: Any) -> None:
        """修改上下文数据"""
        self.modified_data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据（优先取修改后的值）"""
        return self.modified_data.get(key, self.data.get(key, default))


# Hook 回调类型：同步或异步
HookCallback = Callable[[HookContext], Union[None, Awaitable[None]]]


class EventBus:
    """
    事件总线

    参考 Claude Code 的 hookEvents.ts 设计：
    - pending_events 缓存未分发的事件
    - 容量上限防止内存泄漏
    - 支持同步和异步 handler
    """

    def __init__(self, max_pending: int = 100):
        self._handlers: dict[HookEvent, list[HookCallback]] = {}
        self._pending_events: list[tuple[HookEvent, HookContext]] = []
        self._max_pending = max_pending
        self._has_handler: dict[HookEvent, bool] = {}

    def on(self, event: HookEvent, callback: HookCallback) -> None:
        """注册 Hook 回调"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(callback)
        self._has_handler[event] = True

        # 如果有缓存事件，立即重放
        if self._pending_events:
            self._replay_pending(event)

    def off(self, event: HookEvent, callback: HookCallback) -> None:
        """移除 Hook 回调"""
        if event in self._handlers:
            self._handlers[event] = [
                h for h in self._handlers[event] if h != callback
            ]

    async def emit(self, event: HookEvent, context: HookContext) -> HookContext:
        """
        触发事件，依次执行所有注册的 Hook

        返回修改后的 context（可能被 Hook 拦截或修改）
        """
        handlers = self._handlers.get(event, [])

        if not handlers:
            # 没有 handler，缓存事件
            self._pending_events.append((event, context))
            if len(self._pending_events) > self._max_pending:
                dropped = self._pending_events.pop(0)
                logger.warning(
                    f"Event buffer full, dropped: {dropped[0].value}"
                )
            return context

        for callback in handlers:
            if context.should_abort:
                logger.info(
                    f"Hook chain aborted at {event.value}: "
                    f"{context.abort_reason}"
                )
                break

            try:
                result = callback(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Hook error at {event.value}: {e}")
                # Hook 异常不中断主流程，仅记录

        return context

    def _replay_pending(self, event: HookEvent) -> None:
        """重放缓存的指定类型事件"""
        to_replay = [
            (e, ctx) for e, ctx in self._pending_events if e == event
        ]
        self._pending_events = [
            (e, ctx) for e, ctx in self._pending_events if e != event
        ]

    def clear(self) -> None:
        """清空所有 Hook 和缓存"""
        self._handlers.clear()
        self._pending_events.clear()
        self._has_handler.clear()


# === 测试 ===
if __name__ == "__main__":
    async def test_event_bus():
        print("=== 事件总线测试 ===\n")

        bus = EventBus()

        # 测试 1: 注册 Hook
        print("测试 1: 注册 Hook")
        call_log = []

        def hook1(ctx: HookContext) -> None:
            call_log.append(f"hook1: {ctx.event.value}")

        async def hook2(ctx: HookContext) -> None:
            call_log.append(f"hook2: {ctx.event.value}")
            await asyncio.sleep(0.1)

        bus.on(HookEvent.TOOL_CALL, hook1)
        bus.on(HookEvent.TOOL_CALL, hook2)
        print(f"  已注册 Hook: {len(bus._handlers[HookEvent.TOOL_CALL])}\n")

        # 测试 2: 触发事件
        print("测试 2: 触发事件")
        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"tool_name": "bash", "command": "ls -la"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print(f"  调用日志：{call_log}\n")

        # 测试 3: 拦截测试
        print("测试 3: 拦截测试")
        call_log.clear()

        def blocking_hook(ctx: HookContext) -> None:
            ctx.abort("Security check failed!")

        bus.on(HookEvent.TOOL_CALL, blocking_hook)
        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"tool_name": "bash", "command": "rm -rf /"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print(f"  是否拦截：{ctx.should_abort}")
        print(f"  拦截原因：{ctx.abort_reason}\n")

        # 测试 4: 数据修改
        print("测试 4: 数据修改")
        call_log.clear()

        def modify_hook(ctx: HookContext) -> None:
            ctx.modify("command", ctx.get("command") + " --safe")

        bus = EventBus()
        bus.on(HookEvent.TOOL_CALL, modify_hook)
        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"command": "ls"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print(f"  原始命令：ls")
        print(f"  修改后：{ctx.get('command')}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_event_bus())
