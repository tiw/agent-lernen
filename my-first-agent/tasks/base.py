"""
tasks/base.py —— 任务系统核心：基类、状态机、注册表
参考 Claude Code 的 Task.ts / TaskStateBase / stopTask.ts
从零手写 AI Agent 课程 · 第 7 章
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
    """任务类型（参考 Claude Code 的 TaskType）"""
    SHELL = "shell"
    AGENT = "agent"


class TaskStatus(Enum):
    """任务状态机（参考 Claude Code 的 TaskStatus）"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 运行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 已失败
    KILLED = "killed"         # 已终止（用户主动停止）

    @property
    def is_terminal(self) -> bool:
        """是否处于终态（不再转换）"""
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)


# 任务 ID 前缀（参考 Claude Code 的 TASK_ID_PREFIXES）
TASK_ID_PREFIXES = {
    TaskType.SHELL: "b",
    TaskType.AGENT: "a",
}


def generate_task_id(task_type: TaskType) -> str:
    """
    生成带类型前缀的任务 ID。
    参考 Claude Code: prefix + 8 个随机字符
    """
    prefix = TASK_ID_PREFIXES.get(task_type, "x")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}{short_uuid}"


@dataclass
class TaskState:
    """
    任务状态（参考 Claude Code 的 TaskStateBase）

    所有任务类型共享的字段。
    """
    id: str
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    start_time: float = 0.0
    end_time: Optional[float] = None
    output: str = ""
    error: Optional[str] = None
    notified: bool = False  # 是否已发送完成通知

    def __post_init__(self):
        if self.start_time == 0.0:
            self.start_time = time.time()


class Task(ABC):
    """
    任务基类（参考 Claude Code 的 Task 接口）

    核心设计：
    - 每种任务类型实现自己的 spawn（创建）逻辑
    - kill 是统一的接口——所有任务都能被终止
    - 状态转换通过 TaskRegistry 统一管理
    """

    def __init__(self, task_id: str, description: str):
        self.task_id = task_id
        self.description = description
        self.state = TaskState(
            id=task_id,
            type=self.task_type,
            description=description,
        )
        self._cleanup_callbacks: list[Callable] = []

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        """返回任务类型"""
        ...

    @abstractmethod
    async def run(self) -> str:
        """
        执行任务，返回输出字符串。
        子类实现具体逻辑。
        """
        ...

    async def kill(self) -> None:
        """
        终止任务（参考 Claude Code 的 Task.kill）。
        默认实现：设置状态为 killed。
        子类可以覆盖以执行额外清理。
        """
        if not self.state.status.is_terminal:
            self.state.status = TaskStatus.KILLED
            self.state.end_time = time.time()
            logger.info(f"Task {self.task_id} killed")
        await self._run_cleanup()

    def register_cleanup(self, callback: Callable) -> None:
        """注册清理回调（参考 Claude Code 的 registerCleanup）"""
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
    """
    任务注册表（参考 Claude Code 的 tasks 状态管理）

    管理所有任务的生命周期，提供统一的创建、查询、停止接口。
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._running_tasks: set[str] = set()
        self._notification_callbacks: list[Callable] = []

    def on_notification(self, callback: Callable[[dict], None]) -> None:
        """注册通知回调"""
        self._notification_callbacks.append(callback)

    def _notify(self, task_id: str, event: str, data: dict) -> None:
        """发送任务通知（去重）"""
        task = self._tasks.get(task_id)
        if task and task.state.notified:
            return  # 已通知，跳过
        if task:
            task.state.notified = True
        msg = {"task_id": task_id, "event": event, **data}
        for cb in self._notification_callbacks:
            try:
                cb(msg)
            except Exception as e:
                logger.warning(f"Notification callback error: {e}")

    def register(self, task: Task) -> None:
        """注册任务到注册表"""
        self._tasks[task.task_id] = task
        task.state.status = TaskStatus.PENDING
        logger.info(f"Task registered: {task.task_id} ({task.task_type.value})")

    async def start(self, task_id: str) -> asyncio.Task:
        """
        启动任务（参考 Claude Code 的 spawnShellTask / registerAsyncAgent）

        返回 asyncio.Task 供外部 await 或后台运行。
        """
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
                        "output": output[:500],  # 截断避免过大
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
        """
        停止任务（参考 Claude Code 的 stopTask）

        统一入口：查找 → 验证 → 终止 → 通知
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"No task found with ID: {task_id}")
        if task.state.status == TaskStatus.PENDING:
            # pending 任务直接标记为 killed
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

    def list_tasks(self) -> list[dict]:
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


# === 测试 ===
if __name__ == "__main__":
    print("=== 任务系统基础测试 ===\n")

    # 测试 1: 任务 ID 生成
    print("测试 1: 任务 ID 生成")
    shell_id = generate_task_id(TaskType.SHELL)
    agent_id = generate_task_id(TaskType.AGENT)
    print(f"  Shell 任务 ID: {shell_id} (前缀：b)")
    print(f"  Agent 任务 ID: {agent_id} (前缀：a)\n")

    # 测试 2: 任务状态
    print("测试 2: 任务状态")
    print(f"  PENDING.is_terminal: {TaskStatus.PENDING.is_terminal}")
    print(f"  COMPLETED.is_terminal: {TaskStatus.COMPLETED.is_terminal}\n")

    # 测试 3: 任务注册表
    print("测试 3: 任务注册表")
    registry = TaskRegistry()
    print(f"  初始运行数：{registry.running_count}")

    # 添加通知回调
    def on_notify(msg):
        print(f"  通知：{msg['event']} - Task {msg['task_id']}")

    registry.on_notification(on_notify)
    print("  通知回调已注册\n")

    print("✅ 基础测试完成！")
