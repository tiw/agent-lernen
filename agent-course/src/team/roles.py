"""
team/roles.py —— 多智能体角色定义

参考 Claude Code 的 AgentType / AgentDefinition / team file members
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RoleType(Enum):
    """角色类型"""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    WRITER = "writer"


@dataclass
class AgentRole:
    """Agent 角色定义"""
    agent_id: str
    role_type: RoleType
    name: str
    system_prompt: str
    capabilities: list = field(default_factory=list)
    model: str = "default"

    def __repr__(self) -> str:
        return f"AgentRole({self.name}, {self.role_type.value})"


# ─── 预定义角色 ───

PLANNER_ROLE = AgentRole(
    agent_id="planner",
    role_type=RoleType.PLANNER,
    name="Planner",
    system_prompt="""你是一个项目规划师。你的职责：
1. 理解用户需求
2. 将复杂任务分解为可执行的子任务
3. 确定任务依赖关系
4. 分配任务给合适的角色
5. 监控进度，调整计划
""",
    capabilities=["task_decomposition", "dependency_analysis", "planning"],
)

RESEARCHER_ROLE = AgentRole(
    agent_id="researcher",
    role_type=RoleType.RESEARCHER,
    name="Researcher",
    system_prompt="""你是一个研究专家。你的职责：
1. 根据任务描述收集相关信息
2. 整理和总结研究发现
3. 提供技术选型建议
4. 识别潜在风险和最佳实践
""",
    capabilities=["search", "analysis", "summarization"],
)

CODER_ROLE = AgentRole(
    agent_id="coder",
    role_type=RoleType.CODER,
    name="Coder",
    system_prompt="""你是一个资深软件工程师。你的职责：
1. 根据任务描述和研究报告编写代码
2. 遵循最佳实践和编码规范
3. 处理边界情况和错误
4. 编写清晰的注释
""",
    capabilities=["coding", "debugging", "code_review"],
)

REVIEWER_ROLE = AgentRole(
    agent_id="reviewer",
    role_type=RoleType.REVIEWER,
    name="Reviewer",
    system_prompt="""你是一个代码审查专家。你的职责：
1. 审查代码质量和安全性
2. 检查是否符合最佳实践
3. 发现潜在 bug 和漏洞
4. 提供改进建议
""",
    capabilities=["code_review", "security_audit", "quality_assurance"],
)

TESTER_ROLE = AgentRole(
    agent_id="tester",
    role_type=RoleType.TESTER,
    name="Tester",
    system_prompt="""你是一个测试工程师。你的职责：
1. 根据代码和功能描述编写测试
2. 运行测试并报告结果
3. 发现边缘情况
4. 确保测试覆盖率
""",
    capabilities=["testing", "test_design", "quality_assurance"],
)

WRITER_ROLE = AgentRole(
    agent_id="writer",
    role_type=RoleType.WRITER,
    name="Writer",
    system_prompt="""你是一个技术写作者。你的职责：
1. 编写技术文档和 README
2. 撰写 API 文档
3. 创建用户指南
4. 生成变更日志
""",
    capabilities=["documentation", "technical_writing", "markdown"],
)

ALL_ROLES = {
    RoleType.PLANNER: PLANNER_ROLE,
    RoleType.RESEARCHER: RESEARCHER_ROLE,
    RoleType.CODER: CODER_ROLE,
    RoleType.REVIEWER: REVIEWER_ROLE,
    RoleType.TESTER: TESTER_ROLE,
    RoleType.WRITER: WRITER_ROLE,
}


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, role: AgentRole):
        self.role = role
        self.current_task: Optional[str] = None
        self.is_busy = False
        self._message_queue: asyncio.Queue = asyncio.Queue()

    @abstractmethod
    async def execute(self, task_description: str, context: dict = None) -> str:
        """执行任务"""
        ...

    async def receive_message(self, message: str) -> None:
        """接收消息"""
        await self._message_queue.put(message)

    async def get_message(self) -> Optional[str]:
        """获取消息"""
        try:
            return self._message_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    @property
    def is_available(self) -> bool:
        return not self.is_busy

    def __repr__(self) -> str:
        status = "busy" if self.is_busy else "idle"
        return f"Agent({self.role.name}, {status})"


class SimulatedAgent(BaseAgent):
    """模拟 Agent（用于演示和测试）"""

    async def execute(self, task_description: str, context: dict = None) -> str:
        self.is_busy = True
        self.current_task = task_description

        logger.info(f"[{self.role.name}] Starting: {task_description[:60]}...")

        await asyncio.sleep(0.5)

        result = self._generate_response(task_description, context or {})

        self.is_busy = False
        self.current_task = None

        logger.info(f"[{self.role.name}] Completed")
        return result

    def _generate_response(self, task: str, context: dict) -> str:
        """根据角色生成响应"""
        role_type = self.role.role_type

        if role_type == RoleType.PLANNER:
            return f"## Project Plan: {task}\n\nTasks decomposed and assigned."
        elif role_type == RoleType.RESEARCHER:
            return f"## Research Report: {task}\n\nKey findings and recommendations."
        elif role_type == RoleType.CODER:
            return f"## Implementation: {task}\n\nCode written following best practices."
        elif role_type == RoleType.REVIEWER:
            return f"## Code Review: {task}\n\nReview completed with suggestions."
        elif role_type == RoleType.TESTER:
            return f"## Test Report: {task}\n\nAll tests passed. Coverage: 92%."
        elif role_type == RoleType.WRITER:
            return f"## Documentation: {task}\n\nDocumentation written in Markdown."
        return f"[{self.role.name}] Processed: {task}"
