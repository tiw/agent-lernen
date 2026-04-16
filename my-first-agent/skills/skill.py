"""
skills/skill.py —— 技能表示与执行
参考 Claude Code 的 Command / createSkillCommand / parseSkillFrontmatterFields
从零手写 AI Agent 课程 · 第 8 章
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillFrontmatter:
    """
    技能 frontmatter（YAML 元数据）

    参考 Claude Code 的 FrontmatterData / parseSkillFrontmatterFields
    """
    name: Optional[str] = None
    description: str = ""
    when_to_use: Optional[str] = None
    allowed_tools: list[str] = field(default_factory=list)
    argument_hint: Optional[str] = None
    arguments: list[str] = field(default_factory=list)
    model: Optional[str] = None
    user_invocable: bool = True
    context: Optional[str] = None  # "inline" or "fork"
    paths: list[str] = field(default_factory=list)  # 条件激活路径
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SkillFrontmatter":
        """从字典创建"""
        # 解析 allowed-tools（可能是逗号分隔字符串或列表）
        tools = data.get("allowed-tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]

        # 解析 arguments（可能是逗号分隔字符串或列表）
        args = data.get("arguments", [])
        if isinstance(args, str):
            args = [a.strip() for a in args.split(",")]

        # 解析 paths
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


def parse_frontmatter(content: str) -> tuple[SkillFrontmatter, str]:
    """
    解析 SKILL.md 内容，分离 frontmatter 和正文

    参考 Claude Code 的 parseFrontmatter

    格式：
    ---
    name: my-skill
    description: My skill
    ---
    # Skill content starts here
    ...
    """
    # 简单的 YAML frontmatter 解析
    if not content.startswith("---"):
        # 没有 frontmatter，整个文件都是正文
        fm = SkillFrontmatter()
        return fm, content

    # 找到第二个 ---
    parts = content.split("---", 2)
    if len(parts) < 3:
        fm = SkillFrontmatter()
        return fm, content

    yaml_text = parts[1].strip()
    markdown_text = parts[2].strip()

    # 解析 YAML（简单实现，不依赖 pyyaml）
    fm_dict = {}
    for line in yaml_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            # 尝试类型转换
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
    """
    技能表示（参考 Claude Code 的 Command）

    一个技能 = frontmatter 元数据 + Markdown 正文 + 可选的参考文件
    """
    name: str
    description: str
    frontmatter: SkillFrontmatter
    content: str  # Markdown 正文
    base_dir: Optional[Path] = None  # 技能目录
    source: str = "user"  # "user" | "project" | "bundled" | "plugin"
    is_hidden: bool = False

    @classmethod
    def from_file(cls, file_path: Path) -> Optional["Skill"]:
        """
        从 SKILL.md 文件加载技能

        参考 Claude Code 的 loadSkillsFromSkillsDir
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read skill file {file_path}: {e}")
            return None

        frontmatter, markdown_content = parse_frontmatter(content)

        # 技能名优先用 frontmatter，其次用目录名
        skill_name = frontmatter.name or file_path.parent.name

        return cls(
            name=skill_name,
            description=frontmatter.description or skill_name,
            frontmatter=frontmatter,
            content=markdown_content,
            base_dir=file_path.parent,
        )

    def build_prompt(self, args: str = "") -> str:
        """
        构建技能 prompt（参考 Claude Code 的 getPromptForCommand）

        1. 添加技能目录路径
        2. 替换参数占位符
        3. 替换特殊变量
        """
        parts = []

        # 添加基础目录信息
        if self.base_dir:
            parts.append(f"Base directory for this skill: {self.base_dir}\n")

        # 添加技能内容
        prompt = self.content

        # 替换参数占位符 {arg_name}
        if args and self.frontmatter.arguments:
            arg_values = self._parse_args(args)
            for i, arg_name in enumerate(self.frontmatter.arguments):
                placeholder = f"{{{arg_name}}}"
                value = arg_values[i] if i < len(arg_values) else ""
                prompt = prompt.replace(placeholder, value)

        # 替换 ${SKILL_DIR} 变量
        if self.base_dir:
            prompt = prompt.replace("${SKILL_DIR}", str(self.base_dir))

        parts.append(prompt)
        return "\n".join(parts)

    def _parse_args(self, args_str: str) -> list[str]:
        """解析参数字符串"""
        import shlex
        try:
            return shlex.split(args_str)
        except ValueError:
            return args_str.split()

    def matches_path(self, file_path: str) -> bool:
        """
        检查文件路径是否匹配此技能的条件路径

        参考 Claude Code 的 activateConditionalSkillsForPaths
        """
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


# === 测试 ===
if __name__ == "__main__":
    print("=== 技能系统基础测试 ===\n")

    # 测试 1: frontmatter 解析
    print("测试 1: frontmatter 解析")
    test_content = """---
name: test-skill
description: A test skill
when_to_use: For testing
allowed-tools: Read, Write
---
# Skill Content
This is the content.
"""
    fm, content = parse_frontmatter(test_content)
    print(f"  name: {fm.name}")
    print(f"  description: {fm.description}")
    print(f"  when_to_use: {fm.when_to_use}")
    print(f"  allowed_tools: {fm.allowed_tools}")
    print(f"  content: {content[:30]}...\n")

    # 测试 2: 技能加载
    print("测试 2: 技能加载")
    # 创建一个测试技能文件
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = os.path.join(tmpdir, "test-skill")
        os.makedirs(skill_dir)
        skill_file = os.path.join(skill_dir, "SKILL.md")
        
        with open(skill_file, 'w') as f:
            f.write(test_content)
        
        skill = Skill.from_file(Path(skill_file))
        print(f"  技能名：{skill.name}")
        print(f"  描述：{skill.description}")
        print(f"  来源：{skill.source}")
        print(f"  内容长度：{len(skill.content)} 字符\n")

    # 测试 3: prompt 构建
    print("测试 3: prompt 构建")
    test_skill = Skill(
        name="test",
        description="Test skill",
        frontmatter=SkillFrontmatter(arguments=["target"]),
        content="Review the code at {target}",
    )
    prompt = test_skill.build_prompt("src/main.py")
    print(f"  Prompt: {prompt}\n")

    print("✅ 基础测试完成！")
