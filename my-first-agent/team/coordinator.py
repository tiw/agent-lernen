"""
team/coordinator.py —— 多智能体协调器
参考 Claude Code 的 Team Lead Agent
从零手写 AI Agent 课程 · 第 10 章
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
    from team.roles import BaseAgent, AgentRole, RoleType, ALL_ROLES, SimulatedAgent
    from team.message_bus import MessageBus, Message
    from team.task_board import TaskBoard, TaskStatus
else:
    from .roles import BaseAgent, AgentRole, RoleType, ALL_ROLES, SimulatedAgent
    from .message_bus import MessageBus, Message
    from .task_board import TaskBoard, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class TeamConfig:
    """团队配置（参考 Claude Code 的 TeamFile）"""
    name: str
    description: str = ""
    members: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class Coordinator:
    """
    多智能体协调器（主 Agent）

    参考 Claude Code 的 Team Lead Agent：
    1. 创建团队和分配角色
    2. 分解任务并分配到任务板
    3. 协调 Agent 执行
    4. 收集结果并整合
    """

    def __init__(self, team_name: str = "default-team"):
        self.team_name = team_name
        self.config = TeamConfig(name=team_name)
        self.agents: dict[str, BaseAgent] = {}
        self.message_bus = MessageBus()
        self.task_board = TaskBoard()
        self._running = False

    def add_role(self, role: AgentRole) -> BaseAgent:
        """添加角色到团队"""
        agent = SimulatedAgent(role)
        self.agents[role.agent_id] = agent
        self.message_bus.register_agent(role.agent_id)
        self.config.members.append({
            "agent_id": role.agent_id,
            "name": role.name,
            "role": role.role_type.value,
        })
        logger.info(f"Added team member: {role.name} ({role.role_type.value})")
        return agent

    def add_roles(self, role_types: list[RoleType]) -> list[BaseAgent]:
        """批量添加角色"""
        agents = []
        for rt in role_types:
            if rt in ALL_ROLES:
                agents.append(self.add_role(ALL_ROLES[rt]))
        return agents

    async def plan_and_execute(self, project_description: str) -> dict:
        """
        规划并执行项目

        完整的多 Agent 协作流程：
        1. Planner 分解任务
        2. 创建任务到任务板
        3. Agent 认领并执行
        4. 收集结果
        """
        logger.info(f"Starting project: {project_description}")
        self._running = True

        # Step 1: Planner 分解任务
        planner = self.agents.get("planner")
        if not planner:
            tasks = self._default_decomposition(project_description)
        else:
            plan_result = await planner.execute(project_description)
            tasks = self._parse_plan(plan_result)

        # Step 2: 创建任务到任务板
        task_ids = []
        for task_info in tasks:
            task = await self.task_board.create_task(
                description=task_info["description"],
                priority=task_info.get("priority", 1),
                dependencies=task_info.get("dependencies", []),
                created_by="coordinator",
            )
            task_ids.append(task.id)

        # Step 3: Agent 认领并执行
        results = await self._execute_tasks()

        # Step 4: 整合结果
        summary = await self._summarize_results(results)

        self._running = False
        return {
            "project": project_description,
            "tasks_completed": self.task_board.completed_count,
            "tasks_total": self.task_board.total_count,
            "results": results,
            "summary": summary,
        }

    def _default_decomposition(self, description: str) -> list[dict]:
        """默认任务分解"""
        return [
            {"id": 1, "description": f"Research: {description}", "assigned_role": "researcher", "priority": 1, "dependencies": []},
            {"id": 2, "description": f"Implement: {description}", "assigned_role": "coder", "priority": 1, "dependencies": [1]},
            {"id": 3, "description": f"Review code for: {description}", "assigned_role": "reviewer", "priority": 2, "dependencies": [2]},
            {"id": 4, "description": f"Test: {description}", "assigned_role": "tester", "priority": 2, "dependencies": [2]},
            {"id": 5, "description": f"Document: {description}", "assigned_role": "writer", "priority": 3, "dependencies": [2]},
        ]

    def _parse_plan(self, plan_result: str) -> list[dict]:
        """解析 Planner 的输出"""
        return self._default_decomposition(plan_result)

    async def _execute_tasks(self) -> dict[int, str]:
        """执行任务板上的所有任务"""
        results = {}
        max_iterations = 20
        iteration = 0

        while self.task_board.pending_count > 0 and iteration < max_iterations:
            iteration += 1
            progress_made = False

            for agent_id, agent in self.agents.items():
                if agent.is_busy:
                    continue

                task = await self.task_board.claim_task(agent_id)
                if task:
                    progress_made = True
                    try:
                        context = self._gather_context(task.dependencies)
                        result = await agent.execute(task.description, context)
                        await self.task_board.complete_task(task.id, result)
                        results[task.id] = result

                        await self.message_bus.send(Message(
                            sender=agent_id,
                            receiver="coordinator",
                            content=f"Task #{task.id} completed: {task.description[:50]}...",
                        ))
                    except Exception as e:
                        await self.task_board.fail_task(task.id, str(e))
                        results[task.id] = f"Error: {e}"

            if not progress_made:
                await asyncio.sleep(0.1)

        return results

    def _gather_context(self, dependency_ids: list[int]) -> dict:
        """收集依赖任务的输出"""
        context = {}
        for dep_id in dependency_ids:
            context[f"task_{dep_id}"] = f"Result from task {dep_id}"
        return context

    async def _summarize_results(self, results: dict[int, str]) -> str:
        """整合所有结果"""
        parts = [f"## Project Summary: {self.team_name}\n"]
        for task_id, result in sorted(results.items()):
            parts.append(f"\n### Task #{task_id}")
            preview = result[:200] + "..." if len(result) > 200 else result
            parts.append(preview)
        parts.append(f"\n---\n**Total tasks completed: {len(results)}**")
        return "\n".join(parts)

    def get_team_status(self) -> dict:
        """获取团队状态"""
        return {
            "team_name": self.team_name,
            "members": [
                {"name": agent.role.name, "role": agent.role.role_type.value, "status": "busy" if agent.is_busy else "idle", "current_task": agent.current_task}
                for agent in self.agents.values()
            ],
            "tasks": self.task_board.get_status(),
            "messages": self.message_bus.message_count,
        }


# === 测试 ===
if __name__ == "__main__":
    async def test_coordinator():
        print("=== 协调器测试 ===\n")

        coordinator = Coordinator("test-team")

        # 测试 1: 添加角色
        print("测试 1: 添加角色")
        coordinator.add_roles([RoleType.PLANNER, RoleType.CODER, RoleType.TESTER])
        print(f"  团队成员：{len(coordinator.agents)}\n")

        # 测试 2: 规划并执行
        print("测试 2: 规划并执行项目")
        result = await coordinator.plan_and_execute("Build a simple calculator")
        print(f"  任务完成：{result['tasks_completed']}/{result['tasks_total']}\n")

        # 测试 3: 团队状态
        print("测试 3: 团队状态")
        status = coordinator.get_team_status()
        for member in status["members"]:
            print(f"  {member['name']} ({member['role']}) - {member['status']}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_coordinator())
