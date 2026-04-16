# 第二章学习总结：工具调用（Tool Calling）

> 学习时间：2026-04-14  
> 学习状态：✅ 完成  
> 核心收获：让 Agent 从"只会说话"变成"能做事"

---

## 🎯 学习目标

| 目标 | 完成情况 | 备注 |
|------|----------|------|
| 理解 Tool Calling 概念 | ✅ | LLM 请求调用工具而非直接回复 |
| 实现工具基类 | ✅ | Tool 抽象类，统一接口 |
| 实现 BashTool | ✅ | 执行 Shell 命令，带安全检查 |
| Agent 集成工具调用 | ✅ | 核心循环：LLM → 工具 → 结果 → LLM |
| 防止无限循环 | ✅ | max_tool_iterations 限制 |

---

## 📝 核心代码

### 1. 工具基类（tools/base.py）

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    """工具基类（抽象类）"""
    
    name: str = ""
    description: str = ""
    
    @property
    @abstractmethod
    def parameters(self) -> dict:
        """返回工具的参数 schema（JSON Schema 格式）"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具，返回结果字符串"""
        pass
    
    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
```

**关键点**：
- 使用抽象基类（ABC）强制子类实现
- 统一接口：`name`、`description`、`parameters`、`execute()`
- 支持转换为 OpenAI/Anthropic 格式

### 2. BashTool 实现（tools/bash_tool.py）

```python
class BashTool(Tool):
    """执行 Shell 命令的工具"""
    
    name = "bash"
    description = "执行 Shell 命令并返回输出结果"
    
    # 危险命令黑名单
    DANGEROUS_COMMANDS = [
        "rm -rf /", "sudo rm", "mkfs", ":(){:|:&};:", ...
    ]
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"}
            },
            "required": ["command"],
        }
    
    def execute(self, command: str, timeout: int = 30) -> str:
        # 安全检查
        if self._is_dangerous(command):
            return "[错误] 检测到危险命令，已拒绝执行"
        
        # 执行命令
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr
```

**关键点**：
- 安全检查：危险命令黑名单
- 超时保护：防止命令卡死
- 输出限制：防止 token 爆炸（>10000 字符截断）

### 3. Agent 集成工具调用（agent_v2.py）

```python
class Agent:
    def __init__(self, tools: Optional[List[Tool]] = None):
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.max_tool_iterations = 10  # 防止无限循环
    
    def chat(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        tool_defs = [t.to_openai_format() for t in self.tools]
        
        # 核心循环
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # 调用 LLM（带工具定义）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_defs,
            )
            
            message = response.choices[0].message
            
            # 情况 1: LLM 要调用工具
            if message.tool_calls:
                self.messages.append(message)
                
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    result = self.tool_map[tool_name].execute(**tool_args)
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                
                continue  # 继续循环，让 LLM 处理结果
            
            # 情况 2: LLM 直接回复
            reply = message.content
            self.messages.append({"role": "assistant", "content": reply})
            return reply
        
        return "[错误] 工具调用次数过多，已终止"
```

**核心循环图解**：

```
用户输入
    ↓
┌─────────────────────┐
│  调用 LLM (带 tools) │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
有 tool_calls   无 tool_calls
    │           │
    ↓           ↓
执行工具     返回回复
    │
    ↓
结果加入 messages
    │
    ↓
continue (继续循环)
```

---

## 🧪 测试结果

### 测试 1：查看目录

```
用户：当前目录下有什么文件？

[内部流程]
🤔 Agent 思考 → 🔧 调用 bash({'command': 'ls -la'})
   ← 结果：total 56, drwxr-xr-x agent_v2.py, agent.py...
🤔 Agent 思考 → 生成回复

回复：当前目录下有以下文件和文件夹：
- agent_v2.py（7465 字节）
- agent.py（3963 字节）
- CHAPTER1_SUMMARY.md...
```

### 测试 2：检查 Python 版本

```
用户：Python 版本是什么？

[内部流程]
🤔 Agent 思考 → 🔧 调用 bash({'command': 'python --version'})
   ← 结果：Python 3.9.6
🤔 Agent 思考 → 生成回复

回复：当前系统使用的 Python 版本是 Python 3.9.6。
```

### 测试 3：危险命令拦截

```python
tool = BashTool()
tool.execute("rm -rf /")
# 返回：[错误] 检测到危险命令，已拒绝执行
```

---

## ⚠️ 遇到的问题与解决

### 问题 1：相对导入错误

**错误**：
```
ImportError: attempted relative import with no known parent package
```

**原因**：直接运行 `bash_tool.py` 时，Python 不知道父包

**解决**：
```python
import sys
import os

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(...)))
    from tools.base import Tool
else:
    from .base import Tool
```

### 问题 2：工具调用无限循环

**风险**：LLM 可能陷入"调用工具 → 结果不满意 → 再调用工具"的循环

**解决**：
```python
max_tool_iterations = 10  # 最大工具调用次数

while iteration < self.max_tool_iterations:
    iteration += 1
    # ...
    
return "[错误] 工具调用次数过多，已终止"
```

### 问题 3：通义千问工具调用格式

**发现**：阿里云通义千问的工具调用格式与 OpenAI 略有不同

**解决**：使用兼容模式 base_url，大部分情况下工作正常。某些复杂场景可能需要调整 tool 格式。

---

## 📊 教程评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 概念清晰度 | ⭐⭐⭐⭐⭐ | 工具调用流程讲解清晰 |
| 代码可读性 | ⭐⭐⭐⭐⭐ | 代码结构清晰，注释详细 |
| 实践指导性 | ⭐⭐⭐⭐☆ | 有完整实现步骤 |
| 安全意识 | ⭐⭐⭐⭐⭐ | 有危险命令黑名单 |
| 新手友好度 | ⭐⭐⭐⭐☆ | 循序渐进，容易跟上 |

**总体评分**：⭐⭐⭐⭐⭐（5/5）

**相比第一章的改进**：
- ✅ 代码更完整（有安全检查、超时保护）
- ✅ 错误处理更友好
- ✅ 有防止无限循环的机制

---

## 🔧 教程改进建议

### 1. 增加更多工具示例

目前只有 BashTool，建议增加：
- `PythonTool`：专门执行 Python 代码
- `FileReadTool`：读取文件内容
- `WebSearchTool`：网络搜索

### 2. 增加工具调用日志

```python
class ToolLogger:
    def log(self, tool_name, args, result, duration):
        print(f"[{datetime.now()}] {tool_name}({args}) → {result[:100]}... ({duration}s)")
```

### 3. 增加工具权限系统

```python
class PermissionSystem:
    def check_permission(self, tool_name, command) -> bool:
        # 基于用户配置、命令类型等判断是否允许执行
        pass
```

### 4. 增加并行工具调用

目前工具调用是串行的，可以优化为并行：
```python
import asyncio

async def execute_tools_parallel(tool_calls):
    tasks = [execute_tool(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks)
    return results
```

---

## 💡 学习心得

### 核心收获

1. **工具调用是 Agent 的灵魂** — 没有工具的 LLM 只是聊天机器人，有工具才是 Agent
2. **安全至关重要** — 执行 Shell 命令必须有安全检查
3. **循环是核心模式** — LLM → 工具 → 结果 → LLM 的循环让 Agent 能完成复杂任务
4. **防止无限循环** — 必须设置最大迭代次数

### 代码设计启发

1. **抽象基类是好东西** — 强制子类实现统一接口
2. **配置优于硬编码** — 危险命令列表可以配置化
3. **日志帮助调试** — 打印工具调用过程帮助理解 Agent 行为
4. **错误处理要友好** — 用户需要知道发生了什么

### 下一步思考

1. 如何实现文件读写工具？
2. 如何让 Agent 自主决定使用哪个工具？
3. 如何评估工具调用的成功率？
4. 如何优化多次工具调用的效率？

---

## 📁 项目文件

```
~/my-first-agent/
├── agent.py                   # 第一章：基础 Agent
├── agent_v2.py                # 第二章：带工具调用的 Agent
├── tools/
│   ├── __init__.py
│   ├── base.py                # 工具基类
│   └── bash_tool.py           # Bash 工具
├── CHAPTER1_SUMMARY.md        # 第一章总结
├── CHAPTER2_SUMMARY.md        # 第二章总结（本文件）
└── .venv/                     # Python 虚拟环境
```

---

## 📚 下一章预习

**第三章：文件系统工具**

学习目标：
- 实现 FileReadTool（读取文件）
- 实现 FileWriteTool（写入文件）
- 实现 FileEditTool（编辑文件）
- 实现 GrepTool（内容搜索）
- 实现 GlobTool（文件匹配）

预习问题：
1. 文件读写需要注意哪些安全问题？
2. 如何高效地搜索文件内容？
3. 如何处理大文件（超过 token 限制）？

---

## 🏋️ 课后练习完成

| 练习 | 完成情况 | 说明 |
|------|----------|------|
| 添加 PythonTool | ⏸️ 待完成 | 可以后续实现 |
| BashTool 安全限制 | ✅ 完成 | 危险命令黑名单 |
| 工具调用日志 | ✅ 完成 | 控制台输出调用过程 |
| 防止无限循环 | ✅ 完成 | max_tool_iterations |

---

_总结完成时间：2026-04-14_  
_学习时长：约 1.5 小时_  
_状态：第二章完成 ✅_  
_下一步：继续学习第三章（文件系统工具）_
