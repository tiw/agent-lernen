"""
项目 1：自动代码审查助手

功能：
- 扫描指定目录的代码文件
- 使用 LLM 分析代码质量
- 生成结构化的审查报告
- 支持自定义审查规则

架构参考：Claude Code 的 ReadTool + GrepTool + 多步任务编排
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================
# 数据模型
# ============================================================

class Severity(str, Enum):
    CRITICAL = "critical"   # 必须修复
    WARNING = "warning"     # 建议修复
    INFO = "info"           # 可选优化
    POSITIVE = "positive"   # 做得好的地方


@dataclass
class ReviewFinding:
    """审查发现"""
    file: str
    line: int
    severity: Severity
    category: str
    message: str
    suggestion: str = ""
    code_snippet: str = ""


@dataclass
class ReviewReport:
    """审查报告"""
    target: str
    findings: list[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    score: float = 0.0  # 0-100

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    def to_markdown(self) -> str:
        lines = [
            "# 代码审查报告",
            "",
            f"**目标**: {self.target}",
            f"**评分**: {self.score:.0f}/100",
            "",
            "## 概览",
            "",
            "| 类型 | 数量 |",
            "|------|------|",
            f"| 🔴 Critical | {self.critical_count} |",
            f"| 🟡 Warning | {self.warning_count} |",
            f"| ℹ️  Info | {sum(1 for f in self.findings if f.severity == Severity.INFO)} |",
            f"| ✅ Positive | {sum(1 for f in self.findings if f.severity == Severity.POSITIVE)} |",
            "",
        ]

        if self.summary:
            lines.extend([f"## 总结\n\n{self.summary}\n"])

        # 按严重程度排序
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.WARNING: 1,
            Severity.INFO: 2,
            Severity.POSITIVE: 3,
        }
        sorted_findings = sorted(
            self.findings,
            key=lambda f: severity_order[f.severity],
        )

        for finding in sorted_findings:
            icon = {
                Severity.CRITICAL: "🔴",
                Severity.WARNING: "🟡",
                Severity.INFO: "ℹ️",
                Severity.POSITIVE: "✅",
            }[finding.severity]

            lines.extend([
                f"### {icon} [{finding.category}] {finding.file}:{finding.line}",
                "",
                f"**{finding.message}**",
                "",
            ])
            if finding.code_snippet:
                lines.extend([
                    "```python",
                    finding.code_snippet,
                    "```",
                    "",
                ])
            if finding.suggestion:
                lines.extend([
                    f"💡 **建议**: {finding.suggestion}",
                    "",
                ])

        return "\n".join(lines)


# ============================================================
# 代码扫描器
# ============================================================

class CodeScanner:
    """代码文件扫描器"""

    # 支持的文件类型
    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".sh": "shell",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".md": "markdown",
    }

    def __init__(self, max_file_size: int = 500_000):
        self.max_file_size = max_file_size

    def scan_directory(self, path: str | Path) -> list[dict]:
        """扫描目录，返回文件列表"""
        path = Path(path)
        files = []

        for root, dirs, filenames in os.walk(path):
            # 跳过隐藏目录和常见忽略目录
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in (
                    "node_modules", "__pycache__", ".git",
                    "venv", ".venv", "dist", "build",
                )
            ]

            for filename in filenames:
                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                if ext not in self.SUPPORTED_EXTENSIONS:
                    continue

                if filepath.stat().st_size > self.max_file_size:
                    continue

                files.append({
                    "path": str(filepath),
                    "language": self.SUPPORTED_EXTENSIONS[ext],
                    "size": filepath.stat().st_size,
                    "lines": self._count_lines(filepath),
                })

        return files

    def read_file(self, path: str | Path) -> str:
        """读取文件内容"""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _count_lines(self, path: Path) -> int:
        try:
            with open(path) as f:
                return sum(1 for _ in f)
        except Exception:
            return 0


# ============================================================
# 静态分析器（规则引擎）
# ============================================================

class StaticAnalyzer:
    """
    静态代码分析器 —— 不依赖 LLM 的快速检查

    参考 Claude Code 的代码理解能力，但用规则实现基础检查
    """

    def analyze_python(self, code: str, filepath: str) -> list[ReviewFinding]:
        """Python 代码静态分析"""
        findings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 检查：过长的行
            if len(line) > 120:
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="style",
                    message=f"行过长 ({len(line)} 字符，建议 ≤ 120)",
                    suggestion="考虑换行或使用括号隐式续行",
                    code_snippet=line[:80] + "...",
                ))

            # 检查：硬编码的密钥模式
            secret_patterns = [
                (r'(?:password|passwd|pwd|secret|token|api_key)\s*=\s*["\'][^"\']{8,}["\']',
                 "可能包含硬编码的密钥"),
                (r'(?:AKIA[0-9A-Z]{16})',
                 "发现 AWS Access Key"),
                (r'(?:sk-[a-zA-Z0-9]{20,})',
                 "发现可能的 API Key"),
            ]
            for pattern, msg in secret_patterns:
                if re.search(pattern, stripped):
                    findings.append(ReviewFinding(
                        file=filepath,
                        line=i,
                        severity=Severity.CRITICAL,
                        category="security",
                        message=msg,
                        suggestion="使用环境变量或密钥管理服务",
                        code_snippet=stripped[:80],
                    ))

            # 检查：bare except
            if re.match(r"except\s*:", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.WARNING,
                    category="error_handling",
                    message="使用了 bare except，会捕获所有异常",
                    suggestion="使用 except Exception: 或具体异常类型",
                    code_snippet=stripped,
                ))

            # 检查：print 调试代码
            if re.match(r"print\s*\(", stripped) and "logging" not in code[:500]:
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="debug",
                    message="使用 print 调试，建议使用 logging 模块",
                    suggestion="import logging; logging.debug(...)",
                    code_snippet=stripped[:80],
                ))

            # 检查：TODO/FIXME 注释
            if re.match(r"#\s*(TODO|FIXME|HACK|XXX|BUG)", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="maintenance",
                    message=stripped,
                    suggestion="及时处理待办事项",
                    code_snippet=stripped,
                ))

        # 检查：文件级问题
        if "import *" in code:
            findings.append(ReviewFinding(
                file=filepath,
                line=0,
                severity=Severity.WARNING,
                category="imports",
                message="使用了通配符导入 (import *)",
                suggestion="显式导入需要的模块",
            ))

        if len(code.split("\n")) > 500:
            findings.append(ReviewFinding(
                file=filepath,
                line=0,
                severity=Severity.INFO,
                category="architecture",
                message=f"文件过长 ({len(code.split(chr(10)))} 行)",
                suggestion="考虑拆分为多个模块",
            ))

        return findings

    def analyze_javascript(self, code: str, filepath: str) -> list[ReviewFinding]:
        """JavaScript 代码静态分析"""
        findings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 检查：过长的行
            if len(line) > 120:
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="style",
                    message=f"行过长 ({len(line)} 字符，建议 ≤ 120)",
                    suggestion="考虑换行",
                    code_snippet=line[:80] + "...",
                ))

            # 检查：console.log
            if re.search(r"console\.(log|warn|error|debug)\(", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="debug",
                    message="发现 console.log，生产环境应移除",
                    suggestion="使用正式日志库或移除",
                    code_snippet=stripped[:80],
                ))

            # 检查：eval 调用
            if re.search(r"\beval\s*\(", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.CRITICAL,
                    category="security",
                    message="使用 eval() 存在安全风险",
                    suggestion="使用 JSON.parse 或其他安全方法",
                    code_snippet=stripped[:80],
                ))

            # 检查：var 声明
            if re.match(r"var\s+\w+", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.WARNING,
                    category="style",
                    message="使用 var 声明，建议使用 let/const",
                    suggestion="使用 let 或 const 替代 var",
                    code_snippet=stripped[:80],
                ))

            # 检查：TODO/FIXME 注释
            if re.match(r"//\s*(TODO|FIXME|HACK|XXX|BUG)", stripped):
                findings.append(ReviewFinding(
                    file=filepath,
                    line=i,
                    severity=Severity.INFO,
                    category="maintenance",
                    message=stripped,
                    suggestion="及时处理待办事项",
                    code_snippet=stripped,
                ))

        return findings


# ============================================================
# LLM 审查器
# ============================================================

class LLMReviewer:
    """
    基于 LLM 的代码审查

    使用 LLM 进行深度代码分析，补充静态分析的不足
    """

    REVIEW_PROMPT = """你是一个资深代码审查专家。请审查以下代码，找出：

1. 🔴 安全问题（必须修复）
2. 🟡 代码质量问题（建议修复）
3. ℹ️  风格和改进建议
4. ✅ 做得好的地方

## 代码

```{language}
{code}
```

## 输出格式

请以 JSON 数组格式返回，每个发现包含：
- category: 类别（security/style/architecture/performance/error_handling）
- severity: 严重程度（critical/warning/info/positive）
- line: 行号（如果适用）
- message: 问题描述
- suggestion: 改进建议

只返回 JSON 数组，不要其他内容。
"""

    SUMMARY_PROMPT = """请根据以下代码审查发现，生成一段简短的总结（200 字以内），
并给出一个 0-100 的代码质量评分。

审查发现：
{findings}

文件统计：
{stats}

请返回 JSON 格式：
{{"summary": "...", "score": 75}}
"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def review_file(
        self,
        code: str,
        filepath: str,
        language: str,
    ) -> list[ReviewFinding]:
        """审查单个文件"""
        if not self.llm_client:
            return []

        # 截断过长的代码
        max_chars = 8000
        if len(code) > max_chars:
            code = code[:max_chars] + "\n# ... (文件已截断)"

        prompt = self.REVIEW_PROMPT.format(
            language=language,
            code=code,
        )

        try:
            response = await self.llm_client.chat(prompt)
            findings = self._parse_findings(response, filepath)
            return findings
        except Exception as e:
            print(f"LLM review failed for {filepath}: {e}")
            return []

    def _parse_findings(
        self, response: str, filepath: str
    ) -> list[ReviewFinding]:
        """解析 LLM 返回的审查结果"""
        findings = []
        try:
            # 尝试提取 JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                findings.append(ReviewFinding(
                    file=filepath,
                    line=item.get("line", 0),
                    severity=Severity(item.get("severity", "info")),
                    category=item.get("category", "general"),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion", ""),
                ))
        except Exception:
            # 解析失败，返回一个通用的发现
            findings.append(ReviewFinding(
                file=filepath,
                line=0,
                severity=Severity.INFO,
                category="llm_review",
                message="LLM 审查完成",
                suggestion=response[:200],
            ))

        return findings


# ============================================================
# 代码审查 Agent
# ============================================================

class CodeReviewAgent:
    """
    自动代码审查 Agent

    工作流程：
    1. 扫描目标目录
    2. 静态分析（快速检查）
    3. LLM 深度分析（可选）
    4. 生成报告
    """

    def __init__(self, llm_client=None, use_llm: bool = True):
        self.scanner = CodeScanner()
        self.static_analyzer = StaticAnalyzer()
        self.llm_reviewer = LLMReviewer(llm_client)
        self.use_llm = use_llm and llm_client is not None

    async def review(self, target: str | Path) -> ReviewReport:
        """执行代码审查"""
        target = Path(target)
        report = ReviewReport(target=str(target))

        # 1. 扫描文件
        files = self.scanner.scan_directory(target)
        print(f"📂 扫描到 {len(files)} 个文件")

        # 2. 逐个分析
        for file_info in files:
            filepath = file_info["path"]
            language = file_info["language"]

            try:
                code = self.scanner.read_file(filepath)
            except Exception as e:
                print(f"  ⚠️  无法读取 {filepath}: {e}")
                continue

            # 静态分析
            if language == "python":
                static_findings = self.static_analyzer.analyze_python(
                    code, filepath
                )
            elif language in ("javascript", "typescript"):
                static_findings = self.static_analyzer.analyze_javascript(
                    code, filepath
                )
            else:
                static_findings = []
            
            report.findings.extend(static_findings)

            # LLM 分析
            if self.use_llm:
                llm_findings = await self.llm_reviewer.review_file(
                    code, filepath, language
                )
                report.findings.extend(llm_findings)

            print(f"  ✅ {filepath} ({file_info['lines']} 行)")

        # 3. 计算评分
        report.score = self._calculate_score(report.findings)

        # 4. 生成总结
        report.summary = self._generate_summary(report)

        return report

    def _calculate_score(self, findings: list[ReviewFinding]) -> float:
        """根据审查发现计算质量评分"""
        score = 100.0
        for f in findings:
            if f.severity == Severity.CRITICAL:
                score -= 10
            elif f.severity == Severity.WARNING:
                score -= 5
            elif f.severity == Severity.INFO:
                score -= 1
            elif f.severity == Severity.POSITIVE:
                score += 1
        return max(0, min(100, score))

    def _generate_summary(self, report: ReviewReport) -> str:
        """生成审查总结"""
        parts = [
            f"共审查 {len(report.findings)} 个问题。",
        ]
        if report.critical_count > 0:
            parts.append(f"其中 {report.critical_count} 个严重问题需要立即修复。")
        if report.warning_count > 0:
            parts.append(f"{report.warning_count} 个建议改进项。")
        if report.score >= 80:
            parts.append("整体代码质量良好。")
        elif report.score >= 60:
            parts.append("代码质量中等，建议优先处理严重问题。")
        else:
            parts.append("代码质量需要改善，建议全面重构。")
        return " ".join(parts)


# ============================================================
# 使用示例
# ============================================================

async def main():
    """运行代码审查"""
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."

    # 不使用 LLM 的纯静态分析模式
    agent = CodeReviewAgent(use_llm=False)
    report = await agent.review(target)

    # 输出报告
    print("\n" + report.to_markdown())

    # 保存到文件
    output_path = Path("code_review_report.md")
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    print(f"\n📄 报告已保存到 {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
