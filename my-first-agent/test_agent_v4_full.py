"""
Agent v4 完整功能测试
测试所有 9 个工具的协同工作
从零手写 AI Agent 课程 · 第 4 章
"""

import os
import sys
from rich.console import Console

console = Console()


def print_header(title: str):
    """打印标题"""
    console.print("\n" + "=" * 60, style="bold cyan")
    console.print(f"  {title}", style="bold cyan")
    console.print("=" * 60, style="bold cyan")


def test_tool_imports():
    """测试工具导入"""
    print_header("测试 1: 工具导入")
    
    try:
        from tools import (
            BashTool,
            PythonTool,
            FileReadTool, FileWriteTool, FileEditTool,
            WebSearchTool, WebFetchTool,
            GrepTool, GlobTool,
        )
        console.print("✅ 所有工具导入成功", style="green")
        
        # 列出所有工具
        tools = [
            ("BashTool", BashTool),
            ("PythonTool", PythonTool),
            ("FileReadTool", FileReadTool),
            ("FileWriteTool", FileWriteTool),
            ("FileEditTool", FileEditTool),
            ("WebSearchTool", WebSearchTool),
            ("WebFetchTool", WebFetchTool),
            ("GrepTool", GrepTool),
            ("GlobTool", GlobTool),
        ]
        
        console.print(f"\n📦 共 {len(tools)} 个工具:", style="bold")
        for name, cls in tools:
            console.print(f"  • {name}: {cls.description[:50]}...", style="dim")
        
        return True
    except Exception as e:
        console.print(f"❌ 工具导入失败：{e}", style="red")
        return False


def test_bash_tool():
    """测试 BashTool"""
    print_header("测试 2: BashTool")
    
    from tools import BashTool
    
    tool = BashTool()
    all_passed = True
    
    # 测试 1: 简单命令
    result = tool.execute("echo 'Hello Agent'")
    if "Hello Agent" in result:
        console.print("✅ 简单命令执行成功", style="green")
    else:
        console.print(f"❌ 简单命令失败：{result}", style="red")
        all_passed = False
    
    # 测试 2: 查看目录
    result = tool.execute("ls -la | head -5")
    if "total" in result or "drwx" in result:
        console.print("✅ 目录查看成功", style="green")
    else:
        console.print(f"⚠️  目录查看结果：{result[:100]}", style="yellow")
        all_passed = False
    
    # 测试 3: 危险命令拦截
    result = tool.execute("rm -rf /")
    if "危险" in result or "拒绝" in result:
        console.print("✅ 危险命令拦截成功", style="green")
    else:
        console.print(f"❌ 危险命令未拦截：{result}", style="red")
        all_passed = False
    
    return all_passed


def test_python_tool():
    """测试 PythonTool"""
    print_header("测试 3: PythonTool")
    
    from tools import PythonTool
    
    tool = PythonTool()
    all_passed = True
    
    # 测试 1: 简单输出
    result = tool.execute("print('Hello from Python')")
    if "Hello from Python" in result:
        console.print("✅ Python 代码执行成功", style="green")
    else:
        console.print(f"❌ Python 代码执行失败：{result}", style="red")
        all_passed = False
    
    # 测试 2: 数学计算
    result = tool.execute("print(sum(range(1, 101)))")
    if "5050" in result:
        console.print("✅ 数学计算正确", style="green")
    else:
        console.print(f"❌ 数学计算错误：{result}", style="red")
        all_passed = False
    
    # 测试 3: 危险操作拦截
    result = tool.execute("import os; os.system('ls')")
    if "危险" in result or "拒绝" in result:
        console.print("✅ 危险操作拦截成功", style="green")
    else:
        console.print(f"❌ 危险操作未拦截：{result}", style="red")
        all_passed = False
    
    return all_passed


def test_file_tools():
    """测试文件工具"""
    print_header("测试 4: 文件工具")
    
    from tools import FileReadTool, FileWriteTool, FileEditTool, FileSandbox
    import tempfile
    
    # 在当前目录创建测试文件（沙箱允许的范围）
    sandbox = FileSandbox(allowed_dirs=[os.getcwd()])
    
    test_dir = os.path.join(os.getcwd(), "test_tmp")
    os.makedirs(test_dir, exist_ok=True)
    all_passed = True
    
    try:
        test_file = os.path.join(test_dir, "test.txt")
        
        # 测试 1: 写入文件
        write_tool = FileWriteTool(sandbox=sandbox)
        result = write_tool.call(test_file, "Hello World\nLine 2\nLine 3")
        if result.operation == "create":
            console.print("✅ 文件创建成功", style="green")
        else:
            console.print(f"❌ 文件操作异常：{result.operation}", style="red")
            all_passed = False
        
        # 测试 2: 读取文件
        read_tool = FileReadTool(sandbox=sandbox)
        result = read_tool.call(test_file)
        if "Hello World" in result.content:
            console.print("✅ 文件读取成功", style="green")
        else:
            console.print(f"❌ 文件读取失败", style="red")
            all_passed = False
        
        # 测试 3: 编辑文件
        edit_tool = FileEditTool(sandbox=sandbox)
        result = edit_tool.call(test_file, "Hello World", "Hello Agent")
        if result.success:
            console.print("✅ 文件编辑成功", style="green")
        else:
            console.print(f"❌ 文件编辑失败：{result.message}", style="red")
            all_passed = False
        
        # 验证编辑结果
        result = read_tool.call(test_file)
        if "Hello Agent" in result.content:
            console.print("✅ 编辑验证成功", style="green")
        else:
            console.print(f"❌ 编辑验证失败", style="red")
            all_passed = False
    
    except Exception as e:
        console.print(f"❌ 文件工具测试异常：{e}", style="red")
        all_passed = False
    finally:
        # 清理测试目录
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
    
    return all_passed


def test_web_tools():
    """测试网络工具"""
    print_header("测试 5: 网络工具")
    
    from tools import WebFetchTool, SearchCache, WebSearchResult, SearchResult
    
    all_passed = True
    
    # 测试 WebFetch（需要网络）
    console.print("🌐 测试 WebFetchTool（需要网络连接）...", style="yellow")
    
    try:
        tool = WebFetchTool(timeout=10)
        result = tool.call("https://httpbin.org/html")
        
        if result.status_code == 200:
            console.print(f"✅ WebFetch 成功：{result.bytes_fetched} bytes", style="green")
        else:
            console.print(f"⚠️  WebFetch 状态码：{result.status_code}", style="yellow")
            all_passed = False
    except Exception as e:
        console.print(f"⚠️  WebFetch 失败（可能是网络问题）：{e}", style="yellow")
        all_passed = False
    
    # 测试 WebSearch 缓存
    console.print("\n📦 测试 SearchCache...", style="yellow")
    
    cache = SearchCache(ttl=3600)
    result = WebSearchResult(
        query="test",
        results=[SearchResult(title="Test", url="https://example.com", snippet="Test")],
        duration_seconds=0.5,
        num_results=1,
    )
    cache.set("test query", result)
    cached = cache.get("test query")
    
    if cached and cached.num_results == 1:
        console.print("✅ SearchCache 工作正常", style="green")
    else:
        console.print("❌ SearchCache 异常", style="red")
        all_passed = False
    
    return all_passed


def test_search_tools():
    """测试搜索工具"""
    print_header("测试 6: 搜索工具")
    
    from tools import GrepTool, GlobTool
    import tempfile
    
    all_passed = True
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        os.makedirs(os.path.join(tmpdir, "src"))
        files = [
            ("src/main.py", "def main():\n    print('Hello')"),
            ("src/utils.py", "def helper():\n    return True"),
            ("README.md", "# Test Project"),
        ]
        
        for filename, content in files:
            path = os.path.join(tmpdir, filename)
            with open(path, 'w') as f:
                f.write(content)
        
        # 测试 GrepTool
        console.print("🔍 测试 GrepTool...", style="yellow")
        grep = GrepTool(root_dir=tmpdir, use_ripgrep=True)
        result = grep.call("def ", output_mode='files_with_matches')
        
        if result.num_files >= 2:
            console.print(f"✅ Grep 找到 {result.num_files} 个文件", style="green")
        else:
            console.print(f"❌ Grep 结果不足：{result.num_files} 个文件", style="red")
            all_passed = False
        
        console.print(f"   ripgrep 可用：{grep._has_ripgrep}", style="dim")
        
        # 测试 GlobTool
        console.print("\n📁 测试 GlobTool...", style="yellow")
        glob = GlobTool(root_dir=tmpdir, respect_gitignore=True)
        result = glob.call("**/*.py")
        
        if result.num_files >= 2:
            console.print(f"✅ Glob 找到 {result.num_files} 个 Python 文件", style="green")
        else:
            console.print(f"❌ Glob 结果不足：{result.num_files} 个文件", style="red")
            all_passed = False
    
    return all_passed


def test_agent_v4():
    """测试 Agent v4 集成"""
    print_header("测试 7: Agent v4 集成")
    
    try:
        from agent_v4 import Agent
        
        console.print("🤖 创建 Agent v4 实例...", style="yellow")
        
        sandbox_dirs = [os.getcwd(), "/tmp"]
        
        # 检查 API 密钥
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            console.print("⚠️  未设置 DASHSCOPE_API_KEY，跳过 Agent 集成测试", style="yellow")
            console.print("   （工具已加载成功，仅无法测试完整 Agent 对话）", style="dim")
            return True  # 工具已加载成功，只是无法测试对话
        
        agent = Agent(
            system_prompt="你是一个有用的 AI 助手。",
            sandbox_dirs=sandbox_dirs,
        )
        
        console.print(f"✅ Agent v4 创建成功", style="green")
        console.print(f"   工具数量：{len(agent.tools)}", style="dim")
        console.print(f"   沙箱目录：{sandbox_dirs}", style="dim")
        
        # 列出所有工具
        console.print("\n📦 可用工具列表:", style="bold")
        for tool in agent.tools:
            console.print(f"  • {tool.name}", style="dim")
        
        return True
    except Exception as e:
        console.print(f"❌ Agent v4 创建失败：{e}", style="red")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    console.print("\n", style="bold")
    console.print("╔" + "═" * 58 + "╗", style="bold cyan")
    console.print("║" + " " * 15 + "Agent v4 完整功能测试" + " " * 15 + "║", style="bold cyan")
    console.print("╚" + "═" * 58 + "╝", style="bold cyan")
    console.print()
    
    # 运行所有测试
    results = []
    
    results.append(("工具导入", test_tool_imports()))
    results.append(("BashTool", test_bash_tool()))
    results.append(("PythonTool", test_python_tool()))
    results.append(("文件工具", test_file_tools()))
    results.append(("网络工具", test_web_tools()))
    results.append(("搜索工具", test_search_tools()))
    results.append(("Agent v4 集成", test_agent_v4()))
    
    # 总结
    print_header("测试总结")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        console.print(f"{status} {name}", style="green" if result else "red")
    
    console.print()
    console.print(f"📊 测试结果：{passed}/{total} 通过", style="bold cyan")
    
    if passed == total:
        console.print("\n🎉 所有测试通过！Agent v4 准备就绪！", style="bold green")
        return 0
    else:
        console.print(f"\n⚠️  {total - passed} 个测试未通过，请检查", style="yellow")
        return 1


if __name__ == "__main__":
    sys.exit(main())
