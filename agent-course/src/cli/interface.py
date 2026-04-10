from __future__ import annotations

"""
CLI 终端界面 —— 主入口

整合 rich、click、prompt_toolkit，构建完整的终端交互体验。
参考 Claude Code 的 main.tsx（入口）+ ink/（渲染）+ cli/（命令处理）
"""

import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Any

import click
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from cli.completer import AgentCompleter, SLASH_COMMANDS
from cli.commands import CommandRegistry, register_builtin_commands
from cli.themes import ThemeConfig, AGENT_THEME

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

    def print_status(self, status: str) -> None:
        """打印状态行"""
        self.console.print(f"  [{status}]", style="status.busy")

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

    def print_tool_use(self, tool_name: str, tool_input: str) -> None:
        """显示工具调用"""
        panel = Panel(
            f"[bold]{tool_name}[/bold]\n[dim]{tool_input[:200]}[/dim]",
            title=ThemeConfig.TOOL_USE_TEXT,
            border_style="magenta",
            padding=(0, 2),
        )
        self.console.print(panel)

    def print_tool_result(self, result: str) -> None:
        """显示工具结果"""
        # 截断过长的输出
        if len(result) > 500:
            result = result[:500] + "\n... [dim](已截断)[/dim]"
        panel = Panel(
            f"[green]{result}[/green]",
            border_style="green",
            padding=(0, 2),
        )
        self.console.print(panel)

    def print_response_stream(self, chunks: list[str]) -> None:
        """
        流式输出 Agent 回复

        使用 rich.Live 实现打字机效果
        """
        full_text = ""

        with Live(
            console=self.console,
            refresh_per_second=10,  # 每秒刷新 10 次
            transient=False,
        ) as live:
            for chunk in chunks:
                full_text += chunk
                # 渲染 Markdown
                rendered = Markdown(full_text)
                live.update(rendered)

        self.console.print()  # 换行

    def print_response(self, text: str) -> None:
        """打印完整回复（非流式）"""
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

            # 流式调用 Agent
            start_time = time.time()
            chunks = []

            async for chunk in self.agent.stream(line):
                chunks.append(chunk)
                # 实时更新显示
                self.console.print(chunk, end="")

            elapsed = time.time() - start_time
            self.console.print()
            self.console.print(
                f"  [dim]⏱ {elapsed:.1f}s · {len(chunks)} tokens[/dim]"
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
                    # 显示提示符
                    prompt_text = f"{ThemeConfig.PROMPT_PREFIX} "
                    user_input = await self.session.prompt_async(
                        prompt_text
                    )

                    should_continue = await self.handle_command(user_input)
                    if not should_continue:
                        break

                except KeyboardInterrupt:
                    self.console.print()
                    self.console.print(
                        "[dim]按 Ctrl+D 退出，或继续输入[/dim]"
                    )
                except EOFError:
                    break

        finally:
            if self.agent:
                await self.agent.end_session()
            self.console.print()
            self.console.print("[dim]👋 再见！[/dim]")


# Click 入口
@click.command()
@click.option(
    "--model", "-m",
    default="claude-3-5-sonnet-20241022",
    help="LLM 模型名称",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True),
    help="配置文件路径",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="显示详细日志",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="非交互模式（从 stdin 读取，输出 JSON）",
)
def main(model: str, config: str | None, verbose: bool, non_interactive: bool):
    """
    🦞 My Agent CLI —— 从零手写的 AI Agent

    直接运行进入交互模式，支持管道输入输出。
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if non_interactive:
        # 非交互模式：从 stdin 读取 JSON，输出 JSON
        import json
        for line in sys.stdin:
            try:
                data = json.loads(line)
                # 处理 NDJSON 输入
                click.echo(json.dumps({"echo": data}))
            except json.JSONDecodeError:
                click.echo(json.dumps({"error": "invalid json"}))
        return

    # 交互模式
    cli = AgentCLI()
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
