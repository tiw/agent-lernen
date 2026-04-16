# 第三章学习总结：文件系统工具

> 学习时间：2026-04-14  
> 学习状态：✅ 完成  
> 核心收获：让 AI 能读写世界，理解安全沙箱和 SEARCH/REPLACE 编辑机制

---

## 🎯 学习目标

| 目标 | 完成情况 | 备注 |
|------|----------|------|
| 理解文件工具设计原则 | ✅ | 安全性、幂等性、上下文效率 |
| 实现 FileReadTool | ✅ | 分页读取、行号显示、Token 限制 |
| 实现 FileWriteTool | ✅ | 自动创建目录、diff 生成 |
| 实现 FileEditTool | ✅ | SEARCH/REPLACE、全局替换 |
| 实现安全沙箱 | ✅ | 路径校验、设备文件拦截、穿越攻击防护 |
| Agent 集成文件工具 | ✅ | 4 个工具协同工作 |

---

## 📝 核心代码

### 1. 安全沙箱（FileSandbox）

```python
class FileSandbox:
    """安全沙箱：限制文件操作只能在允许的目录内进行"""

    def __init__(self, allowed_dirs: Optional[list[str]] = None):
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]

    def validate_path(self, path: Union[str, Path]) -> Path:
        """校验路径是否在沙箱范围内"""
        resolved = Path(path).resolve()

        # 阻止设备文件
        blocked_devices = {
            '/dev/zero', '/dev/random', '/dev/urandom',
            '/dev/full', '/dev/stdin', '/dev/tty',
        }
        if str(resolved) in blocked_devices:
            raise SandboxViolationError(f"Cannot access device file: {resolved}")

        # 检查是否在允许的目录树内
        for allowed in self.allowed_dirs:
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue

        raise SandboxViolationError(
            f"Path '{resolved}' is outside allowed directories"
        )
```

**关键点**：
- `Path.resolve()` 解析绝对路径，防止 `../../../etc/passwd` 穿越攻击
- `relative_to()` 检查路径是否在允许目录树内
- 设备文件黑名单拦截 `/dev/zero` 等危险文件

### 2. FileReadTool（读取文件）

```python
class FileReadTool:
    """读取文件内容"""

    name = "file_read"
    description = "读取文件内容。支持分页读取（offset/limit）..."

    def call(
        self,
        file_path: str,
        offset: int = 1,
        limit: Optional[int] = None,
        encoding: str = 'utf-8',
    ) -> FileReadResult:
        # 1. 安全校验
        resolved = self.sandbox.validate_path(file_path)

        # 2. 读取全部行
        with open(resolved, 'r', encoding=encoding) as f:
            all_lines = f.readlines()

        # 3. 计算读取范围（分页）
        start = max(0, offset - 1)
        end = start + (limit or self.max_lines)
        end = min(end, total_lines)

        # 4. Token 估算检查
        estimated_tokens = len(content) // 4
        if estimated_tokens > self.max_tokens:
            raise ValueError("File content exceeds maximum tokens")

        return FileReadResult(...)
```

**关键特性**：
- 分页读取（offset/limit）防止大文件撑爆上下文
- Token 限制（默认 25000 tokens）
- 带行号显示（`to_display()` 方法）

### 3. FileWriteTool（写入文件）

```python
class FileWriteTool:
    """写入文件（创建或覆盖）"""

    name = "file_write"

    def call(self, file_path: str, content: str) -> FileWriteResult:
        resolved = self.sandbox.validate_path(file_path)

        # 检测是创建还是更新
        operation = 'update' if resolved.exists() else 'create'

        # 自动创建父目录
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(resolved, 'w', encoding=encoding) as f:
            f.write(content)

        # 生成 diff
        diff = self._make_diff(old_content, content, str(resolved))

        return FileWriteResult(operation=operation, diff=diff)
```

**关键特性**：
- 自动创建父目录（`mkdir(parents=True)`）
- 区分创建/更新操作
- 生成 unified diff 展示变更

### 4. FileEditTool（精准编辑）

```python
class FileEditTool:
    """精准编辑文件（SEARCH/REPLACE 模式）"""

    name = "file_edit"

    def call(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> FileEditResult:
        # 1. 无变化检查
        if old_string == new_string:
            return FileEditResult(success=False, message="No changes to make")

        # 2. 读取文件
        with open(resolved, 'r') as f:
            content = f.read()

        # 3. 查找匹配
        occurrences = content.count(old_string)

        if occurrences == 0:
            return FileEditResult(
                success=False,
                message="String to replace not found in file.\n"
                        "Tip: Make sure the old_string matches exactly..."
            )

        if occurrences > 1 and not replace_all:
            return FileEditResult(
                success=False,
                message=f"Found {occurrences} matches... "
                        "To replace all, set replace_all=True."
            )

        # 4. 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # 5. 写回文件
        with open(resolved, 'w') as f:
            f.write(new_content)

        return FileEditResult(success=True, diff=diff, occurrences=occurrences)
```

**关键特性**：
- 精确匹配替换（old_string → new_string）
- 多处匹配检测与拦截
- 全局替换支持（`replace_all=True`）
- 友好的错误提示（指导用户如何修正）

---

## 🧪 测试结果

### 单元测试

```
==================================================
FileReadTool 测试
==================================================
✅ 全量读取：100 行
✅ 分页读取：第 10-14 行
带行号输出示例:
    10	Line 10: Hello World
    11	Line 11: Hello World
    ...

==================================================
FileWriteTool 测试
==================================================
✅ 创建文件：/tmp/.../sub/deep/test.txt
✅ 更新文件，diff:
--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-Hello, AI Agent!
+Updated content!

==================================================
FileEditTool 测试
==================================================
✅ 编辑成功：The file ... has been updated successfully.
   Diff:
-    print('Hello')
+    print('Hello, World!')
✅ 全局替换：2 处
✅ 未找到匹配：String to replace not found in file...
✅ 多处匹配拦截：Found 2 matches... but replace_all is False.

==================================================
Sandbox 测试
==================================================
✅ 沙箱校验通过：/tmp/test.txt
✅ 沙箱拦截：Path '/etc/passwd' is outside allowed directories
✅ 路径穿越拦截：Path '/etc/passwd' is outside allowed directories

🎉 全部测试通过！
```

### Agent 集成测试

```
测试 1: 创建一个 test.txt 文件，内容是 Hello Agent
→ 调用 file_write({'file_path': 'test.txt', 'content': 'Hello Agent'})
→ 回复：已成功创建 test.txt 文件，内容为 "Hello Agent"。

测试 2: 读取 test.txt 的内容
→ 调用 file_read({'file_path': 'test.txt'})
→ 回复：test.txt 文件的内容是：Hello Agent
```

---

## ⚠️ 遇到的问题与解决

### 问题 1：Python 3.9 类型注解语法

**错误**：
```
TypeError: unsupported operand type(s) for |: 'type' and 'type'
```

**原因**：`str | Path` 是 Python 3.10+ 语法

**解决**：
```python
# Python 3.9 兼容写法
from typing import Union

def validate_path(self, path: Union[str, Path]) -> Path:
    ...
```

### 问题 2：文件工具缺少 name 属性

**错误**：
```
AttributeError: 'FileReadTool' object has no attribute 'name'
```

**原因**：Agent 使用 `tool.name` 构建工具映射，但文件工具是从教程直接复制的，没有继承 Tool 基类

**解决**：为每个文件工具类添加 `name` 和 `description` 类属性，以及 `to_openai_format()` 方法

### 问题 3：沙箱路径穿越攻击

**测试**：
```python
sandbox.validate_path("/tmp/../../../etc/passwd")
```

**验证**：✅ 被正确拦截，因为 `Path.resolve()` 会先解析为 `/etc/passwd`，然后检查不在允许目录内

---

## 📊 教程评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 概念清晰度 | ⭐⭐⭐⭐⭐ | 安全沙箱、SEARCH/REPLACE 讲解清晰 |
| 代码可读性 | ⭐⭐⭐⭐⭐ | 代码结构清晰，注释详细 |
| 实践指导性 | ⭐⭐⭐⭐☆ | 有完整实现和测试 |
| 安全意识 | ⭐⭐⭐⭐⭐ | 沙箱、设备文件拦截、路径穿越防护 |
| 新手友好度 | ⭐⭐⭐⭐☆ | 循序渐进，但需要自己添加 name 属性 |

**总体评分**：⭐⭐⭐⭐⭐（5/5）

**相比第二章的改进**：
- ✅ 更完整的数据类设计（FileReadResult 等）
- ✅ 更友好的错误提示（匹配失败时给出建议）
- ✅ 更强大的安全机制（沙箱、设备文件拦截）

---

## 🔧 教程改进建议

### 1. 增加 Tool 基类继承

教程中文件工具没有继承 Tool 基类，建议统一：

```python
from tools.base import Tool

class FileReadTool(Tool):
    name = "file_read"
    description = "..."
    
    @property
    def parameters(self) -> dict:
        return {...}
    
    def execute(self, **kwargs) -> str:
        result = self.call(**kwargs)
        return str(result)
```

### 2. 增加文件编码自动检测

```python
import chardet

def detect_encoding(file_path: Path) -> str:
    """自动检测文件编码"""
    with open(file_path, 'rb') as f:
        raw = f.read(1024)  # 读取前 1KB
    result = chardet.detect(raw)
    return result['encoding'] or 'utf-8'
```

### 3. 增加编辑历史（Undo 功能）

```python
class EditHistory:
    def __init__(self):
        self.history: dict[str, list[str]] = {}  # file_path → [content_versions]
    
    def save_version(self, file_path: str, content: str):
        if file_path not in self.history:
            self.history[file_path] = []
        self.history[file_path].append(content)
    
    def undo(self, file_path: str) -> Optional[str]:
        if file_path in self.history and len(self.history[file_path]) > 1:
            self.history[file_path].pop()  # 移除当前版本
            return self.history[file_path][-1]  # 返回上一版本
        return None
```

### 4. 增加多编辑块支持

```python
def call_multi(self, edits: list[dict]) -> list[FileEditResult]:
    """一次调用执行多个编辑块"""
    results = []
    for edit in edits:
        result = self.call(**edit)
        results.append(result)
        if not result.success:
            break  # 一个失败则停止
    return results
```

---

## 💡 学习心得

### 核心收获

1. **安全沙箱是关键** — 没有限制的文件访问是危险的
2. **SEARCH/REPLACE 比全量写入更优** — 节省 token，减少冲突
3. **友好的错误提示很重要** — 指导用户如何修正，而非简单报错
4. **数据类让代码更清晰** — FileReadResult 等数据类封装结果和元信息

### 设计启发

1. **Path.resolve() 是防护路径穿越的关键** — 先解析再校验
2. **分页读取防止上下文爆炸** — offset/limit 限制单次读取量
3. **diff 生成帮助理解变更** — unified diff 格式清晰展示差异
4. **多处匹配检测防止误操作** — 要求用户提供更多上下文或开启 replace_all

### 与 Claude Code 对比

| 特性 | Claude Code | 我们的实现 |
|------|-------------|------------|
| 安全沙箱 | ✅ 完整权限系统 | ✅ 基础目录限制 |
| 先读后写 | ✅ 强制检查 | ❌ 未实现 |
| 并发修改检测 | ✅ mtime 检查 | ❌ 未实现 |
| 编辑历史 | ❌ 无 | ❌ 未实现 |
| 多编辑块 | ✅ 支持 | ❌ 未实现 |
| 编码检测 | ✅ 自动 | ❌ 手动指定 |

**后续可以改进的方向**：
1. 实现"先读后写"检查
2. 添加编辑历史（Undo）
3. 实现多编辑块支持
4. 自动编码检测

---

## 📁 项目文件

```
~/my-first-agent/
├── agent.py                   # Ch01: 基础 Agent
├── agent_v2.py                # Ch02: 带 BashTool
├── agent_v3.py                # Ch03: 带文件工具
├── tools/
│   ├── __init__.py
│   ├── base.py                # 工具基类
│   ├── bash_tool.py           # Bash 工具
│   └── file_tools.py          # 文件工具（Read/Write/Edit）
├── test_file_tools.py         # 文件工具单元测试
├── test.txt                   # 测试创建的文件
├── CHAPTER1_SUMMARY.md
├── CHAPTER2_SUMMARY.md
├── CHAPTER3_SUMMARY.md        # 第三章总结（本文件）
├── LEARNING_PROGRESS.md       # 学习进度总览
└── .venv/
```

---

## 📚 下一章预习

**第四章：搜索与网络**

学习目标：
- 实现 GrepTool（内容搜索）
- 实现 GlobTool（文件匹配）
- 实现 WebSearchTool（网络搜索）
- 实现 WebFetchTool（网页抓取）

预习问题：
1. 如何高效搜索大文件内容？
2. 如何处理网络请求的超时和错误？
3. 如何提取网页的正文内容（去除广告、导航等）？

---

## 🏋️ 课后练习完成

| 练习 | 完成情况 | 说明 |
|------|----------|------|
| 文件编码自动检测 | ⏸️ 待完成 | 可以使用 chardet 库 |
| 编辑历史（Undo） | ⏸️ 待完成 | 需要维护版本栈 |
| 多编辑块支持 | ⏸️ 待完成 | call_multi 方法 |
| 沙箱穿越测试 | ✅ 完成 | 路径穿越被正确拦截 |

---

_总结完成时间：2026-04-14_  
_学习时长：约 2 小时_  
_状态：第三章完成 ✅_  
_下一步：继续学习第四章（搜索与网络）_
