from __future__ import annotations

"""
安全策略 —— 综合权限决策引擎

整合白名单、沙箱、过滤器，提供统一的权限决策接口。
参考 Claude Code 的 PermissionContext.ts 和 policyLimits/
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from security.whitelist import CommandWhitelist, SafetyLevel
from security.sandbox import FileSandbox, PathViolationError
from security.filter import SensitiveDataFilter

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    """权限决策结果"""
    ALLOW = "allow"           # 允许执行
    DENY = "deny"             # 拒绝执行
    CONFIRM = "confirm"       # 需要用户确认
    MODIFY = "modify"         # 允许但需要修改


@dataclass
class PermissionResult:
    """权限决策结果"""
    decision: Decision
    reason: str = ""
    modified_command: str | None = None
    modified_data: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.decision in (Decision.ALLOW, Decision.MODIFY)

    @property
    def needs_confirmation(self) -> bool:
        return self.decision == Decision.CONFIRM


class SecurityPolicy:
    """
    安全策略引擎

    多层安全检查：
    1. 命令白名单检查
    2. 文件系统沙箱检查
    3. 敏感信息过滤
    4. 综合决策
    """

    def __init__(
        self,
        whitelist: CommandWhitelist | None = None,
        sandbox: FileSandbox | None = None,
        filter_: SensitiveDataFilter | None = None,
        strict_mode: bool = False,
    ):
        self.whitelist = whitelist or CommandWhitelist()
        self.sandbox = sandbox or FileSandbox()
        self.filter = filter_ or SensitiveDataFilter()
        self.strict_mode = strict_mode

        # 用户权限持久化
        self._permanent_allows: set[str] = set()
        self._permanent_denies: set[str] = set()

    def check_command(self, command: str) -> PermissionResult:
        """
        检查命令的权限

        返回 PermissionResult 包含决策和建议
        """
        # 1. 检查用户永久设置
        if command.strip() in self._permanent_denies:
            return PermissionResult(
                Decision.DENY,
                reason="用户已永久禁止此命令",
            )
        if command.strip() in self._permanent_allows:
            return PermissionResult(
                Decision.ALLOW,
                reason="用户已永久允许此命令",
            )

        # 2. 白名单分类
        level, reason = self.whitelist.classify(command)

        if level == SafetyLevel.BANNED:
            return PermissionResult(
                Decision.DENY,
                reason=f"命令被禁止: {reason}",
                details={"level": level.value, "reason": reason},
            )

        if level == SafetyLevel.SAFE:
            return PermissionResult(
                Decision.ALLOW,
                reason=f"安全命令: {reason}",
                details={"level": level.value, "reason": reason},
            )

        if level == SafetyLevel.DANGEROUS:
            if self.strict_mode:
                return PermissionResult(
                    Decision.DENY,
                    reason=f"严格模式: {reason}",
                    details={"level": level.value, "reason": reason},
                )
            return PermissionResult(
                Decision.CONFIRM,
                reason=f"危险命令，需要确认: {reason}",
                details={"level": level.value, "reason": reason},
            )

        # CONFIRM 或默认策略
        return PermissionResult(
            Decision.CONFIRM,
            reason=f"需要确认: {reason}",
            details={"level": level.value, "reason": reason},
        )

    def check_file_read(self, path: str) -> PermissionResult:
        """检查文件读取权限"""
        try:
            resolved = self.sandbox.check_read(path)
            return PermissionResult(
                Decision.ALLOW,
                reason=f"文件可读: {resolved}",
            )
        except PathViolationError as e:
            return PermissionResult(
                Decision.DENY,
                reason=str(e),
            )
        except FileNotFoundError as e:
            return PermissionResult(
                Decision.DENY,
                reason=str(e),
            )

    def check_file_write(self, path: str) -> PermissionResult:
        """检查文件写入权限"""
        try:
            resolved = self.sandbox.check_write(path)
            return PermissionResult(
                Decision.ALLOW,
                reason=f"文件可写: {resolved}",
            )
        except PathViolationError as e:
            return PermissionResult(
                Decision.DENY,
                reason=str(e),
            )

    def filter_output(self, text: str) -> str:
        """过滤输出中的敏感信息"""
        return self.filter.filter_text(text)

    def permanently_allow(self, command: str) -> None:
        """永久允许某个命令"""
        self._permanent_allows.add(command.strip())
        logger.info(f"Permanently allowed: {command[:50]}")

    def permanently_deny(self, command: str) -> None:
        """永久禁止某个命令"""
        self._permanent_denies.add(command.strip())
        logger.info(f"Permanently denied: {command[:50]}")

    def save_permissions(self, path: str | Path) -> None:
        """保存权限设置到文件"""
        import json
        data = {
            "permanent_allows": list(self._permanent_allows),
            "permanent_denies": list(self._permanent_denies),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_permissions(self, path: str | Path) -> None:
        """从文件加载权限设置"""
        import json
        p = Path(path)
        if not p.exists():
            return
        with open(p) as f:
            data = json.load(f)
        self._permanent_allows = set(data.get("permanent_allows", []))
        self._permanent_denies = set(data.get("permanent_denies", []))

    def get_security_report(self) -> dict:
        """获取安全状态报告"""
        return {
            "strict_mode": self.strict_mode,
            "permanent_allows": len(self._permanent_allows),
            "permanent_denies": len(self._permanent_denies),
            "redacted_count": self.filter.redacted_count,
            "sandbox_roots": [str(r) for r in self.sandbox._allowed_roots],
            "whitelist_rules": len(self.whitelist.safe_patterns),
            "blacklist_rules": len(self.whitelist.dangerous_patterns),
        }


class SecureAgent:
    """集成安全系统的 Agent"""

    def __init__(self):
        self.security = SecurityPolicy(strict_mode=False)
        self.session_id = "session-001"

    async def execute_command(self, command: str) -> dict:
        """
        安全地执行命令

        流程：
        1. 检查命令权限
        2. 如需确认，等待用户
        3. 执行命令
        4. 过滤输出中的敏感信息
        """
        # 1. 权限检查
        result = self.security.check_command(command)

        if result.decision == Decision.DENY:
            return {"error": result.reason}

        if result.decision == Decision.CONFIRM:
            # 这里应该等待用户确认
            confirmed = await self._ask_user_confirmation(
                command, result.reason
            )
            if not confirmed:
                return {"error": "用户拒绝了命令执行"}

        # 2. 执行命令（模拟）
        output = f"执行结果: {command}"

        # 3. 过滤输出
        safe_output = self.security.filter_output(output)

        return {"output": safe_output}

    async def _ask_user_confirmation(
        self, command: str, reason: str
    ) -> bool:
        """请求用户确认（模拟）"""
        print(f"\n⚠️  安全确认")
        print(f"   命令: {command}")
        print(f"   原因: {reason}")
        print(f"   是否继续？(y/n): ", end="")
        return True  # 模拟用户确认

    async def read_file(self, path: str) -> dict:
        """安全地读取文件"""
        result = self.security.check_file_read(path)
        if result.decision == Decision.DENY:
            return {"error": result.reason}
        return {"content": "文件内容（已脱敏）"}
