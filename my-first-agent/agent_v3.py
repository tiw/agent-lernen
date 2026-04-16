"""
支持文件工具的 Agent —— 让 AI 能读写世界
从零手写 AI Agent 课程 · 第 3 章

新增功能：
- FileReadTool: 读取文件内容
- FileWriteTool: 创建/更新文件
- FileEditTool: 精准编辑（SEARCH/REPLACE）
"""

import os
import json
from typing import Optional, List
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

# 导入工具系统
from tools.base import Tool
from tools.bash_tool import BashTool
from tools.file_tools import (
    FileReadTool,
    FileWriteTool,
    FileEditTool,
    FileSandbox,
    create_file_tools,
)


class Agent:
    """支持文件工具和工具调用的 AI Agent"""
    
    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "qwen-plus",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        max_tool_iterations: int = 10,  # 防止无限工具调用循环
        sandbox_dirs: Optional[List[str]] = None,  # 沙箱目录
    ):
        # 初始化 LLM 客户端
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
        
        # 注册工具
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # 防止无限循环
        self.max_tool_iterations = max_tool_iterations
        
        # 沙箱配置
        self.sandbox_dirs = sandbox_dirs or []
        
        self.console = Console()
    
    def _build_tool_defs(self) -> Optional[List[dict]]:
        """构建工具定义列表"""
        if not self.tools:
            return None
        return [tool.to_openai_format() for tool in self.tools]
    
    def chat(self, user_input: str) -> str:
        """
        与 Agent 对话（支持工具调用）
        
        核心循环：
        1. LLM 可能要求调用工具
        2. 系统执行工具，把结果喂回给 LLM
        3. LLM 拿到结果后，可能继续调用工具，也可能直接回复
        4. 直到 LLM 不再调用工具，循环结束
        """
        # 添加用户消息到历史
        self.messages.append({"role": "user", "content": user_input})
        
        # 构建工具定义
        tool_defs = self._build_tool_defs()
        
        # 核心循环：处理工具调用
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            self.console.print("\n[dim]🤔 Agent 正在思考...[/dim]")
            
            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_defs,
            )
            
            choice = response.choices[0]
            message = choice.message
            
            # 情况 1: LLM 要调用工具
            if message.tool_calls:
                self.console.print(f"[dim]🔧 第 {iteration} 次工具调用...[/dim]")
                
                # 添加工具调用请求到历史
                self.messages.append(message)
                
                # 执行每个工具调用
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id
                    
                    self.console.print(f"[dim]   → 调用 {tool_name}({tool_args})[/dim]")
                    
                    if tool_name in self.tool_map:
                        try:
                            result = self.tool_map[tool_name].call(**tool_args)
                            # dataclass 转为字符串
                            if hasattr(result, '__dict__'):
                                result_str = str(result)
                            else:
                                result_str = str(result)
                        except Exception as e:
                            result_str = f"[错误] {str(e)}"
                    else:
                        result_str = f"[错误] 未知工具：{tool_name}"
                    
                    # 添加工具结果到历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_str,
                    })
                    
                    # 显示结果预览
                    preview = result_str[:100] + "..." if len(result_str) > 100 else result_str
                    self.console.print(f"[dim]   ← 结果：{preview}[/dim]")
                
                # 继续循环，让 LLM 处理工具结果
                continue
            
            # 情况 2: LLM 直接回复
            reply = message.content or ""
            self.messages.append({"role": "assistant", "content": reply})
            return reply
        
        # 超过最大迭代次数
        return f"[错误] 工具调用次数过多（超过{self.max_tool_iterations}次），已终止。可能是任务太复杂或 LLM 陷入循环。"
    
    def reset(self):
        """重置对话历史"""
        self.messages = [self.messages[0]]  # 保留 system prompt
        self.console.print("[dim]💭 对话历史已重置[/dim]")
    
    def debug_history(self):
        """调试：打印消息历史"""
        self.console.print("\n[bold]=== 消息历史 ===[/bold]")
        for i, msg in enumerate(self.messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            preview = content[:80] + "..." if len(content) > 80 else content
            self.console.print(f"[dim]{i}. {role}: {preview}[/dim]")


# === 测试运行 ===
if __name__ == "__main__":
    console = Console()
    
    # 创建沙箱（只允许访问当前目录和临时目录）
    sandbox_dirs = [os.getcwd(), "/tmp"]
    
    # 创建文件工具
    read_tool, write_tool, edit_tool = create_file_tools(allowed_dirs=sandbox_dirs)
    
    # 创建 Agent（带所有工具）
    agent = Agent(
        system_prompt=(
            "你是一个有用的 AI 助手，可以执行 Shell 命令和文件操作。"
            "当用户要求查看文件、运行程序、检查系统、创建文件、编辑文件时，使用相应的工具。"
            "回答要简洁明了。"
        ),
        model="qwen-plus",
        tools=[BashTool(), read_tool, write_tool, edit_tool],
        sandbox_dirs=sandbox_dirs,
    )
    
    console.print(Panel.fit(
        "[bold green]🤖 Agent v3 已启动（带文件工具）！[/bold green]\n"
        "[dim]输入 'quit' 退出，输入 'reset' 重置，输入 'debug' 查看历史[/dim]",
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
            
            if user_input.lower() == "debug":
                agent.debug_history()
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
