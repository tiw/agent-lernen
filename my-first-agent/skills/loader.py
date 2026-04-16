"""
skills/loader.py —— 技能加载与管理
参考 Claude Code 的 loadSkillsDir / getSkillDirCommands / bundledSkills
从零手写 AI Agent 课程 · 第 8 章
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from skills.skill import Skill
else:
    from .skill import Skill

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    技能加载器

    参考 Claude Code 的技能加载流程：
    1. 扫描多个技能目录
    2. 解析每个 SKILL.md
    3. 去重（通过 realpath）
    4. 分类（无条件 / 条件）
    5. 返回可用技能列表
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._conditional_skills: dict[str, Skill] = {}
        self._skill_dirs_checked: set[str] = set()

    def load_directory(self, skills_dir: Path, source: str = "user") -> list[Skill]:
        """
        从目录加载所有技能

        参考 Claude Code 的 loadSkillsFromSkillsDir：
        - 只支持目录格式：skill-name/SKILL.md
        - 不支持单个 .md 文件
        """
        if not skills_dir.exists():
            logger.debug(f"Skills directory not found: {skills_dir}")
            return []

        skills = []
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue

            skill_file = entry / "SKILL.md"
            if not skill_file.exists():
                continue

            skill = Skill.from_file(skill_file)
            if skill:
                skill.source = source
                skills.append(skill)
                logger.debug(f"Loaded skill: {skill.name}")

        return skills

    def load_all(
        self,
        user_dir: Optional[Path] = None,
        project_dir: Optional[Path] = None,
    ) -> int:
        """
        从所有来源加载技能

        参考 Claude Code 的 loadAllSkills：
        - 用户级：~/.claude/skills/
        - 项目级：./.claude/skills/
        - 去重：通过 realpath 检测同一文件
        """
        loaded_count = 0

        # 加载用户级技能
        if user_dir and user_dir.exists():
            real_path = str(user_dir.resolve())
            if real_path not in self._skill_dirs_checked:
                self._skill_dirs_checked.add(real_path)
                skills = self.load_directory(user_dir, source="user")
                for skill in skills:
                    self._register_skill(skill)
                    loaded_count += 1

        # 加载项目级技能
        if project_dir and project_dir.exists():
            real_path = str(project_dir.resolve())
            if real_path not in self._skill_dirs_checked:
                self._skill_dirs_checked.add(real_path)
                skills = self.load_directory(project_dir, source="project")
                for skill in skills:
                    self._register_skill(skill)
                    loaded_count += 1

        logger.info(f"Loaded {loaded_count} skills")
        return loaded_count

    def _register_skill(self, skill: Skill) -> None:
        """注册技能（处理去重和条件激活）"""
        # 检查是否有条件路径
        if skill.frontmatter.paths:
            self._conditional_skills[skill.name] = skill
            logger.debug(f"Registered conditional skill: {skill.name}")
        else:
            self._skills[skill.name] = skill
            logger.debug(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        """列出所有可用技能"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "when_to_use": s.frontmatter.when_to_use,
                "source": s.source,
            }
            for s in sorted(self._skills.values(), key=lambda x: x.name)
        ]

    def activate_conditional(self, file_path: str) -> list[str]:
        """
        激活匹配文件路径的条件技能

        参考 Claude Code 的 activateConditionalSkillsForPaths
        """
        activated = []
        for name, skill in list(self._conditional_skills.items()):
            if skill.matches_path(file_path):
                self._skills[name] = skill
                del self._conditional_skills[name]
                activated.append(name)
                logger.info(f"Activated conditional skill: {name}")
        return activated

    def search(self, query: str) -> list[Skill]:
        """
        搜索技能（按描述匹配）

        用于 Agent 自动发现相关技能。
        """
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or (skill.frontmatter.when_to_use
                    and query_lower in skill.frontmatter.when_to_use.lower())
            ):
                results.append(skill)
        return results


# --- 便捷函数 ---

def load_skills_from_dir(skills_dir: Path) -> list[Skill]:
    """快速加载单个目录的技能"""
    loader = SkillLoader()
    return loader.load_directory(skills_dir)


# === 测试 ===
if __name__ == "__main__":
    print("=== 技能加载器测试 ===\n")

    import tempfile
    import os

    # 创建测试技能目录
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        # 创建测试技能 1
        skill1_dir = skills_dir / "code-review"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
name: code-review
description: Perform code review
when_to_use: When reviewing code
allowed-tools: Read, Grep
---
# Code Review Skill
You are a code reviewer.
""")

        # 创建测试技能 2
        skill2_dir = skills_dir / "data-analysis"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
name: data-analysis
description: Analyze data files
when_to_use: When working with data
allowed-tools: Read, Bash
---
# Data Analysis Skill
You are a data analyst.
""")

        # 测试加载
        print("测试 1: 加载技能目录")
        loader = SkillLoader()
        skills = loader.load_directory(skills_dir)
        print(f"  加载技能数：{len(skills)}")
        for skill in skills:
            print(f"    - {skill.name}: {skill.description}")

        # 测试注册
        print("\n测试 2: 注册技能")
        for skill in skills:
            loader._register_skill(skill)
        print(f"  可用技能：{len(loader._skills)}")

        # 测试列出
        print("\n测试 3: 列出技能")
        skill_list = loader.list_skills()
        for s in skill_list:
            print(f"    - {s['name']}: {s['description']}")

        # 测试搜索
        print("\n测试 4: 搜索技能")
        results = loader.search("code")
        print(f"  搜索 'code': {len(results)} 条结果")
        for r in results:
            print(f"    - {r.name}")

    print("\n✅ 所有测试完成！")
