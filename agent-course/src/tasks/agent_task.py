"""
tasks/agent_task.py —— 子 Agent 委派任务

参考 Claude Code 的 LocalAgentTask
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from .base import Task, TaskType, generate_task_id

logger = logging.getLogger(__name__)


@dataclass
class AgentProgress:
    """Agent 进度信息"""
    tool_use_count: int = 0
    token_count: int = 0
    last_activity: str = ""
    summary: str = ""


@dataclass
class AgentDefinition:
    """Agent 定义"""
    name: str
    system_prompt: str
    model: str = "default"
    max_turns: int = 10
    allowed_tools: list = field(default_factory=list)


class AgentTask(Task):
    """
    子 Agent 委派任务
    """

    def __init__(
        self,
        agent_def: AgentDefinition,
        prompt: str,
        description: str = "",
        task_id: Optional[str] = None,
        parent_cancel_token: Optional[asyncio.Event] = None,
    ):
        tid = task_id or generate_task_id(TaskType.AGENT)
        super().__init__(tid, description or f"Agent: {agent_def.name}")
        self.agent_def = agent_def
        self.prompt = prompt
        self.parent_cancel_token = parent_cancel_token
        self.progress = AgentProgress()
        self.pending_messages: list = []
        self._cancel_event = asyncio.Event()
        self._current_turn = 0

    @property
    def task_type(self) -> TaskType:
        return TaskType.AGENT

    async def run(self) -> str:
        """执行子 Agent"""
        logger.info(f"AgentTask {self.task_id}: starting '{self.agent_def.name}'")

        if self.parent_cancel_token:
            asyncio.create_task(self._watch_parent_cancel())

        try:
            result = await self._agent_loop()
            return result
        except asyncio.CancelledError:
            logger.info(f"AgentTask {self.task_id}: cancelled")
            raise

    async def _agent_loop(self) -> str:
        """Agent 主循环（简化版）"""
        messages = [
            {"role": "system", "content": self.agent_def.system_prompt},
            {"role": "user", "content": self.prompt},
        ]

        result_parts = []

        for turn in range(1, self.agent_def.max_turns + 1):
            self._current_turn = turn

            if self._cancel_event.is_set():
                raise asyncio.CancelledError("Agent cancelled")

            while self.pending_messages:
                msg = self.pending_messages.pop(0)
                messages.append({"role": "user", "content": msg})

            response = await self._call_llm(messages)
            result_parts.append(f"[Turn {turn}] {response}")

            self.progress.tool_use_count += 1
            self.progress.token_count += len(response)
            self.progress.last_activity = f"Turn {turn} completed"

            if "[DONE]" in response:
                break

            messages.append({"role": "assistant", "content": response})

        return "\n".join(result_parts)

    async def _call_llm(self, messages: list) -> str:
        """调用 LLM（模拟实现）"""
        last_msg = messages[-1]["content"]
        if "search" in last_msg.lower() or "find" in last_msg.lower():
            await asyncio.sleep(0.5)
            return f"Searching for information about: {last_msg[:50]}... [DONE]"
        elif "write" in last_msg.lower() or "create" in last_msg.lower():
            await asyncio.sleep(0.3)
            return f"Creating content based on: {last_msg[:50]}... [DONE]"
        else:
            await asyncio.sleep(0.2)
            return f"Processed: {last_msg[:50]}... [DONE]"

    async def _watch_parent_cancel(self) -> None:
        """监听父 Agent 取消信号"""
        if self.parent_cancel_token:
            await self.parent_cancel_token.wait()
            logger.info(f"AgentTask {self.task_id}: parent cancelled, stopping")
            self._cancel_event.set()

    def send_message(self, message: str) -> None:
        """向运行中的 Agent 发送消息"""
        self.pending_messages.append(message)
        logger.info(f"AgentTask {self.task_id}: message queued")

    async def kill(self) -> None:
        """终止 Agent 任务"""
        self._cancel_event.set()
        await super().kill()
