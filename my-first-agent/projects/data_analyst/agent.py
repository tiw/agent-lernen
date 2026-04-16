"""
项目 3：数据分析 Agent

功能：
- 读取 CSV/JSON/Excel 数据
- 自动数据探索（描述性统计、分布分析）
- 自然语言查询数据
- 生成可视化图表
- 输出分析报告

架构参考：Claude Code 的工具组合能力 + 多步任务编排
"""

import asyncio
import json
import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============================================================
# 数据工具集
# ============================================================

class DataTools:
    """数据分析工具集"""

    def load_csv(self, path: str | Path) -> dict:
        """加载 CSV 文件"""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        return {
            "path": str(path),
            "columns": list(rows[0].keys()) if rows else [],
            "row_count": len(rows),
            "sample": rows[:5],
            "raw": rows,
        }

    def load_json(self, path: str | Path) -> dict:
        """加载 JSON 文件"""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, list):
            return {
                "path": str(path),
                "columns": list(data[0].keys()) if data else [],
                "row_count": len(data),
                "sample": data[:5],
                "raw": data,
            }
        else:
            return {
                "path": str(path),
                "columns": ["key", "value"],
                "row_count": len(data) if isinstance(data, dict) else 0,
                "sample": dict(list(data.items())[:5]) if isinstance(data, dict) else data,
                "raw": data,
            }

    def describe(self, data: dict) -> dict:
        """描述性统计"""
        rows = data.get("raw", [])
        if not rows:
            return {"error": "无数据"}

        columns = data["columns"]
        stats = {}

        for col in columns:
            values = [row.get(col) for row in rows if col in row]

            # 尝试数值转换
            numeric_values = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            if len(numeric_values) > len(values) * 0.5:
                # 数值列
                numeric_values.sort()
                stats[col] = {
                    "type": "numeric",
                    "count": len(numeric_values),
                    "min": numeric_values[0],
                    "max": numeric_values[-1],
                    "mean": sum(numeric_values) / len(numeric_values),
                    "median": numeric_values[len(numeric_values) // 2],
                    "missing": len(values) - len(numeric_values),
                }
            else:
                # 分类列
                unique = set(str(v) for v in values if v is not None)
                stats[col] = {
                    "type": "categorical",
                    "count": len(values),
                    "unique": len(unique),
                    "missing": len(values) - len(set(str(v) for v in values)),
                    "top_values": self._top_values(values, 5),
                }

        return {
            "row_count": len(rows),
            "column_count": len(columns),
            "columns": stats,
        }

    def query(self, data: dict, condition: str) -> dict:
        """
        简单数据查询

        支持的条件格式：
        - "column > value"
        - "column == value"
        - "column contains value"
        """
        rows = data.get("raw", [])
        parts = condition.split(maxsplit=2)

        if len(parts) < 3:
            return {"error": "查询条件格式错误", "format": "column operator value"}

        col, op, val = parts
        filtered = []

        for row in rows:
            cell = row.get(col, "")

            try:
                if op == ">":
                    if float(cell) > float(val):
                        filtered.append(row)
                elif op == "<":
                    if float(cell) < float(val):
                        filtered.append(row)
                elif op == "==":
                    if str(cell) == val:
                        filtered.append(row)
                elif op == "contains":
                    if val.lower() in str(cell).lower():
                        filtered.append(row)
                elif op == "!=":
                    if str(cell) != val:
                        filtered.append(row)
            except (ValueError, TypeError):
                continue

        return {
            "matched": len(filtered),
            "total": len(rows),
            "data": filtered[:20],  # 限制返回数量
        }

    def _top_values(self, values: list, n: int) -> list[tuple[str, int]]:
        """获取最常见的值"""
        counter = Counter(str(v) for v in values if v is not None)
        return counter.most_common(n)


# ============================================================
# 可视化器
# ============================================================

class Visualizer:
    """数据可视化工具"""

    def __init__(self, output_dir: str | Path = "charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def bar_chart(self, data: dict, column: str) -> Path:
        """生成条形图（ASCII 版本，无需 matplotlib）"""
        stats = data.get("columns", {}).get(column, {})
        if stats.get("type") != "categorical":
            raise ValueError(f"列 {column} 不是分类列")

        top_values = stats.get("top_values", [])
        if not top_values:
            raise ValueError(f"列 {column} 没有数据")

        max_count = max(c for _, c in top_values)
        max_label_len = max(len(str(v)) for v, _ in top_values)

        lines = [f"\n📊 {column} 分布：\n"]
        for value, count in top_values:
            bar_len = int(count / max_count * 40) if max_count > 0 else 0
            bar = "█" * bar_len
            label = str(value).ljust(max_label_len)
            lines.append(f"  {label} │ {bar} {count}")

        result = "\n".join(lines)

        # 同时保存到文件
        output_path = self.output_dir / f"{column}_bar.txt"
        output_path.write_text(result, encoding="utf-8")

        return output_path

    def summary_table(self, description: dict) -> str:
        """生成汇总表格"""
        lines = [
            "\n📋 数据概览：",
            "",
            f"  行数：{description['row_count']}",
            f"  列数：{description['column_count']}",
            "",
            "  列详情：",
            "",
        ]

        for col, stats in description["columns"].items():
            if stats["type"] == "numeric":
                lines.append(
                    f"  📈 {col} (数值): "
                    f"min={stats['min']:.1f}, "
                    f"max={stats['max']:.1f}, "
                    f"mean={stats['mean']:.1f}, "
                    f"median={stats['median']:.1f}"
                )
            else:
                lines.append(
                    f"  📊 {col} (分类): "
                    f"{stats['unique']} 个唯一值，"
                    f"{stats['missing']} 个缺失"
                )

        return "\n".join(lines)


# ============================================================
# 数据分析 Agent
# ============================================================

class DataAnalystAgent:
    """
    数据分析 Agent

    工作流程：
    1. 加载数据
    2. 自动探索（描述性统计）
    3. 生成可视化
    4. 回答自然语言问题
    5. 输出分析报告
    """

    def __init__(self, llm_client=None):
        self.tools = DataTools()
        self.visualizer = Visualizer()
        self.llm_client = llm_client
        self.data = None
        self.description = None

    async def load(self, path: str | Path) -> dict:
        """加载数据文件"""
        path = Path(path)
        ext = path.suffix.lower()

        if ext == ".csv":
            self.data = self.tools.load_csv(path)
        elif ext == ".json":
            self.data = self.tools.load_json(path)
        else:
            raise ValueError(f"不支持的文件格式：{ext}")

        self.description = self.tools.describe(self.data)
        return self.description

    async def explore(self) -> str:
        """探索数据"""
        if not self.description:
            return "请先加载数据"

        table = self.visualizer.summary_table(self.description)

        # 生成可视化
        for col, stats in self.description["columns"].items():
            if stats["type"] == "categorical" and stats.get("unique", 0) <= 20:
                try:
                    self.visualizer.bar_chart(self.description, col)
                except Exception:
                    pass

        return table

    async def query(self, condition: str) -> dict:
        """查询数据"""
        if not self.data:
            return {"error": "请先加载数据"}
        return self.tools.query(self.data, condition)

    async def analyze(self, question: str) -> str:
        """
        用自然语言提问

        如果有 LLM，让 LLM 分析数据并回答
        否则，返回基本的统计信息
        """
        if not self.data:
            return "请先加载数据"

        if self.llm_client:
            context = json.dumps({
                "description": self.description,
                "sample": self.data.get("sample", [])[:3],
            }, ensure_ascii=False)[:3000]

            prompt = f"""你是一个数据分析专家。基于以下数据信息，回答用户的问题。

数据描述：
{context}

用户问题：{question}

请给出具体的分析结果和结论。
"""
            try:
                return await self.llm_client.chat(prompt)
            except Exception as e:
                return f"分析失败：{e}"

        # 无 LLM 时的基础回答
        return (
            f"数据包含 {self.description['row_count']} 行，"
            f"{self.description['column_count']} 列。\n"
            f"请使用 explore() 查看数据概览，"
            f"或使用 query() 进行条件查询。"
        )

    def generate_report(self) -> str:
        """生成完整的数据分析报告"""
        if not self.description:
            return "请先加载数据"

        lines = [
            "# 数据分析报告",
            "",
            self.visualizer.summary_table(self.description),
            "",
            "## 数据样本",
            "",
            "```",
        ]

        # 显示前 5 行
        for row in self.data.get("sample", [])[:5]:
            lines.append(json.dumps(row, ensure_ascii=False))

        lines.extend(["```", ""])
        return "\n".join(lines)


# ============================================================
# 使用示例
# ============================================================

async def main():
    import sys

    if len(sys.argv) < 2:
        print("用法：python data_analyst.py <数据文件> [查询条件]")
        print("示例：python data_analyst.py data.csv 'age > 30'")
        return

    data_file = sys.argv[1]

    agent = DataAnalystAgent()

    # 1. 加载数据
    print(f"📂 加载数据：{data_file}")
    desc = await agent.load(data_file)
    print(f"  ✅ {desc['row_count']} 行 × {desc['column_count']} 列")

    # 2. 探索数据
    print("\n🔍 数据探索：")
    explore_result = await agent.explore()
    print(explore_result)

    # 3. 查询（如果提供了条件）
    if len(sys.argv) > 2:
        condition = " ".join(sys.argv[2:])
        print(f"\n🔎 查询：{condition}")
        query_result = await agent.query(condition)
        print(f"  匹配：{query_result.get('matched', 0)}/{query_result.get('total', 0)}")

    # 4. 生成报告
    report = agent.generate_report()
    report_path = Path("data_analysis_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📄 报告已保存到 {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
