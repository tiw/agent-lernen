from __future__ import annotations

"""
命令白名单 —— 定义允许执行的命令集合

参考 Claude Code 的 bashPermissions.ts 和 policyLimits/
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    """命令安全等级"""
    SAFE = "safe"              # 安全，自动执行
    CONFIRM = "confirm"        # 需要用户确认
    DANGEROUS = "dangerous"    # 危险，默认拒绝
    BANNED = "banned"          # 禁止，绝不执行


@dataclass
class CommandRule:
    """命令规则"""
    pattern: str              # 正则表达式
    level: SafetyLevel
    description: str = ""
    compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)

    def matches(self, command: str) -> bool:
        return bool(self.compiled.search(command))


class CommandWhitelist:
    """
    命令白名单管理器

    三级规则匹配：
    1. 白名单（明确允许的命令模式）
    2. 黑名单（明确禁止的命令模式）
    3. 默认策略（未匹配的规则）
    """

    # 安全命令模式
    SAFE_PATTERNS = [
        CommandRule(r"^\s*ls\b", SafetyLevel.SAFE, "列出目录"),
        CommandRule(r"^\s*cat\b", SafetyLevel.SAFE, "查看文件内容"),
        CommandRule(r"^\s*head\b", SafetyLevel.SAFE, "查看文件头部"),
        CommandRule(r"^\s*tail\b", SafetyLevel.SAFE, "查看文件尾部"),
        CommandRule(r"^\s*grep\b", SafetyLevel.SAFE, "搜索文本"),
        CommandRule(r"^\s*find\s+[^|;]*\s+-name\b", SafetyLevel.SAFE, "查找文件"),
        CommandRule(r"^\s*wc\b", SafetyLevel.SAFE, "统计行数/词数"),
        CommandRule(r"^\s*echo\b", SafetyLevel.SAFE, "输出文本"),
        CommandRule(r"^\s*pwd\b", SafetyLevel.SAFE, "显示当前目录"),
        CommandRule(r"^\s*date\b", SafetyLevel.SAFE, "显示日期"),
        CommandRule(r"^\s*git\s+(status|log|diff|show|branch)", SafetyLevel.SAFE, "Git 只读操作"),
        CommandRule(r"^\s*python\s+-m\s+py_compile\b", SafetyLevel.SAFE, "Python 语法检查"),
        CommandRule(r"^\s*python\s+.*\.py\b", SafetyLevel.CONFIRM, "运行 Python 脚本"),
    ]

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        CommandRule(r"\brm\s+(-rf?|--no-preserve)\s+/", SafetyLevel.BANNED, "禁止删除根目录"),
        CommandRule(r"\brm\s+(-rf?|--no-preserve)\s+\*", SafetyLevel.BANNED, "禁止删除当前目录所有文件"),
        CommandRule(r"\bchmod\s+[0-7]*777\b", SafetyLevel.DANGEROUS, "设置 777 权限"),
        CommandRule(r"\bcurl.*\|\s*(bash|sh|zsh)\b", SafetyLevel.BANNED, "curl 管道执行"),
        CommandRule(r"\bwget.*\|\s*(bash|sh|zsh)\b", SafetyLevel.BANNED, "wget 管道执行"),
        CommandRule(r">\s*/etc/(passwd|shadow|sudoers|hosts)", SafetyLevel.BANNED, "修改系统关键文件"),
        CommandRule(r"\bmkfs\b", SafetyLevel.BANNED, "格式化文件系统"),
        CommandRule(r"\bdd\s+if=", SafetyLevel.BANNED, "dd 写入"),
        CommandRule(r":\(\)\{\s*:\|:&\s*\};:", SafetyLevel.BANNED, "Fork bomb"),
        CommandRule(r"\bsudo\b", SafetyLevel.DANGEROUS, "提权操作"),
        CommandRule(r"\bDROP\s+TABLE\b", SafetyLevel.DANGEROUS, "删除数据库表"),
        CommandRule(r"\bterraform\s+destroy\b", SafetyLevel.DANGEROUS, "销毁基础设施"),
        CommandRule(r"\bgit\s+push\s+--force", SafetyLevel.CONFIRM, "强制推送"),
        CommandRule(r"\bDELETE\s+FROM\b", SafetyLevel.CONFIRM, "删除数据库记录"),
    ]

    def __init__(
        self,
        safe_patterns: list[CommandRule] | None = None,
        dangerous_patterns: list[CommandRule] | None = None,
        default_level: SafetyLevel = SafetyLevel.CONFIRM,
    ):
        self.safe_patterns = safe_patterns or self.SAFE_PATTERNS[:]
        self.dangerous_patterns = dangerous_patterns or self.DANGEROUS_PATTERNS[:]
        self.default_level = default_level

        # 用户自定义规则（运行时添加）
        self.custom_rules: list[CommandRule] = []

    def add_rule(self, pattern: str, level: SafetyLevel, description: str = "") -> None:
        """添加自定义规则"""
        rule = CommandRule(pattern=pattern, level=level, description=description)
        self.custom_rules.append(rule)
        logger.info(f"Added rule: {pattern} -> {level.value}")

    def classify(self, command: str) -> tuple[SafetyLevel, str]:
        """
        分类命令安全性

        返回 (安全等级, 匹配原因)
        """
        command = command.strip()

        # 1. 先检查自定义规则（优先级最高）
        for rule in self.custom_rules:
            if rule.matches(command):
                return rule.level, rule.description or "自定义规则"

        # 2. 检查禁止命令（最高优先级）
        for rule in self.dangerous_patterns:
            if rule.matches(command):
                return rule.level, rule.description

        # 3. 检查安全命令
        for rule in self.safe_patterns:
            if rule.matches(command):
                return rule.level, rule.description

        # 4. 默认策略
        return self.default_level, "未匹配任何规则，使用默认策略"

    def is_allowed(self, command: str) -> bool:
        """快速检查命令是否允许（无需确认）"""
        level, _ = self.classify(command)
        return level == SafetyLevel.SAFE

    def needs_confirmation(self, command: str) -> bool:
        """检查命令是否需要用户确认"""
        level, _ = self.classify(command)
        return level in (SafetyLevel.CONFIRM, SafetyLevel.DANGEROUS)

    def is_banned(self, command: str) -> bool:
        """检查命令是否被禁止"""
        level, _ = self.classify(command)
        return level == SafetyLevel.BANNED

    def get_report(self, command: str) -> dict:
        """获取命令的安全报告"""
        level, reason = self.classify(command)
        return {
            "command": command[:200],
            "level": level.value,
            "reason": reason,
            "allowed": level == SafetyLevel.SAFE,
            "needs_confirmation": level in (SafetyLevel.CONFIRM, SafetyLevel.DANGEROUS),
            "banned": level == SafetyLevel.BANNED,
        }
