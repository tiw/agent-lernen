"""
hooks/builtin/continuous_learn.py —— 持续学习 Hook
在每轮对话结束时记录学习点
参考 Claude Code 的学习和记忆机制
从零手写 AI Agent 课程 · 第 11 章
"""

import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from hooks.event_bus import HookContext, HookEvent
else:
    from ..event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

# 默认学习记录存储路径
DEFAULT_LEARNING_DIR = Path.home() / ".my_agent" / "learning"


class ContinuousLearner:
    """持续学习管理器"""

    def __init__(self, storage_dir=None):
        if storage_dir is None:
            storage_dir = DEFAULT_LEARNING_DIR
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._learning_log = []

    def _log_file(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.storage_dir / f"learning_{today}.jsonl"

    async def on_turn_end(self, ctx: HookContext) -> None:
        """每轮对话结束时记录学习点"""
        user_input = ctx.get("input", "")
        response = ctx.get("response", "")
        tool_calls = ctx.get("tool_calls", [])

        # 简单学习点提取：记录成功的工具调用
        if tool_calls:
            learning_entry = {
                "timestamp": datetime.now().isoformat(),
                "session_id": ctx.session_id,
                "turn_id": ctx.turn_id,
                "user_input": user_input[:200],
                "tool_calls": [
                    {"name": tc.get("name"), "input": tc.get("input")}
                    for tc in tool_calls
                ],
                "response_length": len(response),
            }
            self._learning_log.append(learning_entry)

            # 每 10 条记录写入一次文件
            if len(self._learning_log) >= 10:
                self._flush_to_file()

    def _flush_to_file(self) -> None:
        """将学习记录写入文件"""
        if not self._learning_log:
            return

        log_file = self._log_file()
        with open(log_file, "a") as f:
            for entry in self._learning_log:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"Learning log flushed: {len(self._learning_log)} entries -> {log_file}")
        self._learning_log.clear()

    def flush(self) -> None:
        """强制刷新学习记录"""
        self._flush_to_file()

    def get_stats(self) -> dict:
        """获取学习统计"""
        return {
            "pending_entries": len(self._learning_log),
            "storage_dir": str(self.storage_dir),
            "log_file": str(self._log_file()),
        }


# 便捷函数
_learner = ContinuousLearner()

async def continuous_learn(ctx: HookContext) -> None:
    await _learner.on_turn_end(ctx)


# === 测试 ===
if __name__ == "__main__":
    import asyncio
    async def test_continuous_learn():
        print("=== 持续学习 Hook 测试 ===\n")

        import sys
        import os
        import tempfile

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from hooks.event_bus import EventBus, HookContext, HookEvent

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = ContinuousLearner(storage_dir=tmpdir)

            # 测试 1: 记录学习点
            print("测试 1: 记录学习点")
            for i in range(3):
                ctx = HookContext(
                    event=HookEvent.TURN_END,
                    data={
                        "input": f"Query {i}",
                        "response": f"Response {i}",
                        "tool_calls": [{"name": "bash", "input": {"command": f"cmd{i}"}}],
                    },
                    session_id="test-session",
                    turn_id=f"turn-{i}",
                )
                await learner.on_turn_end(ctx)
            print(f"  待写入记录：{len(learner._learning_log)}\n")

            # 测试 2: 刷新到文件
            print("测试 2: 刷新到文件")
            learner.flush()
            print(f"  待写入记录：{len(learner._learning_log)}\n")

            # 测试 3: 获取统计
            print("测试 3: 获取统计")
            stats = learner.get_stats()
            print(f"  存储目录：{stats['storage_dir']}")
            print(f"  日志文件：{stats['log_file']}\n")

        print("✅ 所有测试完成！")

    asyncio.run(test_continuous_learn())
