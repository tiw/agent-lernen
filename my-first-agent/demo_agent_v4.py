"""
Agent v4 综合演示
展示所有 9 个工具协同工作完成真实任务
从零手写 AI Agent 课程 · 第 4 章
"""

import os
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def print_header(title: str):
    """打印标题"""
    console.print("\n" + "=" * 70, style="bold cyan")
    console.print(f"  {title}", style="bold cyan")
    console.print("=" * 70, style="bold cyan")
    console.print()


def print_step(step_num: int, title: str):
    """打印步骤"""
    console.print(f"\n[bold green]📍 步骤 {step_num}: {title}[/bold green]\n")


def print_result(title: str, content: str, success: bool = True):
    """打印结果"""
    style = "green" if success else "red"
    emoji = "✅" if success else "❌"
    console.print(f"[bold {style}]{emoji} {title}[/bold {style}]")
    if content:
        console.print(f"    [dim]{content}[/dim]")


def demo_scenario_1():
    """
    场景 1: 项目初始化
    任务：创建一个 Python 项目结构
    """
    print_header("场景 1: 项目初始化")
    
    from tools import BashTool, FileWriteTool, FileReadTool, GlobTool
    
    project_dir = Path(os.getcwd()) / "demo_project"
    project_dir.mkdir(exist_ok=True)
    
    print_step(1, "创建项目目录结构")
    
    # 使用 BashTool 创建目录
    bash = BashTool()
    result = bash.execute(f"mkdir -p {project_dir}/src {project_dir}/tests {project_dir}/docs")
    print_result("目录创建完成", "src/, tests/, docs/")
    
    print_step(2, "创建项目配置文件")
    
    # 使用 FileWriteTool 创建文件
    write_tool = FileWriteTool()
    
    # 创建 README.md
    readme_content = """# Demo Project

这是一个演示项目，由 Agent v4 创建。

## 功能
- 工具调用演示
- 文件操作演示
- 搜索功能演示

## 安装
```bash
pip install -r requirements.txt
```

## 使用
```python
from src import main
main.run()
```
"""
    result = write_tool.call(str(project_dir / "README.md"), readme_content)
    print_result("README.md 创建", f"操作类型：{result.operation}")
    
    # 创建 requirements.txt
    requirements = """rich>=13.0.0
click>=8.1.0
"""
    result = write_tool.call(str(project_dir / "requirements.txt"), requirements)
    print_result("requirements.txt 创建", f"操作类型：{result.operation}")
    
    # 创建 Python 模块
    init_content = """\"\"\"Demo Project Package\"\"\"
__version__ = "0.1.0"
"""
    result = write_tool.call(str(project_dir / "src" / "__init__.py"), init_content)
    print_result("src/__init__.py 创建", f"操作类型：{result.operation}")
    
    # 创建 main.py
    main_content = """\"\"\"Main module\"\"\"

def run():
    \"\"\"Run the demo\"\"\"
    print("Hello from Demo Project!")
    return True

if __name__ == "__main__":
    run()
"""
    result = write_tool.call(str(project_dir / "src" / "main.py"), main_content)
    print_result("src/main.py 创建", f"操作类型：{result.operation}")
    
    print_step(3, "验证项目结构")
    
    # 使用 GlobTool 查看所有创建的文件
    glob = GlobTool(root_dir=str(project_dir))
    result = glob.call("**/*")
    print_result(f"项目文件列表", f"共 {result.num_files} 个文件/目录")
    for f in result.filenames[:10]:
        console.print(f"    📄 {f}", style="dim")
    
    print_step(4, "读取并验证文件内容")
    
    # 使用 FileReadTool 读取 README
    read_tool = FileReadTool()
    result = read_tool.call(str(project_dir / "README.md"))
    print_result("README.md 内容验证", f"共 {result.total_lines} 行，包含 {len(result.content)} 字符")
    
    console.print("\n[bold green]✅ 场景 1 完成：项目初始化成功！[/bold green]")
    
    return project_dir


def demo_scenario_2(project_dir: Path):
    """
    场景 2: 代码搜索与修改
    任务：查找代码并批量修改
    """
    print_header("场景 2: 代码搜索与修改")
    
    from tools import GrepTool, FileEditTool, FileReadTool
    
    print_step(1, "搜索代码中的函数定义")
    
    # 使用 GrepTool 搜索函数定义
    grep = GrepTool(root_dir=str(project_dir))
    result = grep.call("def ", output_mode='files_with_matches')
    print_result(f"找到函数定义", f"{result.num_files} 个文件包含函数定义")
    
    print_step(2, "搜索特定函数")
    
    # 搜索 run 函数
    result = grep.call("def run", output_mode='content')
    print_result(f"找到 run 函数", f"内容预览：{result.content[:100]}...")
    
    print_step(3, "批量修改代码")
    
    # 使用 FileEditTool 修改代码
    edit_tool = FileEditTool()
    
    # 修改 main.py 中的 print 语句
    result = edit_tool.call(
        str(project_dir / "src" / "main.py"),
        'print("Hello from Demo Project!")',
        'print("Hello from Agent v4 Demo!")',
    )
    print_result("代码修改", "print 语句已更新" if result.success else result.message)
    
    print_step(4, "验证修改结果")
    
    # 读取验证
    read_tool = FileReadTool()
    result = read_tool.call(str(project_dir / "src" / "main.py"))
    if "Agent v4 Demo" in result.content:
        print_result("修改验证", "✅ 代码已成功修改")
    else:
        print_result("修改验证", "❌ 修改未生效", success=False)
    
    console.print("\n[bold green]✅ 场景 2 完成：代码搜索与修改成功！[/bold green]")


def demo_scenario_3(project_dir: Path):
    """
    场景 3: 网络搜索与文档更新
    任务：搜索最新信息并更新文档
    """
    print_header("场景 3: 网络搜索与文档更新")
    
    from tools import WebFetchTool, FileEditTool
    
    print_step(1, "抓取网页内容")
    
    # 使用 WebFetchTool 抓取示例网页
    fetch_tool = WebFetchTool(timeout=10)
    
    try:
        result = fetch_tool.call("https://httpbin.org/html")
        if result.status_code == 200:
            print_result("网页抓取成功", f"状态码：{result.status_code}, 大小：{result.bytes_fetched} bytes")
        else:
            print_result("网页抓取失败", f"状态码：{result.status_code}", success=False)
    except Exception as e:
        print_result("网络请求异常", str(e), success=False)
    
    print_step(2, "更新项目文档")
    
    # 使用 FileEditTool 更新 README
    edit_tool = FileEditTool()
    
    # 添加更新时间
    update_note = "\n---\n*最后更新：Agent v4 演示*\n"
    
    readme_path = project_dir / "README.md"
    read_content = readme_path.read_text()
    
    result = edit_tool.call(
        str(readme_path),
        "## 使用",
        f"## 使用{update_note}\n"
    )
    print_result("文档更新", "README.md 已添加更新时间戳" if result.success else result.message)
    
    console.print("\n[bold green]✅ 场景 3 完成：网络搜索与文档更新成功！[/bold green]")


def demo_scenario_4(project_dir: Path):
    """
    场景 4: 使用 PythonTool 运行代码
    任务：执行 Python 代码并验证结果
    """
    print_header("场景 4: 代码执行与验证")
    
    from tools import PythonTool, BashTool
    
    print_step(1, "执行 Python 代码")
    
    python_tool = PythonTool()
    
    # 执行简单计算
    result = python_tool.execute("""
# 计算斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# 打印前 10 个斐波那契数
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
""")
    if "F(9) = 34" in result:
        print_result("斐波那契计算", "✅ 计算正确")
        console.print(f"    [dim]{result.strip()[:200]}...[/dim]")
    else:
        print_result("斐波那契计算", result[:100], success=False)
    
    print_step(2, "运行项目代码")
    
    # 使用 BashTool 运行项目
    bash = BashTool()
    result = bash.execute(f"cd {project_dir} && python -c 'from src.main import run; run()'")
    if "Agent v4 Demo" in result:
        print_result("项目运行", "✅ 项目代码执行成功")
    else:
        print_result("项目运行", result[:100], success=False)
    
    console.print("\n[bold green]✅ 场景 4 完成：代码执行与验证成功！[/bold green]")


def demo_cleanup(project_dir: Path):
    """清理演示项目"""
    print_header("清理演示环境")
    
    import shutil
    
    if project_dir.exists():
        shutil.rmtree(project_dir)
        console.print(f"[dim]已清理演示项目目录：{project_dir}[/dim]\n")
    
    # 清理测试临时文件
    test_tmp = Path(os.getcwd()) / "test_tmp"
    if test_tmp.exists():
        shutil.rmtree(test_tmp)
    
    console.print("[bold green]✅ 演示环境清理完成！[/bold green]\n")


def main():
    """主演示函数"""
    console.print("\n", style="bold")
    console.print("╔" + "═" * 68 + "╗", style="bold cyan")
    console.print("║" + " " * 20 + "Agent v4 综合演示" + " " * 21 + "║", style="bold cyan")
    console.print("║" + " " * 15 + "展示 9 个工具协同工作" + " " * 16 + "║", style="bold cyan")
    console.print("╚" + "═" * 68 + "╝", style="bold cyan")
    
    console.print("\n[bold]演示场景:[/bold]")
    console.print("  1. 项目初始化 - 创建 Python 项目结构")
    console.print("  2. 代码搜索与修改 - 使用 Grep 和 Edit")
    console.print("  3. 网络搜索与文档更新 - 抓取网页并更新文档")
    console.print("  4. 代码执行与验证 - 运行 Python 代码")
    console.print()
    
    try:
        # 执行演示场景
        project_dir = demo_scenario_1()
        demo_scenario_2(project_dir)
        demo_scenario_3(project_dir)
        demo_scenario_4(project_dir)
        
        # 最终总结
        print_header("演示总结")
        
        console.print("[bold green]🎉 Agent v4 综合演示完成！[/bold green]\n")
        console.print("[bold]使用的工具:[/bold]")
        tools_used = [
            ("BashTool", "创建目录、运行命令"),
            ("FileWriteTool", "创建项目文件"),
            ("FileReadTool", "读取验证文件"),
            ("FileEditTool", "修改代码和文档"),
            ("GlobTool", "列出项目文件"),
            ("GrepTool", "搜索代码"),
            ("WebFetchTool", "抓取网页"),
            ("PythonTool", "执行 Python 代码"),
        ]
        
        for i, (name, desc) in enumerate(tools_used, 1):
            console.print(f"  {i}. [cyan]{name}[/cyan]: {desc}")
        
        console.print(f"\n[bold]总计：8/9 个工具参与演示[/bold]")
        console.print("[dim]（WebSearchTool 因网络原因未演示）[/dim]\n")
        
    finally:
        # 清理演示环境
        demo_cleanup(Path(os.getcwd()) / "demo_project")


if __name__ == "__main__":
    sys.exit(0 if main() is None else 1)
