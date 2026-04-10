from __future__ import annotations

"""
安全扫描 Hook

在工具调用前检查命令安全性，参考 Claude Code 的
toolPermission/ 和 policyLimits/ 模块。
"""

import logging
import re

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

# 危险命令模式
DANGEROUS_PATTERNS = [
    (r"\brm\s+(-rf?|--no-preserve)\s+/", "禁止删除根目录"),
    (r"\bchmod\s+[0-7]*777\b", "禁止设置 777 权限"),
    (r"\bcurl.*\|\s*(bash|sh)\b", "禁止 curl 管道执行"),
    (r"\bwget.*\|\s*(bash|sh)\b", "禁止 wget 管道执行"),
    (r">\s*/etc/(passwd|shadow|sudoers)", "禁止修改系统关键文件"),
    (r"\bmkfs\b", "禁止格式化文件系统"),
    (r"\bdd\s+if=", "禁止 dd 写入"),
    (r":\(\)\{\s*:\|:&\s*\};:", "禁止 fork bomb"),
]

# 需要用户确认的命令
REQUIRES_CONFIRMATION = [
    (r"\bgit\s+push\s+--force", "强制推送"),
    (r"\bDROP\s+TABLE\b", "删除数据库表"),
    (r"\bDELETE\s+FROM\b", "删除数据库记录"),
    (r"\bterraform\s+destroy\b", "销毁基础设施"),
]


class SecurityScanner:
    """安全扫描器"""

    def __init__(
        self,
        dangerous_patterns: list[tuple[str, str]] | None = None,
        strict_mode: bool = False,
    ):
        self.patterns = dangerous_patterns or DANGEROUS_PATTERNS
        self.compiled = [
            (re.compile(p, re.IGNORECASE), msg) for p, msg in self.patterns
        ]
        self.strict_mode = strict_mode

    async def scan_tool_call(self, ctx: HookContext) -> None:
        """扫描工具调用"""
        tool_name = ctx.get("tool_name", "")
        tool_input = ctx.get("tool_input", {})

        # 只扫描 Bash 类工具
        if tool_name.lower() not in ("bash", "shell", "exec", "run_command"):
            return

        command = tool_input.get("command", "")
        if not command:
            return

        # 检查危险模式
        for pattern, message in self.compiled:
            if pattern.search(command):
                if self.strict_mode:
                    ctx.abort(f"安全拦截: {message}")
                    logger.warning(f"BLOCKED: {message} | cmd: {command[:100]}")
                else:
                    ctx.modify("security_warning", message)
                    logger.warning(f"WARNING: {message} | cmd: {command[:100]}")
                return

        # 检查需要确认的模式
        for pattern, message in REQUIRES_CONFIRMATION:
            if re.search(pattern, command, re.IGNORECASE):
                ctx.modify("requires_confirmation", True)
                ctx.modify("confirmation_reason", message)
                logger.info(f"需要确认: {message} | cmd: {command[:100]}")
                return

        logger.debug(f"Security scan passed: {command[:50]}...")


# 便捷函数
_scanner = SecurityScanner()

async def security_scan(ctx: HookContext) -> None:
    await _scanner.scan_tool_call(ctx)
