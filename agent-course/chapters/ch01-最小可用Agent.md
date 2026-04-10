# 第 1 章：最小可用 Agent —— 让 AI 说第一句话

> **本章目标**：实现第一个 Agent 类，理解 Agent 的核心循环，完成第一次对话

---

## 🔍 先看 Claude Code 怎么做

Claude Code 的核心入口在 `src/tasks/LocalMainSessionTask.ts`。简化后的核心逻辑：

```typescript
// Claude Code 的核心循环（简化版）
async function mainLoop() {
  while (true) {
    // 1. 构建消息历史
    const messages = buildMessageHistory();
    
    // 2. 调用 LLM
    const response = await callLLM(messages);
    
    // 3. 处理响应（工具调用 or 文本回复）
    if (response.hasToolCalls) {
      const results = await executeTools(response.toolCalls);
      messages.push({ role: "tool", content: results });
    } else {
      // 回复用户
      displayResponse(response.text);
      break; // 或继续等待下一轮
    }
  }
}
```

**核心发现**：Agent 的本质就是一个 `while` 循环。LLM 是大脑，循环是心脏。

---

## 🧠 核心概念

### Agent 的最小实现

一个最小可用的 Agent 只需要：

1. **一个类**：封装状态和行为
2. **一个循环**：持续与 LLM 交互
3. **消息历史**：记住对话上下文
4. **API 调用**：连接 LLM

### 消息格式

LLM 对话的消息格式是统一的：

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

---

## 💻 动手实现

### 第一步：Agent 核心类

创建 `agent.py`：

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
        
        # 消息历史
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
        """重置对话历史"""
        self.messages = [self.messages[0]]  # 保留 system prompt


# === 测试运行 ===
if __name__ == "__main__":
    # 创建 Agent
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

| 代码段 | 作用 |
|---|---|
| `self.messages` | 消息历史，初始包含 system prompt |
| `chat()` | 核心方法：添加用户消息 → 调用 LLM → 保存回复 → 返回 |
| `reset()` | 清空历史，保留 system prompt |
| `if __name__ == "__main__"` | 测试入口，交互式对话 |

### 第二步：支持流式输出

上面的实现是一次性返回全部文本。让我们加上流式输出，体验更好：

```python
    def chat_stream(self, user_input: str) -> str:
        """流式对话，逐字输出"""
        self.messages.append({"role": "user", "content": user_input})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=True,  # 开启流式
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
```

### 第三步：支持 Anthropic Claude

如果你的 API 是 Anthropic 的，只需要换一个客户端：

```python
import anthropic

class ClaudeAgent:
    """基于 Claude 的 Agent"""
    
    def __init__(self, system_prompt: str = "你是一个有用的 AI 助手。"):
        self.client = anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.messages = []  # Claude 的 system prompt 单独传
    
    def chat(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.messages,
        )
        
        reply = response.content[0].text
        self.messages.append({"role": "assistant", "content": reply})
        return reply
```

**关键区别**：
- OpenAI：system prompt 放在 messages 里
- Anthropic：system prompt 作为独立参数传入

---

## 🧪 测试验证

```bash
# 设置 API 密钥
export OPENAI_API_KEY="sk-..."

# 运行
python agent.py

# 测试对话
你: 1+1等于几？
🤖: 1+1等于2。

你: 用Python写一个快速排序
🤖: def quick_sort(arr):
        if len(arr) <= 1:
            return arr
        pivot = arr[len(arr) // 2]
        left = [x for x in arr if x < pivot]
        middle = [x for x in arr if x == pivot]
        right = [x for x in arr if x > pivot]
        return quick_sort(left) + middle + quick_sort(right)
```

---

## 📝 本章小结

- Agent 的本质 = LLM + 循环 + 消息历史
- `Agent` 类封装了状态（消息历史）和行为（对话）
- 流式输出提升用户体验
- OpenAI 和 Anthropic 的 API 格式略有不同，但核心逻辑一致

---

## 🏋️ 课后练习

1. 运行上面的代码，完成至少 5 轮对话
2. 修改 system prompt，让 Agent 扮演一个特定角色（比如"你是一个 Python 编程老师"）
3. 实现一个 `chat_history()` 方法，打印完整的对话历史
4. 思考：当前的 Agent 有什么局限性？（提示：它只能"说话"，不能"做事"）

**答案提示**：当前 Agent 的局限性——没有工具调用能力，只能生成文本，无法执行实际操作（读写文件、运行代码、搜索网络等）。下一章我们将解决这个问题。

---

**下一章**：[第 2 章：工具调用 —— 让 AI 有手有脚](ch02-工具调用.md)
