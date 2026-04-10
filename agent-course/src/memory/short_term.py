"""
短期记忆管理 —— 上下文窗口与消息压缩。
参考 Claude Code 的 compact 服务实现。
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .token_counter import TokenEstimator


# ============================================================
# 消息类型
# ============================================================

class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    COMPACT_BOUNDARY = "compact_boundary"
    ATTACHMENT = "attachment"


@dataclass
class Message:
    """统一的消息表示"""
    role: str
    content: str
    msg_type: MessageType = MessageType.USER
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'role': self.role,
            'content': self.content,
            'type': self.msg_type.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
        }


@dataclass
class CompactBoundary:
    """压缩边界标记。"""
    trigger: str
    pre_compact_tokens: int
    post_compact_tokens: int
    messages_summarized: int
    timestamp: float = field(default_factory=time.time)

    def to_message(self) -> Message:
        return Message(
            role='system',
            content=(
                f"[Conversation compacted: {self.messages_summarized} messages "
                f"summarized. Pre-compact: {self.pre_compact_tokens} tokens, "
                f"Post-compact: {self.post_compact_tokens} tokens. "
                f"Trigger: {self.trigger}]"
            ),
            msg_type=MessageType.COMPACT_BOUNDARY,
            timestamp=self.timestamp,
        )


# ============================================================
# 上下文窗口管理器
# ============================================================

class ContextWindow:
    """
    上下文窗口管理器。
    """

    def __init__(
        self,
        max_tokens: int = 150_000,
        compact_threshold: float = 0.75,
        keep_recent: int = 10,
        estimator: Optional[TokenEstimator] = None,
        compact_callback=None,
    ):
        self.max_tokens = max_tokens
        self.compact_threshold = compact_threshold
        self.keep_recent = keep_recent
        self.estimator = estimator or TokenEstimator()
        self.compact_callback = compact_callback

        self.messages: list = []
        self.compact_count = 0
        self.total_tokens = 0

    def add(self, message: Message) -> None:
        """添加一条消息"""
        self.messages.append(message)
        self.total_tokens = self._estimate_total()

    def add_user(self, content: str) -> None:
        """添加用户消息"""
        self.add(Message(
            role='user',
            content=content,
            msg_type=MessageType.USER,
        ))

    def add_assistant(self, content: str) -> None:
        """添加助手消息"""
        self.add(Message(
            role='assistant',
            content=content,
            msg_type=MessageType.ASSISTANT,
        ))

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """添加工具调用结果"""
        self.add(Message(
            role='user',
            content=[{
                'type': 'tool_result',
                'tool_name': tool_name,
                'content': result,
            }],
            msg_type=MessageType.TOOL_RESULT,
        ))

    def needs_compact(self) -> bool:
        """检查是否需要压缩"""
        threshold = self.max_tokens * self.compact_threshold
        return self.total_tokens > threshold

    def get_usage_ratio(self) -> float:
        """获取当前 token 使用率"""
        return self.total_tokens / self.max_tokens

    def compact(self) -> Optional[CompactBoundary]:
        """执行上下文压缩。"""
        if not self.needs_compact():
            return None

        if not self.compact_callback:
            raise RuntimeError(
                "No compact_callback set. "
                "Set context_window.compact_callback = your_function"
            )

        pre_tokens = self.total_tokens
        total_messages = len(self.messages)

        messages_to_summarize = self.messages[:-self.keep_recent]
        messages_to_keep = self.messages[-self.keep_recent:]

        if not messages_to_summarize:
            return None

        summary = self.compact_callback(messages_to_summarize)

        summary_message = Message(
            role='user',
            content=f"[Conversation Summary]\n{summary}",
            msg_type=MessageType.USER,
            metadata={'is_compact_summary': True},
        )

        boundary = CompactBoundary(
            trigger='auto',
            pre_compact_tokens=pre_tokens,
            post_compact_tokens=0,
            messages_summarized=len(messages_to_summarize),
        )

        self.messages = [
            summary_message,
            boundary.to_message(),
            *messages_to_keep,
        ]

        self.compact_count += 1
        self.total_tokens = self._estimate_total()
        boundary.post_compact_tokens = self.total_tokens

        return boundary

    def get_api_messages(self) -> list:
        """获取发送给 API 的消息格式。"""
        api_messages = []
        for msg in self.messages:
            if msg.msg_type in (MessageType.SYSTEM, MessageType.COMPACT_BOUNDARY):
                continue
            api_messages.append({
                'role': msg.role,
                'content': msg.content,
            })
        return api_messages

    def get_status(self) -> dict:
        """获取上下文状态信息"""
        return {
            'total_tokens': self.total_tokens,
            'max_tokens': self.max_tokens,
            'usage_ratio': f"{self.get_usage_ratio():.1%}",
            'message_count': len(self.messages),
            'compact_count': self.compact_count,
            'needs_compact': self.needs_compact(),
        }

    def _estimate_total(self) -> int:
        """估算当前消息的总 token 数"""
        return self.estimator.estimate_messages(self.messages)

    def clear(self) -> None:
        """清空所有消息"""
        self.messages.clear()
        self.total_tokens = 0
        self.compact_count = 0


# ============================================================
# 消息压缩策略
# ============================================================

class CompressionStrategy:
    """消息压缩策略的抽象基类。"""

    def compress(
        self,
        messages: list,
        target_tokens: int,
        estimator: TokenEstimator,
    ) -> list:
        raise NotImplementedError


class TruncationStrategy(CompressionStrategy):
    """简单截断策略。"""

    def compress(
        self,
        messages: list,
        target_tokens: int,
        estimator: TokenEstimator,
    ) -> list:
        result = list(messages)
        while estimator.estimate_messages(result) > target_tokens and len(result) > 1:
            result.pop(0)
        return result


class SlidingWindowStrategy(CompressionStrategy):
    """滑动窗口策略。"""

    def __init__(self, window_size: int = 20):
        self.window_size = window_size

    def compress(
        self,
        messages: list,
        target_tokens: int,
        estimator: TokenEstimator,
    ) -> list:
        return messages[-self.window_size:]


class SummaryStrategy(CompressionStrategy):
    """摘要压缩策略。"""

    def __init__(self, llm_callback, summary_prompt: Optional[str] = None):
        self.llm_callback = llm_callback
        self.summary_prompt = summary_prompt or (
            "请总结以下对话的关键信息，包括：\n"
            "1. 用户的主要需求和目标\n"
            "2. 重要的技术决策和代码变更\n"
            "3. 关键的文件路径和代码片段\n"
            "4. 待解决的问题和下一步行动\n\n"
            "保持简洁，但要保留所有重要细节。"
        )

    def compress(
        self,
        messages: list,
        target_tokens: int,
        estimator: TokenEstimator,
    ) -> list:
        text = '\n'.join(
            f"[{msg.role}] {msg.content if isinstance(msg.content, str) else str(msg.content)}"
            for msg in messages
        )

        summary = self.llm_callback(text)

        return [Message(
            role='user',
            content=f"[Summary of {len(messages)} messages]\n{summary}",
            msg_type=MessageType.USER,
            metadata={'is_compact_summary': True},
        )]


# ============================================================
# 图片/附件剥离
# ============================================================

def strip_media_blocks(content):
    """
    剥离图片和文档 block，替换为文本标记。
    """
    if isinstance(content, str):
        return content

    result = []
    for block in content:
        if block.get('type') == 'image':
            result.append({'type': 'text', 'text': '[image]'})
        elif block.get('type') == 'document':
            result.append({'type': 'text', 'text': '[document]'})
        else:
            result.append(block)

    return result
