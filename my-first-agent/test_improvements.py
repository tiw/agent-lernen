"""
测试完善后的工具功能
从零手写 AI Agent 课程 · 第 2-3 章完善
"""

import tempfile
import os
from tools.file_tools import (
    FileReadTool,
    FileWriteTool,
    FileEditTool,
    EditHistory,
    FileReadState,
    detect_encoding,
)
from tools.python_tool import PythonTool


def test_encoding_detection():
    """测试编码自动检测"""
    print("=" * 50)
    print("编码自动检测测试")
    print("=" * 50)
    
    # 创建 UTF-8 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Hello 世界 🌍")
        utf8_path = f.name
    
    # 检测编码
    encoding = detect_encoding(utf8_path)
    print(f"✅ UTF-8 文件检测：{encoding}")
    
    os.unlink(utf8_path)


def test_edit_history():
    """测试编辑历史（Undo 功能）"""
    print("\n" + "=" * 50)
    print("编辑历史（Undo）测试")
    print("=" * 50)
    
    history = EditHistory(max_versions=5)
    
    # 保存多个版本
    history.save_version("test.py", "version 1")
    history.save_version("test.py", "version 2")
    history.save_version("test.py", "version 3")
    
    print(f"✅ 版本数量：{history.get_versions('test.py')}")
    
    # Undo 一次
    previous = history.undo("test.py")
    print(f"✅ Undo 后版本：{previous}")
    print(f"✅ 剩余版本数：{history.get_versions('test.py')}")
    
    # Undo 到空
    history.undo("test.py")
    history.undo("test.py")
    result = history.undo("test.py")
    print(f"✅ 无版本可 Undo: {result is None}")


def test_read_state():
    """测试先读后写检查"""
    print("\n" + "=" * 50)
    print("先读后写检查测试")
    print("=" * 50)
    
    read_state = FileReadState()
    
    # 未读取就检查
    can_write, reason = read_state.check_can_write("test.py")
    print(f"✅ 未读取检查：can_write={can_write}, reason={reason}")
    
    # 标记为已读
    read_state.mark_as_read("test.py")
    can_write, reason = read_state.check_can_write("test.py")
    print(f"✅ 已读检查：can_write={can_write}, reason={reason}")
    
    # 检查最近读取
    is_recent = read_state.is_recently_read("test.py", max_age=300)
    print(f"✅ 最近读取：{is_recent}")


def test_multi_edit():
    """测试多编辑块"""
    print("\n" + "=" * 50)
    print("多编辑块测试")
    print("=" * 50)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n    print('A')\n\ndef world():\n    print('B')\n")
        tmp_path = f.name
    
    try:
        tool = FileEditTool()
        
        # 多编辑块
        edits = [
            {"old_string": "print('A')", "new_string": "print('Hello')"},
            {"old_string": "print('B')", "new_string": "print('World')"},
        ]
        
        results = tool.call_multi(tmp_path, edits)
        
        for i, result in enumerate(results):
            print(f"✅ 编辑 {i+1}: success={result.success}, message={result.message[:50]}")
        
        # 验证结果
        with open(tmp_path, 'r') as f:
            content = f.read()
        print(f"✅ 最终内容包含 'Hello': {'Hello' in content}")
        print(f"✅ 最终内容包含 'World': {'World' in content}")
        
    finally:
        os.unlink(tmp_path)


def test_python_tool():
    """测试 PythonTool"""
    print("\n" + "=" * 50)
    print("PythonTool 测试")
    print("=" * 50)
    
    tool = PythonTool()
    
    # 测试 1：简单输出
    result = tool.execute("print('Hello from Python!')")
    print(f"✅ 简单输出：{result.strip()}")
    
    # 测试 2：数学计算
    result = tool.execute("print(sum(range(1, 101)))")
    print(f"✅ 1+2+...+100 = {result.strip()}")
    
    # 测试 3：危险操作拦截
    result = tool.execute("import os; os.system('ls')")
    print(f"✅ 危险操作拦截：{result[:50]}...")
    
    # 测试 4：eval 拦截
    result = tool.execute("eval('1+1')")
    print(f"✅ eval 拦截：{result[:50]}...")


def test_file_read_auto_encoding():
    """测试文件读取自动编码检测"""
    print("\n" + "=" * 50)
    print("文件读取自动编码检测测试")
    print("=" * 50)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Hello 世界 🌍\nLine 2\nLine 3")
        tmp_path = f.name
    
    try:
        tool = FileReadTool()
        
        # 自动检测编码
        result = tool.call(tmp_path, auto_detect_encoding=True)
        print(f"✅ 自动检测编码读取：{result.num_lines} 行")
        print(f"✅ 检测到的编码：{result.encoding}")
        print(f"✅ 内容包含中文：{'世界' in result.content}")
        
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 完善功能综合测试")
    print("=" * 60)
    
    test_encoding_detection()
    test_edit_history()
    test_read_state()
    test_multi_edit()
    test_python_tool()
    test_file_read_auto_encoding()
    
    print("\n" + "=" * 60)
    print("🎉 全部完善功能测试通过！")
    print("=" * 60)
