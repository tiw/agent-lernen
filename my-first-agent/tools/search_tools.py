"""
搜索工具集 —— 代码内容搜索和文件路径匹配。
参考 Claude Code 的 Grep / Glob 工具设计。
从零手写 AI Agent 课程 · 第 4 章
"""

import os
import re
import time
import fnmatch
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal

try:
    import pathspec
    HAS_PATHPEC = True
except ImportError:
    HAS_PATHPEC = False

# VCS 目录排除列表
VCS_DIRECTORIES = {
    '.git', '.svn', '.hg', '.bzr', '.jj', '.sl',
    '.tox', '.nox', '.eggs',
}


# ============================================================
# 工具结果
# ============================================================

@dataclass
class GrepResult:
    mode: Literal['content', 'files_with_matches', 'count']
    matches: list[dict]
    num_files: int
    num_matches: int
    content: Optional[str] = None
    applied_limit: Optional[int] = None
    applied_offset: Optional[int] = None

    def to_display(self) -> str:
        if self.mode == 'files_with_matches':
            lines = [f"Found {self.num_files} files with matches:"]
            for m in self.matches:
                lines.append(f"  {m['file']}")
            return '\n'.join(lines)

        elif self.mode == 'content':
            return self.content or "No content"

        elif self.mode == 'count':
            lines = [f"Match counts per file:"]
            for m in self.matches:
                lines.append(f"  {m['file']}: {m['count']}")
            return '\n'.join(lines)

        return str(self)


@dataclass
class GlobResult:
    filenames: list[str]
    num_files: int
    duration_ms: float
    truncated: bool = False

    def to_display(self) -> str:
        if self.truncated:
            return f"Found {self.num_files} files (showing first {len(self.filenames)}):\n" + \
                   '\n'.join(f"  {f}" for f in self.filenames)
        return f"Found {self.num_files} files:\n" + \
               '\n'.join(f"  {f}" for f in self.filenames)


# ============================================================
# GrepTool
# ============================================================

class GrepTool:
    """
    代码内容搜索工具（类似 grep/ripgrep）。

    参考 Claude Code 的 GrepTool：
    - 支持正则表达式搜索
    - 三种输出模式：files_with_matches, content, count
    - 自动排除 VCS 目录
    - 结果截断防止上下文爆炸
    - 支持上下文行（-A/-B/-C）
    """

    name = "grep"
    description = "在文件内容中搜索正则表达式匹配。适用于查找代码中的函数调用、变量定义、特定模式等。支持三种输出模式。"

    def __init__(
        self,
        root_dir: str = '.',
        max_results: int = 250,
        exclude_dirs: Optional[set[str]] = None,
        include_pattern: Optional[str] = None,
        use_ripgrep: bool = True,
    ):
        """
        Args:
            root_dir: 搜索根目录
            max_results: 最大返回结果数
            exclude_dirs: 排除的目录名集合
            include_pattern: 只搜索匹配此 glob 模式的文件（如 "*.py"）
            use_ripgrep: 是否使用 ripgrep（如果可用）
        """
        self.root_dir = Path(root_dir).resolve()
        self.max_results = max_results
        self.exclude_dirs = VCS_DIRECTORIES | (exclude_dirs or set())
        self.include_pattern = include_pattern
        self.use_ripgrep = use_ripgrep
        self._has_ripgrep = shutil.which('rg') is not None

    def call(
        self,
        pattern: str,
        output_mode: Literal['content', 'files_with_matches', 'count'] = 'files_with_matches',
        context: Optional[int] = None,
        glob: Optional[str] = None,
        head_limit: Optional[int] = None,
        offset: int = 0,
    ) -> GrepResult:
        """
        执行搜索。

        Args:
            pattern: 正则表达式模式
            output_mode: 输出模式
            context: 上下文行数（-C 参数）
            glob: 文件 glob 模式（如 "*.py"）
            head_limit: 结果数量限制
            offset: 跳过前 N 个结果

        Returns:
            GrepResult 包含搜索结果
        """
        start_time = time.time()

        # 编译正则
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # 收集所有匹配
        matches = self._grep_files(regex, context, glob)

        # 根据模式处理结果
        if output_mode == 'files_with_matches':
            return self._process_files_mode(matches, head_limit, offset)
        elif output_mode == 'content':
            return self._process_content_mode(matches, head_limit, offset)
        elif output_mode == 'count':
            return self._process_count_mode(matches, head_limit, offset)
        else:
            raise ValueError(f"Unknown output_mode: {output_mode}")

    def _grep_files(
        self,
        regex: re.Pattern,
        context: Optional[int],
        glob: Optional[str],
    ) -> list[dict]:
        """遍历文件并收集匹配"""
        # 优先使用 ripgrep（如果可用且启用）
        if self.use_ripgrep and self._has_ripgrep:
            try:
                return self._grep_with_ripgrep(regex.pattern, context, glob)
            except Exception:
                pass  # ripgrep 失败，回退到 Python 实现
        
        return self._grep_with_python(regex, context, glob)
    
    def _grep_with_ripgrep(
        self,
        pattern: str,
        context: Optional[int],
        glob: Optional[str],
    ) -> list[dict]:
        """使用 ripgrep 进行搜索（性能更好）"""
        import subprocess
        import json as json_lib
        
        # 构建 rg 命令
        cmd = ['rg', '--json', '--max-count', str(self.max_results * 2)]
        
        # 添加上下文
        if context:
            cmd.extend(['--context', str(context)])
        
        # 添加 glob 模式
        if glob:
            cmd.extend(['--glob', glob])
        
        # 排除目录
        for exclude in self.exclude_dirs:
            cmd.extend(['--glob', f'!{exclude}'])
        
        cmd.extend([pattern, str(self.root_dir)])
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        # 解析 JSON 输出
        matches = []
        for line in result.stdout.split('\n'):
            if line.strip():
                try:
                    data = json_lib.loads(line)
                    if 'data' in data:
                        d = data['data']
                        match_info = {
                            'file': str(Path(d['path']['text']).relative_to(self.root_dir)),
                            'line': d['lines']['text'].rstrip(),
                            'line_num': d['line_number'],
                        }
                        if context and 'context' in d:
                            match_info['context'] = d['lines']['context']
                        matches.append(match_info)
                except (json_lib.JSONDecodeError, KeyError, ValueError):
                    continue
        
        return matches
    
    def _grep_with_python(
        self,
        regex: re.Pattern,
        context: Optional[int],
        glob: Optional[str],
    ) -> list[dict]:
        """使用 Python re 模块进行搜索（回退方案）"""
        matches = []

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # 排除不需要的目录
            dirnames[:] = [
                d for d in dirnames
                if d not in self.exclude_dirs
                and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = Path(dirpath) / filename

                # 检查 glob 模式
                if glob and not fnmatch.fnmatch(filename, glob):
                    continue

                # 检查 include_pattern
                if self.include_pattern and not fnmatch.fnmatch(filename, self.include_pattern):
                    continue

                # 读取文件
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                except (IOError, OSError):
                    continue

                # 搜索匹配
                for line_num, line in enumerate(lines, 1):
                    if regex.search(line):
                        match_info = {
                            'file': str(file_path.relative_to(self.root_dir)),
                            'line': line.rstrip(),
                            'line_num': line_num,
                        }

                        # 添加上下文
                        if context:
                            start = max(0, line_num - 1 - context)
                            end = min(len(lines), line_num + context)
                            context_lines = lines[start:end]
                            match_info['context'] = ''.join(context_lines)
                            match_info['context_lines'] = end - start

                        matches.append(match_info)

                        # 限制总数
                        if len(matches) >= self.max_results * 2:
                            return matches

        return matches

    def _process_files_mode(
        self,
        matches: list[dict],
        head_limit: Optional[int],
        offset: int,
    ) -> GrepResult:
        """处理 files_with_matches 模式"""
        # 按文件去重
        seen_files = {}
        for m in matches:
            if m['file'] not in seen_files:
                seen_files[m['file']] = m

        unique_files = list(seen_files.values())
        total = len(unique_files)

        # 应用 offset 和 limit
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

    def _process_content_mode(
        self,
        matches: list[dict],
        head_limit: Optional[int],
        offset: int,
    ) -> GrepResult:
        """处理 content 模式"""
        limit = head_limit or self.max_results
        sliced = matches[offset:offset + limit]
        applied_limit = limit if len(matches) - offset > limit else None

        # 格式化为带文件路径和行号的内容
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

    def _process_count_mode(
        self,
        matches: list[dict],
        head_limit: Optional[int],
        offset: int,
    ) -> GrepResult:
        """处理 count 模式"""
        # 按文件统计
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
                        "pattern": {
                            "type": "string",
                            "description": "正则表达式搜索模式",
                        },
                        "output_mode": {
                            "type": "string",
                            "enum": ["content", "files_with_matches", "count"],
                            "description": "输出模式",
                            "default": "files_with_matches",
                        },
                        "context": {
                            "type": "integer",
                            "description": "显示匹配行上下文的行数",
                        },
                        "glob": {
                            "type": "string",
                            "description": "文件 glob 模式（如 *.py）",
                        },
                        "head_limit": {
                            "type": "integer",
                            "description": "结果数量限制",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "跳过前 N 个结果",
                            "default": 0,
                        },
                    },
                    "required": ["pattern"],
                },
            }
        }


# ============================================================
# GlobTool
# ============================================================

class GlobTool:
    """
    文件路径模式匹配工具（类似 glob）。

    参考 Claude Code 的 GlobTool：
    - 支持 glob 模式（*, **, ?）
    - 结果截断（默认 100）
    - 自动排除 VCS 目录
    """

    name = "glob"
    description = "使用 glob 模式匹配文件路径。适用于查找特定类型的文件（如*.py）、特定目录下的文件等。"

    DEFAULT_MAX_RESULTS = 100

    def __init__(
        self,
        root_dir: str = '.',
        max_results: int = DEFAULT_MAX_RESULTS,
        exclude_dirs: Optional[set[str]] = None,
        respect_gitignore: bool = True,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.max_results = max_results
        self.exclude_dirs = VCS_DIRECTORIES | (exclude_dirs or set())
        self.respect_gitignore = respect_gitignore
        self.gitignore_spec = None
        
        # 加载 .gitignore
        if respect_gitignore and HAS_PATHPEC:
            self.gitignore_spec = self._load_gitignore()

    def call(
        self,
        pattern: str,
        path: Optional[str] = None,
    ) -> GlobResult:
        """
        查找匹配 glob 模式的文件。

        Args:
            pattern: glob 模式（如 "**/*.py"、"src/**/*.ts"）
            path: 搜索根目录

        Returns:
            GlobResult 包含匹配的文件列表
        """
        start_time = time.time()
        search_path = (
            Path(path).resolve() if path else self.root_dir
        )

        if not search_path.exists():
            raise FileNotFoundError(f"Path does not exist: {search_path}")

        # 使用 Path.glob 或手动遍历
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

    def _load_gitignore(self) -> Optional['pathspec.PathSpec']:
        """加载 .gitignore 文件"""
        gitignore_path = self.root_dir / '.gitignore'
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    return pathspec.PathSpec.from_lines('gitwildmatch', f)
            except Exception:
                pass
        return None

    def _is_gitignored(self, file_path: Path) -> bool:
        """检查文件是否被 .gitignore 忽略"""
        if self.gitignore_spec is None:
            return False
        
        try:
            rel_path = file_path.relative_to(self.root_dir)
            return self.gitignore_spec.match_file(str(rel_path))
        except ValueError:
            return False

    def _glob_files(self, root: Path, pattern: str) -> list[Path]:
        """手动实现 glob 匹配（比 Path.glob 更灵活）"""
        files = []

        for dirpath, dirnames, filenames in os.walk(root):
            # 排除不需要的目录
            dirnames[:] = [
                d for d in dirnames
                if d not in self.exclude_dirs
                and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = Path(dirpath) / filename

                # 检查是否匹配模式
                if self._match_pattern(file_path, root, pattern):
                    # 检查是否被 .gitignore 忽略
                    if self.respect_gitignore and self._is_gitignored(file_path):
                        continue
                    files.append(file_path)

        return files

    def _match_pattern(self, file_path: Path, root: Path, pattern: str) -> bool:
        """检查文件路径是否匹配 glob 模式"""
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            return False

        # 使用 fnmatch 支持 *, ?, [seq] 等
        # 对于 ** 模式，需要特殊处理
        if '**' in pattern:
            # ** 匹配任意层级的目录
            parts = pattern.split('**')
            if len(parts) == 2:
                prefix = parts[0].rstrip('/')
                suffix = parts[1].lstrip('/')

                # 检查后缀是否匹配文件名
                if suffix and not fnmatch.fnmatch(file_path.name, suffix):
                    return False

                # 检查前缀是否匹配路径
                if prefix:
                    rel_str = str(rel_path)
                    if not rel_str.startswith(prefix.rstrip('/')):
                        return False

                return True

        return fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(file_path.name, pattern)

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
                        "pattern": {
                            "type": "string",
                            "description": "glob 模式（如 **/*.py、src/**/*.ts）",
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索根目录，默认当前目录",
                        },
                    },
                    "required": ["pattern"],
                },
            }
        }
