"""
memory/tool_budget.py —— 第 1 层：工具结果预算
参考 Claude Code 的 ToolResultBudget 实现
从零手写 AI Agent 课程 · 第 5 章

核心功能：
1. 工具结果超过阈值时，写入磁盘 + 返回 2KB 预览
2. 磁盘持久化（tool-results/<session>/<id>.txt）
3. 状态冻结（pinCacheEdits）：一旦决定用预览，后续不变
4. COMPACTABLE_TOOLS 集合：只对大型工具结果做预算
"""

import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# 工具结果记录
# ============================================================

@dataclass
class ToolResultRecord:
    """工具结果记录"""
    tool_name: str
    tool_call_id: str
    full_result: str
    preview: str
    truncated: bool
    created_at: float = field(default_factory=time.time)
    disk_path: Optional[str] = None
    pinned: bool = False  # 状态冻结标志


# ============================================================
# 工具结果预算
# ============================================================

class ToolResultBudget:
    """
    工具结果预算管理器 — 第 1 层。

    核心职责：
    1. 工具执行结果过大时，截断为 2KB 预览
    2. 完整结果写入磁盘持久化
    3. 状态冻结：一旦截断，后续所有调用用相同预览
    4. 只针对 COMPACTABLE_TOOLS 集合中的工具
    """

    # 可压缩的工具集合
    COMPACTABLE_TOOLS = {
        "file_read", "file_edit", "bash", "python",
        "grep", "glob", "web_fetch", "web_search",
    }

    # 默认阈值
    DEFAULT_MAX_CHARS = 8000        # 工具结果最大字符数
    DEFAULT_PREVIEW_CHARS = 2048    # 预览最大字符数（2KB）

    def __init__(
        self,
        session_id: str = "default",
        storage_dir: str = "tool-results",
        max_chars: int = DEFAULT_MAX_CHARS,
        preview_chars: int = DEFAULT_PREVIEW_CHARS,
    ):
        self.session_id = session_id
        self.storage_dir = Path(storage_dir) / session_id
        self.max_chars = max_chars
        self.preview_chars = preview_chars

        # 记录历史
        self.history: dict[str, ToolResultRecord] = {}

        # 确保存储目录存在
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def process_result(
        self,
        tool_name: str,
        tool_call_id: str,
        result: str,
    ) -> ToolResultRecord:
        """
        处理工具结果。

        如果结果超过阈值：
        1. 完整结果写入磁盘
        2. 返回截断的预览
        3. 状态冻结（后续调用返回相同预览）

        如果结果在阈值内：
        1. 返回完整结果
        """
        # 状态冻结检查
        if tool_call_id in self.history:
            existing = self.history[tool_call_id]
            if existing.pinned:
                return existing

        is_compactable = tool_name in self.COMPACTABLE_TOOLS
        is_too_large = len(result) > self.max_chars
        should_truncate = is_compactable and is_too_large

        if should_truncate:
            # 完整结果写入磁盘
            disk_path = self._save_to_disk(tool_call_id, result)

            # 生成预览
            preview = self._make_preview(result)

            record = ToolResultRecord(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                full_result=preview,  # 压缩后 full_result 就是预览
                preview=preview,
                truncated=True,
                disk_path=disk_path,
                pinned=True,  # 状态冻结
            )
        else:
            record = ToolResultRecord(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                full_result=result,
                preview=result,
                truncated=False,
            )

        self.history[tool_call_id] = record
        return record

    def get_full_result(self, tool_call_id: str) -> Optional[str]:
        """从磁盘恢复完整结果"""
        record = self.history.get(tool_call_id)
        if not record:
            return None

        if record.disk_path:
            path = Path(record.disk_path)
            if path.exists():
                return path.read_text(encoding="utf-8")

        return record.full_result

    def get_stats(self) -> dict:
        """获取统计信息"""
        truncated = sum(1 for r in self.history.values() if r.truncated)
        pinned = sum(1 for r in self.history.values() if r.pinned)
        total_size = sum(len(r.full_result) for r in self.history.values())

        return {
            "total_results": len(self.history),
            "truncated": truncated,
            "pinned": pinned,
            "total_chars_in_memory": total_size,
        }

    def reset(self) -> None:
        """重置所有记录"""
        self.history.clear()

    # ============================================================
    # 内部方法
    # ============================================================

    def _save_to_disk(self, tool_call_id: str, result: str) -> str:
        """将完整结果写入磁盘"""
        path = self.storage_dir / f"{tool_call_id}.txt"
        path.write_text(result, encoding="utf-8")
        return str(path)

    def _make_preview(self, result: str) -> str:
        """生成预览（前 N 字符 + 提示）"""
        if len(result) <= self.preview_chars:
            return result

        preview = result[: self.preview_chars]
        # 找到最后一个换行，避免截断在行中间
        last_newline = preview.rfind("\n")
        if last_newline > self.preview_chars * 0.8:
            preview = preview[: last_newline]

        chars_saved = len(result) - len(preview)
        preview += f"\n\n[... 已截断 {chars_saved} 字符，使用 get_full_result 获取完整结果 ...]"
        return preview

    def _hash_content(self, content: str) -> str:
        """生成内容哈希（用于状态冻结检查）"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()


# === 测试 ===
if __name__ == "__main__":
    print("=== ToolResultBudget 测试 ===\n")

    budget = ToolResultBudget(session_id="test")

    # 测试 1: 小结果（不截断）
    print("测试 1: 小结果（不截断）")
    record = budget.process_result("bash", "call_001", "hello world")
    print(f"  截断：{record.truncated}")
    print(f"  冻结：{record.pinned}")
    print(f"  结果长度：{len(record.full_result)} 字符\n")

    # 测试 2: 大结果（截断）
    print("测试 2: 大结果（截断）")
    large_result = "line " * 2000  # 10000 字符
    record = budget.process_result("file_read", "call_002", large_result)
    print(f"  截断：{record.truncated}")
    print(f"  冻结：{record.pinned}")
    print(f"  预览长度：{len(record.preview)} 字符")
    print(f"  磁盘路径：{record.disk_path}\n")

    # 测试 3: 状态冻结（同一 ID 再次调用应返回相同结果）
    print("测试 3: 状态冻结")
    record2 = budget.process_result("file_read", "call_002", "different content")
    print(f"  内容是否相同：{record2.full_result == record.full_result}\n")

    # 测试 4: 恢复完整结果
    print("测试 4: 恢复完整结果")
    full = budget.get_full_result("call_002")
    print(f"  完整结果长度：{len(full) if full else 0} 字符\n")

    # 测试 5: 统计信息
    print("测试 5: 统计信息")
    stats = budget.get_stats()
    print(f"  总结果数：{stats['total_results']}")
    print(f"  截断数：{stats['truncated']}")
    print(f"  冻结数：{stats['pinned']}\n")

    print("✅ 所有测试完成！")
