"""
第 3 层：会话记忆（Session Memory）。
参考 Claude Code 的会话记忆系统。
从零手写 AI Agent 课程 · 第 5 章

核心功能：
1. 触发条件：Token 增长达到阈值 +（工具调用次数达标 或 上轮无工具调用）
2. 零 API 压缩策略：需要压缩时直接注入现成的会话记忆摘要
3. Prompt Cache 保存策略：14 个缓存断点，粘性锁存器管理
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 配置参数（参考 Claude Code 源码）
# ============================================================

@dataclass
class SessionMemoryConfig:
    """会话记忆配置"""
    minimum_message_tokens_to_init: int = 5000     # 消息总 token 达到 5000 才初始化
    minimum_tokens_between_update: int = 3000      # 两次更新之间至少增长 3000 tokens
    tool_calls_between_updates: int = 10           # 或者工具调用次数达到 10 次
    max_summary_tokens: int = 2000                 # 摘要最大 token 数
    cache_breakpoints: int = 14                    # 缓存断点数量


# ============================================================
# 缓存断点
# ============================================================

class CacheBreakpoint:
    """
    Prompt 缓存断点。

    Claude Code 维护 14 个缓存断点，精确控制缓存边界。
    每个断点标记 Prompt 中一个逻辑段的结束位置。
    """

    # 预定义的断点名称
    NAMES = [
        "system_prompt_end",          # 0: 系统提示词结束
        "tool_definitions_end",       # 1: 工具定义结束
        "skills_end",                 # 2: 技能注入结束
        "session_memory_summary",     # 3: 会话记忆摘要
        "compact_boundary",           # 4: 压缩边界标记
        "attachments_start",          # 5: 附件开始
        "attachments_end",            # 6: 附件结束
        "conversation_start",         # 7: 对话开始
        "user_message_1",             # 8: 第一条用户消息
        "assistant_message_1",        # 9: 第一条助手消息
        "mid_conversation",           # 10: 对话中段
        "recent_messages_start",      # 11: 最近消息开始
        "last_user_message",          # 12: 最后一条用户消息
        "end",                        # 13: 结束
    ]

    def __init__(self, index: int, name: str = ""):
        self.index = index
        self.name = name or (self.NAMES[index] if index < len(self.NAMES) else f"breakpoint_{index}")
        self._sticky_content_hash: Optional[str] = None  # 粘性锁存器

    def is_cache_hit(self, current_content_hash: str) -> bool:
        """
        检查缓存是否命中。

        使用粘性锁存器：即使内容变了，如果变化不大，仍然认为缓存命中。
        """
        if self._sticky_content_hash is None:
            self._sticky_content_hash = current_content_hash
            return True

        if self._sticky_content_hash == current_content_hash:
            return True

        # 粘性逻辑：如果内容变化小于阈值，仍然认为命中
        # 这里简化为直接比较，实际实现可以用编辑距离
        return False

    def update(self, content_hash: str) -> None:
        """更新锁存器"""
        self._sticky_content_hash = content_hash

    def reset(self) -> None:
        """重置锁存器"""
        self._sticky_content_hash = None


# ============================================================
# 会话记忆条目
# ============================================================

@dataclass
class SessionMemoryEntry:
    """会话记忆条目"""
    content: str
    token_count: int
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    category: str = "general"  # general, technical, decision, action


# ============================================================
# 会话记忆管理器
# ============================================================

class SessionMemory:
    """
    会话记忆管理器 — 第 3 层。

    核心职责：
    1. 持续监控对话，在对话过程中实时更新结构化笔记
    2. 触发条件：Token 增长 + 工具调用次数
    3. 零 API 压缩：需要压缩时直接注入现成摘要
    4. 管理 14 个缓存断点，用粘性锁存器保护缓存命中

    类比：实时笔记员——在会议过程中持续做笔记，
    需要总结时直接拿出已有的笔记，不用重新整理。
    """

    def __init__(
        self,
        config: Optional[SessionMemoryConfig] = None,
    ):
        self.config = config or SessionMemoryConfig()

        # 记忆条目
        self.entries: list[SessionMemoryEntry] = []

        # 追踪状态
        self._total_tokens_at_last_update = 0
        self._tool_calls_since_last_update = 0
        self._total_tool_calls = 0
        self._initialized = False

        # 缓存断点
        self.cache_breakpoints = [
            CacheBreakpoint(i, name)
            for i, name in enumerate(CacheBreakpoint.NAMES)
        ]

        # 当前摘要
        self._current_summary: str = ""

    def record_tool_call(self) -> None:
        """记录一次工具调用"""
        self._total_tool_calls += 1
        self._tool_calls_since_last_update += 1

    def should_update(self, current_total_tokens: int) -> bool:
        """
        检查是否应该更新会话记忆。

        触发条件（参考 Claude Code 源码）：
        1. 消息总 token 达到 minimum_message_tokens_to_init
        2. 且满足以下任一条件：
           a. Token 增长达到 minimum_tokens_between_update
           b. 工具调用次数达到 tool_calls_between_updates
        """
        if not self._initialized:
            return current_total_tokens >= self.config.minimum_message_tokens_to_init

        token_growth = current_total_tokens - self._total_tokens_at_last_update

        return (
            token_growth >= self.config.minimum_tokens_between_update
            or self._tool_calls_since_last_update >= self.config.tool_calls_between_updates
        )

    def update(self, summary: str, current_total_tokens: int) -> None:
        """
        更新会话记忆。

        Args:
            summary: 新的会话摘要（由 LLM 生成或手动更新）
            current_total_tokens: 当前总 token 数
        """
        self._current_summary = summary
        self._total_tokens_at_last_update = current_total_tokens
        self._tool_calls_since_last_update = 0
        self._initialized = True

        entry = SessionMemoryEntry(
            content=summary,
            token_count=self._estimate_tokens(summary),
            category="general",
        )
        self.entries.append(entry)

        # 更新缓存断点（会话记忆摘要断点）
        summary_bp = self.cache_breakpoints[3]  # session_memory_summary
        summary_bp.update(self._hash_content(summary))

    def get_injection_prompt(self) -> str:
        """
        获取注入提示词。

        当需要压缩时，直接返回现成的会话记忆摘要，
        不需要额外调用 LLM（零 API 策略）。
        """
        if not self._current_summary:
            return ""

        return (
            f"[Session Memory — Auto-generated summary]\n"
            f"{self._current_summary}\n"
            f"[End of Session Memory]\n"
        )

    def get_cache_status(self) -> dict:
        """获取缓存断点状态"""
        return {
            'breakpoints': [
                {'index': bp.index, 'name': bp.name, 'has_sticky': bp._sticky_content_hash is not None}
                for bp in self.cache_breakpoints
            ],
            'initialized': self._initialized,
            'total_entries': len(self.entries),
        }

    def reset(self) -> None:
        """重置会话记忆"""
        self.entries.clear()
        self._current_summary = ""
        self._total_tokens_at_last_update = 0
        self._tool_calls_since_last_update = 0
        self._total_tool_calls = 0
        self._initialized = False

        for bp in self.cache_breakpoints:
            bp.reset()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'initialized': self._initialized,
            'total_entries': len(self.entries),
            'total_tool_calls': self._total_tool_calls,
            'tokens_at_last_update': self._total_tokens_at_last_update,
            'tool_calls_since_last_update': self._tool_calls_since_last_update,
            'summary_length': len(self._current_summary),
            'cache_breakpoints': sum(1 for bp in self.cache_breakpoints if bp._sticky_content_hash is not None),
        }

    # ============================================================
    # 内部方法
    # ============================================================

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数"""
        # 简单估算：4 chars/token
        return len(text) // 4

    def _hash_content(self, content: str) -> str:
        """生成内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()


# ============================================================
# 短期记忆管理器（整合层）
# ============================================================

class ShortTermMemory:
    """
    短期记忆管理器 — 整合第 1-3 层。

    将工具结果预算、微压缩、会话记忆整合在一起，
    提供统一的上下文管理接口。
    """

    def __init__(
        self,
        session_id: str = "default",
        max_context_tokens: int = 100000,  # 最大上下文 token 数
    ):
        # 延迟导入，避免循环依赖
        import sys
        if __name__ == "__main__":
            sys.path.insert(0, '..')
        from tool_budget import ToolResultBudget
        from micro_compact import MicroCompact

        self.session_id = session_id
        self.max_context_tokens = max_context_tokens

        # 第 1 层：工具结果预算
        self.tool_budget = ToolResultBudget(session_id=session_id)

        # 第 2 层：微压缩
        self.micro_compact = MicroCompact()

        # 第 3 层：会话记忆
        self.session_memory = SessionMemory()

        # 消息历史
        self.messages: list[dict] = []

    def add_message(self, message: dict) -> None:
        """添加消息到历史"""
        self.messages.append(message)

        # 如果是工具调用，记录
        if message.get('role') == 'tool':
            self.session_memory.record_tool_call()

    def process_tool_result(
        self,
        tool_name: str,
        tool_call_id: str,
        result: str,
    ) -> str:
        """
        处理工具结果（第 1 层）。

        Returns:
            处理后的结果（可能是预览）
        """
        record = self.tool_budget.process_result(tool_name, tool_call_id, result)
        return record.full_result

    def should_compress(self) -> bool:
        """检查是否需要压缩"""
        # 延迟导入
        import sys
        if __name__ == "__main__":
            sys.path.insert(0, '..')
        from token_counter import TokenEstimator

        estimator = TokenEstimator()
        total_tokens = estimator.estimate_messages(self.messages)

        # 检查是否超过最大上下文
        if total_tokens > self.max_context_tokens:
            return True

        # 检查会话记忆是否需要更新
        if self.session_memory.should_update(total_tokens):
            return True

        return False

    def compress(self) -> dict:
        """
        执行压缩。

        Returns:
            压缩结果和 API 请求参数
        """
        # 第 2 层：微压缩决策
        decisions = self.micro_compact.evaluate(self.messages)

        # 应用微压缩
        api_messages, context_management = self.micro_compact.apply_omissions(
            self.messages, decisions
        )

        # 第 3 层：注入会话记忆
        injection = self.session_memory.get_injection_prompt()

        return {
            'messages': api_messages,
            'context_management': context_management,
            'session_memory_injection': injection,
            'decisions': decisions,
        }

    def get_stats(self) -> dict:
        """获取完整统计"""
        from .token_counter import TokenEstimator

        estimator = TokenEstimator()
        total_tokens = estimator.estimate_messages(self.messages)

        return {
            'total_tokens': total_tokens,
            'max_context_tokens': self.max_context_tokens,
            'message_count': len(self.messages),
            'tool_budget': self.tool_budget.get_stats(),
            'session_memory': self.session_memory.get_stats(),
            'should_compress': self.should_compress(),
        }


# === 测试 ===
if __name__ == "__main__":
    print("=== SessionMemory 测试 ===\n")

    # 测试 1: 创建会话记忆
    memory = SessionMemory()
    print("测试 1: 创建会话记忆")
    print(f"  已初始化：{memory._initialized}")
    print(f"  触发阈值：{memory.config.minimum_message_tokens_to_init} tokens\n")

    # 测试 2: 记录工具调用
    print("测试 2: 记录工具调用")
    for i in range(5):
        memory.record_tool_call()
    print(f"  总工具调用：{memory._total_tool_calls}")
    print(f"  上次更新后调用：{memory._tool_calls_since_last_update}\n")

    # 测试 3: 检查是否应该更新
    print("测试 3: 检查更新条件")
    should_update = memory.should_update(6000)
    print(f"  6000 tokens 时应该更新：{should_update}\n")

    # 测试 4: 更新会话记忆
    print("测试 4: 更新会话记忆")
    summary = "用户正在学习第五章：记忆系统。已理解七层架构，正在实现短期记忆。"
    memory.update(summary, 6000)
    print(f"  已初始化：{memory._initialized}")
    print(f"  摘要长度：{len(summary)} 字符")
    print(f"  注入提示：\n{memory.get_injection_prompt()}\n")

    # 测试 5: 缓存断点状态
    print("测试 5: 缓存断点状态")
    status = memory.get_cache_status()
    sticky_count = sum(1 for bp in status['breakpoints'] if bp['has_sticky'])
    print(f"  粘性锁存器数量：{sticky_count}\n")

    # 测试 6: ShortTermMemory 管理器（跳过，需要完整模块导入）
    print("测试 6: ShortTermMemory 管理器")
    print("  （需要完整模块环境，跳过详细测试）\n")

    print("✅ 所有测试完成！")
