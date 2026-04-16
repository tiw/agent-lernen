"""
hooks/builtin/security_scan.py —— 安全扫描 Hook
在工具调用前检查命令安全性
参考 Claude Code 的 toolPermission/ 和 policyLimits/ 模块
从零手写 AI Agent 课程 · 第 11 章
"""

import logging
import re
import sys
import os

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from hooks.event_bus import HookContext, HookEvent
else:
    from ..event_bus import HookContext, HookEvent

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
        dangerous_patterns=None,
        strict_mode: bool = False,
    ):
        self.patterns = dangerous_patterns or DANGEROUS_PATTERNS
        self.confirmation_patterns = REQUIRES_CONFIRMATION
        self.strict_mode = strict_mode

    def scan(self, command: str) -> tuple[bool, str]:
        """
        扫描命令安全性

        Returns:
            (is_safe, reason)
        """
        # 检查危险模式
        for pattern, reason in self.patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"危险命令：{reason}"

        # 检查需要确认的模式
        for pattern, reason in self.confirmation_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                if self.strict_mode:
                    return False, f"需要确认：{reason}"
                else:
                    logger.warning(f"命令需要确认：{reason} - {command[:50]}")

        return True, "安全"

    async def on_tool_call(self, ctx: HookContext) -> None:
        """工具调用前的安全扫描"""
        tool_name = ctx.get("tool_name", "")
        if tool_name != "bash":
            return

        command = ctx.get("command", "")
        is_safe, reason = self.scan(command)

        if not is_safe:
            ctx.abort(reason)
            logger.warning(f"安全扫描拦截：{reason} - {command[:50]}")
        else:
            logger.debug(f"安全扫描通过：{command[:50]}")


# 便捷函数
_scanner = SecurityScanner()

async def security_scan(ctx: HookContext) -> None:
    await _scanner.on_tool_call(ctx)


# === 测试 ===
if __name__ == "__main__":
    import asyncio
    async def test_security_scan():
        print("=== 安全扫描 Hook 测试 ===\n")

        import sys
        import os

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from hooks.event_bus import EventBus, HookContext, HookEvent

        scanner = SecurityScanner()

        # 测试 1: 安全命令
        print("测试 1: 安全命令")
        is_safe, reason = scanner.scan("ls -la")
        print(f"  ls -la: {reason}\n")

        # 测试 2: 危险命令
        print("测试 2: 危险命令")
        is_safe, reason = scanner.scan("rm -rf /")
        print(f"  rm -rf /: {reason}\n")

        # 测试 3: Hook 拦截
        print("测试 3: Hook 拦截")
        bus = EventBus()
        bus.on(HookEvent.TOOL_CALL, security_scan)

        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"tool_name": "bash", "command": "rm -rf /"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print(f"  是否拦截：{ctx.should_abort}")
        print(f"  拦截原因：{ctx.abort_reason}\n")

        # 测试 4: 安全命令通过
        print("测试 4: 安全命令通过")
        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"tool_name": "bash", "command": "ls -la"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print(f"  是否拦截：{ctx.should_abort}\n")

        print("✅ 所有测试完成！")

    asyncio.run(test_security_scan())
