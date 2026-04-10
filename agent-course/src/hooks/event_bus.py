"""
事件总线 —— Hook 系统的中枢神经

设计参考：Claude Code 的 hookEvents.ts
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

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
    data: dict
    session_id: str = ""
    turn_id: str = ""
    should_abort: bool = False
    abort_reason: str = ""
    modified_data: dict = field(default_factory=dict)

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


# Hook 回调类型
HookCallback = Callable[[HookContext], Any]


class EventBus:
    """
    事件总线
    """

    def __init__(self, max_pending: int = 100):
        self._handlers: dict = {}
        self._pending_events: list = []
        self._max_pending = max_pending
        self._has_handler: dict = {}

    def on(self, event: HookEvent, callback: HookCallback) -> None:
        """注册 Hook 回调"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(callback)
        self._has_handler[event] = True

        if self._pending_events:
            self._replay_pending(event)

    def off(self, event: HookEvent, callback: HookCallback) -> None:
        """移除 Hook 回调"""
        if event in self._handlers:
            self._handlers[event] = [
                h for h in self._handlers[event] if h != callback
            ]

    async def emit(self, event: HookEvent, context: HookContext) -> HookContext:
        """触发事件，依次执行所有注册的 Hook"""
        handlers = self._handlers.get(event, [])

        if not handlers:
            self._pending_events.append((event, context))
            if len(self._pending_events) > self._max_pending:
                dropped = self._pending_events.pop(0)
                logger.warning(f"Event buffer full, dropped: {dropped[0].value}")
            return context

        for callback in handlers:
            if context.should_abort:
                logger.info(f"Hook chain aborted at {event.value}: {context.abort_reason}")
                break

            try:
                result = callback(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Hook error at {event.value}: {e}")

        return context

    def _replay_pending(self, event: HookEvent) -> None:
        """重放缓存的指定类型事件"""
        self._pending_events = [
            (e, ctx) for e, ctx in self._pending_events if e != event
        ]

    def clear(self) -> None:
        """清空所有 Hook 和缓存"""
        self._handlers.clear()
        self._pending_events.clear()
        self._has_handler.clear()
