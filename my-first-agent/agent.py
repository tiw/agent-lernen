"""
最小可用 Agent —— 让 AI 说第一句话
从零手写 AI Agent 课程 · 第 1 章

新手学习笔记：这是我第一次亲手写的 AI Agent！
"""

import os
from typing import Optional
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel


class Agent:
    """最小可用的 AI Agent"""
    
    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "qwen-plus",  # 使用阿里云通义千问模型
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # 初始化 LLM 客户端
        # 注意：阿里云 DashScope 兼容 OpenAI 接口
        # 需要显式设置 api_key，因为 OpenAI 客户端不会自动读取 DASHSCOPE_API_KEY
        api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "未找到 API 密钥！请设置 DASHSCOPE_API_KEY 环境变量\n"
                "可以在 ~/.zshrc 中添加：export DASHSCOPE_API_KEY=your_key"
            )
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        
        # 消息历史
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        self.console = Console()
    
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
        self.console.print("\n[dim]🤔 Agent 正在思考...[/dim]")
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
        self.console.print("[dim]💭 对话历史已重置[/dim]")


# === 测试运行 ===
if __name__ == "__main__":
    console = Console()
    
    # 创建 Agent
    agent = Agent(
        system_prompt="你是一个简洁的 AI 助手。回答要简短、准确。",
        model="qwen-plus",  # 阿里云通义千问
    )
    
    console.print(Panel.fit(
        "[bold green]🤖 Agent 已启动！[/bold green]\n"
        "[dim]输入 'quit' 退出，输入 'reset' 重置对话[/dim]",
        border_style="green"
    ))
    console.print()
    
    while True:
        try:
            user_input = input("你：").strip()
            
            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[bold blue]👋 再见！[/bold blue]")
                break
            
            if user_input.lower() == "reset":
                agent.reset()
                continue
            
            if not user_input:
                continue
            
            # 获取 Agent 回复
            reply = agent.chat(user_input)
            
            # 显示回复
            console.print()
            console.print(Panel(
                reply,
                title="[bold cyan]🤖 Agent[/bold cyan]",
                border_style="cyan"
            ))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[bold blue]👋 再见！[/bold blue]")
            break
        except Exception as e:
            console.print(f"[bold red]❌ 错误：{e}[/bold red]")
