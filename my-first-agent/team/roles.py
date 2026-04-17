"""
team/roles.py —— 多智能体角色定义
参考 Claude Code 的 AgentType / AgentDefinition / team file members
从零手写 AI Agent 课程 · 第 10 章
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from openai import OpenAI

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
    """
    Agent 角色定义（参考 Claude Code 的 AgentDefinition + team member）

    每个角色有：
    - 唯一的 agent_id
    - 角色类型
    - 系统提示词
    - 能力描述
    """
    agent_id: str
    role_type: RoleType
    name: str
    system_prompt: str
    capabilities: list[str] = field(default_factory=list)
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

输出格式：
- 任务列表（JSON 格式）
- 每个任务包含：id, description, assigned_role, dependencies, priority
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

输出格式：
- 研究报告（结构化文本）
- 包含：背景、发现、建议、参考资料
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

输出格式：
- 代码文件内容
- 包含：文件名、代码、说明
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

输出格式：
- 审查报告
- 包含：问题列表（严重级别、描述、建议修复）
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

输出格式：
- 测试报告
- 包含：测试用例、结果、覆盖率
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

输出格式：
- Markdown 文档
- 包含：标题、正文、代码示例、表格
""",
    capabilities=["documentation", "technical_writing", "markdown"],
)

# 所有预定义角色
ALL_ROLES = {
    RoleType.PLANNER: PLANNER_ROLE,
    RoleType.RESEARCHER: RESEARCHER_ROLE,
    RoleType.CODER: CODER_ROLE,
    RoleType.REVIEWER: REVIEWER_ROLE,
    RoleType.TESTER: TESTER_ROLE,
    RoleType.WRITER: WRITER_ROLE,
}


class BaseAgent(ABC):
    """
    Agent 基类（参考 Claude Code 的 Agent 概念）

    每个 Agent 实例代表一个角色，可以：
    - 接收任务
    - 执行任务
    - 返回结果
    - 发送消息
    """

    def __init__(self, role: AgentRole):
        self.role = role
        self.current_task: Optional[str] = None
        self.is_busy = False
        self._message_queue: asyncio.Queue = asyncio.Queue()

    @abstractmethod
    async def execute(self, task_description: str, context: dict = None) -> str:
        """
        执行任务

        Args:
            task_description: 任务描述
            context: 上下文信息（如研究成果、代码等）

        Returns:
            执行结果
        """
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
    """
    模拟 Agent（用于演示和测试）

    真实实现应该调用 LLM API。
    """

    async def execute(self, task_description: str, context: dict = None) -> str:
        self.is_busy = True
        self.current_task = task_description

        logger.info(f"[{self.role.name}] Starting: {task_description[:60]}...")

        # 模拟执行时间
        await asyncio.sleep(0.5)

        # 根据角色生成不同的响应
        result = self._generate_response(task_description, context or {})

        self.is_busy = False
        self.current_task = None

        logger.info(f"[{self.role.name}] Completed")
        return result

    def _generate_response(self, task: str, context: dict) -> str:
        """根据角色生成响应"""
        role_type = self.role.role_type

        if role_type == RoleType.PLANNER:
            return self._plan_response(task)
        elif role_type == RoleType.RESEARCHER:
            return self._research_response(task, context)
        elif role_type == RoleType.CODER:
            return self._code_response(task, context)
        elif role_type == RoleType.REVIEWER:
            return self._review_response(task, context)
        elif role_type == RoleType.TESTER:
            return self._test_response(task, context)
        elif role_type == RoleType.WRITER:
            return self._write_response(task, context)
        return f"[{self.role.name}] Processed: {task}"

    def _plan_response(self, task: str) -> str:
        return f"""## Project Plan: {task}

### Tasks
1. [P0] Research the domain and gather requirements
   - Assigned to: Researcher
   - Dependencies: None

2. [P0] Design the architecture
   - Assigned to: Planner
   - Dependencies: Task 1

3. [P1] Implement core functionality
   - Assigned to: Coder
   - Dependencies: Task 2

4. [P1] Write tests
   - Assigned to: Tester
   - Dependencies: Task 3

5. [P2] Code review
   - Assigned to: Reviewer
   - Dependencies: Task 3

6. [P2] Write documentation
   - Assigned to: Writer
   - Dependencies: Task 3
"""

    def _research_response(self, task: str, context: dict) -> str:
        return f"""## Research Report: {task}

### Background
Based on analysis of the task requirements...

### Key Findings
1. The domain involves several key concepts
2. Best practices suggest a modular architecture
3. Common pitfalls include: tight coupling, lack of testing

### Recommendations
- Use a component-based approach
- Implement comprehensive error handling
- Write tests before implementation (TDD)

### References
- Industry best practices
- Similar project analysis
"""

    def _code_response(self, task: str, context: dict) -> str:
        return f"""## Implementation: {task}

```python
# Generated code for: {task}

def main():
    '''Main entry point'''
    print("Hello from generated code!")
    return True

if __name__ == "__main__":
    main()
```

### Notes
- Follows PEP 8 style guide
- Includes type hints
- Has comprehensive docstrings
"""

    def _review_response(self, task: str, context: dict) -> str:
        return f"""## Code Review: {task}

### 🔴 Critical Issues
- None found

### 🟡 Warnings
- Consider adding more error handling
- Add unit tests for edge cases

### 🟢 Suggestions
- Could use more descriptive variable names
- Consider extracting helper functions

### ✅ Good Practices
- Clean code structure
- Good use of type hints
- Comprehensive docstrings
"""

    def _test_response(self, task: str, context: dict) -> str:
        return f"""## Test Report: {task}

### Test Cases
1. ✅ Test main function returns True
2. ✅ Test error handling
3. ✅ Test edge cases

### Coverage
- Line coverage: 85%
- Branch coverage: 75%

### Recommendations
- Add more edge case tests
- Increase branch coverage to 90%
"""

    def _write_response(self, task: str, context: dict) -> str:
        return f"""# Documentation: {task}

## Overview
This document provides comprehensive documentation for the project.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
```python
from project import main
main()
```

## API Reference
See API documentation for details.

## Changelog
- v1.0.0: Initial release
"""


# ============================================================
# LLM Agent（真实调用 LLM，而非硬编码模板）
# ============================================================


def _format_context(ctx: dict) -> str:
    """将上下文 dict 格式化为可读字符串"""
    if not ctx:
        return "(无上下文)"
    parts = []
    for key, value in ctx.items():
        parts.append(f"--- {key} ---")
        parts.append(str(value))
    return "\n".join(parts)


class LLMAgent(BaseAgent):
    """
    基于 LLM 的真实 Agent。

    使用 OpenAI 兼容 API 调用 LLM，基于角色 system prompt
    和真实任务上下文生成内容（而非硬编码模板）。
    """

    def __init__(
        self,
        role: AgentRole,
        client: OpenAI,
        model: str = "qwen-plus",
    ):
        super().__init__(role)
        self.client = client
        self.model = model

    async def execute(self, task_description: str, context: dict = None) -> str:
        self.is_busy = True
        self.current_task = task_description

        logger.info(f"[{self.role.name}] Starting LLM: {task_description[:60]}...")

        # 构建用户消息：任务 + 上下文
        context_str = _format_context(context or {})
        user_msg = f"Task: {task_description}\n\nContext:\n{context_str}"

        # 调用 LLM（单轮，无工具）
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            messages=[
                {"role": "system", "content": self.role.system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        result = response.choices[0].message.content or ""
        self.is_busy = False
        self.current_task = None

        logger.info(f"[{self.role.name}] Completed")
        return result


# === 测试 ===
if __name__ == "__main__":
    async def test_roles():
        print("=== 多智能体角色测试 ===\n")

        # 测试 1: 角色定义
        print("测试 1: 角色定义")
        print(f"  Planner: {PLANNER_ROLE}")
        print(f"  Coder: {CODER_ROLE}")
        print(f"  所有角色：{list(ALL_ROLES.keys())}\n")

        # 测试 2: 模拟 Agent 执行
        print("测试 2: 模拟 Agent 执行")
        agent = SimulatedAgent(PLANNER_ROLE)
        result = await agent.execute("Build a web application")
        print(f"  Planner 结果：{result[:100]}...\n")

        agent = SimulatedAgent(CODER_ROLE)
        result = await agent.execute("Implement login feature")
        print(f"  Coder 结果：{result[:100]}...\n")

        # 测试 3: Agent 状态
        print("测试 3: Agent 状态")
        print(f"  是否可用：{agent.is_available}")
        print(f"  当前任务：{agent.current_task}")
        print(f"  _repr_：{repr(agent)}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_roles())
