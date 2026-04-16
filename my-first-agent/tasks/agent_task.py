"""
tasks/agent_task.py —— 子 Agent 委派任务（简化版）
参考 Claude Code 的 LocalAgentTask
从零手写 AI Agent 课程 · 第 7 章
"""

import asyncio
import logging
import time
import sys
import os
from dataclasses import dataclass, field
from typing import Optional

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tasks.base import Task, TaskType, generate_task_id
else:
    from .base import Task, TaskType, generate_task_id

logger = logging.getLogger(__name__)


@dataclass
class AgentProgress:
    """Agent 进度信息"""
    tool_use_count: int = 0
    token_count: int = 0
    last_activity: str = ""


@dataclass
class AgentDefinition:
    """Agent 定义"""
    name: str
    system_prompt: str
    model: str = "default"
    max_turns: int = 10


class AgentTask(Task):
    """
    子 Agent 委派任务（简化版）

    注意：这是一个框架实现，实际需要接入完整的 Agent 系统
    """

    def __init__(
        self,
        agent_def: AgentDefinition,
        prompt: str,
        description: str = "",
        task_id: Optional[str] = None,
    ):
        tid = task_id or generate_task_id(TaskType.AGENT)
        super().__init__(tid, description or f"Agent: {agent_def.name}")
        self.agent_def = agent_def
        self.prompt = prompt
        self.progress = AgentProgress()
        self._cancel_event = asyncio.Event()

    @property
    def task_type(self) -> TaskType:
        return TaskType.AGENT

    async def run(self) -> str:
        """执行 Agent 任务（简化版：返回模拟结果）"""
        logger.info(f"AgentTask {self.task_id}: running '{self.agent_def.name}'")

        # 模拟 Agent 执行过程
        self.progress.last_activity = "思考中..."
        await asyncio.sleep(0.5)

        self.progress.last_activity = "执行工具..."
        self.progress.tool_use_count = 3
        await asyncio.sleep(0.5)

        self.progress.last_activity = "生成回复..."
        await asyncio.sleep(0.5)

        result = f"Agent '{self.agent_def.name}' 完成任务：{self.prompt}"
        return result

    async def kill(self) -> None:
        """终止 Agent 任务"""
        self._cancel_event.set()
        await super().kill()


# === 测试 ===
if __name__ == "__main__":
    async def test_agent_task():
        print("=== Agent 任务测试 ===\n")

        agent_def = AgentDefinition(
            name="Assistant",
            system_prompt="你是一个有用的助手",
        )

        task = AgentTask(
            agent_def=agent_def,
            prompt="帮我写一个 Python 函数",
            description="测试 Agent 任务",
        )

        result = await task.run()
        print(f"结果：{result}")
        print(f"进度：{task.progress.tool_use_count} 次工具调用")
        print(f"状态：{task.state.status.value}")

        print("\n✅ 测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_agent_task())
