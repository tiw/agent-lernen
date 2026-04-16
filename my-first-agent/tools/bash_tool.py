"""
BashTool —— 执行 Shell 命令
从零手写 AI Agent 课程 · 第 2 章
"""

import subprocess
import sys
import os

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.base import Tool
else:
    from .base import Tool


class BashTool(Tool):
    """执行 Shell 命令的工具"""
    
    name = "bash"
    description = "执行 Shell 命令并返回输出结果。适用于查看文件、运行程序、安装依赖、检查系统信息等操作。"
    
    # 危险命令黑名单（安全限制）
    DANGEROUS_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "sudo rm",
        "mkfs",
        "dd if=/dev/zero",
        ":(){:|:&};:",  # Fork bomb
        "chmod -R 000",
        "chown -R nobody",
    ]
    
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
    
    def _is_dangerous(self, command: str) -> bool:
        """检查命令是否危险"""
        command_lower = command.lower()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in command_lower:
                return True
        return False
    
    def execute(self, command: str, timeout: int = 30) -> str:
        """
        执行命令
        
        Args:
            command: Shell 命令
            timeout: 超时时间（秒），默认 30 秒
            
        Returns:
            命令输出（stdout + stderr）
        """
        # 安全检查
        if self._is_dangerous(command):
            return "[错误] 检测到危险命令，已拒绝执行"
        
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
                output += f"\n[退出码：{result.returncode}]"
            
            # 限制输出长度（防止 token 爆炸）
            if len(output) > 10000:
                output = output[:10000] + "\n...（输出过长，已截断）"
            
            return output
            
        except subprocess.TimeoutExpired:
            return f"[错误] 命令执行超时（{timeout}秒）"
        except Exception as e:
            return f"[错误] {str(e)}"


# === 测试 ===
if __name__ == "__main__":
    tool = BashTool()
    
    print("=== BashTool 测试 ===\n")
    
    # 测试 1：简单命令
    print("测试 1: pwd")
    print(tool.execute("pwd"))
    print()
    
    # 测试 2：查看文件
    print("测试 2: ls -la")
    print(tool.execute("ls -la"))
    print()
    
    # 测试 3：危险命令（应该被拒绝）
    print("测试 3: rm -rf / (危险命令)")
    print(tool.execute("rm -rf /"))
    print()
    
    # 测试 4：Python 版本
    print("测试 4: python3 --version")
    print(tool.execute("python3 --version"))
