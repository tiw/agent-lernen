"""
文件系统工具集 —— 让 AI Agent 安全地读写和编辑文件。
参考 Claude Code 的 Read / Write / Edit 工具设计。
从零手写 AI Agent 课程 · 第 3 章
"""

import os
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Union, List
import chardet


# ============================================================
# 工具函数
# ============================================================

def detect_encoding(file_path: Path, sample_size: int = 1024) -> str:
    """
    自动检测文件编码
    
    Args:
        file_path: 文件路径
        sample_size: 采样字节数（默认 1KB）
        
    Returns:
        检测到的编码（默认 utf-8）
    """
    try:
        with open(file_path, 'rb') as f:
            raw = f.read(sample_size)
        result = chardet.detect(raw)
        encoding = result.get('encoding')
        confidence = result.get('confidence', 0)
        
        # 如果置信度低于 0.5，使用 utf-8 作为默认
        if encoding and confidence > 0.5:
            return encoding
        return 'utf-8'
    except Exception:
        return 'utf-8'


# ============================================================
# 编辑历史记录器（Undo 功能）
# ============================================================

class EditHistory:
    """
    编辑历史记录器 — 支持 Undo 操作
    
    用法：
        history = EditHistory()
        history.save_version(file_path, content)  # 保存版本
        history.undo(file_path)  # 撤销上一次编辑
    """
    
    def __init__(self, max_versions: int = 10):
        """
        Args:
            max_versions: 每个文件保留的最大版本数（默认 10）
        """
        self.history: dict[str, List[str]] = {}  # file_path → [content_versions]
        self.max_versions = max_versions
    
    def save_version(self, file_path: str, content: str) -> None:
        """保存文件版本"""
        if file_path not in self.history:
            self.history[file_path] = []
        
        self.history[file_path].append(content)
        
        # 限制版本数量
        if len(self.history[file_path]) > self.max_versions:
            self.history[file_path].pop(0)  # 移除最旧的版本
    
    def undo(self, file_path: str) -> Optional[str]:
        """
        撤销上一次编辑
        
        Returns:
            上一个版本的内容，如果没有可撤销的版本则返回 None
        """
        if file_path not in self.history or len(self.history[file_path]) <= 1:
            return None
        
        self.history[file_path].pop()  # 移除当前版本
        return self.history[file_path][-1]  # 返回上一个版本
    
    def get_versions(self, file_path: str) -> int:
        """获取文件的版本数量"""
        return len(self.history.get(file_path, []))
    
    def clear(self, file_path: Optional[str] = None) -> None:
        """清除历史记录"""
        if file_path:
            self.history.pop(file_path, None)
        else:
            self.history.clear()


# ============================================================
# 文件读取状态追踪（先读后写检查）
# ============================================================

class FileReadState:
    """
    追踪文件读取状态 — 实现"先读后写"检查
    
    用法：
        read_state = FileReadState()
        read_state.mark_as_read(file_path)  # 标记为已读
        read_state.check_can_write(file_path)  # 检查是否可以写入
    """
    
    def __init__(self):
        self.read_files: dict[str, float] = {}  # file_path → read_timestamp
    
    def mark_as_read(self, file_path: str) -> None:
        """标记文件为已读"""
        import time
        self.read_files[file_path] = time.time()
    
    def check_can_write(self, file_path: str) -> tuple[bool, str]:
        """
        检查文件是否可以写入
        
        Returns:
            (can_write, reason)
        """
        if file_path not in self.read_files:
            return False, "File has not been read yet. Read it first before writing."
        return True, "OK"
    
    def is_recently_read(self, file_path: str, max_age: float = 300) -> bool:
        """
        检查文件是否是最近读取的
        
        Args:
            file_path: 文件路径
            max_age: 最大年龄（秒），默认 5 分钟
        """
        import time
        if file_path not in self.read_files:
            return False
        return (time.time() - self.read_files[file_path]) < max_age
    
    def clear(self, file_path: Optional[str] = None) -> None:
        """清除读取状态"""
        if file_path:
            self.read_files.pop(file_path, None)
        else:
            self.read_files.clear()


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

    def __init__(self, allowed_dirs: Optional[list[str]] = None):
        """
        Args:
            allowed_dirs: 允许访问的目录列表。如果为空，则不限制。
        """
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]

    def validate_path(self, path: Union[str, Path]) -> Path:
        """
        校验路径是否在沙箱范围内。

        安全检查步骤：
        1. 解析为绝对路径（处理 ../ 等）
        2. 检查是否在允许的目录树内
        3. 检查是否为设备文件
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

    参考 Claude Code 的 FileReadTool：
    - 支持 offset / limit 分页读取
    - 自动检测编码
    - Token 限制（防止大文件撑爆上下文）
    - 带行号格式输出
    """

    name = "file_read"
    description = "读取文件内容。支持分页读取（offset/limit），自动检测编码，带行号格式输出。适用于查看配置文件、源代码、文档等。"

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
        encoding: Optional[str] = None,  # None 表示自动检测
        auto_detect_encoding: bool = True,
    ) -> FileReadResult:
        """
        读取文件内容。

        Args:
            file_path: 文件路径（绝对或相对）
            offset: 起始行号（1-indexed）
            limit: 最多读取的行数
            encoding: 文件编码（None 表示自动检测）
            auto_detect_encoding: 是否自动检测编码（默认 True）

        Returns:
            FileReadResult 包含文件内容和元信息
        """
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

        # 2. 自动检测编码
        detected_encoding = encoding
        if auto_detect_encoding and encoding is None:
            detected_encoding = detect_encoding(resolved)

        # 3. 读取全部行
        with open(resolved, 'r', encoding=detected_encoding) as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        # 3. 计算读取范围
        start = max(0, offset - 1)  # 转为 0-indexed
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

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要读取的文件路径（绝对或相对）",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "起始行号（1-indexed），默认 1",
                            "default": 1,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最多读取的行数，默认 2000",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "文件编码，默认 utf-8",
                            "default": "utf-8",
                        },
                    },
                    "required": ["file_path"],
                },
            }
        }


# ============================================================
# FileWriteTool
# ============================================================

class FileWriteTool:
    """
    写入文件（创建或覆盖）。

    参考 Claude Code 的 FileWriteTool：
    - 自动创建父目录
    - 检测是创建还是更新
    - 生成 diff 展示变更
    """

    name = "file_write"
    description = "写入文件内容（创建新文件或覆盖已有文件）。自动创建父目录，生成 diff 展示变更。适用于创建配置文件、代码文件、文档等。"

    def __init__(self, sandbox: Optional[FileSandbox] = None):
        self.sandbox = sandbox or FileSandbox()

    def call(
        self,
        file_path: str,
        content: str,
        encoding: str = 'utf-8',
    ) -> FileWriteResult:
        """
        写入文件内容。

        Args:
            file_path: 目标文件路径
            content: 要写入的内容
            encoding: 文件编码

        Returns:
            FileWriteResult 包含操作类型和 diff
        """
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

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "目标文件路径（绝对或相对）",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的文件内容",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "文件编码，默认 utf-8",
                            "default": "utf-8",
                        },
                    },
                    "required": ["file_path", "content"],
                },
            }
        }

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

    参考 Claude Code 的 FileEditTool：
    - old_string / new_string 精确匹配替换
    - replace_all 支持全局替换
    - 字符串未找到时提供友好错误信息
    - 生成 diff 展示变更
    - 支持 Undo 操作
    - 支持多编辑块（call_multi）
    """

    name = "file_edit"
    description = "精准编辑文件（SEARCH/REPLACE 模式）。使用 old_string/new_string 精确匹配替换，支持全局替换、Undo 操作。适用于修改代码、配置文件等。"

    def __init__(
        self,
        sandbox: Optional[FileSandbox] = None,
        edit_history: Optional[EditHistory] = None,
    ):
        self.sandbox = sandbox or FileSandbox()
        self.edit_history = edit_history or EditHistory()

    def call(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        encoding: str = 'utf-8',
    ) -> FileEditResult:
        """
        在文件中执行精确的字符串替换。

        Args:
            file_path: 目标文件路径
            old_string: 要替换的原文（必须唯一匹配）
            new_string: 替换后的新内容
            replace_all: 是否替换所有匹配项
            encoding: 文件编码

        Returns:
            FileEditResult 包含编辑结果
        """
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

        # 4. 保存当前版本到历史（用于 Undo）
        self.edit_history.save_version(str(resolved), content)

        # 5. 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # 6. 写回文件
        with open(resolved, 'w', encoding=encoding) as f:
            f.write(new_content)

        # 7. 生成 diff
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

    def undo(self, file_path: str) -> FileEditResult:
        """
        撤销上一次编辑
        
        Args:
            file_path: 文件路径
            
        Returns:
            FileEditResult 包含撤销结果
        """
        resolved = self.sandbox.validate_path(file_path)
        
        previous_content = self.edit_history.undo(str(resolved))
        
        if previous_content is None:
            return FileEditResult(
                file_path=str(resolved),
                old_string="",
                new_string="",
                success=False,
                message="No version to undo. The file has no edit history.",
            )
        
        # 写回上一个版本
        with open(resolved, 'w', encoding='utf-8') as f:
            f.write(previous_content)
        
        return FileEditResult(
            file_path=str(resolved),
            old_string="",
            new_string="",
            success=True,
            message=f"Undone last edit to {resolved}.",
            diff="Undo operation",
        )

    def call_multi(
        self,
        file_path: str,
        edits: List[dict],
        encoding: str = 'utf-8',
    ) -> List[FileEditResult]:
        """
        一次调用执行多个编辑块
        
        Args:
            file_path: 目标文件路径
            edits: 编辑块列表，每个包含 {old_string, new_string, replace_all}
            encoding: 文件编码
            
        Returns:
            FileEditResult 列表
        """
        results = []
        resolved = self.sandbox.validate_path(file_path)
        
        # 保存当前版本
        with open(resolved, 'r', encoding=encoding) as f:
            content = f.read()
        self.edit_history.save_version(str(resolved), content)
        
        for i, edit in enumerate(edits):
            # 在更新后的内容上依次应用编辑
            old_string = edit.get('old_string', '')
            new_string = edit.get('new_string', '')
            replace_all = edit.get('replace_all', False)
            
            occurrences = content.count(old_string)
            
            if occurrences == 0:
                results.append(FileEditResult(
                    file_path=str(resolved),
                    old_string=old_string,
                    new_string=new_string,
                    success=False,
                    message=f"Edit {i+1}: String not found: {old_string!r}",
                ))
                break  # 一个失败则停止
            
            if replace_all:
                content = content.replace(old_string, new_string)
            else:
                content = content.replace(old_string, new_string, 1)
            
            results.append(FileEditResult(
                file_path=str(resolved),
                old_string=old_string,
                new_string=new_string,
                success=True,
                message=f"Edit {i+1}: Applied successfully.",
                occurrences=occurrences,
            ))
        
        # 如果所有编辑都成功，写回文件
        if all(r.success for r in results):
            with open(resolved, 'w', encoding=encoding) as f:
                f.write(content)
        
        return results

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "目标文件路径（绝对或相对）",
                        },
                        "old_string": {
                            "type": "string",
                            "description": "要替换的原文（必须唯一匹配）",
                        },
                        "new_string": {
                            "type": "string",
                            "description": "替换后的新内容",
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "是否替换所有匹配项，默认 false",
                            "default": False,
                        },
                        "encoding": {
                            "type": "string",
                            "description": "文件编码，默认 utf-8",
                            "default": "utf-8",
                        },
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            }
        }

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
    allowed_dirs: Optional[list[str]] = None,
    max_lines: int = 2000,
    max_tokens: int = 25000,
) -> tuple[FileReadTool, FileWriteTool, FileEditTool]:
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
