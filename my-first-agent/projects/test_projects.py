"""
测试第 14 章的三个实战项目
"""

import sys
import tempfile
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.code_review.agent import (
    CodeScanner, StaticAnalyzer, CodeReviewAgent,
    ReviewReport, ReviewFinding, Severity
)
from projects.doc_generator.agent import (
    CodebaseAnalyzer, DocGenerator, DocTemplates
)
from projects.data_analyst.agent import (
    DataTools, Visualizer, DataAnalystAgent
)


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ============================================================
# 项目 1：代码审查助手测试
# ============================================================

def test_code_scanner():
    """测试代码扫描器"""
    print_header("1️⃣  代码扫描器测试")
    
    scanner = CodeScanner()
    
    # 扫描当前项目
    files = scanner.scan_directory(Path(__file__).parent.parent)
    
    print(f"\n扫描到 {len(files)} 个文件")
    
    # 显示前 5 个文件
    for f in files[:5]:
        print(f"  - {f['path']} ({f['lines']} 行，{f['language']})")
    
    assert len(files) > 0, "应该扫描到文件"
    assert "path" in files[0], "文件应该有 path 字段"
    assert "language" in files[0], "文件应该有 language 字段"
    
    print("\n✅ 代码扫描器测试通过")


def test_static_analyzer():
    """测试静态分析器"""
    print_header("2️⃣  静态分析器测试")
    
    analyzer = StaticAnalyzer()
    
    # Python 代码测试
    python_code = """
# TODO: 实现这个功能
import *
password = "supersecret123"
sk-abcdefghijklmnopqrstuvwxyz1234567890

def test():
    print("debug")
    try:
        pass
    except:
        pass
"""
    
    findings = analyzer.analyze_python(python_code, "test.py")
    
    print(f"\n发现 {len(findings)} 个问题：")
    for f in findings:
        icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(f.severity.value, "")
        print(f"  {icon} [{f.category}] {f.message}")
    
    # 验证发现的问题
    categories = [f.category for f in findings]
    assert "security" in categories, "应该发现安全问题"
    assert "error_handling" in categories, "应该发现 bare except"
    assert "debug" in categories, "应该发现 print 调试"
    assert "maintenance" in categories, "应该发现 TODO"
    
    print("\n✅ 静态分析器测试通过")


def test_code_review_agent():
    """测试代码审查 Agent"""
    print_header("3️⃣  代码审查 Agent 测试")
    
    agent = CodeReviewAgent(use_llm=False)
    
    # 创建一个临时项目目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 创建测试文件
        test_file = tmpdir / "test.py"
        test_file.write_text("""
# TODO: 实现
password = "secret123"

def hello():
    print("hello")
    except:
        pass
""")
        
        # 执行审查
        report = asyncio.run(agent.review(tmpdir))
        
        print(f"\n审查报告：")
        print(f"  目标：{report.target}")
        print(f"  评分：{report.score:.0f}/100")
        print(f"  问题数：{len(report.findings)}")
        print(f"  严重问题：{report.critical_count}")
        print(f"  警告：{report.warning_count}")
        
        assert report.score >= 0 and report.score <= 100, "评分应该在 0-100 之间"
        assert len(report.findings) > 0, "应该发现一些问题"
        
        # 测试 Markdown 输出
        markdown = report.to_markdown()
        assert "# 代码审查报告" in markdown
        assert "评分" in markdown
        
        print("\n✅ 代码审查 Agent 测试通过")


# ============================================================
# 项目 2：文档生成器测试
# ============================================================

def test_codebase_analyzer():
    """测试代码仓库分析器"""
    print_header("4️⃣  代码仓库分析器测试")
    
    analyzer = CodebaseAnalyzer()
    
    # 分析当前项目
    info = analyzer.analyze(Path(__file__).parent.parent)
    
    print(f"\n项目信息：")
    print(f"  名称：{info['name']}")
    print(f"  文件数：{len(info['files'])}")
    print(f"  总行数：{info['total_lines']}")
    print(f"  总大小：{info['total_size']} 字节")
    print(f"  语言：{info['languages']}")
    print(f"  模块数：{len(info['modules'])}")
    print(f"  依赖数：{len(info['dependencies'])}")
    
    assert info['name'], "应该有项目名称"
    assert len(info['files']) > 0, "应该有文件"
    assert info['total_lines'] > 0, "应该有代码行数"
    
    print("\n✅ 代码仓库分析器测试通过")


def test_doc_generator():
    """测试文档生成器"""
    print_header("5️⃣  文档生成器测试")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "docs"
        
        # 创建一个简单的项目结构
        (tmpdir / "main.py").write_text("print('hello')")
        (tmpdir / "requirements.txt").write_text("requests\n")
        
        generator = DocGenerator()
        
        # 生成 README
        readme = asyncio.run(generator.generate_readme(tmpdir))
        
        print(f"\n生成的 README：")
        print(f"  长度：{len(readme)} 字符")
        print(f"  包含项目名：{tmpdir.name in readme}")
        
        assert "# " in readme, "应该有标题"
        assert "快速开始" in readme, "应该有快速开始部分"
        
        # 生成所有文档
        files = asyncio.run(generator.generate_all(tmpdir, output_dir))
        
        print(f"\n生成了 {len(files)} 个文档：")
        for f in files:
            print(f"  - {f}")
            assert f.exists(), f"文件应该存在：{f}"
        
        print("\n✅ 文档生成器测试通过")


# ============================================================
# 项目 3：数据分析 Agent 测试
# ============================================================

def test_data_tools():
    """测试数据工具"""
    print_header("6️⃣  数据工具测试")
    
    tools = DataTools()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 创建测试 CSV
        csv_file = tmpdir / "test.csv"
        csv_file.write_text("""name,age,city,score
Alice,25,Beijing,85
Bob,30,Shanghai,90
Charlie,35,Guangzhou,75
Diana,28,Shenzhen,95
""")
        
        # 加载 CSV
        data = tools.load_csv(csv_file)
        
        print(f"\n加载数据：")
        print(f"  文件：{data['path']}")
        print(f"  列：{data['columns']}")
        print(f"  行数：{data['row_count']}")
        
        assert data['row_count'] == 4, "应该有 4 行"
        assert 'name' in data['columns'], "应该有 name 列"
        
        # 描述性统计
        desc = tools.describe(data)
        
        print(f"\n描述性统计：")
        print(f"  行数：{desc['row_count']}")
        print(f"  列数：{desc['column_count']}")
        
        for col, stats in desc['columns'].items():
            if stats['type'] == 'numeric':
                print(f"  {col}: mean={stats['mean']:.1f}, min={stats['min']}, max={stats['max']}")
            else:
                print(f"  {col}: {stats['unique']} 个唯一值")
        
        # 查询测试
        result = tools.query(data, "age > 28")
        print(f"\n查询 'age > 28'：匹配 {result['matched']}/{result['total']}")
        
        assert result['matched'] == 2, "应该有 2 行匹配"
        
        print("\n✅ 数据工具测试通过")


def test_visualizer():
    """测试可视化器"""
    print_header("7️⃣  可视化器测试")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        visualizer = Visualizer(tmpdir / "charts")
        
        tools = DataTools()
        
        # 创建测试数据
        csv_file = tmpdir / "test.csv"
        csv_file.write_text("""name,category,value
A,X,10
B,Y,20
C,X,15
D,Z,25
E,Y,30
""")
        
        data = tools.load_csv(csv_file)
        desc = tools.describe(data)
        
        # 生成汇总表格
        table = visualizer.summary_table(desc)
        print(f"\n汇总表格：")
        print(table)
        
        assert "行数" in table
        assert "列数" in table
        
        # 生成条形图
        chart_path = visualizer.bar_chart(desc, "category")
        print(f"\n条形图已保存：{chart_path}")
        
        assert chart_path.exists(), "图表文件应该存在"
        
        chart_content = chart_path.read_text()
        print(f"\n条形图内容：")
        print(chart_content)
        
        assert "█" in chart_content, "应该包含条形图字符"
        
        print("\n✅ 可视化器测试通过")


def test_data_analyst_agent():
    """测试数据分析 Agent"""
    print_header("8️⃣  数据分析 Agent 测试")
    
    agent = DataAnalystAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 创建测试数据
        csv_file = tmpdir / "sales.csv"
        csv_file.write_text("""product,region,sales,price
iPhone,North,100,999
iPhone,South,80,999
Samsung,North,60,799
Samsung,South,90,799
Huawei,North,120,699
Huawei,South,70,699
""")
        
        # 加载数据
        desc = asyncio.run(agent.load(csv_file))
        print(f"\n加载数据：{desc['row_count']} 行 × {desc['column_count']} 列")
        
        assert desc['row_count'] == 6
        
        # 探索数据
        explore = asyncio.run(agent.explore())
        print(f"\n数据探索：")
        print(explore[:500])
        
        # 查询
        result = asyncio.run(agent.query("sales > 80"))
        print(f"\n查询 'sales > 80'：匹配 {result.get('matched', 0)} 行")
        
        assert result.get('matched', 0) >= 2
        
        # 生成报告
        report = agent.generate_report()
        print(f"\n生成报告（{len(report)} 字符）")
        
        assert "# 数据分析报告" in report
        
        print("\n✅ 数据分析 Agent 测试通过")


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🚀" * 30)
    print("  第 14 章：实战项目 - 综合测试")
    print("🚀" * 30)
    
    # 项目 1 测试
    test_code_scanner()
    test_static_analyzer()
    test_code_review_agent()
    
    # 项目 2 测试
    test_codebase_analyzer()
    test_doc_generator()
    
    # 项目 3 测试
    test_data_tools()
    test_visualizer()
    test_data_analyst_agent()
    
    print_header("🎉 所有测试通过")
    print("\n第 14 章实现的三个项目：")
    print("  ✅ 代码审查助手 - 静态分析 + LLM 深度审查")
    print("  ✅ 智能文档生成器 - 代码仓库分析 + 文档生成")
    print("  ✅ 数据分析 Agent - 数据加载 + 探索 + 查询 + 可视化")
    print()


if __name__ == "__main__":
    main()
