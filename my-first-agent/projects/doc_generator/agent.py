"""
项目 2：智能文档生成器

功能：
- 分析代码仓库结构
- 自动生成 README、API 文档、架构文档
- 支持多种输出格式（Markdown、HTML、PDF）
- 可自定义文档模板

架构参考：Claude Code 的 WriteTool + 多文件生成能力
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============================================================
# 文档模板
# ============================================================

class DocTemplates:
    """文档模板集合"""

    README = """# {project_name}

{description}

## 快速开始

{getting_started}

## 项目结构

{project_structure}

## 核心功能

{features}

## API 文档

{api_docs}

## 开发指南

{dev_guide}

## 许可证

{license}
"""

    API_DOC = """# API 文档

{project_name} 的 API 接口文档。

## 模块概览

{modules_overview}

## 详细 API

{api_details}

## 使用示例

{examples}
"""

    ARCHITECTURE = """# 架构文档

## 系统概览

{system_overview}

## 核心组件

{components}

## 数据流

{data_flow}

## 依赖关系

{dependencies}

## 设计决策

{design_decisions}
"""


# ============================================================
# 代码分析器
# ============================================================

class CodebaseAnalyzer:
    """代码仓库分析器"""

    def __init__(self):
        self.files: list[dict] = []
        self.modules: list[dict] = []
        self.dependencies: list[dict] = []

    def analyze(self, root: str | Path) -> dict:
        """分析代码仓库"""
        root = Path(root)

        # 基本信息
        info = {
            "name": root.name,
            "path": str(root),
            "files": [],
            "languages": {},
            "total_lines": 0,
            "total_size": 0,
            "modules": [],
            "dependencies": [],
        }

        # 扫描文件
        for filepath in root.rglob("*"):
            if not filepath.is_file():
                continue
            if any(p.startswith(".") for p in filepath.parts):
                continue
            if any(p in ("node_modules", "__pycache__", ".git", "venv") for p in filepath.parts):
                continue

            ext = filepath.suffix.lower()
            size = filepath.stat().st_size

            try:
                lines = filepath.read_text(encoding="utf-8", errors="replace").count("\n")
            except Exception:
                lines = 0

            info["files"].append({
                "path": str(filepath.relative_to(root)),
                "extension": ext,
                "size": size,
                "lines": lines,
            })

            info["total_lines"] += lines
            info["total_size"] += size

            lang = self._ext_to_language(ext)
            if lang:
                info["languages"][lang] = info["languages"].get(lang, 0) + 1

        # 分析模块结构（Python 项目）
        info["modules"] = self._analyze_modules(root)
        info["dependencies"] = self._analyze_dependencies(root)

        return info

    def _ext_to_language(self, ext: str) -> str:
        mapping = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".go": "Go", ".rs": "Rust", ".java": "Java",
            ".rb": "Ruby", ".sh": "Shell", ".yaml": "YAML",
            ".json": "JSON", ".md": "Markdown",
        }
        return mapping.get(ext, "")

    def _analyze_modules(self, root: Path) -> list[dict]:
        """分析 Python 模块结构"""
        modules = []
        for init_file in root.rglob("__init__.py"):
            module_path = init_file.parent.relative_to(root)
            py_files = list(init_file.parent.glob("*.py"))
            modules.append({
                "name": str(module_path).replace("/", "."),
                "path": str(module_path),
                "files": len(py_files),
            })
        return modules

    def _analyze_dependencies(self, root: Path) -> list[str]:
        """分析项目依赖"""
        deps = []

        # requirements.txt
        req_file = root / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(line.split("==")[0].split(">=")[0].split("<")[0].strip())

        # pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[project]" in content or "[tool.poetry]" in content:
                deps.append("(from pyproject.toml)")

        # package.json
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                deps.extend(data.get("dependencies", {}).keys())
                deps.extend(data.get("devDependencies", {}).keys())
            except Exception:
                pass

        return deps


# ============================================================
# 文档生成器
# ============================================================

class DocGenerator:
    """
    智能文档生成器

    工作流程：
    1. 分析代码仓库
    2. 使用 LLM 生成文档内容
    3. 填充模板
    4. 导出为多种格式
    """

    def __init__(self, llm_client=None):
        self.analyzer = CodebaseAnalyzer()
        self.llm_client = llm_client
        self.templates = DocTemplates()

    async def generate_readme(self, root: str | Path) -> str:
        """生成 README"""
        info = self.analyzer.analyze(root)

        # 使用 LLM 生成各部分内容
        sections = {}
        for section in [
            "description", "getting_started", "features",
            "api_docs", "dev_guide",
        ]:
            if self.llm_client:
                sections[section] = await self._llm_generate_section(
                    info, section
                )
            else:
                sections[section] = self._default_section(info, section)

        # 项目结构
        sections["project_structure"] = self._format_tree(info["files"])

        # 许可证
        sections["license"] = self._detect_license(root)

        return self.templates.README.format(
            project_name=info["name"],
            **sections,
        )

    async def generate_api_doc(self, root: str | Path) -> str:
        """生成 API 文档"""
        info = self.analyzer.analyze(root)

        modules_overview = ""
        api_details = ""
        examples = ""

        if self.llm_client:
            modules_overview = await self._llm_generate_section(
                info, "modules_overview"
            )
            api_details = await self._llm_generate_section(
                info, "api_details"
            )
            examples = await self._llm_generate_section(
                info, "examples"
            )

        return self.templates.API_DOC.format(
            project_name=info["name"],
            modules_overview=modules_overview or "待生成",
            api_details=api_details or "待生成",
            examples=examples or "待补充",
        )

    async def generate_all(
        self,
        root: str | Path,
        output_dir: str | Path = "docs",
    ) -> list[Path]:
        """生成所有文档"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        files = []

        # README
        readme = await self.generate_readme(root)
        readme_path = output_dir / "README.md"
        readme_path.write_text(readme, encoding="utf-8")
        files.append(readme_path)

        # API 文档
        api_doc = await self.generate_api_doc(root)
        api_path = output_dir / "API.md"
        api_path.write_text(api_doc, encoding="utf-8")
        files.append(api_path)

        return files

    async def _llm_generate_section(self, info: dict, section: str) -> str:
        """使用 LLM 生成文档章节"""
        prompts = {
            "description": f"用一句话描述这个项目的用途。\n项目信息：{json.dumps(info, ensure_ascii=False)[:1000]}",
            "getting_started": f"为这个项目写一个快速开始指南（安装、配置、运行）。\n项目信息：{json.dumps(info, ensure_ascii=False)[:1000]}",
            "features": f"列出这个项目的主要功能特性。\n项目信息：{json.dumps(info, ensure_ascii=False)[:1000]}",
            "api_docs": f"为这个项目生成 API 文档概览。\n项目信息：{json.dumps(info, ensure_ascii=False)[:1000]}",
            "dev_guide": f"为这个项目写开发指南（如何贡献代码）。\n项目信息：{json.dumps(info, ensure_ascii=False)[:1000]}",
        }

        prompt = prompts.get(section, f"生成 {section} 的内容。")
        try:
            return await self.llm_client.chat(prompt)
        except Exception:
            return f"（{section} 生成失败）"

    def _default_section(self, info: dict, section: str) -> str:
        """默认章节内容（无 LLM 时）"""
        defaults = {
            "description": f"一个 {info['name']} 项目，包含 {len(info['files'])} 个文件，{info['total_lines']} 行代码。",
            "getting_started": "```\npip install -r requirements.txt\npython main.py\n```",
            "features": f"- 支持 {', '.join(info['languages'].keys())} 语言",
            "api_docs": "详见 API.md",
            "dev_guide": "1. Fork 仓库\n2. 创建特性分支\n3. 提交 PR",
        }
        return defaults.get(section, "")

    def _format_tree(self, files: list[dict], max_items: int = 30) -> str:
        """格式化文件树"""
        lines = ["```"]
        shown = files[:max_items]
        for f in shown:
            indent = "  " * f["path"].count("/")
            lines.append(f"{indent}{f['path']}")
        if len(files) > max_items:
            lines.append(f"... 还有 {len(files) - max_items} 个文件")
        lines.append("```")
        return "\n".join(lines)

    def _detect_license(self, root: Path) -> str:
        """检测许可证"""
        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt"]:
            if (root / name).exists():
                return f"详见 [{name}]({name})"
        return "未检测到许可证文件"


# ============================================================
# 使用示例
# ============================================================

async def main():
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    output = sys.argv[2] if len(sys.argv) > 2 else "docs"

    generator = DocGenerator()  # 不使用 LLM 的基础模式
    files = await generator.generate_all(target, output)

    print("📄 文档生成完成：")
    for f in files:
        print(f"  - {f}")


if __name__ == "__main__":
    asyncio.run(main())
