"""
测试搜索与网络工具
从零手写 AI Agent 课程 · 第 4 章
"""

import tempfile
import os
from tools.web_tools import WebSearchTool, WebFetchTool
from tools.search_tools import GrepTool, GlobTool


def test_web_search():
    """测试网络搜索（需要网络连接）"""
    print("=" * 50)
    print("WebSearchTool 测试")
    print("=" * 50)
    
    try:
        tool = WebSearchTool(max_results=5)
        result = tool.call("Python 3.13 新特性")
        print(f"✅ 搜索：\"{result.query}\"")
        print(f"   找到 {result.num_results} 条结果，耗时 {result.duration_seconds:.2f}s")
        print(f"   预览：{result.to_display()[:300]}...")
    except ImportError as e:
        print(f"⚠️  跳过 WebSearch 测试：{e}")
    except Exception as e:
        print(f"⚠️  搜索失败（可能需要网络）: {e}")


def test_web_fetch():
    """测试网页抓取"""
    print("\n" + "=" * 50)
    print("WebFetchTool 测试")
    print("=" * 50)
    
    try:
        tool = WebFetchTool(timeout=10)
        # 使用 httpbin 测试页面
        result = tool.call("https://httpbin.org/html")
        print(f"✅ 抓取：{result.url}")
        print(f"   状态码：{result.status_code}")
        print(f"   大小：{result.bytes_fetched} bytes")
        print(f"   内容预览：{result.content[:200]}...")
    except Exception as e:
        print(f"⚠️  抓取失败：{e}")


def test_grep():
    """测试代码搜索"""
    print("\n" + "=" * 50)
    print("GrepTool 测试")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        for name in ['app.py', 'utils.py', 'config.py']:
            with open(os.path.join(tmpdir, name), 'w') as f:
                f.write("import os\n")
                f.write("import sys\n\n")
                f.write("def main():\n")
                f.write("    print('Hello World')\n")
                f.write("    return True\n")

        tool = GrepTool(root_dir=tmpdir)

        # 测试 files_with_matches 模式
        result = tool.call("def main", output_mode='files_with_matches')
        print(f"✅ files_with_matches: 找到 {result.num_files} 个文件")
        print(f"   {result.to_display()}")

        # 测试 content 模式
        result = tool.call("import os", output_mode='content')
        print(f"\n✅ content 模式:")
        print(f"   {result.to_display()}")

        # 测试 count 模式
        result = tool.call("def", output_mode='count')
        print(f"\n✅ count 模式:")
        print(f"   {result.to_display()}")

        # 测试 glob 过滤
        result = tool.call("main", glob='*.py', output_mode='files_with_matches')
        print(f"\n✅ glob 过滤 (*.py): {result.num_files} 个文件")


def test_glob():
    """测试文件模式匹配"""
    print("\n" + "=" * 50)
    print("GlobTool 测试")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试目录结构
        os.makedirs(os.path.join(tmpdir, 'src', 'core'))
        os.makedirs(os.path.join(tmpdir, 'tests'))

        files = [
            'src/main.py', 'src/core/utils.py', 'src/core/__init__.py',
            'tests/test_main.py', 'README.md', 'setup.py',
        ]
        for f in files:
            with open(os.path.join(tmpdir, f), 'w') as fh:
                fh.write("# test\n")

        tool = GlobTool(root_dir=tmpdir)

        # 匹配所有 Python 文件
        result = tool.call("**/*.py")
        print(f"✅ **/*.py: 找到 {result.num_files} 个文件")
        print(f"   {result.to_display()}")

        # 匹配 __init__.py
        result = tool.call("**/__init__.py")
        print(f"\n✅ **/__init__.py: 找到 {result.num_files} 个文件")

        # 匹配 README
        result = tool.call("*.md")
        print(f"\n✅ *.md: 找到 {result.num_files} 个文件")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 第四章：搜索与网络工具测试")
    print("=" * 60)
    
    test_web_search()
    test_web_fetch()
    test_grep()
    test_glob()
    
    print("\n" + "=" * 60)
    print("🎉 全部测试完成！")
    print("=" * 60)
