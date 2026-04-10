# Claude Code 架构分析报告

> **分析对象**: `~/ai_base/claude-code-main`  
> **分析视角**: Agent 操作系统  
> **分析日期**: 2026-04-08  
> **代码规模**: ~512K 行 TypeScript, ~1,900 文件

---

## 📌 执行摘要

Claude Code 本质上是一个**终端原生的 Agent 操作系统**，而非简单的 CLI 工具。它实现了完整的 Agent 运行时环境，包括：

- **工具系统**（40+ 原子能力）
- **命令系统**（50+ 用户指令）
- **多 Agent 协作**（Swarm/Team 模式）
- **持久化记忆**（Session/Project Memory）
- **权限治理**（细粒度工具审批）
- **插件/技能生态**（可扩展架构）
- **IDE 桥接**（双向通信协议）

**核心设计哲学**: 将 LLM 的推理能力与终端的系统访问能力深度融合，通过严格的权限模型和可审计的执行轨迹，实现安全的自主代码操作。

---

## 🏗️ 整体架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户交互层。 (User Interface)                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │  REPL/Ink   │  │  Slash Cmds  │  │  Bridge (IDE/Remote)  │   │
│  │  React TUI  │  │  /commit ... │  │  JWT + Message Proto  │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                    协调层 (Orchestration)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ QueryEngine │  │  Coordinator │  │  Tool Orchestrator    │   │
│  │ LLM 循环。   │  │  Multi-Agent │  │  并行工具执行           │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                    能力层 (Capabilities)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Tool System (40+)                    │    │
│  │  Bash | FileRead/Write/Edit | Grep | Glob | MCP | LSP   │    │
│  │  Agent | Skill | Task | Team | WebFetch | WebSearch     │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Command System (50+)                  │    │
│  │  /commit | /review | /mcp | /memory | /tasks | /vim     │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                    服务层 (Services)                             │
│  ┌─────────┐ ┌───────┐ ┌──────┐ ┌────────┐ ┌────────────────┐   │
│  │ API     │ │ MCP   │ │ OAuth│ │ LSP    │ │ Analytics/GB   │   │
│  │ Client  │ │ Svc   │ │ Auth │ │ Manager│ │ Feature Flags  │   │
│  └─────────┘ └───────┘ └──────┘ └────────┘ └────────────────┘   │
│  ┌─────────┐ ┌───────────┐ ┌──────────────┐ ┌───────────────┐   │
│  │ Compact │ │ Plugins   │ │ Memory Sync  │ │ Token Est.    │   │
│  │ Context │ │ Loader    │ │ Team Memory  │ │ Cost Tracking │   │
│  └─────────┘ └───────────┘ └──────────────┘ └───────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                    基础设施层。 (Infrastructure)                  │
│  ┌──────────┐ ┌─────────┐ ┌─────────--┐ ┌─────────────────────┐ │
│  │ State Mgt│ │ Perms   │ │Migrations │ │ Feature Flags (Bun) │ │
│  │ AppState │ │ System  │ │Zod Schemas│ │ Dead Code Elim      │ │
│  └──────────┘ └─────────┘ └────────--─┘ └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    运行时 (Runtime)                              │
│         Bun Runtime | TypeScript (strict) | React + Ink         │
└─────────────────────────────────────────────────────────────────┘
```

## 🔑 核心组件详解

### 1. QueryEngine — Agent 推理引擎

**文件**: `src/QueryEngine.ts` (~46K 行) | `src/query.ts` (~1.7K 行)

**职责**: LLM API 调用循环、流式响应处理、工具调用编排、Token 预算管理

```typescript
// 核心查询循环
async function* queryLoop(params: QueryParams): AsyncGenerator<...> {
  // 1. 构建不可变配置（Feature Flags、环境状态）
  const config = buildQueryConfig()
  
  // 2. 初始化可变状态（messages, toolUseContext, turnCount）
  let state: State = { ... }
  
  // 3. Token 预算跟踪（可选）
  const budgetTracker = feature('TOKEN_BUDGET') ? createBudgetTracker() : null
  
  // 4. 主循环：采样 → 工具执行 → 结果注入 → 再采样
  while (true) {
    // API 调用
    const response = await deps.samplingAPI(...)
    
    // 工具执行
    const toolResults = await runTools(...)
    
    // 上下文压缩（自动/手动）
    if (shouldCompact) {
      yield* compactContext(...)
    }
    
    // 预算检查
    if (budgetTracker && !budgetTracker.hasRemaining()) {
      break
    }
  }
}
```

**关键特性**:

| 特性 | 说明 |
|------|------|
| **流式工具执行** | `StreamingToolExecutor` 支持工具执行进度实时反馈 |
| **自动上下文压缩** | `autoCompact` 在 Token 超限时自动触发摘要 |
| **Token 预算** | 每 Turn 可配置最大 Token 消耗，超限自动终止 |
| **恢复循环** | `max_output_tokens` 错误时自动重试（最多 3 次） |
| **Thinking 模式** | 支持深度推理模式，保留思考块完整轨迹 |

---

### 2. Tool System — 原子能力系统

**目录**: `src/tools/` (45+ 子目录) | **定义**: `src/Tool.ts` (~29K 行)

**设计模式**: 每个工具是独立模块，定义输入 Schema、权限模型、执行逻辑

```typescript
// 工具接口定义
export interface Tool {
  name: string
  description: string
  inputSchema: z.ZodType  // Zod v4 验证
  execute: (input: any, context: ToolUseContext) => Promise<ToolResult>
  getPermissionRequirements?: () => PermissionRequirements
  renderProgress?: (progress: ToolProgressData) => React.ReactNode
}
```

**核心工具分类**:

| 类别 | 工具 | 说明 |
|------|------|------|
| **文件系统** | `FileRead`, `FileWrite`, `FileEdit`, `NotebookEdit` | 支持图片/PDF/Notebook |
| **代码搜索** | `GrepTool` (ripgrep), `GlobTool`, `LSPTool` | 符号跳转/引用查找 |
| **Shell 执行** | `BashTool`, `PowerShellTool` | 带权限审批的命令执行 |
| **网络** | `WebFetchTool`, `WebSearchTool` | URL 内容抓取/搜索引擎 |
| **Agent 协作** | `AgentTool`, `TeamCreateTool`, `SendMessageTool` | 子 Agent 生成/团队管理 |
| **任务管理** | `TaskCreateTool`, `TaskUpdateTool`, `TaskListTool` | 异步任务跟踪 |
| **技能/插件** | `SkillTool`, `MCPTool` | 可复用工作流/MCP 服务器 |
| **模式切换** | `EnterPlanModeTool`, `EnterWorktreeTool` | 计划模式/Git 工作树隔离 |
| **系统** | `SleepTool`, `ConfigTool`, `CronCreateTool` | 主动模式/配置/定时触发 |

**权限模型**:

```typescript
export type PermissionMode = 
  | 'default'      // 危险操作询问
  | 'plan'         // 计划模式（批量审批）
  | 'bypassPermissions'  // 完全信任（仅限本地）
  | 'auto'         // 自动模式（分类器决策）
  | 'ask'          // 每次询问

export type ToolPermissionContext = {
  mode: PermissionMode
  alwaysAllowRules: ToolPermissionRulesBySource
  alwaysDenyRules: ToolPermissionRulesBySource
  alwaysAskRules: ToolPermissionRulesBySource
  shouldAvoidPermissionPrompts?: boolean  // 后台 Agent 自动拒绝
}
```

---

### 3. Command System — 用户指令系统

**目录**: `src/commands/` (103+ 子目录) | **注册**: `src/commands.ts` (~25K 行)

**设计**: Commander.js 解析 + 条件加载（Feature Flags）

```typescript
// 命令注册示例
export const commands: Command[] = [
  {
    name: 'commit',
    description: 'Create a git commit',
    action: async (args, context) => {
      // 调用 GitTool + 用户确认
    },
    featureFlag: null  // 可选 Feature Flag
  },
  {
    name: 'voice',
    description: 'Voice input mode',
    action: ...,
    featureFlag: 'VOICE_MODE'  // 仅当 Flag 启用时加载
  }
]
```

**核心命令**:

| 命令 | 功能 |
|------|------|
| `/commit` | 创建 Git 提交（可选 PR） |
| `/review` | 代码审查 |
| `/compact` | 手动触发上下文压缩 |
| `/mcp` | MCP 服务器管理 |
| `/memory` | 持久化记忆管理 |
| `/skills` | 技能安装/执行 |
| `/tasks` | 任务列表/状态 |
| `/doctor` | 环境诊断 |
| `/vim` | Vim 模式切换 |
| `/resume` | 恢复上次会话 |
| `/desktop` / `/mobile` | 跨设备移交 |

---

### 4. Coordinator — 多 Agent 协调器

**目录**: `src/coordinator/`

**职责**: 管理 Agent Swarm、任务分配、结果聚合

```typescript
// Team 创建流程
TeamCreateTool.execute({
  name: "feature-team",
  agents: [
    { type: "architect", model: "opus" },
    { type: "coder", model: "sonnet" },
    { type: "reviewer", model: "opus" }
  ]
})

// Coordinator 调度
coordinator.dispatch(task, {
  strategy: "parallel" | "sequential" | "pipeline",
  timeout: 3600,  // 秒
  retryPolicy: { maxRetries: 3 }
})
```

**Agent 类型**:

- **Architect**: 架构设计、任务分解
- **Coder**: 代码实现
- **Reviewer**: 代码审查
- **Tester**: 测试生成
- **Specialist**: 领域专家（通过 `agents/` 目录定义）

---

### 5. Service Layer — 外部服务集成

**目录**: `src/services/` (38+ 子目录)

| 服务 | 职责 |
|------|------|
| `api/` | Anthropic API 客户端、文件 API、Bootstrap 数据 |
| `mcp/` | Model Context Protocol 服务器连接/资源发现 |
| `oauth/` | OAuth 2.0 认证流程（Anthropic/Google/GitHub） |
| `lsp/` | 语言服务器协议管理（自动发现/连接） |
| `analytics/` | GrowthBook Feature Flags + 事件上报 |
| `compact/` | 上下文压缩（手动/自动/响应式） |
| `plugins/` | 插件加载器（版本管理/依赖解析） |
| `extractMemories/` | 自动记忆提取（从对话中抽取长期记忆） |
| `tokenEstimation/` | Token 计数估算（本地快速估算） |
| `policyLimits/` | 组织策略限制（企业版功能） |

**MCP 集成示例**:

```typescript
// MCP 服务器配置
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "..." }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "args": ["/path/to/allowed/dir"]
    }
  }
}
```

---

### 6. Bridge System — IDE 桥接协议

**目录**: `src/bridge/` (33+ 子目录)

**职责**: VS Code / JetBrains 扩展 ↔ CLI 双向通信

**协议栈**:

```
┌─────────────────┐         ┌─────────────────┐
│  IDE Extension  │ ←JWT→   │  Claude Code    │
│  (VSCode/JB)    │  Msg    │  CLI (Bridge)   │
└─────────────────┘  Proto  └─────────────────┘
       │                          │
       │  - Tool Invocation       │
       │  - Permission Prompts    │
       │  - File Diffs            │
       │  - Terminal Output       │
       │                          │
```

**核心模块**:

| 文件 | 职责 |
|------|------|
| `bridgeMain.ts` | 桥接主循环（消息泵） |
| `bridgeMessaging.ts` | 消息协议（请求/响应/通知） |
| `bridgePermissionCallbacks.ts` | 权限审批回调 |
| `replBridge.ts` | REPL 会话桥接 |
| `jwtUtils.ts` | JWT 认证（会话隔离） |
| `sessionRunner.ts` | 会话执行管理 |

---

### 7. State Management — 状态管理

**目录**: `src/state/` | **核心**: `src/state/AppStateStore.ts`

**设计**: React 风格的不可变状态树 + 订阅通知

```typescript
export interface AppState {
  // 会话状态
  sessionId: UUID
  conversationId: UUID
  messages: Message[]
  
  // Agent 状态
  agentType: string
  agentId?: AgentId
  isSpeculating: boolean
  
  // 工具状态
  inProgressToolUseIDs: Set<string>
  hasInterruptibleToolInProgress: boolean
  
  // 权限状态
  permissionMode: PermissionMode
  additionalWorkingDirectories: Map<string, AdditionalWorkingDirectory>
  
  // 记忆状态
  memoryAttachments: MemoryAttachment[]
  teamMemorySyncState: TeamMemorySyncState
  
  // UI 状态
  theme: ThemeName
  vimMode: boolean
  isPlanMode: boolean
}

// 状态更新
const store = createStore(getDefaultAppState())
onChangeAppState(store, (newState, prevState) => {
  // 响应状态变化（UI 刷新/持久化/遥测）
})
```

---

### 8. Memory System — 持久化记忆

**目录**: `src/memdir/` | **服务**: `src/services/SessionMemory/`, `src/services/extractMemories/`

**记忆类型**:

| 类型 | 作用域 | 说明 |
|------|--------|------|
| **Session Memory** | 单会话 | 当前对话的短期记忆（自动提取） |
| **Project Memory** | 项目级 | `.claude/memory.md` 持久化 |
| **Team Memory** | 团队级 | 多 Agent 共享记忆 |
| **User Memory** | 全局 | 用户偏好/历史行为模式 |

**记忆提取流程**:

```
对话 → extractMemories 服务 → 候选记忆 → 用户确认 → 写入 memory.md
```

---

## 🔐 安全与权限架构

### 权限决策流程

```
工具调用请求
     │
     ▼
┌─────────────────────────┐
│ 1. 检查。 PermissionMode │
│    - bypassPermissions  │ → ✅ 直接执行
│    - default/plan/auto  │ → 继续检查
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ 2. 匹配规则优先级.        │
│    alwaysDeny > alwaysAsk > alwaysAllow
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ 3. 分类器决策 (auto 模式) │
│   TRANSCRIPT_CLASSIFIER │
│    判断工具是否安全。      │
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ 4. 用户审批 (如需)        │
│   TUI 对话框 / IDE 弹窗。 │
└─────────────────────────┘
     │
     ▼
执行 / 拒绝
```

### 危险工具分类

```typescript
const DANGEROUS_TOOLS = [
  'BashTool',           // 任意命令执行
  'FileWriteTool',      // 文件覆盖
  'FileEditTool',       // 文件修改
  'WebFetchTool',       // 外部网络
  'MCPTool',            // 外部服务
]

// Auto 模式下自动移除
const strippedDangerousPermissions = removeDangerousPermissions(context)
```

---

## 🚀 性能优化策略

### 1. 并行预取 (Parallel Prefetch)

```typescript
// main.tsx — 启动时并行执行
startMdmRawRead()      // MDM 设置读取
startKeychainPrefetch() // Keychain OAuth/API Key
initializeGrowthBook()  // Feature Flags
```

**效果**: 启动时间从 ~200ms 降至 ~135ms

### 2. 懒加载 (Lazy Loading)

```typescript
// 重型模块按需加载
const otel = feature('OTEL') 
  ? await import('./services/analytics/otel.js')
  : null

const voiceModule = feature('VOICE_MODE')
  ? await import('./voice/index.js')
  : null
```

### 3. Feature Flags 死代码消除

```typescript
// Bun 编译时完全移除
import { feature } from 'bun:bundle'

if (feature('PROACTIVE')) {
  // 仅在 Flag 启用时包含此代码
  require('./proactive/index.js')
}
```

**Flag 列表**: `PROACTIVE`, `KAIROS`, `BRIDGE_MODE`, `DAEMON`, `VOICE_MODE`, `AGENT_TRIGGERS`, `MONITOR_TOOL`, `COORDINATOR_MODE`, `TOKEN_BUDGET`, `REACTIVE_COMPACT`

### 4. Token 估算缓存

```typescript
// 本地快速估算（不调用 API）
const estimatedTokens = tokenCountWithEstimation(messages)
if (estimatedTokens > CONTEXT_LIMIT * 0.9) {
  triggerAutoCompact()
}
```

---

## 🧩 扩展架构

### 插件系统

**目录**: `src/plugins/` | **命令**: `/plugins install|list|update`

```typescript
// 插件接口
interface Plugin {
  name: string
  version: string
  tools?: Tool[]
  commands?: Command[]
  hooks?: {
    preQuery?: (context) => void
    postToolExecute?: (tool, result) => void
  }
}

// 插件加载
const plugins = await loadAllPlugins()
for (const plugin of plugins) {
  registerTools(plugin.tools)
  registerCommands(plugin.commands)
  registerHooks(plugin.hooks)
}
```

### 技能系统

**目录**: `src/skills/` | **命令**: `/skills run|list|install`

```yaml
# 技能定义 (YAML)
name: pr-review
description: Automated PR review workflow
tools:
  - BashTool
  - FileReadTool
  - SendMessageTool
steps:
  - fetch_pr_changes
  - run_linter
  - run_tests
  - generate_review_comments
  - post_to_github
```

---

## 📊 架构度量

| 指标 | 数值 |
|------|------|
| **总代码量** | ~512K 行 |
| **TypeScript 文件** | ~1,900 |
| **工具数量** | 40+ |
| **命令数量** | 50+ |
| **UI 组件** | 140+ (Ink/React) |
| **Hooks** | 87+ |
| **服务模块** | 38+ |
| **Feature Flags** | 12+ |

---

## 🧠 KAIROS — 动态 AI 实时操作系统

**Feature Flag**: `KAIROS` | **激活命令**: `/brief` | **状态 API**: `getKairosActive()`, `setKairosActive()`

### 核心特性

KAIROS 是 Claude Code 的**实时感知操作系统层**，赋予 Agent 持续环境感知和自主行动能力。

```typescript
// bootstrap/state.ts — 全局状态
interface AppState {
  kairosActive: boolean      // KAIROS 模式激活状态
  isBriefOnly: boolean       // 仅 Brief 输出模式
  userMsgOptIn: boolean      // 用户消息授权
}
```

### 15 秒唤醒机制 (Tick System)

```typescript
// main.tsx — Proactive Mode 系统提示
const proactivePrompt = `
# Proactive Mode

You are in proactive mode. Take initiative — explore, act, and make progress without waiting for instructions.

Start by briefly greeting the user.

You will receive periodic <tick> prompts. These are check-ins. Do whatever seems most useful, or call Sleep if there's nothing to do.
`
```

**Tick 调度架构**:

```
┌─────────────────────────────────────────────────────────┐
│              KAIROS Tick Scheduler                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Tick #1    │    │  Tick #2    │    │  Tick #3    │  │
│  │  t=0s       │───▶│  t=15s      │───▶│  t=30s      │  │
│  │  <tick>     │    │  <tick>     │    │  <tick>     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │         │
│         ▼                  ▼                  ▼         │
│   探索/执行/回复      检查进展/继续      调用 Sleep 或       │
│   Bash/File/Agent     或调用工具         进入空闲等待。     │
└─────────────────────────────────────────────────────────┘
```

**Tick 间隔配置**:

| 场景 | 间隔 | 说明 |
|------|------|------|
| **默认 Tick** | ~15 秒 | 主动模式下的定期检查点 |
| **后台任务执行** | 动态 | Bash/Sleep 工具每秒发射进度 tick |
| **窗口失焦** | ×2 | `BLURRED_TICK_INTERVAL_MS = FRAME_INTERVAL_MS * 2` |

**下次 Tick 预测 API**:

```typescript
// components/PromptInput/PromptInputFooterLeftSide.tsx
const nextTickAt = useSyncExternalStore(
  proactiveModule?.subscribeToProactiveChanges,
  proactiveModule?.getNextTickAt
)

// 显示倒计时
const remaining = Math.max(0, Math.ceil((nextTickAt - Date.now()) / 1000))
```

### Brief 模式 (精简输出)

**设计目标**: 在 KAIROS 模式下，Agent 的所有用户可见输出必须通过 `BriefTool`，避免纯文本泄露。

```typescript
// tools/BriefTool/BriefTool.ts
function isBriefEntitled(): boolean {
  // KAIROS 模式绕过 opt-in 检查
  return getKairosActive() || getUserMsgOptIn()
}

// 系统提示强制要求
const briefVisibility = feature('KAIROS') || feature('KAIROS_BRIEF') 
  ? isBriefEnabled() 
    ? 'Call SendUserMessage at checkpoints to mark where things stand.' 
    : 'The user will see any text you output.'
  : 'The user will see any text you output.'
```

**启用流程**:

```
用户输入 /brief
     │
     ▼
setUserMsgOptIn(true)  ← 启用 BriefTool
     │
     ▼
setKairosActive(true)  ← 激活 KAIROS 模式
     │
     ▼
系统提示注入 Proactive Mode 指令
     │
     ▼
Agent 开始接收 <tick> 提示 → 每 15 秒自主行动
```

### 与 Proactive Mode 的关系

```typescript
// feature('KAIROS') 和 feature('PROACTIVE') 共享底层模块
const proactiveModule = feature('PROACTIVE') || feature('KAIROS') 
  ? require('./proactive/index.js') 
  : null

// KAIROS 是 Proactive 的增强版
// - Proactive: 基础主动模式
// - KAIROS: + 实时感知 + Brief 输出 + 环境缓存
```

---

## 💤 AutoDream — 记忆巩固机制

**Feature Flag**: `tengu_onyx_plover` | **触发条件**: 24 小时 + 5 个会话

### 核心设计

AutoDream 是**系统空闲时的记忆修剪与巩固服务**，在后台自动运行，避免记忆冗余膨胀。

```typescript
// services/autoDream/autoDream.ts
interface AutoDreamConfig {
  minHours: number      // 距上次巩固的最小时数 (默认 24h)
  minSessions: number   // 需审查的最少会话数 (默认 5 个)
}

const DEFAULTS: AutoDreamConfig = {
  minHours: 24,
  minSessions: 5,
}
```

### 触发条件 (双门控机制)

```
┌─────────────────────────────────────────────────────────┐
│                  AutoDream 触发流程。                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 时间门控 (Time Gate)。                                │
│     hoursSince = (Date.now() - lastConsolidatedAt) / 1h │
│     if (hoursSince < 24) → 跳过                          │
│                                                         │
│  2. 会话门控 (Session Gate)。                             │
│     sessions = listSessionsTouchedSince(lastAt)         │
│     if (sessions.length < 5) → 跳过。                    │
│                                                         │
│  3. 锁获取 (Lock Acquisition)                            │
│     tryAcquireConsolidationLock() → PID + mtime         │
│     if (locked by other process) → 跳过。                │
│                                                         │
│  4. 触发 Forked Agent 。                                 │
│    runForkedAgent(prompt: "Dream: Memory Consolidation")│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 记忆巩固四阶段

```typescript
// services/autoDream/consolidationPrompt.ts

## Phase 1 — Orient (定向)
- `ls` 记忆目录查看现有结构
- 读取 `ENTRYPOINT_NAME` (索引文件)
- 浏览现有主题文件避免重复

## Phase 2 — Gather Recent Signal (收集信号)
- 扫描每日日志 `logs/YYYY/MM/YYYY-MM-DD.md`
- 识别漂移的旧记忆 (与代码库矛盾的事实)
- 有限搜索转录文件 (grep 窄匹配，不全文读取)

## Phase 3 — Consolidate (巩固)
- 更新或创建顶层记忆文件
- 合并新信号到现有主题 (而非创建近似重复)
- 转换相对日期为绝对日期 ("昨天" → "2026-04-07")
- 删除被证伪的记忆

## Phase 4 — Prune and Index (修剪与索引)
- 更新索引文件 (<25KB, <MAX_ENTRYPOINT_LINES 行)
- 每行 <150 字符：`- [Title](file.md) — one-line hook`
- 移除过时/被取代的记忆指针
- 解决矛盾 (修正错误的一方)
```

### 锁机制与崩溃恢复

```typescript
// services/autoDream/consolidationLock.ts

// 锁文件结构
// Path: <memoryDir>/.consolidate-lock
// Body: PID (进程 ID)
// mtime: lastConsolidatedAt (最后巩固时间戳)

async function tryAcquireConsolidationLock(): Promise<number | null> {
  // 1. 读取现有锁
  const [stat, raw] = await Promise.all([stat(path), readFile(path)])
  
  // 2. 检查是否过期 (1 小时)
  if (Date.now() - mtimeMs < HOLDER_STALE_MS) {
    if (isProcessRunning(holderPid)) {
      return null  // 锁被活跃进程持有
    }
    // PID 已死 → 回收锁
  }
  
  // 3. 写入当前 PID
  await writeFile(path, String(process.pid))
  
  // 4. 验证写入成功 (防并发竞争)
  const verify = await readFile(path)
  if (parseInt(verify) !== process.pid) return null  // 竞争失败
  
  return priorMtime  // 用于回滚
}

// 崩溃回滚
async function rollbackConsolidationLock(priorMtime: number) {
  if (priorMtime === 0) {
    await unlink(path)  // 删除锁文件
  } else {
    await writeFile(path, '')  // 清空 PID
    await utimes(path, priorMtime/1000, priorMtime/1000)  // 回滚 mtime
  }
}
```

### 会话扫描节流

```typescript
// 防止每次 Turn 都扫描会话
const SESSION_SCAN_INTERVAL_MS = 10 * 60 * 1000  // 10 分钟

let lastSessionScanAt = 0
const sinceScanMs = Date.now() - lastSessionScanAt
if (sinceScanMs < SESSION_SCAN_INTERVAL_MS) {
  return  // 节流跳过
}
lastSessionScanAt = Date.now()
```

### Forked Agent 执行

```typescript
const result = await runForkedAgent({
  promptMessages: [createUserMessage({ content: dreamPrompt })],
  cacheSafeParams: createCacheSafeParams(context),
  canUseTool: createAutoMemCanUseTool(memoryRoot),  // 只读权限
  querySource: 'auto_dream',
  forkLabel: 'auto_dream',
  skipTranscript: true,  // 不记录转录
  overrides: { abortController },
  onMessage: makeDreamProgressWatcher(taskId, setAppState),
})

// 工具限制：只读命令
**Tool constraints for this run:** Bash is restricted to read-only commands 
(`ls`, `find`, `grep`, `cat`, `stat`, `wc`, `head`, `tail`)
```

### 缓存指标遥测

```typescript
logEvent('tengu_auto_dream_completed', {
  cache_read: result.totalUsage.cache_read_input_tokens,
  cache_created: result.totalUsage.cache_creation_input_tokens,
  output: result.totalUsage.output_tokens,
  sessions_reviewed: sessionIds.length,
})
```

---

## 💡 设计亮点

### 1. 终端原生 UI (Ink + React)

```tsx
// 组件化终端 UI
function ToolExecutionView({ tool, progress }) {
  return (
    <Box flexDirection="column">
      <Text bold>{tool.name}</Text>
      <Spinner mode={progress.state} />
      <Text dimColor>{progress.message}</Text>
    </Box>
  )
}
```

### 2. 可恢复会话 (Session Recovery)

```typescript
// 会话持久化
await saveSession({
  sessionId,
  messages,
  state: appState,
  timestamp: Date.now()
})

// 恢复
const session = await loadSession(sessionId)
await processResumedConversation(session)
```

### 3. Git 工作树隔离

```typescript
// 进入独立工作树
await EnterWorktreeTool.execute({
  branch: 'feature/claude-work',
  isolated: true  // 独立目录，不影响主工作区
})

// 退出时清理
await ExitWorktreeTool.execute()
```

### 4. 跨设备移交

```typescript
// 生成深度链接
const deepLink = buildDeepLinkBanner({
  sessionId,
  target: 'desktop' | 'mobile',
  state: serializeAppState()
})

// 目标设备恢复
await restoreFromDeepLink(deepLink)
```

---

## ⚠️ 潜在风险与改进建议

### 安全风险

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| **Bash 注入** | 工具可能执行任意命令 | 权限审批 + 命令审计日志 |
| **文件覆盖** | `FileWriteTool` 可覆盖关键文件 | Git diff 预览 + 确认 |
| **MCP 信任** | 第三方 MCP 服务器可能恶意 | 服务器审批 + 沙箱执行 |
| **Token 泄露** | API Key 存储于 Keychain | 加密存储 + 最小权限 |

### 架构改进建议

1. **工具沙箱化**: 为 `BashTool` 引入容器化执行（如 Firecracker）
2. **策略引擎**: 引入 OPA/Rego 风格的声明式策略语言
3. **审计日志**: 完整的工具执行审计轨迹（合规需求）
4. **速率限制**: 防止 Agent 失控导致 API 费用爆炸
5. **回滚机制**: 文件修改的自动回滚点（类似 Time Machine）

---

## 🔮 与 OpenClaw 的对比

| 维度 | Claude Code | OpenClaw |
|------|-------------|----------|
| **定位** | 终端原生 Agent CLI | 通用 Agent 运行时平台 |
| **UI** | Ink (React TUI) | 多通道 (Telegram/Discord/钉钉) |
| **工具系统** | 40+ 内置工具 | 技能 (Skill) 扩展模型 |
| **多 Agent** | Team/Coordinator | Sub-agent + ClawFlow |
| **记忆** | Session/Project/Team | MEMORY.md + memory/*.md |
| **扩展** | Plugins + Skills | Skills (clawhub) |
| **IDE 集成** | Bridge (VSCode/JB) | 待实现 |
| **运行时** | Bun | Node.js |
| **开源状态** | 源码暴露 (研究用) | 开源 |

**借鉴点**:

1. **权限模型**: Claude Code 的细粒度工具审批可直接借鉴
2. **工具编排**: `StreamingToolExecutor` 的进度反馈机制
3. **会话恢复**: 完整的会话序列化/反序列化
4. **Feature Flags**: Bun 编译时死代码消除
5. **MCP 集成**: Model Context Protocol 的标准化工具接入

---

## 📝 总结

Claude Code 代表了一种**终端原生 Agent 操作系统**的设计范式：

1. **能力原子化**: 40+ 工具覆盖开发全流程
2. **权限显式化**: 细粒度审批 + 多模式切换
3. **协作规模化**: 多 Agent Team 并行工作
4. **记忆持久化**: 会话/项目/团队三级记忆
5. **生态开放化**: 插件 + 技能 + MCP 三重扩展
6. **实时感知化**: KAIROS 15 秒唤醒 + 自主行动
7. **记忆自优化**: AutoDream 空闲时自动修剪巩固

### KAIROS + AutoDream 的协同效应

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code 智能循环                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────────┐         ┌───────────────┐               │
│   │  KAIROS       │         │  AutoDream    │               │
│   │  (实时感知)    │         │  (离线巩固)     │               │
│   │               │         │               │               │
│   │  • 15 秒 Tick │         │  • 24h 门控    │               │
│   │  • 自主探索    │         │  • 5 会话触发   │               │
│   │  • Brief 输出  │         │  • 锁保护      │               │
│   │  • 环境缓存    │         │  • 只读 Fork   │               │
│   │               │         │               │               │
│   │  主动模式      │         │  后台模式       │               │
│   │  (用户交互)    │         │  (系统空闲)     │               │
│   └───────────────┘         └───────────────┘               │
│            │                       │                        │
│            └───────────┬───────────┘                        │
│                        ▼                                    │
│              ┌───────────────────┐                          │
│              │   记忆系统进化      │                          │
│              │  - 实时写入        │                          │
│              │  - 离线修剪        │                          │
│              │  - 矛盾消除        │                          │
│              │  - 索引优化        │                          │
│              └───────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**KAIROS** 负责**实时感知与行动**——每 15 秒唤醒，自主探索环境、执行任务、与用户交互。

**AutoDream** 负责**离线记忆优化**——系统空闲时审查多个会话，修剪冗余记忆，巩固关键知识。

两者结合形成了一个**完整的认知循环**：
- **白天 (KAIROS)**: 积极行动，积累原始经验
- **夜晚 (AutoDream)**: 反思整合，提炼持久记忆

这与人类的**清醒 - 睡眠 - 梦境**认知模式高度相似，是 Agent 系统设计的重要里程碑。

---

其架构设计对构建企业级 Agent 平台具有重要参考价值，尤其在**安全治理**、**可扩展性**、**用户体验**和**认知架构**四个维度的平衡上。

---

*报告生成于 2026-04-08 | 分析工具：OpenClaw 🦞*
