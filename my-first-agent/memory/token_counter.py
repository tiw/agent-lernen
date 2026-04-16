"""
Token 计数与估算模块。
参考 Claude Code 的 tokenEstimation.ts 实现。
从零手写 AI Agent 课程 · 第 5 章
"""

import json
import math
from typing import Optional


class TokenEstimator:
    """
    Token 估算器。

    提供三种精度的 token 计数：
    1. 粗糙估算（基于字符数，4 chars/token）
    2. 类型感知估算（JSON 用 2 chars/token）
    3. API 精确计数（需要 Anthropic API Key）

    Claude Code 的策略：
    - 日常监控用粗糙估算
    - 压缩决策用 API 精确计数
    """

    DEFAULT_BYTES_PER_TOKEN = 4
    DENSE_BYTES_PER_TOKEN = 2
    IMAGE_TOKEN_ESTIMATE = 750
    DOCUMENT_TOKEN_ESTIMATE = 500

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def estimate(self, text: str) -> int:
        """粗糙估算：tokens ≈ len(text) / 4"""
        return math.ceil(len(text) / self.DEFAULT_BYTES_PER_TOKEN)

    def estimate_for_type(self, text: str, file_type: str = '') -> int:
        """类型感知的 token 估算"""
        ext = file_type.lower().lstrip('.')
        if ext in ('json', 'jsonl', 'jsonc'):
            return math.ceil(len(text) / self.DENSE_BYTES_PER_TOKEN)
        return self.estimate(text)

    def estimate_message(self, message: dict) -> int:
        """估算一条消息的 token 数"""
        content = message.get('content', '')
        if isinstance(content, str):
            return self.estimate(content)
        if isinstance(content, list):
            return sum(self._estimate_block(block) for block in content)
        return 0

    def estimate_messages(self, messages: list[dict]) -> int:
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
                name + json.dumps(inp, ensure_ascii=False), 'json'
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
            json.dumps(block, ensure_ascii=False), 'json'
        )

    def count_tokens_api(self, text: str) -> Optional[int]:
        """使用 Anthropic API 精确计数 token"""
        if not self.api_key:
            return None
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            response = client.beta.messages.count_tokens(
                model="claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": text}],
            )
            return response.input_tokens
        except Exception:
            return None

    @classmethod
    def analyze_context(cls, messages: list[dict]) -> dict:
        """分析上下文，返回详细的 token 分布"""
        estimator = cls()
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


# === 测试 ===
if __name__ == "__main__":
    estimator = TokenEstimator()

    print("=== Token 估算测试 ===\n")

    # 测试 1: 简单文本
    text = "Hello, World!"
    print(f"测试 1: '{text}'")
    print(f"  估算：{estimator.estimate(text)} tokens\n")

    # 测试 2: JSON
    json_text = '{"name": "test", "value": 123}'
    print(f"测试 2: JSON")
    print(f"  普通估算：{estimator.estimate(json_text)} tokens")
    print(f"  JSON 估算：{estimator.estimate_for_type(json_text, 'json')} tokens\n")

    # 测试 3: 消息分析
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you?"},
    ]
    print(f"测试 3: 消息分析")
    analysis = TokenEstimator.analyze_context(messages)
    print(f"  总 token: {analysis['total_tokens']}")
    print(f"  用户 token: {analysis['user_tokens']}")
    print(f"  助手 token: {analysis['assistant_tokens']}")
    print(f"  消息数：{analysis['message_count']}")
