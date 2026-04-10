"""
文件系统工具集 —— 让 AI Agent 安全地读写和编辑文件。
参考 Claude Code 的 Read / Write / Edit 工具设计。
"""

import os
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 安全沙箱
# ============================================================

class SandboxViolationError(Exception):
    """路径超出沙箱范围"""
    pass


class FileSandbox:
    """
    安全沙箱：限制文件操作只能在允许的目录内进行。
    类似 Claude Code 的权限检查机制。
    """

    def __init__(self, allowed_dirs: Optional[list] = None):
        """
        Args:
            allowed_dirs: 允许访问的目录列表。如果为空，则不限制。
        """
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]

    def validate_path(self, path) -> Path:
        """
        校验路径是否在沙箱范围内。
        """
        resolved = Path(path).resolve()

        # 阻止设备文件
        blocked_devices = {
            '/dev/zero', '/dev/random', '/dev/urandom',
            '/dev/full', '/dev/stdin', '/dev/tty',
        }
        if str(resolved) in blocked_devices:
            raise SandboxViolationError(
                f"Cannot access device file: {resolved}"
            )

        # 如果没设置沙箱，不限制
        if not self.allowed_dirs:
            return resolved

        # 检查是否在允许的目录树内
        for allowed in self.allowed_dirs:
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue

        raise SandboxViolationError(
            f"Path '{resolved}' is outside allowed directories: "
            f"{[str(d) for d in self.allowed_dirs]}"
        )


# ============================================================
# 工具结果
# ============================================================

@dataclass
class FileReadResult:
    file_path: str
    content: str
    num_lines: int
    start_line: int
    total_lines: int
    encoding: str = 'utf-8'

    def to_display(self) -> str:
        """格式化为带行号的显示内容（类似 cat -n）"""
        lines = self.content.split('\n')
        numbered = []
        for i, line in enumerate(lines, start=self.start_line):
            numbered.append(f"{i:>6}\t{line}")
        return '\n'.join(numbered)


@dataclass
class FileWriteResult:
    file_path: str
    operation: str  # 'create' or 'update'
    bytes_written: int
    diff: str = ''


@dataclass
class FileEditResult:
    file_path: str
    old_string: str
    new_string: str
    success: bool
    message: str
    diff: str = ''
    occurrences: int = 0


# ============================================================
# FileReadTool
# ============================================================

class FileReadTool:
    """
    读取文件内容。
    """

    def __init__(
        self,
        sandbox: Optional[FileSandbox] = None,
        max_lines: int = 2000,
        max_tokens: int = 25000,
    ):
        self.sandbox = sandbox or FileSandbox()
        self.max_lines = max_lines
        self.max_tokens = max_tokens

    def call(
        self,
        file_path: str,
        offset: int = 1,
        limit: Optional[int] = None,
        encoding: str = 'utf-8',
    ) -> FileReadResult:
        """读取文件内容。"""
        # 1. 安全校验
        resolved = self.sandbox.validate_path(file_path)

        if not resolved.exists():
            raise FileNotFoundError(
                f"File not found: {resolved}\n"
                f"Current working directory: {os.getcwd()}"
            )

        if not resolved.is_file():
            raise IsADirectoryError(
                f"Path is a directory, not a file: {resolved}"
            )

        # 2. 读取全部行
        with open(resolved, 'r', encoding=encoding) as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        # 3. 计算读取范围
        start = max(0, offset - 1)
        end = start + (limit or self.max_lines)
        end = min(end, total_lines)

        selected_lines = all_lines[start:end]
        content = ''.join(selected_lines)

        # 4. Token 估算检查
        estimated_tokens = len(content) // 4
        if estimated_tokens > self.max_tokens:
            raise ValueError(
                f"File content ({estimated_tokens} estimated tokens) exceeds "
                f"maximum ({self.max_tokens} tokens). "
                f"Use offset and limit to read a smaller portion."
            )

        return FileReadResult(
            file_path=str(resolved),
            content=content,
            num_lines=end - start,
            start_line=offset,
            total_lines=total_lines,
            encoding=encoding,
        )


# ============================================================
# FileWriteTool
# ============================================================

class FileWriteTool:
    """
    写入文件（创建或覆盖）。
    """

    def __init__(self, sandbox: Optional[FileSandbox] = None):
        self.sandbox = sandbox or FileSandbox()

    def call(
        self,
        file_path: str,
        content: str,
        encoding: str = 'utf-8',
    ) -> FileWriteResult:
        """写入文件内容。"""
        resolved = self.sandbox.validate_path(file_path)

        # 检测是创建还是更新
        operation = 'update' if resolved.exists() else 'create'
        old_content = ''
        if operation == 'update':
            with open(resolved, 'r', encoding=encoding) as f:
                old_content = f.read()

        # 自动创建父目录
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(resolved, 'w', encoding=encoding) as f:
            f.write(content)

        # 生成 diff
        diff = self._make_diff(old_content, content, str(resolved))

        return FileWriteResult(
            file_path=str(resolved),
            operation=operation,
            bytes_written=len(content.encode(encoding)),
            diff=diff,
        )

    @staticmethod
    def _make_diff(old: str, new: str, path: str) -> str:
        """生成 unified diff"""
        if not old:
            return f"New file created: {path}"

        diff_lines = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        return ''.join(diff_lines)


# ============================================================
# FileEditTool
# ============================================================

class FileEditTool:
    """
    精准编辑文件（SEARCH/REPLACE 模式）。
    """

    def __init__(self, sandbox: Optional[FileSandbox] = None):
        self.sandbox = sandbox or FileSandbox()

    def call(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        encoding: str = 'utf-8',
    ) -> FileEditResult:
        """在文件中执行精确的字符串替换。"""
        resolved = self.sandbox.validate_path(file_path)

        # 1. 无变化检查
        if old_string == new_string:
            return FileEditResult(
                file_path=str(resolved),
                old_string=old_string,
                new_string=new_string,
                success=False,
                message="No changes to make: old_string and new_string are identical.",
            )

        # 2. 读取文件
        if not resolved.exists():
            return FileEditResult(
                file_path=str(resolved),
                old_string=old_string,
                new_string=new_string,
                success=False,
                message=f"File does not exist: {resolved}",
            )

        with open(resolved, 'r', encoding=encoding) as f:
            content = f.read()

        # 3. 查找匹配
        occurrences = content.count(old_string)

        if occurrences == 0:
            return FileEditResult(
                file_path=str(resolved),
                old_string=old_string,
                new_string=new_string,
                success=False,
                message=(
                    f"String to replace not found in file.\n"
                    f"String: {old_string!r}\n\n"
                    f"Tip: Make sure the old_string matches exactly, "
                    f"including whitespace and line endings."
                ),
            )

        if occurrences > 1 and not replace_all:
            return FileEditResult(
                file_path=str(resolved),
                old_string=old_string,
                new_string=new_string,
                success=False,
                message=(
                    f"Found {occurrences} matches of the string to replace, "
                    f"but replace_all is False.\n"
                    f"To replace all occurrences, set replace_all=True.\n"
                    f"To replace only one, provide more context to make "
                    f"old_string unique.\n"
                    f"String: {old_string!r}"
                ),
            )

        # 4. 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # 5. 写回文件
        with open(resolved, 'w', encoding=encoding) as f:
            f.write(new_content)

        # 6. 生成 diff
        diff = self._make_diff(content, new_content, str(resolved))

        return FileEditResult(
            file_path=str(resolved),
            old_string=old_string,
            new_string=new_string,
            success=True,
            message=f"The file {resolved} has been updated successfully.",
            diff=diff,
            occurrences=occurrences,
        )

    @staticmethod
    def _make_diff(old: str, new: str, path: str) -> str:
        """生成 unified diff"""
        diff_lines = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        return ''.join(diff_lines)


# ============================================================
# 便捷工厂函数
# ============================================================

def create_file_tools(
    allowed_dirs: Optional[list] = None,
    max_lines: int = 2000,
    max_tokens: int = 25000,
) -> tuple:
    """
    创建一组文件工具，共享同一个沙箱配置。

    Returns:
        (read_tool, write_tool, edit_tool)
    """
    sandbox = FileSandbox(allowed_dirs)
    return (
        FileReadTool(sandbox=sandbox, max_lines=max_lines, max_tokens=max_tokens),
        FileWriteTool(sandbox=sandbox),
        FileEditTool(sandbox=sandbox),
    )
