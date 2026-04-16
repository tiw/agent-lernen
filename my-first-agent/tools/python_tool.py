"""
PythonTool —— 专门执行 Python 代码
从零手写 AI Agent 课程 · 第 2-3 章完善

与 BashTool 的区别：
- BashTool: 执行 Shell 命令（如 `python3 script.py`）
- PythonTool: 直接执行 Python 代码字符串（使用 subprocess）
"""

import subprocess
import sys
import tempfile
import os
from typing import Optional
from .base import Tool


class PythonTool(Tool):
    """执行 Python 代码的工具"""
    
    name = "python"
    description = "执行 Python 代码。适用于运行 Python 脚本、测试代码片段、数据处理等。代码在临时文件中执行，执行后自动清理。"
    
    # 危险操作黑名单
    DANGEROUS_PATTERNS = [
        "os.system(",
        "os.popen(",
        "subprocess.call(",
        "subprocess.run(",
        "__import__('os').system",
        "eval(",
        "exec(",
    ]
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30",
                    "default": 30,
                },
            },
            "required": ["code"],
        }
    
    def _is_dangerous(self, code: str) -> bool:
        """检查代码是否包含危险操作"""
        code_lower = code.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in code_lower:
                return True
        return False
    
    def execute(
        self,
        code: str,
        timeout: int = 30,
        python_path: Optional[str] = None,
    ) -> str:
        """
        执行 Python 代码
        
        Args:
            code: Python 代码字符串
            timeout: 超时时间（秒）
            python_path: Python 解释器路径（默认使用当前环境的 Python）
            
        Returns:
            执行结果（stdout + stderr）
        """
        # 安全检查
        if self._is_dangerous(code):
            return "[错误] 检测到危险操作（如 os.system、eval、exec 等），已拒绝执行"
        
        # 使用当前环境的 Python
        if python_path is None:
            python_path = sys.executable
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8',
        ) as f:
            f.write(code)
            tmp_path = f.name
        
        try:
            # 执行 Python 脚本
            result = subprocess.run(
                [python_path, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[退出码：{result.returncode}]"
            
            # 限制输出长度
            if len(output) > 10000:
                output = output[:10000] + "\n...（输出过长，已截断）"
            
            return output
            
        except subprocess.TimeoutExpired:
            return f"[错误] 代码执行超时（{timeout}秒）"
        except Exception as e:
            return f"[错误] {str(e)}"
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# === 测试 ===
if __name__ == "__main__":
    tool = PythonTool()
    
    print("=== PythonTool 测试 ===\n")
    
    # 测试 1：简单计算
    print("测试 1: 打印 Hello World")
    print(tool.execute("print('Hello World')"))
    print()
    
    # 测试 2：数学计算
    print("测试 2: 计算 1+2+...+100")
    print(tool.execute("print(sum(range(1, 101)))"))
    print()
    
    # 测试 3：多行代码
    print("测试 3: 多行代码")
    print(tool.execute("""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(f"5! = {factorial(5)}")
"""))
    print()
    
    # 测试 4：危险操作（应该被拒绝）
    print("测试 4: os.system('ls') (危险操作)")
    print(tool.execute("import os; os.system('ls')"))
    print()
    
    # 测试 5：eval（应该被拒绝）
    print("测试 5: eval('__import__(\"os\").system(\"ls\")') (危险操作)")
    print(tool.execute("eval('__import__(\"os\").system(\"ls\")')"))
