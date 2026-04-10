"""
tasks/shell_task.py —— 异步 Shell 任务

参考 Claude Code 的 LocalShellTask
"""

import asyncio
import logging
import time
from typing import Optional

from .base import Task, TaskType, generate_task_id

logger = logging.getLogger(__name__)


class ShellTask(Task):
    """
    异步 Shell 任务
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
        """异步执行 Shell 命令"""
        logger.info(f"ShellTask {self.task_id}: running '{self.command}'")

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        self.register_cleanup(self._cleanup_process)

        try:
            output_lines = []
            async for line in self._process.stdout:
                decoded = line.decode("utf-8", errors="replace")
                output_lines.append(decoded)
                self.state.output = "".join(output_lines)

                if self._killed:
                    break

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
        """终止 Shell 进程"""
        self._killed = True
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass
        await super().kill()

    async def _cleanup_process(self) -> None:
        """清理子进程"""
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass
