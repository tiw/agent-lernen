"""
搜索工具集 —— 在代码库中搜索内容和匹配文件。
参考 Claude Code 的 GrepTool / GlobTool 设计。
"""

import os
import re
import time
import fnmatch
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ============================================================
# 工具结果
# ============================================================

@dataclass
class GrepResult:
    """Grep 搜索结果"""
    mode: str  # 'content', 'files_with_matches', 'count'
    matches: list
    num_files: int
    num_matches: int
    content: str = ''
    applied_limit: Optional[int] = None
    applied_offset: Optional[int] = None

    def to_display(self) -> str:
        if self.content:
            return self.content
        if self.mode == 'files_with_matches':
            lines = [f"Found {self.num_files} file(s):"]
            for m in self.matches:
                lines.append(f"  {m['file']}")
            return '\n'.join(lines)
        if self.mode == 'count':
            lines = [f"Found {self.num_matches} occurrence(s) in {self.num_files} file(s):"]
            for m in self.matches:
                lines.append(f"  {m['file']}: {m['count']}")
            return '\n'.join(lines)
        return "No matches found"


@dataclass
class GlobResult:
    """Glob 搜索结果"""
    filenames: list
    num_files: int
    duration_ms: float
    truncated: bool

    def to_display(self) -> str:
        if not self.filenames:
            return "No files found"
        lines = [f"Found {self.num_files} file(s):"]
        for f in self.filenames:
            lines.append(f"  {f}")
        if self.truncated:
            lines.append(
                "(Results truncated. Consider using a more specific path or pattern.)"
            )
        return '\n'.join(lines)


# ============================================================
# GrepTool
# ============================================================

VCS_DIRECTORIES = {'.git', '.svn', '.hg', '.bzr', '.jj', '.sl', '__pycache__', '.mypy_cache', '.pytest_cache', 'node_modules'}
DEFAULT_HEAD_LIMIT = 250


class GrepTool:
    """
    代码内容搜索工具（正则表达式）。
    """

    def __init__(
        self,
        root_dir: str = '.',
        max_results: int = DEFAULT_HEAD_LIMIT,
        exclude_dirs: Optional[set] = None,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.max_results = max_results
        self.exclude_dirs = VCS_DIRECTORIES | (exclude_dirs or set())

    def call(
        self,
        pattern: str,
        path: Optional[str] = None,
        glob: Optional[str] = None,
        output_mode: str = 'files_with_matches',
        context_lines: int = 0,
        case_insensitive: bool = False,
        head_limit: Optional[int] = None,
        offset: int = 0,
    ) -> GrepResult:
        """在代码中搜索匹配内容。"""
        search_path = (
            Path(path).resolve() if path else self.root_dir
        )

        if not search_path.exists():
            raise FileNotFoundError(f"Path does not exist: {search_path}")

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # 收集所有要搜索的文件
        files = self._collect_files(search_path, glob)

        # 执行搜索
        all_matches = []
        for file_path in files:
            try:
                matches = self._search_file(file_path, regex, context_lines)
                all_matches.extend(matches)
            except (UnicodeDecodeError, PermissionError):
                continue

        # 根据模式处理结果
        if output_mode == 'files_with_matches':
            return self._process_files_mode(all_matches, head_limit, offset)
        elif output_mode == 'content':
            return self._process_content_mode(all_matches, head_limit, offset)
        elif output_mode == 'count':
            return self._process_count_mode(all_matches, head_limit, offset)
        else:
            raise ValueError(f"Unknown output_mode: {output_mode}")

    def _collect_files(self, path: Path, glob: Optional[str]) -> list:
        """收集要搜索的文件列表"""
        if path.is_file():
            return [path]

        files = []
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [
                d for d in dirs
                if d not in self.exclude_dirs
                and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = Path(root) / filename
                if glob and not fnmatch.fnmatch(filename, glob):
                    continue
                files.append(file_path)

        return files

    def _search_file(self, file_path: Path, regex, context_lines: int) -> list:
        """在单个文件中搜索"""
        with open(file_path, 'r', errors='replace') as f:
            lines = f.readlines()

        matches = []
        for i, line in enumerate(lines):
            if regex.search(line):
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(lines), i + context_lines + 1)
                context = ''.join(lines[ctx_start:ctx_end])

                matches.append({
                    'file': str(file_path),
                    'line_num': i + 1,
                    'line': line.rstrip(),
                    'context': context if context_lines > 0 else None,
                })

        return matches

    def _process_files_mode(self, matches: list, head_limit: Optional[int], offset: int) -> GrepResult:
        """处理 files_with_matches 模式"""
        seen_files = {}
        for m in matches:
            if m['file'] not in seen_files:
                seen_files[m['file']] = m

        unique_files = list(seen_files.values())
        total = len(unique_files)

        limit = head_limit or self.max_results
        sliced = unique_files[offset:offset + limit]
        applied_limit = limit if total - offset > limit else None

        return GrepResult(
            mode='files_with_matches',
            matches=sliced,
            num_files=len(sliced),
            num_matches=len(matches),
            applied_limit=applied_limit,
            applied_offset=offset if offset > 0 else None,
        )

    def _process_content_mode(self, matches: list, head_limit: Optional[int], offset: int) -> GrepResult:
        """处理 content 模式"""
        limit = head_limit or self.max_results
        sliced = matches[offset:offset + limit]
        applied_limit = limit if len(matches) - offset > limit else None

        lines = []
        for m in sliced:
            prefix = f"{m['file']}:{m['line_num']}"
            if m.get('context'):
                lines.append(f"{prefix}:\n{m['context']}")
            else:
                lines.append(f"{prefix}:{m['line']}")

        content = '\n'.join(lines)

        return GrepResult(
            mode='content',
            matches=sliced,
            num_files=len(set(m['file'] for m in sliced)),
            num_matches=len(sliced),
            content=content,
            applied_limit=applied_limit,
            applied_offset=offset if offset > 0 else None,
        )

    def _process_count_mode(self, matches: list, head_limit: Optional[int], offset: int) -> GrepResult:
        """处理 count 模式"""
        file_counts = {}
        for m in matches:
            file_counts[m['file']] = file_counts.get(m['file'], 0) + 1

        count_list = [
            {'file': f, 'count': c}
            for f, c in sorted(file_counts.items())
        ]

        limit = head_limit or self.max_results
        sliced = count_list[offset:offset + limit]
        applied_limit = limit if len(count_list) - offset > limit else None

        return GrepResult(
            mode='count',
            matches=sliced,
            num_files=len(sliced),
            num_matches=sum(m['count'] for m in sliced),
            applied_limit=applied_limit,
            applied_offset=offset if offset > 0 else None,
        )


# ============================================================
# GlobTool
# ============================================================

class GlobTool:
    """
    文件路径模式匹配工具。
    """

    DEFAULT_MAX_RESULTS = 100

    def __init__(
        self,
        root_dir: str = '.',
        max_results: int = DEFAULT_MAX_RESULTS,
        exclude_dirs: Optional[set] = None,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.max_results = max_results
        self.exclude_dirs = VCS_DIRECTORIES | (exclude_dirs or set())

    def call(
        self,
        pattern: str,
        path: Optional[str] = None,
    ) -> GlobResult:
        """查找匹配 glob 模式的文件。"""
        start_time = time.time()
        search_path = (
            Path(path).resolve() if path else self.root_dir
        )

        if not search_path.exists():
            raise FileNotFoundError(f"Path does not exist: {search_path}")

        files = self._glob_files(search_path, pattern)

        # 截断
        truncated = len(files) > self.max_results
        files = files[:self.max_results]

        # 转为相对路径
        try:
            relative_files = [
                str(f.relative_to(search_path)) for f in files
            ]
        except ValueError:
            relative_files = [str(f) for f in files]

        duration = (time.time() - start_time) * 1000

        return GlobResult(
            filenames=relative_files,
            num_files=len(relative_files),
            duration_ms=duration,
            truncated=truncated,
        )

    def _glob_files(self, root: Path, pattern: str) -> list:
        """手动实现 glob 匹配"""
        files = []

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in self.exclude_dirs
                and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                if self._match_pattern(file_path, root, pattern):
                    files.append(file_path)

        return files

    def _match_pattern(self, file_path: Path, root: Path, pattern: str) -> bool:
        """检查文件路径是否匹配 glob 模式"""
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            return False

        if '**' in pattern:
            parts = pattern.split('**')
            if len(parts) == 2:
                prefix = parts[0].rstrip('/')
                suffix = parts[1].lstrip('/')

                if suffix and not fnmatch.fnmatch(file_path.name, suffix):
                    return False

                if prefix:
                    rel_str = str(rel_path)
                    if not rel_str.startswith(prefix.rstrip('/')):
                        return False

                return True

        return fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(file_path.name, pattern)
