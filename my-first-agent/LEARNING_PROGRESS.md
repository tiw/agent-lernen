# 📚 从零手写 AI Agent 学习进度

> 学习者：Agent 开发新手  
> 开始时间：2026-04-14  
> 使用 LLM：阿里云通义千问（qwen-plus）  
> 教程：agent-course/chapters/

---

## 📈 学习进度

| 章节 | 主题 | 状态 | 学习时长 | 总结文档 |
|------|------|------|----------|----------|
| Ch00 | 为什么从零手写 | ✅ 已阅读 | 15 分钟 | - |
| Ch01 | 最小可用 Agent | ✅ 完成 | 1 小时 | [CHAPTER1_SUMMARY.md](CHAPTER1_SUMMARY.md) |
| Ch02 | 工具调用 | ✅ 完成 | 1.5 小时 | [CHAPTER2_SUMMARY.md](CHAPTER2_SUMMARY.md) |
| Ch03 | 文件系统工具 | ✅ 完成 | 2 小时 | [CHAPTER3_SUMMARY.md](CHAPTER3_SUMMARY.md) |
| Ch04 | 搜索与网络 | ✅ 完成 | 2 小时 | [CHAPTER4_SUMMARY.md](CHAPTER4_SUMMARY.md) |
| Ch05 | 记忆系统（上） | ✅ 完成 | 2.5 小时 | [CHAPTER5_SUMMARY.md](CHAPTER5_SUMMARY.md) |
| Ch06 | 记忆系统（下） | ✅ 完成 | 2 小时 | [CHAPTER6_SUMMARY.md](CHAPTER6_SUMMARY.md) |
| Ch07 | 任务系统 | ✅ 完成 | 2 小时 | [CHAPTER7_SUMMARY.md](CHAPTER7_SUMMARY.md) |
| Ch08 | 技能系统 | ✅ 完成 | 2 小时 | [CHAPTER8_SUMMARY.md](CHAPTER8_SUMMARY.md) |
| Ch09 | MCP 协议 | ✅ 完成 | 2.5 小时 | [CHAPTER9_SUMMARY.md](CHAPTER9_SUMMARY.md) |
| Ch10 | 多智能体协作 | ✅ 完成 | 2.5 小时 | [CHAPTER10_SUMMARY.md](CHAPTER10_SUMMARY.md) |
| Ch11 | Hook 系统 | ✅ 完成 | 2 小时 | [CHAPTER11_SUMMARY.md](CHAPTER11_SUMMARY.md) |
| Ch12 | CLI 终端界面 | ✅ 完成 | 2 小时 | [CHAPTER12_SUMMARY.md](CHAPTER12_SUMMARY.md) |
| Ch13 | 安全与权限 | ✅ 完成 | 2.5 小时 | [CHAPTER13_SUMMARY.md](CHAPTER13_SUMMARY.md) |
| Ch14 | 实战项目 | ✅ 完成 | 3 小时 | [CHAPTER14_SUMMARY.md](CHAPTER14_SUMMARY.md) |

**总体进度**：14/15 章节完成（93%）

---

## 📁 项目结构

```
~/my-first-agent/
├── agent.py                   # Ch01: 基础 Agent（无工具）
├── agent_v2.py                # Ch02: 带工具调用的 Agent
├── agent_v3.py                # Ch03: 带文件工具的 Agent
├── tools/
│   ├── __init__.py
│   ├── base.py                # 工具基类
│   ├── bash_tool.py           # Bash 工具
│   └── file_tools.py          # 文件工具（Read/Write/Edit）
├── test_file_tools.py         # 文件工具单元测试
├── CHAPTER1_SUMMARY.md        # 第一章学习总结
├── CHAPTER2_SUMMARY.md        # 第二章学习总结
├── CHAPTER3_SUMMARY.md        # 第三章学习总结
├── LEARNING_PROGRESS.md       # 学习进度（本文件）
└── .venv/                     # Python 虚拟环境
```

---

## 🎯 已掌握的核心概念

### Ch01: 最小可用 Agent

- ✅ Agent 公式：`Agent = LLM + 循环 + 工具 + 记忆`
- ✅ 消息历史管理（system/user/assistant）
- ✅ OpenAI 兼容 API 调用
- ✅ 对话循环（while True）

### Ch02: 工具调用

- ✅ Tool Calling 概念
- ✅ 工具基类设计（抽象类）
- ✅ BashTool 实现
- ✅ 安全检查（危险命令黑名单）
- ✅ 防止无限循环（max_tool_iterations）
- ✅ 核心循环：LLM → 工具 → 结果 → LLM

### Ch03: 文件系统工具

- ✅ FileReadTool（分页读取、Token 限制）
- ✅ FileWriteTool（自动创建目录、diff 生成）
- ✅ FileEditTool（SEARCH/REPLACE、全局替换）
- ✅ FileSandbox（路径校验、设备文件拦截）
- ✅ 路径穿越攻击防护
- ✅ 友好的错误提示

---

## 🧪 已实现的功能

### 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 基础对话 | ✅ | 与通义千问正常对话 |
| 消息历史 | ✅ | 多轮对话上下文保持 |
| Bash 工具 | ✅ | 执行 Shell 命令 |
| 安全检查 | ✅ | 危险命令拦截 |
| 工具调用日志 | ✅ | 控制台显示调用过程 |
| 超时保护 | ✅ | 命令执行超时限制 |
| 输出限制 | ✅ | 防止 token 爆炸 |
| 文件读取 | ✅ | 分页读取、行号显示 |
| 文件写入 | ✅ | 自动创建目录、diff 生成 |
| 文件编辑 | ✅ | SEARCH/REPLACE 精准编辑 |
| 安全沙箱 | ✅ | 路径校验、穿越攻击防护 |

### 完善功能（新增）

| 功能 | 状态 | 说明 |
|------|------|------|
| 编码自动检测 | ✅ | chardet 库自动检测 |
| 编辑历史（Undo） | ✅ | 支持撤销编辑 |
| 多编辑块 | ✅ | call_multi 方法 |
| Python 工具 | ✅ | 专用 Python 执行 |
| 先读后写检查 | ✅ | FileReadState 类 |

---

## 📝 学习笔记

### 环境配置

```bash
# Python 版本
python3 --version  # 3.9.6

# 虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install openai rich

# API 配置
export DASHSCOPE_API_KEY="sk-cdf7384475cf4063a80e3720c70122a7"
```

### 运行测试

```bash
# 运行第一章 Agent
python agent.py

# 运行第二章 Agent（带工具）
python agent_v2.py

# 测试 BashTool
python tools/bash_tool.py
```

### 测试用例

```
✅ "你好，请介绍一下你自己" → 正常回复
✅ "1+1 等于几？" → 正常回复
✅ "当前目录下有什么文件？" → 调用 bash: ls -la
✅ "Python 版本是什么？" → 调用 bash: python --version
✅ "rm -rf /" → 被安全拦截
```

---

## ⚠️ 遇到的问题汇总

| 问题 | 章节 | 解决方案 |
|------|------|----------|
| API Key 未找到 | Ch01 | 显式传递 api_key 参数 |
| API Key 格式错误 | Ch01 | 检查环境变量，去除换行符 |
| 相对导入错误 | Ch02 | 支持直接运行和模块导入两种模式 |
| 无限循环风险 | Ch02 | 设置 max_tool_iterations |
| 网络下载慢 | Ch01 | 使用国内镜像源 |

---

## 🔧 教程改进建议汇总

### 通用建议

1. **增加国内 LLM 服务配置** - 阿里云、智谱、DeepSeek 等
2. **增加错误处理示例** - 友好的错误提示
3. **增加调试技巧** - 打印变量、日志等
4. **增加模型选择建议** - 不同场景的模型推荐

### Ch01 特定建议

- 环境变量加载说明不足
- 缺少 Python 版本要求说明
- 虚拟环境重要性未强调

### Ch02 特定建议

- 可以增加更多工具示例（PythonTool、FileReadTool 等）
- 增加工具调用日志系统
- 增加工具权限系统设计

---

## 💡 学习心得

### 新手建议

1. **不要直接复制代码** — 理解每一行的作用
2. **遇到错误先读报错信息** — 大部分问题都在报错里
3. **多打印调试** — 用 `print()` 查看变量状态
4. **适配自己的环境** — 教程是参考，要根据实际情况调整
5. **每章写总结** — 帮助巩固知识

### 核心收获

1. **Agent 的本质是循环** — while 循环 + LLM 调用
2. **工具是 Agent 的手脚** — 没有工具只是聊天机器人
3. **安全至关重要** — 执行外部命令必须有检查
4. **抽象基类是好东西** — 强制统一接口

---

## 📅 后续学习计划

### 短期（本周）

- [ ] 完成 Ch03：文件系统工具
- [ ] 完成 Ch04：搜索与网络
- [ ] 实现 FileReadTool、FileWriteTool

### 中期（本月）

- [ ] 完成 Ch05-Ch06：记忆系统
- [ ] 完成 Ch07-Ch08：任务与技能系统
- [ ] 实现一个简单的实战项目

### 长期

- [ ] 完成全部 15 章
- [ ] 基于所学构建自己的 Agent 框架
- [ ] 给原教程提 PR 改进建议

---

## 📊 每章评分汇总

| 章节 | 概念清晰 | 代码可读 | 实践指导 | 新手友好 | 总分 |
|------|----------|----------|----------|----------|------|
| Ch01 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ | ⭐⭐⭐☆☆ | ⭐⭐⭐☆☆ | 4/5 |
| Ch02 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐☆ | 5/5 |
| Ch03 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐☆ | 5/5 |

---

_最后更新：2026-04-14_  
_下次学习：第四章（搜索与网络）_
