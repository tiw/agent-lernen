"""
BashTool —— 执行 Shell 命令的工具
从零手写 AI Agent 课程 · 第 2 章
"""

import subprocess
from .base import Tool


class BashTool(Tool):
    """执行 Shell 命令的工具"""

    name = "bash"
    description = "执行 Shell 命令并返回输出结果。适用于查看文件、运行程序、安装依赖等操作。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令",
                }
            },
            "required": ["command"],
        }

    def execute(self, command: str, timeout: int = 30) -> str:
        """
        执行命令

        Args:
            command: Shell 命令
            timeout: 超时时间（秒）

        Returns:
            命令输出（stdout + stderr）
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"

            # 限制输出长度
            if len(output) > 10000:
                output = output[:10000] + "\n...（输出过长，已截断）"

            return output

        except subprocess.TimeoutExpired:
            return f"[错误] 命令执行超时（{timeout}秒）"
        except Exception as e:
            return f"[错误] {str(e)}"
