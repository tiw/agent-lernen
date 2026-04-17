"""
memory/micro_compact.py —— 第 2 层：微压缩
参考 Claude Code 的 MicroCompact 实现
从零手写 AI Agent 课程 · 第 5 章

核心功能：
1. 时间清理：基于时间的渐进式清理策略
2. 缓存编辑压缩：服务器端删除，本地不变
3. API 级上下文管理：在 API 调用前压缩上下文
4. 省略决策（OmissionDecision）：判断哪些消息可以省略
"""

import time
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 省略决策
# ============================================================

@dataclass
class OmissionDecision:
    """单条消息的压缩/省略决策"""
    message_index: int
    role: str
    omit: bool = False          # 是否完全省略
    truncate: bool = False      # 是否截断内容
    truncated_content: str = ""  # 截断后的内容
    reason: str = ""             # 决策原因


# ============================================================
# 微压缩
# ============================================================

class MicroCompact:
    """
    微压缩管理器 — 第 2 层。

    核心职责：
    1. 评估消息历史，决定哪些可以省略或截断
    2. 应用压缩决策，生成 API 可用的消息列表
    3. 基于时间和角色类型的智能压缩策略

    类比：日常保洁——定期清理不重要的对话片段，
    保持上下文整洁，但不过度干预。
    """

    # 工具结果超过此长度时考虑截断
    TOOL_RESULT_TRUNCATE_CHARS = 3000

    # 保留最近 N 条消息不做压缩
    RECENT_MESSAGES_KEEP = 6

    def __init__(self):
        # 缓存编辑压缩状态
        self.cache_edits: dict[str, bool] = {}
        self._last_cleanup_time = time.time()

    def evaluate(self, messages: list[dict]) -> list[OmissionDecision]:
        """
        评估消息列表，生成压缩决策。

        策略：
        1. 保留 system 消息
        2. 保留最近 N 条消息
        3. 长的工具结果标记为截断
        4. 中间的 assistant 纯确认消息标记为省略
        """
        decisions = []
        total = len(messages)

        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # System 消息永远保留
            if role == "system":
                decisions.append(OmissionDecision(
                    message_index=i, role=role, omit=False,
                    reason="system message preserved",
                ))
                continue

            # 最近消息保留
            if i >= total - self.RECENT_MESSAGES_KEEP:
                decisions.append(OmissionDecision(
                    message_index=i, role=role, omit=False,
                    reason="recent message preserved",
                ))
                continue

            # 长的工具结果截断
            if role == "tool" and len(content) > self.TOOL_RESULT_TRUNCATE_CHARS:
                truncated = content[: self.TOOL_RESULT_TRUNCATE_CHARS]
                truncated += f"\n[... 已截断 {len(content) - self.TOOL_RESULT_TRUNCATE_CHARS} 字符 ...]"
                decisions.append(OmissionDecision(
                    message_index=i, role=role, omit=False, truncate=True,
                    truncated_content=truncated,
                    reason="tool result truncated",
                ))
                continue

            # assistant 纯确认类消息省略
            if role == "assistant":
                # 如果是工具调用后的简短确认，可以省略
                # 检查上一条消息是否是 tool
                if i > 0 and messages[i - 1].get("role") == "tool":
                    # 没有 tool_calls 且内容很短
                    if "tool_calls" not in msg and len(content.strip()) < 100:
                        decisions.append(OmissionDecision(
                            message_index=i, role=role, omit=True,
                            reason="assistant short acknowledgment omitted",
                        ))
                        continue

            # 默认保留
            decisions.append(OmissionDecision(
                message_index=i, role=role, omit=False,
                reason="default preserve",
            ))

        return decisions

    def apply_omissions(
        self,
        messages: list[dict],
        decisions: list[OmissionDecision],
    ) -> tuple[list[dict], dict]:
        """
        应用压缩决策，生成 API 消息列表。

        Returns:
            (api_messages, context_management_stats)
        """
        api_messages = []
        omitted_count = 0
        truncated_count = 0

        for decision in decisions:
            if decision.omit:
                omitted_count += 1
                continue

            msg = messages[decision.message_index]
            if decision.truncate and decision.truncated_content:
                truncated_count += 1
                api_messages.append({
                    **msg,
                    "content": decision.truncated_content,
                })
            else:
                api_messages.append(msg)

        context_management = {
            "original_count": len(messages),
            "compressed_count": len(api_messages),
            "omitted_count": omitted_count,
            "truncated_count": truncated_count,
        }

        return api_messages, context_management

    def evaluate_and_apply(self, messages: list[dict]) -> tuple[list[dict], dict]:
        """一键评估并应用"""
        decisions = self.evaluate(messages)
        return self.apply_omissions(messages, decisions)

    # ============================================================
    # 缓存编辑压缩
    # ============================================================

    def pin_cache_edit(self, edit_id: str) -> None:
        """标记编辑为缓存冻结（服务器端删除，本地不变）"""
        self.cache_edits[edit_id] = True

    def is_cache_edit_pinned(self, edit_id: str) -> bool:
        """检查编辑是否冻结"""
        return self.cache_edits.get(edit_id, False)

    def clear_cache_edits(self) -> None:
        """清除所有缓存编辑状态"""
        self.cache_edits.clear()

    # ============================================================
    # 时间清理
    # ============================================================

    def should_cleanup(self, interval_seconds: int = 300) -> bool:
        """检查是否应该进行时间清理（默认 5 分钟）"""
        now = time.time()
        if now - self._last_cleanup_time >= interval_seconds:
            self._last_cleanup_time = now
            return True
        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "cache_edits_pinned": sum(1 for v in self.cache_edits.values() if v),
            "last_cleanup_ago": f"{time.time() - self._last_cleanup_time:.0f}s",
        }


# === 测试 ===
if __name__ == "__main__":
    print("=== MicroCompact 测试 ===\n")

    compact = MicroCompact()

    # 测试 1: 创建测试消息
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help you?"},
        {"role": "user", "content": "List all files"},
        {"role": "tool", "content": "file1.py\nfile2.py\n" * 200},  # 长结果
        {"role": "assistant", "content": "I found these files."},
        {"role": "user", "content": "What is the latest file?"},
    ]

    print("测试 1: 评估消息")
    decisions = compact.evaluate(messages)
    for d in decisions:
        status = "OMIT" if d.omit else ("TRUNCATE" if d.truncate else "KEEP")
        print(f"  [{d.role:12s}] {status} — {d.reason}")
    print()

    # 测试 2: 应用压缩
    print("测试 2: 应用压缩")
    api_messages, stats = compact.apply_omissions(messages, decisions)
    print(f"  原始消息数：{stats['original_count']}")
    print(f"  压缩后数量：{stats['compressed_count']}")
    print(f"  省略数：{stats['omitted_count']}")
    print(f"  截断数：{stats['truncated_count']}\n")

    # 测试 3: 缓存编辑
    print("测试 3: 缓存编辑")
    compact.pin_cache_edit("edit_001")
    print(f"  edit_001 冻结：{compact.is_cache_edit_pinned('edit_001')}")
    print(f"  edit_002 冻结：{compact.is_cache_edit_pinned('edit_002')}\n")

    # 测试 4: 统计
    print("测试 4: 统计")
    stats = compact.get_stats()
    print(f"  {stats}\n")

    print("✅ 所有测试完成！")
