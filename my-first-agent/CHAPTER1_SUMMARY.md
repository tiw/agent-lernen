# 第一章学习总结：最小可用 Agent

> 学习时间：2026-04-14  
> 学习状态：✅ 完成  
> 使用 LLM：阿里云通义千问（qwen-plus）

---

## 🎯 学习目标

| 目标 | 完成情况 | 备注 |
|------|----------|------|
| 理解 Agent 核心公式 | ✅ | Agent = LLM + 循环 + 工具 + 记忆 |
| 实现第一个 Agent 类 | ✅ | 成功创建 Agent 类 |
| 理解消息历史管理 | ✅ | system/user/assistant 三种角色 |
| 完成第一次对话 | ✅ | 成功与通义千问对话 |
| 适配国内 LLM 服务 | ✅ | 阿里云 DashScope 配置 |

---

## 📝 核心代码

### Agent 类实现

```python
class Agent:
    """最小可用的 AI Agent"""
    
    def __init__(
        self,
        system_prompt: str = "你是一个有用的 AI 助手。",
        model: str = "qwen-plus",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # 初始化 LLM 客户端（兼容 OpenAI 接口）
        api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        
        # 消息历史（核心！）
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]
    
    def chat(self, user_input: str) -> str:
        """与 Agent 对话一次"""
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
```

### 核心概念

```
Agent 的本质 = 一个 while 循环 + 消息历史 + LLM 调用

消息格式：
[
    {"role": "system", "content": "系统提示，定义 Agent 身份"},
    {"role": "user", "content": "用户输入"},
    {"role": "assistant", "content": "AI 回复"},
]
```

---

## 🧪 测试结果

```bash
$ python agent.py

🤖 Agent 已启动！

你：你好，请介绍一下你自己

🤖 Agent
你好！😊 我是通义千问（Qwen），阿里巴巴集团旗下的超大规模语言模型...

你：1+1 等于几？

🤖 Agent  
1 + 1 = 2 ✅
这是数学中最基础的加法运算...

你：quit
👋 再见！
```

**测试结果**：✅ 成功对话，消息历史正常累积

---

## ⚠️ 遇到的问题与解决

### 问题 1：API Key 未找到

**错误信息**：
```
ValueError: 未找到 API 密钥！请设置 DASHSCOPE_API_KEY 环境变量
```

**原因**：OpenAI 客户端不会自动读取 `DASHSCOPE_API_KEY`

**解决**：
```python
# 显式传递 api_key
api_key = os.environ.get("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("未找到 API 密钥！...")
self.client = OpenAI(api_key=api_key, base_url=...)
```

### 问题 2：API Key 格式错误

**错误信息**：
```
httpx.LocalProtocolError: Illegal header value b'Bearer sk-...\nsk-...'
```

**原因**：环境变量中包含了换行符和多个 key

**解决**：
```bash
# 检查 ~/.zshrc 中的配置
grep "DASHSCOPE_API_KEY" ~/.zshrc

# 确保只有一行，没有换行
export DASHSCOPE_API_KEY="sk-xxxxx"
```

### 问题 3：环境变量未加载

**原因**：`source ~/.zshrc` 在脚本中不生效

**解决**：
```bash
# 手动 export
export DASHSCOPE_API_KEY="sk-cdf7384475cf4063a80e3720c70122a7"
```

---

## 📊 教程评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 概念清晰度 | ⭐⭐⭐⭐⭐ | Agent 公式简单易懂 |
| 代码可读性 | ⭐⭐⭐⭐☆ | 代码结构清晰，注释充分 |
| 实践指导性 | ⭐⭐⭐☆☆ | 需要自己适配国内服务 |
| 错误处理 | ⭐⭐☆☆☆ | 缺少友好的错误提示 |
| 新手友好度 | ⭐⭐⭐☆☆ | 有基础编程知识可以跟上 |

**总体评分**：⭐⭐⭐⭐☆（4/5）

---

## 🔧 教程改进建议

### 1. 增加国内 LLM 服务配置说明

```markdown
### 配置 API 密钥（多种选择）

# OpenAI（需要海外账号）
export OPENAI_API_KEY="sk-..."

# 阿里云 DashScope（推荐国内用户）
export DASHSCOPE_API_KEY="sk-..."
# 代码中设置：base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"

# 智谱 AI
export ZHIPU_API_KEY="..."
# base_url="https://open.bigmodel.cn/api/paas/v4/"

# 深度求索
export DEEPSEEK_API_KEY="..."
# base_url="https://api.deepseek.com/v1"
```

### 2. 增加错误处理示例

```python
# 友好的错误提示
try:
    response = self.client.chat.completions.create(...)
except openai.APIConnectionError as e:
    print(f"❌ 网络连接错误：{e}")
    print("请检查：1) 网络连接 2) API Key 是否正确")
except openai.AuthenticationError as e:
    print(f"❌ 认证失败：{e}")
    print("请检查 API Key 是否正确")
```

### 3. 增加调试技巧

```python
# 打印消息历史，帮助理解
def debug_history(self):
    print("=== 消息历史 ===")
    for i, msg in enumerate(self.messages):
        preview = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
        print(f"{i}. {msg['role']}: {preview}")
```

### 4. 增加模型选择建议

| 场景 | 推荐模型 | 说明 |
|------|----------|------|
| 快速测试 | qwen-turbo | 便宜、快速 |
| 日常对话 | qwen-plus | 平衡性能与成本 |
| 复杂任务 | qwen-max | 最强能力 |
| 代码生成 | qwen-coder | 专为代码优化 |

---

## 💡 学习心得

1. **不要直接复制代码** — 理解每一行的作用
2. **遇到错误先读报错信息** — 大部分问题都在报错里
3. **多打印调试** — 用 `print()` 查看变量状态
4. **适配自己的环境** — 教程是参考，要根据实际情况调整
5. **消息历史是核心** — 理解为什么需要保留 system prompt

---

## 📁 项目文件

```
~/my-first-agent/
├── agent.py                  # Agent 核心代码
├── CHAPTER1_SUMMARY.md       # 本章总结（本文件）
├── LEARNING_NOTES.md         # 详细学习笔记
└── .venv/                    # Python 虚拟环境
```

---

## 📚 下一章预习

**第二章：工具调用（Tool Calling）**

学习目标：
- 理解 Tool Calling 协议
- 实现工具基类
- 实现 BashTool（执行 Shell 命令）
- 让 Agent 能执行实际操作

预习问题：
1. 什么是 Tool Calling？
2. OpenAI 和 Anthropic 的工具调用格式有什么区别？
3. 如何安全地执行 Shell 命令？

---

_总结完成时间：2026-04-14_
_下一步：继续学习第二章_
