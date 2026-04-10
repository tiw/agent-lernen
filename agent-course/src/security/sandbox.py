from __future__ import annotations

"""
文件系统沙箱 —— 限制 Agent 可访问的文件范围

参考 Claude Code 的文件访问控制和沙箱机制。
核心思想：Agent 只能访问允许的路径，禁止访问系统关键文件。
"""

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """沙箱配置"""
    # 允许访问的根目录列表
    allowed_roots: list[str]
    # 禁止访问的路径（即使在 allowed_roots 内）
    denied_paths: list[str]
    # 禁止的文件扩展名
    denied_extensions: list[str]
    # 是否允许符号链接
    allow_symlinks: bool
    # 最大文件大小（字节）
    max_file_size: int
    # 是否允许写入
    allow_write: bool


# 默认沙箱配置
DEFAULT_SANDBOX = SandboxConfig(
    allowed_roots=[str(Path.cwd())],  # 默认只允许当前工作目录
    denied_paths=[
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/root",
        "/var/log",
    ],
    denied_extensions=[
        ".pyc", ".pyo", ".so", ".dylib",  # 编译文件
        ".exe", ".dll", ".bat", ".cmd",   # 可执行文件
    ],
    allow_symlinks=False,
    max_file_size=10 * 1024 * 1024,  # 10MB
    allow_write=True,
)


class PathViolationError(Exception):
    """路径越界异常"""
    pass


class FileSandbox:
    """
    文件系统沙箱

    安全检查流程：
    1. 解析路径（处理 .., ~, 符号链接）
    2. 检查是否在允许的根目录内
    3. 检查是否在禁止路径列表中
    4. 检查文件扩展名
    5. 检查文件大小
    """

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or DEFAULT_SANDBOX
        self._allowed_roots = [
            Path(root).resolve() for root in self.config.allowed_roots
        ]
        self._denied_paths = [
            Path(p).resolve() for p in self.config.denied_paths
        ]

    def resolve_path(self, path: str | Path) -> Path:
        """
        安全地解析路径

        处理 .., ~, 符号链接，防止路径穿越攻击
        """
        p = Path(path).expanduser()

        # 检查符号链接
        if not self.config.allow_symlinks and p.is_symlink():
            raise PathViolationError(
                f"符号链接被禁止: {path}"
            )

        # 解析为绝对路径
        resolved = p.resolve()

        # 检查是否在允许的根目录内
        allowed = False
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                allowed = True
                break
            except ValueError:
                continue

        if not allowed:
            raise PathViolationError(
                f"路径越界: {path} -> {resolved}\n"
                f"允许的范围: {[str(r) for r in self._allowed_roots]}"
            )

        # 检查禁止路径
        for denied in self._denied_paths:
            try:
                resolved.relative_to(denied)
                raise PathViolationError(
                    f"禁止访问: {path} -> {resolved}"
                )
            except ValueError:
                continue

        return resolved

    def check_read(self, path: str | Path) -> Path:
        """检查文件是否可读"""
        resolved = self.resolve_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"文件不存在: {resolved}")

        if not resolved.is_file():
            raise PathViolationError(f"不是文件: {resolved}")

        # 检查扩展名
        if resolved.suffix.lower() in self.config.denied_extensions:
            raise PathViolationError(
                f"禁止访问该类型文件: {resolved.suffix}"
            )

        # 检查文件大小
        size = resolved.stat().st_size
        if size > self.config.max_file_size:
            raise PathViolationError(
                f"文件过大: {size} bytes > {self.config.max_file_size} bytes"
            )

        return resolved

    def check_write(self, path: str | Path) -> Path:
        """检查文件是否可写"""
        if not self.config.allow_write:
            raise PathViolationError("沙箱不允许写入")

        resolved = self.resolve_path(path)

        # 检查父目录是否存在
        parent = resolved.parent
        if not parent.exists():
            raise PathViolationError(f"父目录不存在: {parent}")

        return resolved

    def check_execute(self, path: str | Path) -> Path:
        """检查文件是否可执行"""
        resolved = self.check_read(path)

        # 禁止执行编译文件和脚本
        dangerous_exts = {".exe", ".sh", ".bash", ".zsh", ".fish"}
        if resolved.suffix.lower() in dangerous_exts:
            raise PathViolationError(
                f"禁止执行: {resolved.suffix} 文件"
            )

        return resolved

    def get_allowed_summary(self) -> str:
        """获取沙箱范围摘要"""
        lines = ["📦 文件系统沙箱范围："]
        for root in self._allowed_roots:
            lines.append(f"  ✅ {root}")
        if self._denied_paths:
            lines.append("  ❌ 禁止路径：")
            for p in self._denied_paths:
                lines.append(f"    {p}")
        lines.append(f"  📏 最大文件大小: {self.config.max_file_size / 1024 / 1024:.0f}MB")
        lines.append(f"  ✏️  写入权限: {'允许' if self.config.allow_write else '禁止'}")
        return "\n".join(lines)
