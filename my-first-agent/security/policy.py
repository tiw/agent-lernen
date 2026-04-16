"""
安全策略 —— 综合权限决策引擎

整合白名单、沙箱、过滤器，提供统一的权限决策接口。
参考 Claude Code 的 PermissionContext.ts 和 policyLimits/
"""

import json
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
        permissions_file: str | None = None,
    ):
        self.whitelist = whitelist or CommandWhitelist()
        self.sandbox = sandbox or FileSandbox()
        self.filter = filter_ or SensitiveDataFilter()
        self.strict_mode = strict_mode
        self.permissions_file = permissions_file or str(Path.home() / ".my_agent" / "permissions.json")

        # 用户权限持久化
        self._permanent_allows: set[str] = set()
        self._permanent_denies: set[str] = set()

        # 加载已保存的权限
        self._load_permissions()

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
                reason=f"命令被禁止：{reason}",
                details={"level": level.value, "reason": reason},
            )

        if level == SafetyLevel.SAFE:
            return PermissionResult(
                Decision.ALLOW,
                reason=f"安全命令：{reason}",
                details={"level": level.value, "reason": reason},
            )

        if level == SafetyLevel.DANGEROUS:
            if self.strict_mode:
                return PermissionResult(
                    Decision.DENY,
                    reason=f"严格模式：{reason}",
                    details={"level": level.value, "reason": reason},
                )
            return PermissionResult(
                Decision.CONFIRM,
                reason=f"危险命令，需要确认：{reason}",
                details={"level": level.value, "reason": reason},
            )

        # CONFIRM 或默认策略
        return PermissionResult(
            Decision.CONFIRM,
            reason=f"需要确认：{reason}",
            details={"level": level.value, "reason": reason},
        )

    def check_file_read(self, path: str) -> PermissionResult:
        """检查文件读取权限"""
        try:
            resolved = self.sandbox.check_read(path)
            return PermissionResult(
                Decision.ALLOW,
                reason=f"文件可读：{resolved}",
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
                reason=f"文件可写：{resolved}",
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
        self._save_permissions()
        logger.info(f"Permanently allowed: {command[:50]}")

    def permanently_deny(self, command: str) -> None:
        """永久禁止某个命令"""
        self._permanent_denies.add(command.strip())
        self._save_permissions()
        logger.info(f"Permanently denied: {command[:50]}")

    def _save_permissions(self) -> None:
        """保存权限设置到文件"""
        data = {
            "permanent_allows": list(self._permanent_allows),
            "permanent_denies": list(self._permanent_denies),
        }
        # 确保目录存在
        Path(self.permissions_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.permissions_file, "w") as f:
            json.dump(data, f, indent=2)
        # 设置文件权限为 600
        try:
            Path(self.permissions_file).chmod(0o600)
        except Exception as e:
            logger.warning(f"Failed to set permissions file mode: {e}")

    def _load_permissions(self) -> None:
        """从文件加载权限设置"""
        p = Path(self.permissions_file)
        if not p.exists():
            return
        try:
            with open(p) as f:
                data = json.load(f)
            self._permanent_allows = set(data.get("permanent_allows", []))
            self._permanent_denies = set(data.get("permanent_denies", []))
            logger.info(f"Loaded {len(self._permanent_allows)} allows and {len(self._permanent_denies)} denies")
        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")

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
