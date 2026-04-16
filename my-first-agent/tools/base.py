"""
工具基类 —— 定义统一接口
从零手写 AI Agent 课程 · 第 2 章
"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """工具基类（抽象类，不能直接实例化）"""
    
    name: str = ""
    description: str = ""
    
    @property
    @abstractmethod
    def parameters(self) -> dict:
        """
        返回工具的参数 schema（JSON Schema 格式）
        
        示例：
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"}
            },
            "required": ["command"]
        }
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        执行工具，返回结果字符串
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            执行结果（字符串）
        """
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
    
    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', description='{self.description[:50]}...')"
