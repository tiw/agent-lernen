from __future__ import annotations

"""
持续学习 Hook

从 Agent 的交互中提取经验教训，持续改进。
参考 Claude Code 的 extractMemories/ 和 teamMemorySync/ 服务。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_DIR = Path.home() / ".my_agent" / "memory"


class ContinuousLearner:
    """持续学习管理器"""

    def __init__(self, memory_dir: str | Path | None = None):
        self.memory_dir = Path(memory_dir or DEFAULT_MEMORY_DIR)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lessons_file = self.memory_dir / "lessons.json"
        self.lessons = self._load_lessons()

    def _load_lessons(self) -> list[dict]:
        if self.lessons_file.exists():
            try:
                with open(self.lessons_file) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_lessons(self) -> None:
        with open(self.lessons_file, "w") as f:
            json.dump(self.lessons, f, indent=2, ensure_ascii=False)

    def add_lesson(
        self,
        category: str,
        lesson: str,
        context: str = "",
        confidence: float = 0.5,
    ) -> None:
        """添加一条经验教训"""
        self.lessons.append({
            "category": category,
            "lesson": lesson,
            "context": context,
            "confidence": confidence,
            "created_at": datetime.now().isoformat(),
        })
        # 只保留最近 500 条
        if len(self.lessons) > 500:
            self.lessons = self.lessons[-500:]
        self._save_lessons()

    async def on_turn_end(self, ctx: HookContext) -> None:
        """一轮对话结束后，分析是否需要学习"""
        tool_calls = ctx.get("tool_calls", [])
        errors = ctx.get("errors", [])
        user_feedback = ctx.get("user_feedback", "")

        # 从错误中学习
        for error in errors:
            self.add_lesson(
                category="error_recovery",
                lesson=f"遇到错误: {error.get('message', 'unknown')}",
                context=json.dumps(error, ensure_ascii=False)[:200],
                confidence=0.7,
            )

        # 从用户反馈中学习
        if user_feedback:
            self.add_lesson(
                category="user_preference",
                lesson=user_feedback,
                confidence=0.9,
            )

        # 从成功的工具调用中学习
        for tc in tool_calls:
            if tc.get("success") and tc.get("tool_name") == "bash":
                cmd = tc.get("command", "")
                if len(cmd) > 20:  # 只记录有意义的命令
                    self.add_lesson(
                        category="tool_usage",
                        lesson=f"成功执行: {cmd[:100]}",
                        confidence=0.5,
                    )

    def get_lessons(self, category: str | None = None) -> list[dict]:
        """获取经验教训"""
        if category:
            return [l for l in self.lessons if l["category"] == category]
        return self.lessons


# 便捷函数
_learner = ContinuousLearner()

async def continuous_learn(ctx: HookContext) -> None:
    await _learner.on_turn_end(ctx)
