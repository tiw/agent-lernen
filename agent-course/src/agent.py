"""
最小可用 Agent —— 让 AI 说第一句话
从零手写 AI Agent 课程 · 第 1-2 章
"""

import os
import json
from typing import Optional, List

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class Agent:
    """支持工具调用的 Agent"""

    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "gpt-4o-mini",
        tools: Optional[List] = None,
        api_key: Optional[str] = None,
    ):
        if HAS_OPENAI:
            self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        else:
            self.client = None
        self.model = model

        self.messages = [{"role": "system", "content": system_prompt}]

        # 注册工具
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}

    def chat(self, user_input: str) -> str:
        """对话（支持工具调用）"""
        self.messages.append({"role": "user", "content": user_input})

        # 构建工具定义
        tool_defs = [t.to_openai_format() for t in self.tools] if self.tools else None

        while True:
            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_defs,
            )

            choice = response.choices[0]
            message = choice.message

            # 情况1：LLM 要调用工具
            if message.tool_calls:
                # 添加工具调用请求到历史
                self.messages.append(message)

                # 执行每个工具调用
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    if tool_name in self.tool_map:
                        result = self.tool_map[tool_name].execute(**tool_args)
                    else:
                        result = f"[错误] 未知工具: {tool_name}"

                    # 添加工具结果到历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                # 继续循环，让 LLM 处理工具结果
                continue

            # 情况2：LLM 直接回复
            reply = message.content or ""
            self.messages.append({"role": "assistant", "content": reply})
            return reply

    def chat_stream(self, user_input: str) -> str:
        """流式对话，逐字输出"""
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

    def reset(self):
        """重置对话历史"""
        self.messages = [self.messages[0]]  # 保留 system prompt


class ClaudeAgent:
    """基于 Claude 的 Agent"""

    def __init__(self, system_prompt: str = "你是一个有用的 AI 助手。"):
        if HAS_ANTHROPIC:
            self.client = anthropic.Anthropic()
        else:
            self.client = None
        self.system_prompt = system_prompt
        self.messages = []

    def chat(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.messages,
        )

        reply = response.content[0].text
        self.messages.append({"role": "assistant", "content": reply})
        return reply


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
