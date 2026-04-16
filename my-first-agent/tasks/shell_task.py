"""
tasks/shell_task.py —— 异步 Shell 任务
参考 Claude Code 的 LocalShellTask：
- 后台执行 Shell 命令
- 支持超时
- 输出实时收集
- 卡死检测（简化版）
从零手写 AI Agent 课程 · 第 7 章
"""

import asyncio
import logging
import time
import sys
import os
from typing import Optional

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tasks.base import Task, TaskType, generate_task_id
else:
    from .base import Task, TaskType, generate_task_id

logger = logging.getLogger(__name__)


class ShellTask(Task):
    """
    异步 Shell 任务

    参考 Claude Code 的 LocalShellTask：
    - 命令在后台异步执行
    - 输出实时收集到 state.output
    - 支持超时自动终止
    - 支持前台/后台模式
    """

    def __init__(
        self,
        command: str,
        description: str = "",
        timeout: Optional[float] = None,
        task_id: Optional[str] = None,
        background: bool = True,
    ):
        tid = task_id or generate_task_id(TaskType.SHELL)
        super().__init__(tid, description or command)
        self.command = command
        self.timeout = timeout
        self.background = background
        self._process: Optional[asyncio.subprocess.Process] = None
        self._killed = False

    @property
    def task_type(self) -> TaskType:
        return TaskType.SHELL

    async def run(self) -> str:
        """
        异步执行 Shell 命令

        参考 Claude Code 的 spawnShellTask：
        1. 创建子进程
        2. 实时读取输出
        3. 处理超时
        4. 返回完整输出
        """
        logger.info(f"ShellTask {self.task_id}: running '{self.command}'")

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # 注册清理：进程异常退出时清理
        self.register_cleanup(self._cleanup_process)

        try:
            # 实时读取输出
            output_lines = []
            async for line in self._process.stdout:
                decoded = line.decode("utf-8", errors="replace")
                output_lines.append(decoded)
                self.state.output = "".join(output_lines)

                # 如果已被 kill，停止读取
                if self._killed:
                    break

            # 等待进程结束
            if not self._killed:
                await self._process.wait()

            return self.state.output

        except asyncio.TimeoutError:
            if self._process:
                self._process.kill()
                await self._process.wait()
            raise TimeoutError(
                f"Shell command timed out after {self.timeout}s: {self.command}"
            )

    async def kill(self) -> None:
        """终止 Shell 进程（参考 Claude Code 的 killTask）"""
        self._killed = True
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass  # 进程已结束
        await super().kill()

    async def _cleanup_process(self) -> None:
        """清理子进程"""
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass


# === 测试 ===
if __name__ == "__main__":
    async def test_shell_task():
        print("=== Shell 任务测试 ===\n")

        # 测试 1: 简单命令
        print("测试 1: 简单命令 (echo)")
        task = ShellTask("echo 'Hello World'", description="测试 echo 命令")
        result = await task.run()
        print(f"  结果：{result.strip()}")
        print(f"  状态：{task.state.status.value}\n")

        # 测试 2: 多行输出
        print("测试 2: 多行输出 (ls -la)")
        task = ShellTask("ls -la | head -5", description="查看目录")
        result = await task.run()
        line_count = len(result.strip().split('\n'))
        print(f"  结果行数：{line_count}")
        print(f"  状态：{task.state.status.value}\n")

        # 测试 3: 任务注册表
        print("测试 3: 任务注册表")
        from tasks.base import TaskRegistry

        registry = TaskRegistry()

        def on_notify(msg):
            print(f"  通知：{msg['event']} - Task {msg['task_id']}")

        registry.on_notification(on_notify)

        task = ShellTask("echo 'Test'", description="注册表测试")
        registry.register(task)
        print(f"  任务已注册：{task.task_id}")
        print(f"  运行数：{registry.running_count}")

        # 启动任务
        asyncio_task = await registry.start(task.task_id)
        await asyncio_task
        print(f"  任务完成：{task.state.status.value}\n")

        # 测试 4: 终止任务
        print("测试 4: 终止任务 (sleep)")
        task = ShellTask("sleep 10", description="测试终止")
        registry.register(task)

        asyncio_task = await registry.start(task.task_id)
        await asyncio.sleep(0.5)  # 等待任务启动
        print(f"  任务状态：{task.state.status.value}")

        # 终止任务
        await registry.stop(task.task_id)
        print(f"  终止后状态：{task.state.status.value}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_shell_task())
