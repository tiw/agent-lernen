"""
skills/skill.py —— 技能表示与执行

参考 Claude Code 的 Command / createSkillCommand / parseSkillFrontmatterFields
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillFrontmatter:
    """技能 frontmatter（YAML 元数据）"""
    name: Optional[str] = None
    description: str = ""
    when_to_use: Optional[str] = None
    allowed_tools: list = field(default_factory=list)
    argument_hint: Optional[str] = None
    arguments: list = field(default_factory=list)
    model: Optional[str] = None
    user_invocable: bool = True
    context: Optional[str] = None
    paths: list = field(default_factory=list)
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SkillFrontmatter":
        """从字典创建"""
        tools = data.get("allowed-tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]

        args = data.get("arguments", [])
        if isinstance(args, str):
            args = [a.strip() for a in args.split(",")]

        paths = data.get("paths", [])
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.split(",")]

        return cls(
            name=data.get("name"),
            description=data.get("description", ""),
            when_to_use=data.get("when_to_use"),
            allowed_tools=tools,
            argument_hint=data.get("argument-hint"),
            arguments=args,
            model=data.get("model"),
            user_invocable=data.get("user-invocable", True),
            context=data.get("context"),
            paths=paths,
            version=data.get("version"),
        )


def parse_frontmatter(content: str) -> tuple:
    """
    解析 SKILL.md 内容，分离 frontmatter 和正文
    """
    if not content.startswith("---"):
        fm = SkillFrontmatter()
        return fm, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        fm = SkillFrontmatter()
        return fm, content

    yaml_text = parts[1].strip()
    markdown_text = parts[2].strip()

    fm_dict = {}
    for line in yaml_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            fm_dict[key] = value

    fm = SkillFrontmatter.from_dict(fm_dict)
    return fm, markdown_text


@dataclass
class Skill:
    """技能表示"""
    name: str
    description: str
    frontmatter: SkillFrontmatter
    content: str
    base_dir: Optional[Path] = None
    source: str = "user"
    is_hidden: bool = False

    @classmethod
    def from_file(cls, file_path: Path) -> Optional["Skill"]:
        """从 SKILL.md 文件加载技能"""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read skill file {file_path}: {e}")
            return None

        frontmatter, markdown_content = parse_frontmatter(content)

        skill_name = frontmatter.name or file_path.parent.name

        return cls(
            name=skill_name,
            description=frontmatter.description or skill_name,
            frontmatter=frontmatter,
            content=markdown_content,
            base_dir=file_path.parent,
        )

    def build_prompt(self, args: str = "") -> str:
        """构建技能 prompt"""
        parts = []

        if self.base_dir:
            parts.append(f"Base directory for this skill: {self.base_dir}\n")

        prompt = self.content

        if args and self.frontmatter.arguments:
            arg_values = self._parse_args(args)
            for i, arg_name in enumerate(self.frontmatter.arguments):
                placeholder = f"{{{arg_name}}}"
                value = arg_values[i] if i < len(arg_values) else ""
                prompt = prompt.replace(placeholder, value)

        if self.base_dir:
            prompt = prompt.replace("${SKILL_DIR}", str(self.base_dir))

        parts.append(prompt)
        return "\n".join(parts)

    def _parse_args(self, args_str: str) -> list:
        """解析参数字符串"""
        import shlex
        try:
            return shlex.split(args_str)
        except ValueError:
            return args_str.split()

    def matches_path(self, file_path: str) -> bool:
        """检查文件路径是否匹配此技能的条件路径"""
        if not self.frontmatter.paths:
            return True

        for pattern in self.frontmatter.paths:
            if self._match_glob(pattern, file_path):
                return True
        return False

    def _match_glob(self, pattern: str, file_path: str) -> bool:
        """简单的 glob 匹配"""
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)

    def __repr__(self) -> str:
        return f"Skill({self.name!r}, {self.description[:50]!r})"
