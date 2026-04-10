# 第 12 章：CLI 终端界面 —— 让 Agent 好用

> **本章目标**：使用 rich、prompt_toolkit 和 click 构建美观、交互流畅的 CLI 界面
>
> 🎯 **里程碑进度**：▓▓▓▓▓▓▓▓▓▓▓▓░ 120% — Agent 有了漂亮的终端界面

---

## 🧠 核心概念

### 为什么需要好的 CLI？

`input()` / `print()` 能用，但体验很差。好的 CLI 能提供：

| 功能 | `input/print` | `rich + prompt_toolkit` |
|------|---------------|------------------------|
| 彩色输出 | ❌ | ✅ |
| Markdown 渲染 | ❌ | ✅ |
| 命令补全 | ❌ | ✅ |
| 历史记录 | ❌ | ✅ |
| 流式输出 | 手动实现 | 内置支持 |
| 进度条 | ❌ | ✅ |

### 技术选型

| 库 | 用途 | 安装 |
|----|------|------|
| **rich** | 彩色输出、Markdown 渲染、表格、进度条 | `pip install rich` |
| **prompt_toolkit** | 命令行补全、历史、多行输入 | `pip install prompt_toolkit` |
| **click** | 命令解析、参数验证 | `pip install click` |

---

## 💻 动手实现

### 项目结构

```
src/
├── cli.py                # 🆕 CLI 入口
└── ui/
    ├── __init__.py
    ├── renderer.py       # 🆕 rich 渲染
    └── prompt.py         # 🆕 prompt_toolkit 输入
```

### 代码 1：`src/ui/__init__.py`

```python
"""UI 模块入口"""
from ui.renderer import UIRenderer
from ui.prompt import PromptInput

__all__ = ["UIRenderer", "PromptInput"]
```

### 代码 2：`src/ui/renderer.py`

```python
"""
UI 渲染器 —— 使用 rich 美化终端输出。

从零手写 AI Agent 课程 · 第 12 章
"""

from __future__ import annotations

import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.spinner import Spinner
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class UIRenderer:
    """
    使用 rich 的终端渲染器。
    
    提供：
    - 彩色面板输出
    - Markdown 渲染
    - 表格展示
    - 加载动画
    
    使用示例：
        ui = UIRenderer()
        ui.print_welcome()
        ui.print_user("你好")
        ui.print_assistant("你好！有什么可以帮你的？")
        ui.print_tool_call("bash", {"command": "ls"})
        ui.print_tool_result("total 42")
    """
    
    def __init__(self, markdown: bool = True):
        """
        Args:
            markdown: 是否启用 Markdown 渲染
        """
        self.console = Console()
        self.use_markdown = markdown and HAS_RICH
    
    def print_welcome(self, version: str = "0.1.0"):
        """打印欢迎信息"""
        if not HAS_RICH:
            print(f"🤖 Agent CLI v{version}")
            print("=" * 40)
            return
        
        self.console.print(Panel.fit(
            f"[bold green]🤖 Agent CLI[/bold green] v{version}\n"
            "[dim]输入 'quit' 退出，'help' 查看帮助[/dim]",
            border_style="green",
        ))
        self.console.print(Rule(style="dim"))
    
    def print_user(self, text: str):
        """打印用户输入"""
        if not HAS_RICH:
            print(f"\n你: {text}")
            return
        
        self.console.print()
        self.console.print(
            Panel(text, title="[bold blue]👤 你[/bold blue]",
                  border_style="blue", padding=(0, 2))
        )
    
    def print_assistant(self, text: str, streaming: bool = False):
        """打印助手回复"""
        if not HAS_RICH:
            print(f"\n🤖: {text}")
            return
        
        if self.use_markdown:
            content = Markdown(text)
        else:
            content = text
        
        self.console.print(
            Panel(content, title="[bold green]🤖 Agent[/bold green]",
                  border_style="green", padding=(0, 2))
        )
    
    def print_tool_call(self, tool_name: str, args: dict):
        """打印工具调用信息"""
        if not HAS_RICH:
            print(f"  🔧 调用: {tool_name}({args})")
            return
        
        args_text = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self.console.print(
            f"  [bold yellow]🔧[/bold yellow] "
            f"[yellow]{tool_name}[/yellow]({args_text})"
        )
    
    def print_tool_result(self, result: str, max_lines: int = 10):
        """打印工具结果"""
        if not HAS_RICH:
            lines = result.split('\n')
            display = '\n'.join(lines[:max_lines])
            if len(lines) > max_lines:
                display += f"\n...（共 {len(lines)} 行）"
            print(f"  📋 结果:\n{display}")
            return
        
        lines = result.split('\n')
        display = '\n'.join(lines[:max_lines])
        if len(lines) > max_lines:
            display += f"\n[dim]...（共 {len(lines)} 行）[/dim]"
        
        self.console.print(
            Panel(display, title="[dim]📋 工具结果[/dim]",
                  border_style="dim", padding=(0, 1))
        )
    
    def print_error(self, message: str):
        """打印错误"""
        if not HAS_RICH:
            print(f"❌ 错误: {message}")
            return
        
        self.console.print(f"[bold red]❌ 错误:[/bold red] {message}")
    
    def print_warning(self, message: str):
        """打印警告"""
        if not HAS_RICH:
            print(f"⚠️  警告: {message}")
            return
        
        self.console.print(f"[bold yellow]⚠️  警告:[/bold yellow] {message}")
    
    def print_stats(self, stats: dict):
        """打印统计信息（表格形式）"""
        if not HAS_RICH:
            for k, v in stats.items():
                print(f"  {k}: {v}")
            return
        
        table = Table(title="📊 上下文统计")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        for k, v in stats.items():
            table.add_row(str(k), str(v))
        
        self.console.print(table)
    
    def print_separator(self, text: str = ""):
        """打印分隔线"""
        if not HAS_RICH:
            print(f"\n{'─' * 40}")
            return
        
        self.console.print(Rule(text, style="dim"))
    
    def streaming_print(self, text: str):
        """
        流式打印（打字机效果）。
        
        注意：这个方法需要逐字调用。
        """
        if not HAS_RICH:
            print(text, end="", flush=True)
            return
        
        self.console.print(text, end="", flush=True)
```

### 代码 3：`src/ui/prompt.py`

```python
"""
命令行输入 —— 使用 prompt_toolkit 提供补全和历史。

从零手写 AI Agent 课程 · 第 12 章
"""

from __future__ import annotations

from typing import Optional

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


class PromptInput:
    """
    增强的命令行输入。
    
    特性：
    - 命令补全（Tab）
    - 历史记录（上下箭头）
    - 自动建议
    - 历史持久化
    
    使用示例：
        prompt = PromptInput(
            commands=["quit", "help", "reset", "stats"],
            history_file=".agent_history",
        )
        user_input = prompt.get_input()
    """
    
    def __init__(
        self,
        commands: Optional[list[str]] = None,
        history_file: str = ".agent_history",
        prompt_text: str = "你: ",
    ):
        """
        Args:
            commands: 可补全的命令列表
            history_file: 历史文件路径
            prompt_text: 提示符文本
        """
        self.commands = commands or ["quit", "help", "reset", "stats"]
        self.history_file = history_file
        self.prompt_text = prompt_text
        self._session: Optional[PromptSession] = None
    
    def _create_session(self) -> PromptSession:
        """创建 PromptSession"""
        completer = WordCompleter(self.commands, ignore_case=True)
        
        history = None
        if HAS_PROMPT_TOOLKIT:
            try:
                history = FileHistory(self.history_file)
            except Exception:
                pass
        
        return PromptSession(
            completer=completer,
            history=history,
            auto_suggest=AutoSuggestFromHistory() if HAS_PROMPT_TOOLKIT else None,
        )
    
    def get_input(self) -> str:
        """
        获取用户输入。
        
        Returns:
            用户输入的文本
        """
        if HAS_PROMPT_TOOLKIT:
            try:
                if not self._session:
                    self._session = self._create_session()
                return self._session.prompt(self.prompt_text).strip()
            except (EOFError, KeyboardInterrupt):
                return "quit"
        else:
            # 回退到 input()
            try:
                return input(self.prompt_text).strip()
            except (EOFError, KeyboardInterrupt):
                return "quit"
    
    def add_commands(self, commands: list[str]):
        """添加可补全的命令"""
        self.commands.extend(commands)
        self._session = None  # 重建 session
```

### 代码 4：`src/cli.py`

```python
"""
CLI 入口 —— 完整的命令行界面。

使用方式：
    python -m src.cli              # 交互模式
    python -m src.cli --model gpt-4o-mini
    python -m src.cli --help

从零手写 AI Agent 课程 · 第 12 章
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 确保 src 在 Python 路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import click
    HAS_CLICK = True
except ImportError:
    HAS_CLICK = False

from agent import Agent
from ui.renderer import UIRenderer
from ui.prompt import PromptInput
from tools.bash_tool import BashTool
from tools.file_tools import create_file_tools
from hooks.builtin import SessionPersistHook, SecurityScanHook


def create_agent(model: str, skills_dir: str = None) -> Agent:
    """创建配置好的 Agent 实例"""
    # 创建工具
    read_tool, write_tool, edit_tool = create_file_tools(
        allowed_dirs=[os.getcwd()]
    )
    
    agent = Agent(
        system_prompt=(
            "你是一个全能的 AI 编程助手。"
            "你可以执行 Shell 命令、读写文件、搜索网络。"
        ),
        model=model,
        tools=[
            BashTool(),
            read_tool, write_tool, edit_tool,
        ],
    )
    
    # 加载 Hook
    agent.hook_registry.register(SessionPersistHook())
    agent.hook_registry.register(SecurityScanHook())
    
    # 加载技能
    if skills_dir and os.path.exists(skills_dir):
        count = agent.load_skills(skills_dir)
        if count > 0:
            print(f"📚 加载了 {count} 个技能")
    
    return agent


def run_interactive(agent: Agent, ui: UIRenderer, prompt: PromptInput):
    """运行交互模式"""
    ui.print_welcome()
    
    # 触发会话开始事件
    agent.event_bus.emit("session_start", {
        "session_id": agent._session_id,
    })
    
    while True:
        user_input = prompt.get_input()
        
        if not user_input:
            continue
        
        # 处理内置命令
        if user_input.lower() in ("quit", "exit", "q"):
            ui.print_separator("再见")
            break
        
        if user_input.lower() == "help":
            ui.print_assistant(
                "**可用命令：**\n"
                "- `quit` / `exit` / `q` - 退出\n"
                "- `help` - 显示帮助\n"
                "- `reset` - 重置对话\n"
                "- `stats` - 显示上下文统计\n"
                "- `tasks` - 显示任务列表\n"
                "\n直接输入任意内容进行对话。"
            )
            continue
        
        if user_input.lower() == "reset":
            agent.reset()
            ui.print_warning("对话已重置")
            continue
        
        if user_input.lower() == "stats":
            stats = agent.get_context_stats()
            ui.print_stats(stats)
            continue
        
        # 显示用户输入
        ui.print_user(user_input)
        ui.print_separator()
        
        # 获取回复
        try:
            reply = agent.chat(user_input)
            ui.print_assistant(reply)
        except Exception as e:
            ui.print_error(str(e))
    
    # 触发会话结束事件
    agent.event_bus.emit("session_end", {
        "session_id": agent._session_id,
        "messages": agent.messages,
    })


@click.command()
@click.option("--model", default="gpt-4o-mini", help="LLM 模型名称")
@click.option("--skills", default=None, help="技能目录路径")
@click.option("--no-rich", is_flag=True, help="禁用 rich 渲染")
def main(model: str, skills: str, no_rich: bool):
    """🤖 从零手写的 AI Agent CLI"""
    if not HAS_CLICK:
        # 没有 click，手动解析
        print("⚠️  click 未安装，使用默认配置")
        print("   安装: pip install click")
    
    # 创建组件
    ui = UIRenderer(markdown=not no_rich)
    prompt = PromptInput(
        commands=["quit", "help", "reset", "stats", "tasks"],
    )
    
    # 创建 Agent
    try:
        agent = create_agent(model, skills_dir=skills)
    except Exception as e:
        ui.print_error(f"创建 Agent 失败: {e}")
        sys.exit(1)
    
    # 运行交互
    run_interactive(agent, ui, prompt)


if __name__ == "__main__":
    if HAS_CLICK:
        main()
    else:
        # 没有 click 的回退
        ui = UIRenderer()
        prompt = PromptInput()
        agent = create_agent("gpt-4o-mini")
        run_interactive(agent, ui, prompt)
```

---

## 🧪 测试验证

```bash
# 安装依赖
pip install rich prompt_toolkit click

# 运行 CLI
python -m src.cli

# 使用不同模型
python -m src.cli --model gpt-4o

# 禁用 rich
python -m src.cli --no-rich

# 加载技能
python -m src.cli --skills ./skills
```

---

## ⚠️ 常见错误

### 错误 1：`ModuleNotFoundError: No module named 'rich'`
**解决**：`pip install rich prompt_toolkit click`

### 错误 2：中文显示乱码
**原因**：终端编码不是 UTF-8。
**解决**：`export PYTHONIOENCODING=utf-8`

### 错误 3：prompt_toolkit 在 Windows 上异常
**原因**：Windows 终端兼容性问题。
**解决**：使用 `--no-rich` 回退到简单模式。

---

## 📝 本章小结

本章实现了美观的 CLI 终端界面：

| 组件 | 作用 |
|------|------|
| **UIRenderer** | rich 渲染（彩色面板、Markdown、表格） |
| **PromptInput** | prompt_toolkit 输入（补全、历史） |
| **CLI 入口** | click 命令解析 + 交互循环 |

### 当前局限性

- ❌ 没有真正的流式输出（逐 token 显示）
- ❌ 没有多面板布局（输入/输出/状态分离）
- ❌ 不支持 vim 模式

**下一章**，我们将实现安全与权限系统——生产级 Agent 的底线。

---

## 🏋️ 课后练习

### 练习 1：实现流式输出
使用 `rich.live.Live` 实现逐 token 打字机效果。

### 练习 2：实现侧边栏
用 rich 的 Layout 实现输入/输出/状态三栏布局。

### 练习 3：实现命令别名
支持 `!ls` 直接执行命令，`?keyword` 直接搜索。

---

**下一章**：[第 13 章：安全与权限 —— 生产级 Agent 的底线](ch13-安全与权限.md)
