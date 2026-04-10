"""
team/task_board.py —— 共享任务板
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
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
    dependencies: list = field(default_factory=list)
    result: Optional[str] = None
    created_by: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.status == TaskStatus.BLOCKED

    @property
    def is_ready(self) -> bool:
        return self.status == TaskStatus.PENDING and not self.is_blocked


class TaskBoard:
    """共享任务板"""

    def __init__(self):
        self._tasks: dict = {}
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        description: str,
        priority: int = 1,
        dependencies: list = None,
        created_by: str = "",
    ) -> Task:
        """创建任务"""
        async with self._lock:
            task = Task(
                id=self._next_id,
                description=description,
                priority=priority,
                dependencies=dependencies or [],
                created_by=created_by,
            )
            self._tasks[task.id] = task
            self._next_id += 1
            logger.info(f"Task created: #{task.id} - {description[:50]}...")
            return task

    async def claim_task(self, agent_id: str) -> Optional[Task]:
        """认领任务"""
        async with self._lock:
            ready_tasks = [
                t for t in self._tasks.values()
                if t.is_ready and t.assigned_to is None
            ]

            for task in sorted(ready_tasks, key=lambda t: (t.priority, t.id)):
                deps_met = all(
                    self._tasks.get(dep_id, Task(0, "")).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_met:
                    task.assigned_to = agent_id
                    task.status = TaskStatus.IN_PROGRESS
                    logger.info(f"Task #{task.id} claimed by {agent_id}")
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
            logger.info(f"Task #{task_id} completed by {task.assigned_to}")
            self._update_blocked_tasks()
            return True

    async def fail_task(self, task_id: int, error: str) -> bool:
        """标记任务失败"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = TaskStatus.FAILED
            task.result = f"Error: {error}"
            return True

    def _update_blocked_tasks(self) -> None:
        """更新被阻塞的任务状态"""
        for task in self._tasks.values():
            if task.status == TaskStatus.BLOCKED:
                deps_met = all(
                    self._tasks.get(dep_id, Task(0, "")).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_met:
                    task.status = TaskStatus.PENDING

    def get_status(self) -> list:
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
