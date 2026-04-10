"""
多智能体协作演示脚本

演示如何创建团队、分配角色、执行任务。
"""

import asyncio
from team.roles import AgentRole, RoleType, BaseAgent
from team.message_bus import MessageBus
from team.task_board import TaskBoard
from team.coordinator import Coordinator


async def demo():
    print("=" * 50)
    print("多智能体协作演示")
    print("=" * 50)

    # 1. 创建协调器
    coordinator = Coordinator()

    # 2. 添加角色
    planner = coordinator.add_role(RoleType.PLANNER)
    coder = coordinator.add_role(RoleType.CODER)
    reviewer = coordinator.add_role(RoleType.REVIEWER)

    print(f"\n✅ 团队组建完成:")
    print(f"   - Planner: {planner.role_id}")
    print(f"   - Coder: {coder.role_id}")
    print(f"   - Reviewer: {reviewer.role_id}")

    # 3. 创建任务
    task_board = coordinator.task_board
    task_board.create_task("设计用户认证模块", priority=1, created_by=planner.role_id)
    task_board.create_task("实现登录接口", priority=2, created_by=planner.role_id)
    task_board.create_task("编写单元测试", priority=3, created_by=planner.role_id)

    print(f"\n📋 任务列表:")
    for task in task_board.list_tasks():
        print(f"   [{task['priority']}] {task['description']} - {task['status']}")

    # 4. 模拟任务执行
    tasks = task_board.list_tasks()
    if tasks:
        task = tasks[0]
        planner.claim_task(task["id"])
        print(f"\n🔄 {planner.role_id} 开始规划: {task['description']}")

    # 5. 执行完整流程
    print(f"\n🚀 执行项目: 构建用户管理系统")
    result = await coordinator.plan_and_execute("构建一个完整的用户管理系统，包括注册、登录、权限管理")

    print(f"\n✅ 项目执行完成!")
    print(f"   任务数: {result.get('tasks_completed', 0)}")
    print(f"   消息数: {result.get('messages_exchanged', 0)}")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(demo())
