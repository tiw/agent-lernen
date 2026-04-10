from __future__ import annotations

"""
会话持久化 Hook

在会话开始/结束时自动保存和恢复对话历史。
参考 Claude Code 的 sessionHistory.ts 和 history.ts。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

# 默认存储路径
DEFAULT_STORAGE_DIR = Path.home() / ".my_agent" / "sessions"


class SessionPersister:
    """会话持久化管理器"""

    def __init__(self, storage_dir: str | Path | None = None):
        self.storage_dir = Path(storage_dir or DEFAULT_STORAGE_DIR)
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
