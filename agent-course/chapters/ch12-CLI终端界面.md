# 第 12 章：CLI 终端界面 —— 让 Agent 好用

> **本章目标**：掌握终端 UI 设计原则，使用 `rich` 和 `click` 构建一个美观、交互流畅的 CLI 界面，支持流式输出、命令补全和历史记录。

---

## 🔍 先看 Claude Code 怎么做

Claude Code 的终端体验是其核心竞争力之一。它没有使用传统的 `input()/print()`，而是构建了一套完整的终端渲染管线。

### 源码导读

**1. 终端渲染引擎**（`src/ink/`）

Claude Code 使用了基于 React 的终端渲染框架 Ink，将终端 UI 组件化：

```typescript
// src/ink/renderer.ts 核心逻辑
// Ink 将 React 组件渲染为终端 ANSI 输出
// 支持增量更新、光标控制、区域刷新

// src/ink/render-to-screen.ts
function renderToScreen(output: Output, write: WriteFunction): void {
  // 1. 计算需要刷新的区域
  // 2. 生成 ANSI 转义序列
  // 3. 写入终端
  // 4. 恢复光标位置
}
```

关键设计：
- **增量渲染**：只刷新变化的区域，不重绘整个屏幕
- **双缓冲**：先在内存中构建下一帧，然后原子切换，避免闪烁
- **区域分割**：屏幕分为输入区、输出区、状态栏等独立区域

**2. 结构化 I/O**（`src/cli/structuredIO.ts`）

Claude Code 支持两种输出模式：

```typescript
// src/cli/structuredIO.ts
// 交互模式：渲染漂亮的终端 UI
// 非交互模式（--output-format json）：输出结构化 JSON，供脚本消费

export async function writeToStdout(message: SDKMessage): Promise<void> {
  if (isNonInteractive) {
    // JSON 模式：每行一个 JSON 对象
    process.stdout.write(ndjsonSafeStringify(message) + "\n")
  } else {
    // 交互模式：通过 Ink 渲染
    renderToInk(message)
  }
}
```

**3. 输入处理**（`src/ink/hooks/use-input.ts`）

```typescript
// src/ink/hooks/use-input.ts
// 处理键盘输入，支持：
// - 命令补全（Tab）
// - 历史导航（上下箭头）
// - 搜索历史（Ctrl+R）
// - 多行输入（Shift+Enter）

function useInput(handler: InputHandler, options?: InputOptions) {
  // 注册键盘事件监听
  // 处理特殊键位
  // 支持 vim 模式
}
```

**4. 流式输出**（`src/ink/output.ts`）

```typescript
// src/ink/output.ts
// 流式输出 Agent 的回复，逐 token 渲染
// 支持打字机效果、光标闪烁
```

**5. CLI 入口**（`src/cli/handlers/`）

```
src/cli/handlers/
├── agents.ts      # Agent 模式处理
├── auth.ts        # 认证流程
├── autoMode.ts    # 非交互模式
├── mcp.tsx        # MCP 服务器管理
├── plugins.ts     # 插件管理
└── util.tsx       # 工具函数
```

### 架构总结

```
用户键盘输入
    │
    ▼
输入处理器（解析键位、补全、历史）
    │
    ▼
命令解析（slash 命令、自然语言）
    │
    ▼
Agent 处理 → 流式输出
    │
    ▼
Ink 渲染引擎（增量更新、双缓冲）
    │
    ▼
终端显示
```

---

## 🧠 核心概念

### 终端 UI 设计原则

1. **信息层次**：重要信息突出显示，次要信息弱化
2. **即时反馈**：用户操作后 100ms 内给出视觉反馈
3. **流式输出**：不要等全部生成完再显示，逐段输出
4. **状态可见**：始终让用户知道 Agent 在做什么
5. **键盘优先**：减少鼠标依赖，支持快捷键

### 技术选型

| 组件 | 库 | 作用 |
|------|-----|------|
| CLI 框架 | `click` | 命令解析、参数处理、帮助文本 |
| 富文本输出 | `rich` | 彩色文本、表格、进度条、Markdown 渲染 |
| 实时交互 | `prompt_toolkit` | 输入补全、历史记录、多行编辑 |
| 流式输出 | `rich.live` | 实时更新终端内容 |

### 为什么不用 `input()/print()`？

```python
# ❌ 传统方式：无法流式输出，无法美化
print("Agent 正在思考...")
result = agent.run(user_input)
print(result)

# ✅ 现代方式：流式输出，实时更新
with Live(console=console) as live:
    for chunk in agent.stream(user_input):
        live.update(render_chunk(chunk))
```

---

## 💻 动手实现

### 项目结构

```
my_agent/
├── cli/
│   ├── __init__.py
│   ├── interface.py      # 主 CLI 界面
│   ├── completer.py      # 命令补全
│   ├── theme.py          # 主题配色
│   └── commands.py       # Slash 命令
├── core/
│   └── ...
└── main.py
```

### 1. 主题与配色（`cli/theme.py`）

```python
"""
CLI 主题配置

定义颜色、样式、布局，参考 Claude Code 的 ink/styles.ts
"""

from rich.theme import Theme
from rich.style import Style

# 配色方案 —— 暗色终端风格
AGENT_THEME = Theme({
    # Agent 输出
    "agent.name": "bold cyan",
    "agent.thinking": "dim yellow",
    "agent.tool_use": "magenta",
    "agent.tool_result": "green",
    "agent.error": "bold red",
    "agent.system": "dim blue",

    # 用户输入
    "user.prompt": "white",
    "user.prefix": "bold green",

    # 界面元素
    "separator": "dim white",
    "timestamp": "dim white",
    "status.ready": "bold green",
    "status.busy": "bold yellow",
    "status.error": "bold red",

    # 代码
    "code.block": "dim cyan",
    "code.inline": "bold yellow",
})


class ThemeConfig:
    """主题配置类"""

    # 提示符
    PROMPT_PREFIX = "🦞"
    THINKING_TEXT = "💭 思考中..."
    TOOL_USE_TEXT = "🔧 使用工具"
    ERROR_TEXT = "❌ 错误"

    # 状态指示器
    STATUS_READY = "● 就绪"
    STATUS_THINKING = "◐ 思考中"
    STATUS_TOOL = "◑ 执行中"
    STATUS_ERROR = "✕ 错误"

    # 布局
    MAX_OUTPUT_WIDTH = 120
    MAX_TOOL_OUTPUT_LINES = 50

    # 动画
    THINKING_DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
```

### 2. 命令补全（`cli/completer.py`）

```python
"""
命令补全器

参考 Claude Code 的 useArrowKeyHistory.tsx 和 fileSuggestions.ts
支持：
- Slash 命令补全
- 文件路径补全
- 历史命令补全
"""

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from pathlib import Path
import os


# Slash 命令定义
SLASH_COMMANDS = {
    "/help": "显示帮助信息",
    "/clear": "清空对话历史",
    "/history": "查看对话历史",
    "/model": "切换模型",
    "/settings": "查看/修改设置",
    "/quit": "退出",
    "/exit": "退出",
    "/cost": "查看本次会话成本",
    "/tools": "列出可用工具",
    "/hooks": "管理 Hook 系统",
}


class AgentCompleter(Completer):
    """
    智能补全器

    - 输入 / 时补全 slash 命令
    - 输入路径时补全文件
    - 上下箭头浏览历史
    """

    def __init__(self, history: FileHistory | None = None):
        self.history = history
        self._history_items: list[str] = []

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Slash 命令补全
        if text.startswith("/"):
            word = text.split()[0] if text.strip() else text
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(word),
                        display=cmd,
                        display_meta=desc,
                    )
            return

        # 文件路径补全（检测到 / 或 ./ 或 ~/）
        if "/" in text or text.startswith("~"):
            yield from self._complete_path(document, text)
            return

        # 历史命令补全
        if self.history:
            yield from self._complete_history(document, text)

    def _complete_path(self, document, text: str):
        """文件路径补全（生成器）"""
        # 获取最后一个词
        words = text.split()
        if not words:
            return

        last_word = words[-1]
        directory = os.path.dirname(last_word) or "."

        try:
            path = Path(directory).expanduser()
            if path.is_dir():
                for item in path.iterdir():
                    name = item.name
                    if name.startswith(os.path.basename(last_word)):
                        suffix = "/" if item.is_dir() else ""
                        yield Completion(
                            name + suffix,
                            start_position=-len(os.path.basename(last_word)),
                            display=name + suffix,
                            display_meta="目录" if item.is_dir() else "文件",
                        )
        except (PermissionError, OSError):
            pass

    def _complete_history(self, document, text: str):
        """历史命令补全（生成器）"""
        if text and self.history:
            for item in self.history.load_history_strings():
                if item.startswith(text) and item != text:
                    yield Completion(
                        item,
                        start_position=-len(text),
                        display=item[:60],
                        display_meta="历史",
                    )
```

### 3. Slash 命令处理（`cli/commands.py`）

```python
"""
Slash 命令处理器

参考 Claude Code 的 commands/ 目录（100+ 个命令）
"""

import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Slash 命令注册表"""

    def __init__(self):
        self._commands: dict[str, dict] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """注册一个命令"""
        self._commands[name] = {
            "handler": handler,
            "description": description,
            "aliases": aliases or [],
        }
        for alias in (aliases or []):
            self._commands[alias] = self._commands[name]

    async def execute(self, command_line: str, context: dict) -> Any:
        """执行命令"""
        parts = command_line.strip().split(maxsplit=1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(cmd_name)
        if not cmd:
            return f"未知命令: {cmd_name}。输入 /help 查看可用命令。"

        try:
            result = cmd["handler"](args, context)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            logger.error(f"Command error: {cmd_name}: {e}")
            return f"命令执行失败: {e}"

    def list_commands(self) -> list[dict]:
        """列出所有命令"""
        seen = set()
        commands = []
        for name, info in self._commands.items():
            if name not in seen:
                seen.add(name)
                commands.append({
                    "name": name,
                    "description": info["description"],
                    "aliases": info["aliases"],
                })
        return sorted(commands, key=lambda x: x["name"])


def register_builtin_commands(registry: CommandRegistry) -> None:
    """注册内置命令"""

    def cmd_help(args: str, ctx: dict) -> str:
        cmds = registry.list_commands()
        lines = ["📋 可用命令：", ""]
        for cmd in cmds:
            aliases = f" ({', '.join(cmd['aliases'])})" if cmd["aliases"] else ""
            lines.append(f"  {cmd['name']:<12} {cmd['description']}{aliases}")
        lines.append("")
        lines.append("💡 直接输入文字即可与 Agent 对话")
        return "\n".join(lines)

    def cmd_clear(args: str, ctx: dict) -> str:
        ctx.get("clear_callback", lambda: None)()
        return ""

    def cmd_quit(args: str, ctx: dict) -> str:
        raise SystemExit(0)

    def cmd_cost(args: str, ctx: dict) -> str:
        agent = ctx.get("agent")
        if agent and hasattr(agent, "cost_tracker"):
            return agent.cost_tracker.summary()
        return "成本追踪未启用"

    def cmd_tools(args: str, ctx: dict) -> str:
        agent = ctx.get("agent")
        if agent and hasattr(agent, "tools"):
            lines = ["🔧 可用工具：", ""]
            for tool in agent.tools:
                lines.append(f"  {tool.name:<15} {tool.description}")
            return "\n".join(lines)
        return "无可用工具"

    registry.register("/help", cmd_help, "显示帮助信息", ["/h", "/?"])
    registry.register("/clear", cmd_clear, "清空对话", ["/cls"])
    registry.register("/quit", cmd_quit, "退出", ["/exit", "/q"])
    registry.register("/cost", cmd_cost, "查看成本")
    registry.register("/tools", cmd_tools, "列出工具")
```

### 4. 主 CLI 界面（`cli/interface.py`）

```python
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
from cli.theme import ThemeConfig, AGENT_THEME

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
        from pathlib import Path

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
```

---

## 🧪 测试验证

### 测试 1：CLI 界面基本功能

```python
"""
测试 CLI 界面
"""

import asyncio
from io import StringIO
from unittest.mock import AsyncMock, patch

from rich.console import Console
from cli.interface import AgentCLI
from cli.completer import AgentCompleter, SLASH_COMMANDS
from cli.commands import CommandRegistry, register_builtin_commands


def test_completer_slash_commands():
    """测试 slash 命令补全"""
    from prompt_toolkit.document import Document

    completer = AgentCompleter()

    # 输入 /h 应补全 /help
    doc = Document(text="/h", cursor_position=2)
    completions = list(completer.get_completions(doc, None))
    assert any(c.text == "/help" for c in completions)
    print("✅ Slash 命令补全测试通过")


def test_completer_no_match():
    """测试无匹配时不补全"""
    from prompt_toolkit.document import Document

    completer = AgentCompleter()
    doc = Document(text="/xyz", cursor_position=4)
    completions = list(completer.get_completions(doc, None))
    assert len(completions) == 0
    print("✅ 无匹配测试通过")


def test_command_registry():
    """测试命令注册表"""
    registry = CommandRegistry()

    def dummy_handler(args, ctx):
        return f"Hello, {args}!"

    registry.register("/greet", dummy_handler, "打招呼", ["/hello"])
    registry.register("/help", lambda a, c: "Help text", "帮助")

    # 执行命令
    result = asyncio.get_event_loop().run_until_complete(
        registry.execute("/greet World", {})
    )
    assert result == "Hello, World!"

    # 别名
    result = asyncio.get_event_loop().run_until_complete(
        registry.execute("/hello World", {})
    )
    assert result == "Hello, World!"

    # 未知命令
    result = asyncio.get_event_loop().run_until_complete(
        registry.execute("/unknown", {})
    )
    assert "未知命令" in result

    # 列出命令
    cmds = registry.list_commands()
    assert len(cmds) >= 2
    print("✅ 命令注册表测试通过")


def test_theme():
    """测试主题配置"""
    from cli.theme import AGENT_THEME, ThemeConfig

    console = Console(theme=AGENT_THEME, force_terminal=True, width=80)

    # 测试渲染
    with console.capture() as capture:
        console.print("测试", style="agent.thinking")

    assert capture.get()  # 有输出
    assert ThemeConfig.PROMPT_PREFIX == "🦞"
    assert ThemeConfig.THINKING_TEXT == "💭 思考中..."
    print("✅ 主题配置测试通过")


def test_cli_banner():
    """测试欢迎横幅"""
    cli = AgentCLI()

    with cli.console.capture() as capture:
        cli.print_banner()

    output = capture.get()
    assert "🦞" in output
    assert "My Agent CLI" in output
    print("✅ 欢迎横幅测试通过")


def test_streaming_output():
    """测试流式输出"""
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown

    console = Console(force_terminal=True, width=80)
    chunks = ["# Hello", "\n", "This is ", "**bold**", " text."]

    with console.capture() as capture:
        full_text = ""
        for chunk in chunks:
            full_text += chunk

        # 模拟流式输出
        rendered = Markdown(full_text)
        console.print(rendered)

    output = capture.get()
    assert "Hello" in output
    print("✅ 流式输出测试通过")


def main():
    print("=" * 50)
    print("CLI 界面测试")
    print("=" * 50)

    test_completer_slash_commands()
    test_completer_no_match()
    test_command_registry()
    test_theme()
    test_cli_banner()
    test_streaming_output()

    print("=" * 50)
    print("所有测试通过！🎉")
    print("=" * 50)


if __name__ == "__main__":
    main()
```

### 测试 2：手动运行 CLI

```bash
# 安装依赖
pip install rich click prompt_toolkit

# 运行 CLI
python -m cli.interface

# 非交互模式（管道）
echo '{"prompt": "你好"}' | python -m cli.interface --non-interactive

# 查看帮助
python -m cli.interface --help
```

---

## 📝 本章小结

本章我们构建了 Agent 的 CLI 终端界面：

1. **技术栈**：`rich`（富文本渲染）+ `click`（CLI 框架）+ `prompt_toolkit`（交互式输入）
2. **流式输出**：使用 `rich.Live` 实现打字机效果，逐 token 更新显示
3. **命令补全**：支持 slash 命令、文件路径、历史命令三种补全模式
4. **Slash 命令**：可扩展的命令系统，支持别名和参数
5. **主题系统**：统一配色和样式，可自定义

与 Claude Code 的对比：
- Claude Code 用 Ink（React）做终端渲染，我们用 rich（Python）
- 核心思想一致：增量渲染、状态可见、键盘优先
- Claude Code 支持 vim 模式、多标签页等高级功能，我们的实现是基础版

---

## 🏋️ 课后练习

### 练习 1：实现打字机动画

**题目**：当前流式输出是直接追加文本。请实现一个打字机动画效果，每个字符逐个显示，带有微小的延迟（10ms），模拟人类打字的感觉。

**答案提示**：
- 使用 `time.sleep(0.01)` 控制速度
- 用 `rich.Live` 或 `rich.Console` 的 `control` 方法控制光标
- 注意：实际 LLM 流式输出不需要这个效果，但作为 UI 练习很有价值

### 练习 2：实现多行输入

**题目**：当前输入是单行的。请实现多行输入模式：按 `Shift+Enter` 换行，按 `Enter` 提交。

**答案提示**：
- 使用 `prompt_toolkit` 的 `accept_default=False` 配置
- 自定义 `KeyBindings`，绑定 `Enter` 到提交，`Shift+Enter` 到换行
- 在提示符中显示当前行号

### 练习 3：实现进度条显示

**题目**：当 Agent 调用外部工具（如执行 bash 命令）时，显示一个进度条或旋转动画，让用户知道工具正在执行中。

**答案提示**：
- 使用 `rich.progress.Progress` + `SpinnerColumn`
- 工具开始执行时启动进度，结束时停止
- 如果工具支持实时输出，将 stdout 重定向到进度条下方

---

*下一章：第 13 章 —— 安全与权限，生产级 Agent 的底线。*

这个回答有帮助吗？回复数字让我知道：0 差 · 1 一般 · 2 好
