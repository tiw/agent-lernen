"""
team/task_board.py —— 共享任务板
参考 Claude Code 的 Task List / task ownership
从零手写 AI Agent 课程 · 第 10 章
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .roles import BaseAgent


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class Task:
    """任务"""
    id: int
    description: str
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1
    dependencies: list[int] = field(default_factory=list)
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class TaskBoard:
    """
    共享任务板

    参考 Claude Code 的团队任务列表：
    - 任务创建和分配
    - 依赖管理
    - 状态追踪
    """

    def __init__(self):
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        description: str,
        priority: int = 1,
        dependencies: list[int] = None,
        created_by: str = "coordinator",
    ) -> Task:
        """创建任务"""
        async with self._lock:
            task = Task(
                id=self._next_id,
                description=description,
                priority=priority,
                dependencies=dependencies or [],
            )
            self._tasks[task.id] = task
            self._next_id += 1
            return task

    async def claim_task(self, agent_id: str) -> Optional[Task]:
        """
        认领任务

        认领条件：
        - 状态为 pending
        - 依赖任务已完成
        """
        async with self._lock:
            for task in self._tasks.values():
                if task.status != TaskStatus.PENDING:
                    continue
                if task.assigned_to is not None:
                    continue
                if not self._dependencies_met(task):
                    task.status = TaskStatus.BLOCKED
                    continue

                task.assigned_to = agent_id
                task.status = TaskStatus.IN_PROGRESS
                return task

            return None

    async def complete_task(self, task_id: int, result: str) -> bool:
        """完成任务"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()

            # 更新阻塞的任务
            for t in self._tasks.values():
                if t.status == TaskStatus.BLOCKED and self._dependencies_met(t):
                    t.status = TaskStatus.PENDING

            return True

    async def fail_task(self, task_id: int, error: str) -> bool:
        """任务失败"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.status = TaskStatus.FAILED
            task.result = f"Error: {error}"
            return True

    def _dependencies_met(self, task: Task) -> bool:
        """检查依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_task(self, task_id: int) -> Optional[Task]:
        """获取指定任务（含结果）"""
        return self._tasks.get(task_id)

    def get_status(self) -> list[dict]:
        """获取所有任务状态"""
        return [
            {
                "id": t.id,
                "description": t.description,
                "assigned_to": t.assigned_to,
                "status": t.status.value,
                "priority": t.priority,
                "dependencies": t.dependencies,
            }
            for t in sorted(self._tasks.values(), key=lambda x: (x.priority, x.id))
        ]

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)

    @property
    def total_count(self) -> int:
        return len(self._tasks)


# === 测试 ===
if __name__ == "__main__":
    async def test_task_board():
        print("=== 任务板测试 ===\n")

        board = TaskBoard()

        # 测试 1: 创建任务
        print("测试 1: 创建任务")
        task1 = await board.create_task("Research domain", priority=1)
        task2 = await board.create_task("Implement feature", priority=1, dependencies=[1])
        print(f"  创建任务：{board.total_count} 个\n")

        # 测试 2: 认领任务
        print("测试 2: 认领任务")
        claimed = await board.claim_task("agent1")
        print(f"  认领：{claimed.id if claimed else None} → agent1\n")

        # 测试 3: 完成任务
        print("测试 3: 完成任务")
        await board.complete_task(1, "Research completed")
        print(f"  完成：{board.completed_count}/{board.total_count}\n")

        # 测试 4: 任务状态
        print("测试 4: 任务状态")
        for t in board.get_status():
            print(f"  #{t['id']} [{t['status']}] {t['description'][:30]}...\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_task_board())
