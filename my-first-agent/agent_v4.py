"""
Agent v4 —— 集成搜索与网络工具
从零手写 AI Agent 课程 · 第 4 章

新增工具：
- WebSearchTool: 网络搜索
- WebFetchTool: 网页抓取
- GrepTool: 代码内容搜索
- GlobTool: 文件路径匹配
"""

import os
import json
from typing import Optional, List
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

# 导入所有工具
from tools.bash_tool import BashTool
from tools.python_tool import PythonTool
from tools.file_tools import create_file_tools, FileSandbox
from tools.web_tools import WebSearchTool, WebFetchTool
from tools.search_tools import GrepTool, GlobTool


class Agent:
    """支持搜索与网络工具的 AI Agent"""
    
    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "qwen-plus",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tool_iterations: int = 10,
        sandbox_dirs: Optional[List[str]] = None,
    ):
        # 初始化 LLM 客户端
        api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未找到 API 密钥！")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        self.messages = [{"role": "system", "content": system_prompt}]
        self.max_tool_iterations = max_tool_iterations
        self.sandbox_dirs = sandbox_dirs or []
        self.console = Console()
        
        # 初始化所有工具
        self._init_tools()
    
    def _init_tools(self):
        """初始化所有工具"""
        sandbox = FileSandbox(self.sandbox_dirs)
        
        # 文件工具
        read_tool, write_tool, edit_tool = create_file_tools(
            allowed_dirs=self.sandbox_dirs
        )
        
        # 搜索与网络工具
        web_search = WebSearchTool(max_results=8)
        web_fetch = WebFetchTool(timeout=30)
        grep = GrepTool(root_dir=os.getcwd())
        glob = GlobTool(root_dir=os.getcwd())
        
        # 所有工具
        self.tools = [
            BashTool(),
            PythonTool(),
            read_tool, write_tool, edit_tool,
            web_search, web_fetch,
            grep, glob,
        ]
        
        self.tool_map = {tool.name: tool for tool in self.tools}
    
    def _build_tool_defs(self) -> list:
        """构建工具定义列表"""
        return [tool.to_openai_format() for tool in self.tools]
    
    def chat(self, user_input: str) -> str:
        """与 Agent 对话（支持工具调用）"""
        self.messages.append({"role": "user", "content": user_input})
        tool_defs = self._build_tool_defs()
        
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            self.console.print("\n[dim]🤔 Agent 正在思考...[/dim]")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_defs,
            )
            
            message = response.choices[0].message
            
            if message.tool_calls:
                self.console.print(f"[dim]🔧 第 {iteration} 次工具调用...[/dim]")
                self.messages.append(message)
                
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id
                    
                    self.console.print(f"[dim]   → 调用 {tool_name}[/dim]")
                    
                    if tool_name in self.tool_map:
                        try:
                            tool = self.tool_map[tool_name]
                            # 处理不同的调用方式
                            if hasattr(tool, 'call'):
                                result = tool.call(**tool_args)
                                result_str = str(result)
                            else:
                                result = tool.execute(**tool_args)
                                result_str = str(result)
                        except Exception as e:
                            result_str = f"[错误] {str(e)}"
                    else:
                        result_str = f"[错误] 未知工具：{tool_name}"
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_str,
                    })
                    
                    preview = result_str[:100] + "..." if len(result_str) > 100 else result_str
                    self.console.print(f"[dim]   ← 结果：{preview}[/dim]")
                
                continue
            
            reply = message.content or ""
            self.messages.append({"role": "assistant", "content": reply})
            return reply
        
        return f"[错误] 工具调用次数过多（超过{self.max_tool_iterations}次），已终止。"
    
    def reset(self):
        """重置对话历史"""
        self.messages = [self.messages[0]]
        self.console.print("[dim]💭 对话历史已重置[/dim]")
    
    def list_tools(self):
        """列出所有可用工具"""
        self.console.print("\n[bold]=== 可用工具 ===[/bold]")
        for tool in self.tools:
            self.console.print(f"  • [cyan]{tool.name}[/cyan]: {tool.description[:60]}...")


# === 测试运行 ===
if __name__ == "__main__":
    console = Console()
    
    sandbox_dirs = [os.getcwd(), "/tmp"]
    
    agent = Agent(
        system_prompt=(
            "你是一个有用的 AI 助手，可以执行 Shell 命令、文件操作、网络搜索和代码搜索。"
            "回答要简洁明了。"
        ),
        sandbox_dirs=sandbox_dirs,
    )
    
    # 列出工具
    agent.list_tools()
    
    console.print(Panel.fit(
        "[bold green]🤖 Agent v4 已启动（带搜索与网络工具）！[/bold green]\n"
        "[dim]输入 'quit' 退出，输入 'reset' 重置，输入 'tools' 查看工具列表[/dim]",
        border_style="green"
    ))
    
    while True:
        try:
            user_input = input("你：").strip()
            
            # 退出命令（支持 /quit 和 quit 两种格式）
            if user_input.lower() in ("quit", "exit", "q", "/quit", "/exit", "/q"):
                console.print("[bold blue]👋 再见！[/bold blue]")
                break
            
            if user_input.lower() in ("reset", "/reset"):
                agent.reset()
                continue
            
            if user_input.lower() in ("tools", "/tools"):
                agent.list_tools()
                continue
            
            if not user_input:
                continue
            
            reply = agent.chat(user_input)
            
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
