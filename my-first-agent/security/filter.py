"""
敏感信息过滤器 —— 防止密钥、密码等敏感信息泄露

参考 Claude Code 的敏感信息保护机制。
在 Agent 输出前扫描，发现敏感信息时进行脱敏处理。
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterRule:
    """过滤规则"""
    name: str
    pattern: re.Pattern
    replacement: str
    enabled: bool = True


class SensitiveDataFilter:
    """
    敏感信息过滤器

    扫描 Agent 的输入和输出，对敏感信息进行脱敏：
    - API 密钥
    - 密码
    - Token
    - 邮箱
    - 手机号
    - IP 地址
    """

    # 预定义的敏感信息模式
    DEFAULT_RULES = [
        FilterRule(
            name="AWS Access Key",
            pattern=re.compile(r'AKIA[0-9A-Z]{16}'),
            replacement="[AWS_KEY_REDACTED]",
        ),
        FilterRule(
            name="API Key (通用)",
            pattern=re.compile(r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'),
            replacement=r"\1=[API_KEY_REDACTED]",
        ),
        FilterRule(
            name="Bearer Token",
            pattern=re.compile(r'Bearer\s+[a-zA-Z0-9\-._~+/]+=*'),
            replacement="Bearer [TOKEN_REDACTED]",
        ),
        FilterRule(
            name="私钥",
            pattern=re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----'),
            replacement="[PRIVATE_KEY_REDACTED]",
        ),
        FilterRule(
            name="密码赋值",
            pattern=re.compile(r'(?:password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']{4,}["\']?', re.IGNORECASE),
            replacement="password=[PASSWORD_REDACTED]",
        ),
        FilterRule(
            name="邮箱地址",
            pattern=re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
            replacement="[EMAIL_REDACTED]",
        ),
        FilterRule(
            name="手机号（中国）",
            pattern=re.compile(r'\b1[3-9]\d{9}\b'),
            replacement="[PHONE_REDACTED]",
        ),
        FilterRule(
            name="IP 地址",
            pattern=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            replacement="[IP_REDACTED]",
        ),
        FilterRule(
            name="GitHub Token",
            pattern=re.compile(r'ghp_[a-zA-Z0-9]{36}'),
            replacement="[GITHUB_TOKEN_REDACTED]",
        ),
        FilterRule(
            name="OpenAI Key",
            pattern=re.compile(r'sk-[a-zA-Z0-9]{20,}'),
            replacement="[OPENAI_KEY_REDACTED]",
        ),
        FilterRule(
            name="Anthropic Key",
            pattern=re.compile(r'sk-ant-[a-zA-Z0-9\-]{20,}'),
            replacement="[ANTHROPIC_KEY_REDACTED]",
        ),
    ]

    def __init__(self, rules: list[FilterRule] | None = None):
        self.rules = rules or self.DEFAULT_RULES[:]
        self._redacted_count = 0

    def add_rule(self, name: str, pattern: str, replacement: str) -> None:
        """添加自定义过滤规则"""
        rule = FilterRule(
            name=name,
            pattern=re.compile(pattern),
            replacement=replacement,
        )
        self.rules.append(rule)

    def filter_text(self, text: str) -> str:
        """
        过滤文本中的敏感信息

        返回脱敏后的文本
        """
        result = text
        for rule in self.rules:
            if not rule.enabled:
                continue
            matches = rule.pattern.findall(result)
            if matches:
                result = rule.pattern.sub(rule.replacement, result)
                self._redacted_count += len(matches)
                logger.debug(
                    f"Redacted {len(matches)} {rule.name}(s)"
                )
        return result

    def filter_dict(self, data: dict) -> dict:
        """过滤字典中的敏感信息（递归）"""
        result = {}
        for key, value in data.items():
            # 跳过敏感键
            sensitive_keys = {
                "password", "passwd", "pwd", "secret", "token",
                "api_key", "apikey", "access_key", "private_key",
                "authorization", "credential",
            }
            if key.lower() in sensitive_keys:
                result[key] = "[REDACTED]"
            elif isinstance(value, str):
                result[key] = self.filter_text(value)
            elif isinstance(value, dict):
                result[key] = self.filter_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.filter_dict(item) if isinstance(item, dict)
                    else self.filter_text(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    @property
    def redacted_count(self) -> int:
        return self._redacted_count

    def reset_counter(self) -> int:
        """重置并返回计数"""
        count = self._redacted_count
        self._redacted_count = 0
        return count
