"""
cli/theme.py —— CLI 主题配置
定义颜色、样式、布局，参考 Claude Code 的 ink/styles.ts
从零手写 AI Agent 课程 · 第 12 章
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


# === 测试 ===
if __name__ == "__main__":
    print("=== CLI 主题测试 ===\n")

    from rich.console import Console

    console = Console(theme=AGENT_THEME)

    # 测试 1: Agent 输出样式
    print("测试 1: Agent 输出样式")
    console.print("  Agent 名称", style="agent.name")
    console.print("  思考中", style="agent.thinking")
    console.print("  工具使用", style="agent.tool_use")
    console.print("  工具结果", style="agent.tool_result")
    console.print("  错误信息", style="agent.error")
    print()

    # 测试 2: 用户输入样式
    print("测试 2: 用户输入样式")
    console.print(f"{ThemeConfig.PROMPT_PREFIX} ", end="", style="user.prefix")
    console.print("用户输入的文字", style="user.prompt")
    print()

    # 测试 3: 状态指示器
    print("测试 3: 状态指示器")
    console.print(f"  {ThemeConfig.STATUS_READY}", style="status.ready")
    console.print(f"  {ThemeConfig.STATUS_THINKING}", style="status.busy")
    console.print(f"  {ThemeConfig.STATUS_ERROR}", style="status.error")
    print()

    # 测试 4: 配置常量
    print("测试 4: 配置常量")
    print(f"  最大输出宽度：{ThemeConfig.MAX_OUTPUT_WIDTH}")
    print(f"  思考动画：{' '.join(ThemeConfig.THINKING_DOTS[:5])}...")
    print()

    print("✅ 所有测试完成！")
