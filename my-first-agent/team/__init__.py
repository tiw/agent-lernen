"""
多智能体协作模块
从零手写 AI Agent 课程 · 第 10 章
"""

from .roles import (
    RoleType,
    AgentRole,
    BaseAgent,
    SimulatedAgent,
    PLANNER_ROLE,
    RESEARCHER_ROLE,
    CODER_ROLE,
    REVIEWER_ROLE,
    TESTER_ROLE,
    WRITER_ROLE,
    ALL_ROLES,
)
from .message_bus import MessageBus, Message
from .task_board import TaskBoard, Task, TaskStatus
from .coordinator import Coordinator, TeamConfig

__all__ = [
    "RoleType",
    "AgentRole",
    "BaseAgent",
    "SimulatedAgent",
    "PLANNER_ROLE",
    "RESEARCHER_ROLE",
    "CODER_ROLE",
    "REVIEWER_ROLE",
    "TESTER_ROLE",
    "WRITER_ROLE",
    "ALL_ROLES",
    "MessageBus",
    "Message",
    "TaskBoard",
    "Task",
    "TaskStatus",
    "Coordinator",
    "TeamConfig",
]
