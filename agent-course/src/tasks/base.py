"""
tasks/base.py —— 任务系统核心：基类、状态机、注册表

参考 Claude Code 的 Task.ts / TaskStateBase / stopTask.ts
"""

import uuid
import time
import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    SHELL = "shell"
    AGENT = "agent"


class TaskStatus(Enum):
    """任务状态机"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

    @property
    def is_terminal(self) -> bool:
        """是否处于终态"""
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)


TASK_ID_PREFIXES = {
    TaskType.SHELL: "b",
    TaskType.AGENT: "a",
}


def generate_task_id(task_type: TaskType) -> str:
    """生成带类型前缀的任务 ID。"""
    prefix = TASK_ID_PREFIXES.get(task_type, "x")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}{short_uuid}"


@dataclass
class TaskState:
    """任务状态"""
    id: str
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    start_time: float = 0.0
    end_time: Optional[float] = None
    output: str = ""
    error: Optional[str] = None
    notified: bool = False

    def __post_init__(self):
        if self.start_time == 0.0:
            self.start_time = time.time()


class Task(ABC):
    """任务基类"""

    def __init__(self, task_id: str, description: str):
        self.task_id = task_id
        self.description = description
        self.state = TaskState(
            id=task_id,
            type=self.task_type,
            description=description,
        )
        self._cleanup_callbacks: list = []

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        """返回任务类型"""
        ...

    @abstractmethod
    async def run(self) -> str:
        """执行任务，返回输出字符串。"""
        ...

    async def kill(self) -> None:
        """终止任务"""
        if not self.state.status.is_terminal:
            self.state.status = TaskStatus.KILLED
            self.state.end_time = time.time()
            logger.info(f"Task {self.task_id} killed")
        await self._run_cleanup()

    def register_cleanup(self, callback: Callable) -> None:
        """注册清理回调"""
        self._cleanup_callbacks.append(callback)

    async def _run_cleanup(self) -> None:
        """执行所有清理回调"""
        for cb in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb()
                else:
                    cb()
            except Exception as e:
                logger.warning(f"Cleanup callback error: {e}")
        self._cleanup_callbacks.clear()


class TaskRegistry:
    """任务注册表"""

    def __init__(self):
        self._tasks: dict = {}
        self._running_tasks: set = set()
        self._notification_callbacks: list = []

    def on_notification(self, callback: Callable) -> None:
        """注册通知回调"""
        self._notification_callbacks.append(callback)

    def _notify(self, task_id: str, event: str, data: dict) -> None:
        """发送任务通知"""
        task = self._tasks.get(task_id)
        if task and task.state.notified:
            return
        if task:
            task.state.notified = True
        msg = {"task_id": task_id, "event": event, **data}
        for cb in self._notification_callbacks:
            try:
                cb(msg)
            except Exception as e:
                logger.warning(f"Notification callback error: {e}")

    def register(self, task: Task) -> None:
        """注册任务"""
        self._tasks[task.task_id] = task
        task.state.status = TaskStatus.PENDING
        logger.info(f"Task registered: {task.task_id} ({task.task_type.value})")

    async def start(self, task_id: str) -> asyncio.Task:
        """启动任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if task.state.status != TaskStatus.PENDING:
            raise ValueError(f"Task {task_id} is not pending (status: {task.state.status.value})")

        task.state.status = TaskStatus.RUNNING
        self._running_tasks.add(task_id)

        async def _run_wrapper():
            try:
                output = await task.run()
                if task.state.status == TaskStatus.RUNNING:
                    task.state.status = TaskStatus.COMPLETED
                    task.state.output = output
                    task.state.end_time = time.time()
                    self._notify(task_id, "completed", {
                        "output": output[:500],
                        "duration": task.state.end_time - task.state.start_time,
                    })
            except asyncio.CancelledError:
                task.state.status = TaskStatus.KILLED
                task.state.end_time = time.time()
                self._notify(task_id, "killed", {})
            except Exception as e:
                task.state.status = TaskStatus.FAILED
                task.state.error = str(e)
                task.state.end_time = time.time()
                self._notify(task_id, "failed", {"error": str(e)})
            finally:
                self._running_tasks.discard(task_id)
                await task._run_cleanup()

        return asyncio.create_task(_run_wrapper(), name=f"task-{task_id}")

    async def stop(self, task_id: str) -> dict:
        """停止任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"No task found with ID: {task_id}")
        if task.state.status == TaskStatus.PENDING:
            task.state.status = TaskStatus.KILLED
            task.state.end_time = time.time()
            self._notify(task_id, "killed", {})
            return {"task_id": task_id, "status": "killed"}
        if task.state.status != TaskStatus.RUNNING:
            raise ValueError(f"Task {task_id} is not running (status: {task.state.status.value})")

        await task.kill()
        self._running_tasks.discard(task_id)
        return {"task_id": task_id, "status": "killed"}

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list:
        """列出所有任务状态"""
        return [
            {
                "id": t.task_id,
                "type": t.task_type.value,
                "status": t.state.status.value,
                "description": t.description,
            }
            for t in self._tasks.values()
        ]

    @property
    def running_count(self) -> int:
        return len(self._running_tasks)
