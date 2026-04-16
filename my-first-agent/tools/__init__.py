"""
工具系统 —— 让 AI 有手有脚
从零手写 AI Agent 课程 · 第 2-4 章完善版
"""

from .base import Tool
from .bash_tool import BashTool
from .python_tool import PythonTool
from .file_tools import (
    FileReadTool,
    FileWriteTool,
    FileEditTool,
    FileSandbox,
    FileReadResult,
    FileWriteResult,
    FileEditResult,
    EditHistory,
    FileReadState,
    create_file_tools,
    detect_encoding,
)
from .web_tools import (
    WebSearchTool,
    WebFetchTool,
    WebSearchResult,
    WebFetchResult,
    SearchResult,
    SearchCache,
)
from .search_tools import (
    GrepTool,
    GlobTool,
    GrepResult,
    GlobResult,
)

__all__ = [
    # 基类
    "Tool",
    # Bash 工具
    "BashTool",
    # Python 工具
    "PythonTool",
    # 文件工具
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "FileSandbox",
    "FileReadResult",
    "FileWriteResult",
    "FileEditResult",
    # 辅助类
    "EditHistory",
    "FileReadState",
    # 网络工具
    "WebSearchTool",
    "WebFetchTool",
    "WebSearchResult",
    "WebFetchResult",
    "SearchResult",
    "SearchCache",
    # 搜索工具
    "GrepTool",
    "GlobTool",
    "GrepResult",
    "GlobResult",
    # 工具函数
    "create_file_tools",
    "detect_encoding",
]
