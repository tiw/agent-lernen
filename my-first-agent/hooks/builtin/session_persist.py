"""
hooks/builtin/session_persist.py —— 会话持久化 Hook
在会话开始/结束时自动保存和恢复对话历史
参考 Claude Code 的 sessionHistory.ts 和 history.ts
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

# 默认存储路径
DEFAULT_STORAGE_DIR = Path.home() / ".my_agent" / "sessions"


class SessionPersister:
    """会话持久化管理器"""

    def __init__(self, storage_dir=None):
        if storage_dir is None:
            storage_dir = DEFAULT_STORAGE_DIR
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _session_file(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    async def on_session_start(self, ctx: HookContext) -> None:
        """会话开始时，尝试恢复历史"""
        session_id = ctx.get("session_id", "")
        if not session_id:
            return

        file_path = self._session_file(session_id)
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                ctx.modify("history", data.get("messages", []))
                logger.info(
                    f"Session restored: {session_id}, "
                    f"{len(data.get('messages', []))} messages"
                )
            except Exception as e:
                logger.error(f"Failed to restore session {session_id}: {e}")
        else:
            logger.info(f"New session: {session_id}")

    async def on_session_end(self, ctx: HookContext) -> None:
        """会话结束时，保存历史"""
        session_id = ctx.get("session_id", "")
        if not session_id:
            return

        history = ctx.get("history", [])
        file_path = self._session_file(session_id)

        data = {
            "session_id": session_id,
            "messages": history,
            "ended_at": datetime.now().isoformat(),
            "turn_count": ctx.get("turn_count", 0),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved: {session_id} -> {file_path}")


# 便捷函数（供注册表直接引用）
_persister = SessionPersister()

async def restore_session(ctx: HookContext) -> None:
    await _persister.on_session_start(ctx)

async def save_session(ctx: HookContext) -> None:
    await _persister.on_session_end(ctx)


# === 测试 ===
if __name__ == "__main__":
    import asyncio
    async def test_session_persist():
        print("=== 会话持久化 Hook 测试 ===\n")

        import sys
        import os
        import tempfile

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from hooks.event_bus import EventBus, HookContext, HookEvent

        # 使用临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            persister = SessionPersister(storage_dir=tmpdir)

            # 测试 1: 新会话
            print("测试 1: 新会话")
            ctx = HookContext(
                event=HookEvent.SESSION_START,
                data={},
                session_id="test-session-001",
            )
            await persister.on_session_start(ctx)
            print(f"  恢复的历史：{ctx.get('history', [])}\n")

            # 测试 2: 保存会话
            print("测试 2: 保存会话")
            ctx = HookContext(
                event=HookEvent.SESSION_END,
                data={
                    "history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi!"},
                    ],
                    "turn_count": 1,
                },
                session_id="test-session-001",
            )
            await persister.on_session_end(ctx)
            print(f"  会话已保存\n")

            # 测试 3: 恢复会话
            print("测试 3: 恢复会话")
            ctx = HookContext(
                event=HookEvent.SESSION_START,
                data={},
                session_id="test-session-001",
            )
            await persister.on_session_start(ctx)
            history = ctx.get("history", [])
            print(f"  恢复的历史：{len(history)} 条消息")
            for msg in history:
                print(f"    {msg['role']}: {msg['content']}\n")

        print("✅ 所有测试完成！")

    asyncio.run(test_session_persist())
