from __future__ import annotations

"""
审计日志 —— 记录所有安全相关事件

参考 Claude Code 的 permissionLogging.ts 和 analytics/
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """审计事件"""
    timestamp: str
    event_type: str
    decision: str
    details: dict[str, Any]
    session_id: str = ""

    @classmethod
    def create(
        cls,
        event_type: str,
        decision: str,
        details: dict[str, Any],
        session_id: str = "",
    ) -> "AuditEvent":
        return cls(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            decision=decision,
            details=details,
            session_id=session_id,
        )


class Auditor:
    """审计日志管理器"""

    def __init__(self, log_dir: str | Path | None = None):
        self.log_dir = Path(log_dir or Path.home() / ".my_agent" / "audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[AuditEvent] = []

    def log(self, event: AuditEvent) -> None:
        """记录审计事件"""
        self._events.append(event)
        logger.info(
            f"AUDIT [{event.decision}] {event.event_type}: "
            f"{json.dumps(event.details, ensure_ascii=False)[:200]}"
        )

    def log_command_check(
        self,
        command: str,
        decision: str,
        reason: str,
        session_id: str = "",
    ) -> None:
        """记录命令检查事件"""
        self.log(AuditEvent.create(
            event_type="command_check",
            decision=decision,
            details={"command": command[:200], "reason": reason},
            session_id=session_id,
        ))

    def log_file_access(
        self,
        path: str,
        action: str,
        decision: str,
        session_id: str = "",
    ) -> None:
        """记录文件访问事件"""
        self.log(AuditEvent.create(
            event_type="file_access",
            decision=decision,
            details={"path": path, "action": action},
            session_id=session_id,
        ))

    def log_sensitive_data(
        self,
        count: int,
        types: list[str],
        session_id: str = "",
    ) -> None:
        """记录敏感信息过滤事件"""
        self.log(AuditEvent.create(
            event_type="sensitive_data_filtered",
            decision="redacted",
            details={"count": count, "types": types},
            session_id=session_id,
        ))

    def save(self) -> Path:
        """保存审计日志到文件"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit-{today}.jsonl"

        with open(log_file, "a") as f:
            for event in self._events:
                f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

        self._events.clear()
        return log_file

    def get_recent(self, n: int = 50) -> list[AuditEvent]:
        """获取最近的审计事件"""
        return self._events[-n:]
