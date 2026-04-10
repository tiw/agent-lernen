# 第 1 章：最小可用 Agent —— 让 AI 说第一句话

> **本章目标**：实现第一个 Agent 类，理解 Agent 的核心循环，完成第一次对话
> 
> 🎯 **里程碑进度**：▓░░░░░░░░░ 10% — 让 Agent 能"说话"

---

## 🧠 核心概念

### Agent 的最小实现

一个最小可用的 Agent 只需要 4 样东西：

1. **一个类**：封装状态（消息历史）和行为（对话）
2. **一个循环**：持续与 LLM 交互
3. **消息历史**：记住对话上下文
4. **API 调用**：连接 LLM

不需要框架，不需要复杂架构。就是这四样。

### 消息格式

LLM 对话的消息格式是统一的，所有 LLM 提供商都用这个格式：

```python
messages = [
    {"role": "system", "content": "你是一个有用的助手"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的？"},
]
```

三个角色：
- **system**：系统提示，定义 Agent 的行为和身份
- **user**：用户输入
- **assistant**：AI 的回复

> 💡 **重要**：消息历史是 Agent 的"短期记忆"。没有它，Agent 每次对话都是第一次见面。

---

## 💻 动手实现

### 第一步：创建项目文件

在你的项目目录下创建 `agent.py`：

```bash
cd my-agent
touch agent.py
```

### 第二步：写 Agent 核心类

把下面的代码复制到 `agent.py`：

```python
"""
最小可用 Agent —— 让 AI 说第一句话
从零手写 AI Agent 课程 · 第 1 章
"""

import os
from typing import Optional
from openai import OpenAI


class Agent:
    """最小可用的 AI Agent"""
    
    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
    ):
        # 初始化 LLM 客户端
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        
        # 消息历史（初始包含 system prompt）
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]
    
    def chat(self, user_input: str) -> str:
        """
        与 Agent 对话一次
        
        Args:
            user_input: 用户输入
            
        Returns:
            Agent 的回复
        """
        # 1. 添加用户消息到历史
        self.messages.append({"role": "user", "content": user_input})
        
        # 2. 调用 LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
        )
        
        # 3. 获取回复文本
        reply = response.choices[0].message.content
        
        # 4. 添加助手回复到历史
        self.messages.append({"role": "assistant", "content": reply})
        
        return reply
    
    def reset(self):
        """重置对话历史，保留 system prompt"""
        self.messages = [self.messages[0]]
    
    def chat_stream(self, user_input: str) -> str:
        """流式对话，逐字输出（体验更好）"""
        self.messages.append({"role": "user", "content": user_input})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=True,
        )
        
        full_reply = ""
        print("\n🤖: ", end="", flush=True)
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                full_reply += text
        
        print()  # 换行
        self.messages.append({"role": "assistant", "content": full_reply})
        return full_reply


# === 测试运行 ===
if __name__ == "__main__":
    agent = Agent(
        system_prompt="你是一个简洁的 AI 助手。回答要简短、准确。",
        model="gpt-4o-mini",
    )
    
    print("🤖 Agent 已启动！输入 'quit' 退出\n")
    
    while True:
        user_input = input("你: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 再见！")
            break
        
        reply = agent.chat(user_input)
        print(f"\n🤖: {reply}\n")
```

### 代码解析

| 代码段 | 作用 | 类比 |
|---|---|---|
| `self.messages` | 消息历史 | Agent 的"记忆本" |
| `chat()` | 核心方法 | Agent 的"嘴巴" |
| `reset()` | 清空历史 | Agent 的"失忆药" |
| `chat_stream()` | 流式输出 | 打字机效果 |

### 第三步：运行测试

```bash
# 确保 API 密钥已设置
export OPENAI_API_KEY="sk-..."

# 运行
python agent.py
```

你应该看到：
```
🤖 Agent 已启动！输入 'quit' 退出

你: 1+1等于几？

🤖: 1+1等于2。

你: 用一句话解释什么是递归

🤖: 递归就是函数调用自己，直到满足某个条件为止。
```

> ⚠️ **没有 API 密钥？** 用 Ollama 本地运行：
> ```bash
> # 安装 Ollama: https://ollama.com
> ollama pull qwen2.5
> 
> # 代码中改用 OpenAI 兼容模式
> client = OpenAI(
>     base_url="http://localhost:11434/v1",
>     api_key="ollama"
> )
> ```

---

## 📐 架构说明

这一章我们的 Agent 架构：

```
用户输入 → Agent.chat() → LLM API → 回复
              │
              └─→ 消息历史（记住对话）
```

很简单，对吧？这就是 Agent 的最小形态。

---

## ⚠️ 常见错误

### 错误 1：`AuthenticationError: No API key provided`
**原因**：API 密钥没有设置。
**解决**：
```bash
export OPENAI_API_KEY="sk-..."
# 然后重新运行 python agent.py
```

### 错误 2：`ModuleNotFoundError: No module named 'openai'`
**原因**：没有安装 openai 包。
**解决**：`pip install openai`

### 错误 3：`RateLimitError: Rate limit reached`
**原因**：API 调用太频繁，触发了限流。
**解决**：等几分钟再试，或者检查你的 API 套餐额度。

### 错误 4：Agent "忘记"了之前说的话
**原因**：这不是 bug，是正常行为——如果你每次创建新的 `Agent()` 实例，历史会丢失。
**解决**：确保在同一个 `Agent` 实例上连续调用 `chat()`。

---

## 📝 本章小结

- **Agent = LLM + 循环 + 消息历史**
- `Agent` 类封装了状态（消息历史）和行为（对话）
- 流式输出提升用户体验
- OpenAI 和 Anthropic 的 API 格式略有不同，但核心逻辑一致

### 当前 Agent 的局限性

我们的 Agent 现在只能"说话"，不能"做事"。它无法：
- ❌ 读写文件
- ❌ 执行命令
- ❌ 搜索网络
- ❌ 记住上次对话（重启后历史丢失）

**下一章**，我们给它加上"手和脚"——工具调用能力。

---

## 🏋️ 课后练习

### 练习 1：完成对话测试
运行 `agent.py`，完成至少 5 轮对话。观察 Agent 是否能记住上下文。

### 练习 2：角色扮演
修改 system prompt，让 Agent 扮演特定角色：
```python
agent = Agent(
    system_prompt="你是一个 Python 编程老师。用简单的方式解释概念，并给出代码示例。",
)
```

### 练习 3：实现 `chat_history()` 方法
添加一个方法，打印完整的对话历史：
```python
def chat_history(self) -> str:
    """返回格式化的对话历史"""
    # 你的代码
```

**参考答案**：
```python
def chat_history(self) -> str:
    lines = []
    for msg in self.messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            lines.append(f"[系统] {content}")
        elif role == "user":
            lines.append(f"[你] {content}")
        elif role == "assistant":
            lines.append(f"[Agent] {content}")
    return "\n".join(lines)
```

### 练习 4：思考题
当前的 Agent 有什么局限性？如果让你给它加一个"做事"的能力，你最想加什么？

**思考方向**：
- 它只能生成文本，无法执行实际操作
- 消息历史会无限增长，可能导致 Token 超限
- 没有错误处理（API 失败时直接崩溃）

---

**下一章**：[第 2 章：工具调用 —— 让 AI 有手有脚](ch02-工具调用.md)
