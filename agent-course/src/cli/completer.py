from __future__ import annotations

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
