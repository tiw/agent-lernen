"""
工具系统 —— 让 AI 有手有脚
从零手写 AI Agent 课程 · 第 2 章
"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """返回工具的参数 schema（JSON Schema 格式）"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具，返回结果字符串"""
        pass

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_anthropic_format(self) -> dict:
        """转换为 Anthropic 工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
