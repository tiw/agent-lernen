"""
测试文件工具
从零手写 AI Agent 课程 · 第 3 章
"""

import tempfile
import os
from tools.file_tools import (
    FileReadTool, FileWriteTool, FileEditTool,
    FileSandbox, create_file_tools,
)


def test_file_read():
    """测试文件读取"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for i in range(1, 101):
            f.write(f"Line {i}: Hello World\n")
        tmp_path = f.name

    try:
        tool = FileReadTool()

        # 读取全部内容
        result = tool.call(tmp_path)
        assert result.total_lines == 100
        assert result.num_lines == 100
        assert "Line 1:" in result.content
        print(f"✅ 全量读取：{result.total_lines} 行")

        # 分页读取
        result = tool.call(tmp_path, offset=10, limit=5)
        assert result.start_line == 10
        assert result.num_lines == 5
        assert "Line 10:" in result.content
        print(f"✅ 分页读取：第 {result.start_line}-{result.start_line + result.num_lines - 1} 行")

        # 带行号显示
        display = result.to_display()
        print("带行号输出示例:")
        print(display[:200])
    finally:
        os.unlink(tmp_path)


def test_file_write():
    """测试文件写入"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = FileWriteTool()

        # 创建新文件（自动创建父目录）
        new_file = os.path.join(tmpdir, "sub", "deep", "test.txt")
        result = tool.call(new_file, "Hello, AI Agent!\n")
        assert result.operation == 'create'
        print(f"✅ 创建文件：{result.file_path}")

        # 更新已有文件
        result = tool.call(new_file, "Updated content!\n")
        assert result.operation == 'update'
        assert result.diff  # 应该有 diff
        print(f"✅ 更新文件，diff:\n{result.diff}")


def test_file_edit():
    """测试精准编辑"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n")
        f.write("    print('Hello')\n")
        f.write("    return True\n")
        f.write("\n")
        f.write("def goodbye():\n")
        f.write("    print('Goodbye')\n")
        tmp_path = f.name

    try:
        tool = FileEditTool()

        # 精确替换
        result = tool.call(
            tmp_path,
            old_string="    print('Hello')",
            new_string="    print('Hello, World!')",
        )
        assert result.success
        print(f"✅ 编辑成功：{result.message}")
        print(f"   Diff:\n{result.diff}")

        # 全局替换
        result = tool.call(
            tmp_path,
            old_string="print(",
            new_string="logger.info(",
            replace_all=True,
        )
        assert result.success
        assert result.occurrences == 2
        print(f"✅ 全局替换：{result.occurrences} 处")

        # 未找到匹配
        result = tool.call(tmp_path, old_string="nonexistent", new_string="x")
        assert not result.success
        print(f"✅ 未找到匹配：{result.message[:60]}...")

        # 多处匹配但未开启 replace_all
        result = tool.call(tmp_path, old_string="def ", new_string="async def ")
        assert not result.success
        print(f"✅ 多处匹配拦截：{result.message[:60]}...")

    finally:
        os.unlink(tmp_path)


def test_sandbox():
    """测试安全沙箱"""
    sandbox = FileSandbox(allowed_dirs=["/tmp"])

    # 允许的路径
    path = sandbox.validate_path("/tmp/test.txt")
    print(f"✅ 沙箱校验通过：{path}")

    # 越权路径
    try:
        sandbox.validate_path("/etc/passwd")
        assert False, "Should have raised"
    except Exception as e:
        print(f"✅ 沙箱拦截：{e}")
    
    # 路径穿越攻击测试
    try:
        sandbox.validate_path("/tmp/../../../etc/passwd")
        assert False, "Should have raised"
    except Exception as e:
        print(f"✅ 路径穿越拦截：{e}")


if __name__ == "__main__":
    print("=" * 50)
    print("FileReadTool 测试")
    print("=" * 50)
    test_file_read()

    print("\n" + "=" * 50)
    print("FileWriteTool 测试")
    print("=" * 50)
    test_file_write()

    print("\n" + "=" * 50)
    print("FileEditTool 测试")
    print("=" * 50)
    test_file_edit()

    print("\n" + "=" * 50)
    print("Sandbox 测试")
    print("=" * 50)
    test_sandbox()

    print("\n🎉 全部测试通过！")
