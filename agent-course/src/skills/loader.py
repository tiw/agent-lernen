"""
skills/loader.py —— 技能加载与管理

参考 Claude Code 的 loadSkillsDir / getSkillDirCommands / bundledSkills
"""

import logging
from pathlib import Path
from typing import Optional

from .skill import Skill

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    技能加载器
    """

    def __init__(self):
        self._skills: dict = {}
        self._conditional_skills: dict = {}
        self._skill_dirs_checked: set = set()

    def load_directory(self, skills_dir: Path, source: str = "user") -> list:
        """从目录加载所有技能"""
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
        bundled_dir: Optional[Path] = None,
    ) -> dict:
        """从所有目录加载技能"""
        all_skills: list = []

        if bundled_dir:
            for skill in self.load_directory(bundled_dir, "bundled"):
                all_skills.append(("bundled", skill))

        if user_dir:
            for skill in self.load_directory(user_dir, "user"):
                all_skills.append(("user", skill))

        if project_dir:
            for skill in self.load_directory(project_dir, "project"):
                all_skills.append(("project", skill))

        self._skills.clear()
        self._conditional_skills.clear()

        for source, skill in all_skills:
            if skill.frontmatter.paths:
                self._conditional_skills[skill.name] = skill
            else:
                self._skills[skill.name] = skill

        logger.info(
            f"Loaded {len(self._skills)} skills "
            f"({len(self._conditional_skills)} conditional)"
        )
        return dict(self._skills)

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)

    def list_skills(self) -> list:
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

    def activate_conditional(self, file_path: str) -> list:
        """激活匹配文件路径的条件技能"""
        activated = []
        for name, skill in list(self._conditional_skills.items()):
            if skill.matches_path(file_path):
                self._skills[name] = skill
                del self._conditional_skills[name]
                activated.append(name)
                logger.info(f"Activated conditional skill: {name}")
        return activated

    def search(self, query: str) -> list:
        """搜索技能（按描述匹配）"""
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


def load_skills_from_dir(skills_dir: Path) -> list:
    """快速加载单个目录的技能"""
    loader = SkillLoader()
    return loader.load_directory(skills_dir)
