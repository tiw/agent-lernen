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
