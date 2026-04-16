"""
cli/interface.py —— CLI 终端界面主入口
整合 rich、prompt_toolkit，构建完整的终端交互体验
参考 Claude Code 的 main.tsx + ink/ + cli/
从零手写 AI Agent 课程 · 第 12 章
"""

import asyncio
import logging
import sys
import os
import time
from datetime import datetime
from typing import Any

from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cli.completer import AgentCompleter
    from cli.commands import CommandRegistry, register_builtin_commands
    from cli.theme import ThemeConfig, AGENT_THEME
else:
    from .completer import AgentCompleter
    from .commands import CommandRegistry, register_builtin_commands
    from .theme import ThemeConfig, AGENT_THEME

logger = logging.getLogger(__name__)


class AgentCLI:
    """
    Agent CLI 界面

    核心功能：
    - 流式输出 Agent 回复
    - 命令补全和历史记录
    - 交互式对话
    - Slash 命令支持
    """

    def __init__(self, agent=None):
        self.agent = agent
        self.console = Console(theme=AGENT_THEME, force_terminal=True)
        self.command_registry = CommandRegistry()
        self.session_context: dict[str, Any] = {}

        # 历史记录
        self.history_file = Path.home() / ".my_agent" / "cli_history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # 初始化
        self._setup_commands()
        self._setup_session()

    def _setup_commands(self) -> None:
        """注册 Slash 命令"""
        register_builtin_commands(self.command_registry)
        self.session_context = {
            "agent": self.agent,
            "console": self.console,
            "clear_callback": self.console.clear,
        }

    def _setup_session(self) -> None:
        """配置 prompt_toolkit 会话"""
        bindings = KeyBindings()

        @bindings.add("c-c")
        def _(event):
            """Ctrl+C 中断当前操作"""
            event.app.exit(exception=KeyboardInterrupt())

        @bindings.add("c-d")
        def _(event):
            """Ctrl+D 退出"""
            event.app.exit(exception=EOFError())

        self.session = PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=AgentCompleter(),
            complete_while_typing=True,
            key_bindings=bindings,
            style=PTStyle.from_dict({
                "prompt": "fg:#00ff00 bold",
                "input": "fg:#ffffff",
            }),
        )

    def print_banner(self) -> None:
        """打印欢迎横幅"""
        banner = Panel.fit(
            "[bold cyan]🦞 My Agent CLI[/bold cyan]\n"
            "[dim]从零手写的 AI Agent，跟着 Claude Code 学架构[/dim]\n"
            f"[dim]输入 /help 查看命令 · {datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]",
            border_style="cyan",
        )
        self.console.print()
        self.console.print(banner)
        self.console.print()

    def print_user_prompt(self, text: str) -> None:
        """打印用户输入"""
        self.console.print()
        self.console.print(
            f"{ThemeConfig.PROMPT_PREFIX} ",
            end="",
            style="user.prefix",
        )
        self.console.print(text, style="user.prompt")
        self.console.print(Rule(style="separator"))

    def print_thinking(self) -> None:
        """显示思考状态"""
        self.console.print(
            f"  {ThemeConfig.THINKING_TEXT}",
            style="agent.thinking",
        )

    def print_response(self, text: str) -> None:
        """打印完整回复"""
        self.console.print(Markdown(text))
        self.console.print()

    def print_error(self, message: str) -> None:
        """打印错误"""
        self.console.print(
            f"  {ThemeConfig.ERROR_TEXT}: {message}",
            style="agent.error",
        )

    async def handle_command(self, line: str) -> bool:
        """
        处理用户输入

        返回 True 表示继续循环，False 表示退出
        """
        line = line.strip()
        if not line:
            return True

        # Slash 命令
        if line.startswith("/"):
            try:
                result = await self.command_registry.execute(
                    line, self.session_context
                )
                if result:
                    self.console.print(result)
            except SystemExit:
                return False
            return True

        # 普通对话
        self.print_user_prompt(line)

        if not self.agent:
            self.print_error("Agent 未初始化")
            return True

        try:
            # 显示思考状态
            self.print_thinking()

            # 调用 Agent
            start_time = time.time()
            response = await self.agent.chat(line)
            elapsed = time.time() - start_time

            self.print_response(response)
            self.console.print(
                f"  [dim]⏱ {elapsed:.1f}s[/dim]"
            )

        except KeyboardInterrupt:
            self.console.print()
            self.print_error("已中断")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            self.print_error(str(e))

        return True

    async def run(self) -> None:
        """运行 CLI 主循环"""
        self.print_banner()

        # 启动 Agent 会话
        if self.agent:
            await self.agent.start_session()

        try:
            while True:
                try:
                    line = await self.session.prompt_async(
                        f"{ThemeConfig.PROMPT_PREFIX} ",
                        style=PTStyle.from_dict({
                            "prompt": "fg:#00ff00 bold",
                        }),
                    )
                    should_continue = await self.handle_command(line)
                    if not should_continue:
                        break
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    break
        finally:
            self.console.print("\n[dim]👋 再见！[/dim]")


# === 测试 ===
if __name__ == "__main__":
    async def test_cli():
        print("=== CLI 界面测试 ===\n")

        import sys
        import os

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # 创建 CLI（无 Agent）
        cli = AgentCLI()
        cli.print_banner()

        # 测试命令
        print("测试：执行 /help")
        result = await cli.command_registry.execute("/help", cli.session_context)
        print(result[:300])
        print("\n✅ 测试完成！")

    asyncio.run(test_cli())
