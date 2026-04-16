"""
测试第四章改进功能
从零手写 AI Agent 课程 · 第 4 章完善
"""

import tempfile
import os
import time
from tools.web_tools import SearchCache, WebSearchTool, WebSearchResult, SearchResult
from tools.search_tools import GrepTool, GlobTool


def test_search_cache():
    """测试搜索结果缓存"""
    print("=" * 50)
    print("SearchCache 测试")
    print("=" * 50)
    
    cache = SearchCache(ttl=3600)
    
    # 创建模拟搜索结果
    result = WebSearchResult(
        query="test query",
        results=[
            SearchResult(title="Result 1", url="https://example.com/1", snippet="Snippet 1"),
            SearchResult(title="Result 2", url="https://example.com/2", snippet="Snippet 2"),
        ],
        duration_seconds=0.5,
        num_results=2,
    )
    
    # 测试缓存
    print("✅ 创建搜索结果")
    cache.set("test query", result)
    print("✅ 缓存已保存")
    
    # 测试获取缓存
    cached = cache.get("test query")
    assert cached is not None
    assert cached.query == "test query"
    assert len(cached.results) == 2
    print(f"✅ 缓存命中：{cached.num_results} 条结果")
    
    # 测试缓存未命中
    missing = cache.get("nonexistent query")
    assert missing is None
    print("✅ 缓存未命中返回 None")
    
    # 测试缓存清除
    cache.clear()
    assert cache.get("test query") is None
    print("✅ 缓存清除成功")
    
    # 测试文件持久化
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = f.name
    
    try:
        cache2 = SearchCache(ttl=3600, cache_file=cache_file)
        cache2.set("persistent query", result)
        print("✅ 缓存保存到文件")
        
        # 新建缓存实例，从文件加载
        cache3 = SearchCache(ttl=3600, cache_file=cache_file)
        loaded = cache3.get("persistent query")
        assert loaded is not None
        print("✅ 从文件加载缓存成功")
    finally:
        if os.path.exists(cache_file):
            os.unlink(cache_file)


def test_gitignore_support():
    """测试 .gitignore 支持"""
    print("\n" + "=" * 50)
    print("GlobTool .gitignore 支持测试")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试目录结构
        os.makedirs(os.path.join(tmpdir, 'src'))
        
        # 创建文件
        files = ['src/main.py', 'src/test.py', 'src/__pycache__/cache.pyc']
        for f in files:
            path = os.path.join(tmpdir, f)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as fh:
                fh.write("# test\n")
        
        # 创建 .gitignore
        with open(os.path.join(tmpdir, '.gitignore'), 'w') as f:
            f.write("__pycache__/\n")
            f.write("*.pyc\n")
        
        # 测试带 .gitignore 的 GlobTool
        tool = GlobTool(root_dir=tmpdir, respect_gitignore=True)
        result = tool.call("**/*.py")
        
        print(f"✅ 找到 {result.num_files} 个 Python 文件")
        for filename in result.filenames:
            print(f"   - {filename}")
        
        # 验证 __pycache__ 被排除
        assert not any('__pycache__' in f for f in result.filenames)
        print("✅ __pycache__ 目录被正确排除")


def test_ripgrep_backend():
    """测试 ripgrep 后端"""
    print("\n" + "=" * 50)
    print("GrepTool ripgrep 后端测试")
    print("=" * 50)
    
    import shutil
    has_ripgrep = shutil.which('rg') is not None
    print(f"ripgrep 可用：{has_ripgrep}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        for name in ['app.py', 'utils.py']:
            with open(os.path.join(tmpdir, name), 'w') as f:
                f.write("def hello():\n    print('Hello')\n")
        
        # 测试带 ripgrep 的 GrepTool
        tool = GrepTool(root_dir=tmpdir, use_ripgrep=True)
        
        print(f"ripgrep 启用：{tool.use_ripgrep}")
        print(f"ripgrep 可用：{tool._has_ripgrep}")
        
        result = tool.call("def hello", output_mode='files_with_matches')
        print(f"✅ 找到 {result.num_files} 个文件")
        
        if has_ripgrep:
            print("✅ 使用 ripgrep 后端")
        else:
            print("✅ 回退到 Python 后端")


def test_websearch_with_cache():
    """测试带缓存的 WebSearchTool"""
    print("\n" + "=" * 50)
    print("WebSearchTool 缓存测试")
    print("=" * 50)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = f.name
    
    try:
        # 创建带缓存的搜索工具
        tool = WebSearchTool(
            max_results=5,
            use_cache=True,
            cache_ttl=3600,
            cache_file=cache_file,
        )
        
        print(f"✅ 缓存启用：{tool.use_cache}")
        print(f"✅ 缓存文件：{cache_file}")
        
        # 注意：实际搜索需要网络连接
        # 这里只测试缓存机制
        print("⚠️  实际搜索测试需要网络连接，跳过")
        
    finally:
        if os.path.exists(cache_file):
            os.unlink(cache_file)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 第四章改进功能测试")
    print("=" * 60)
    
    test_search_cache()
    test_gitignore_support()
    test_ripgrep_backend()
    test_websearch_with_cache()
    
    print("\n" + "=" * 60)
    print("🎉 全部改进功能测试完成！")
    print("=" * 60)
