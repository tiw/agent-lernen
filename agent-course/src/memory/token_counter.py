"""
Token 计数与估算模块。
参考 Claude Code 的 tokenEstimation.ts 实现。
"""

import json
import math
from typing import Optional


class TokenEstimator:
    """
    Token 估算器。
    """

    DEFAULT_BYTES_PER_TOKEN = 4
    DENSE_BYTES_PER_TOKEN = 2
    IMAGE_TOKEN_ESTIMATE = 2000
    DOCUMENT_TOKEN_ESTIMATE = 2000

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def estimate(self, text: str) -> int:
        """粗糙估算：基于字符数。"""
        return math.ceil(len(text) / self.DEFAULT_BYTES_PER_TOKEN)

    def estimate_for_type(self, text: str, file_type: str = '') -> int:
        """类型感知的 token 估算。"""
        ext = file_type.lower().lstrip('.')
        if ext in ('json', 'jsonl', 'jsonc'):
            return math.ceil(len(text) / self.DENSE_BYTES_PER_TOKEN)
        return self.estimate(text)

    def estimate_message(self, message: dict) -> int:
        """估算一条消息的 token 数。"""
        content = message.get('content', '')

        if isinstance(content, str):
            return self.estimate(content)

        if isinstance(content, list):
            total = 0
            for block in content:
                total += self._estimate_block(block)
            return total

        return 0

    def estimate_messages(self, messages: list) -> int:
        """估算消息列表的总 token 数"""
        return sum(self.estimate_message(m) for m in messages)

    def _estimate_block(self, block: dict) -> int:
        """估算单个内容块的 token 数"""
        block_type = block.get('type', 'text')

        if block_type == 'text':
            return self.estimate(block.get('text', ''))

        if block_type == 'tool_use':
            name = block.get('name', '')
            inp = block.get('input', {})
            return self.estimate_for_type(
                name + json.dumps(inp, ensure_ascii=False),
                'json'
            )

        if block_type == 'tool_result':
            content = block.get('content', '')
            if isinstance(content, str):
                return self.estimate(content)
            if isinstance(content, list):
                return sum(self._estimate_block(b) for b in content)
            return 0

        if block_type == 'image':
            return self.IMAGE_TOKEN_ESTIMATE

        if block_type == 'document':
            return self.DOCUMENT_TOKEN_ESTIMATE

        return self.estimate_for_type(
            json.dumps(block, ensure_ascii=False),
            'json'
        )

    def count_tokens_api(self, text: str) -> Optional[int]:
        """使用 Anthropic API 精确计数 token。"""
        if not self.api_key:
            return None

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            response = client.beta.messages.count_tokens(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": text}],
            )
            return response.input_tokens
        except Exception:
            return None


def analyze_context(messages: list) -> dict:
    """
    分析上下文，返回详细的 token 分布。
    """
    estimator = TokenEstimator()
    result = {
        'total_tokens': 0,
        'user_tokens': 0,
        'assistant_tokens': 0,
        'tool_tokens': 0,
        'message_count': len(messages),
    }

    for msg in messages:
        tokens = estimator.estimate_message(msg)
        result['total_tokens'] += tokens

        role = msg.get('role', '')
        if role == 'user':
            result['user_tokens'] += tokens
        elif role == 'assistant':
            result['assistant_tokens'] += tokens
        elif role == 'tool':
            result['tool_tokens'] += tokens

    return result
