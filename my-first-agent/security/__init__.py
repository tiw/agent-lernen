"""
Security module for AI Agent

Provides comprehensive security features:
- Command whitelist and classification
- File system sandbox
- Sensitive data filtering
- Security policy engine
- Audit logging
"""

from security.whitelist import CommandWhitelist, SafetyLevel, CommandRule
from security.sandbox import FileSandbox, SandboxConfig, PathViolationError
from security.filter import SensitiveDataFilter, FilterRule
from security.policy import SecurityPolicy, Decision, PermissionResult
from security.auditor import Auditor, AuditEvent

__all__ = [
    # Whitelist
    "CommandWhitelist",
    "SafetyLevel",
    "CommandRule",
    # Sandbox
    "FileSandbox",
    "SandboxConfig",
    "PathViolationError",
    # Filter
    "SensitiveDataFilter",
    "FilterRule",
    # Policy
    "SecurityPolicy",
    "Decision",
    "PermissionResult",
    # Auditor
    "Auditor",
    "AuditEvent",
]
