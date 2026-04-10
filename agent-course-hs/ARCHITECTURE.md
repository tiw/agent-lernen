# 架构设计文档

## 系统架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    用户交互层                             │
│              (CLI / Web API / GUI)                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent.Session                           │
│           会话管理 + 交互循环                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent.Core                             │
│           核心对话逻辑 + 状态管理                          │
│  ┌──────────────┐    ┌───────────┐    ┌──────────────┐ │
│  │  AgentEnv    │    │ AgentM    │    │ AgentState   │ │
│  │  (配置/工具)  │    │ (Monad)   │    │ (状态)       │ │
│  └──────────────┘    └───────────┘    └──────────────┘ │
└───────┬──────────────┬──────────────────┬───────────────┘
        │              │                  │
        ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Agent.Tools  │ │Agent.Hooks   │ │   LLM API        │
│ (工具执行器)  │ │(事件系统)    │ │ (OpenAI/Claude)  │
└──────────────┘ └──────────────┘ └──────────────────┘
```

---

## 模块职责

### 1. Agent.Types - 类型定义层

**职责**：定义整个系统的核心数据类型

```
Types.hs
├── 消息类型 (Role, Message, ToolCall)
├── 工具类型 (ToolDef, ToolResult)
├── Hook 类型 (HookEvent, HookContext, HookHandler)
├── 配置类型 (AgentConfig)
└── 状态类型 (AgentState)
```

**设计原则**：
- 不可变数据
- Maybe 表示可选值
- 完整的 JSON 序列化支持

---

### 2. Agent.Tools - 工具系统

**职责**：提供工具定义、执行和管理

```
Tools.hs
├── ToolExecutor (工具执行器)
│   ├── execName: 工具名称
│   ├── execDescription: 工具描述
│   ├── execParameters: JSON Schema
│   └── execFunction: 执行函数
├── 内置工具
│   ├── echoTool: 回显工具
│   ├── calculatorTool: 计算器
│   ├── bashTool: Bash 命令
│   └── readFileTool: 文件读取
└── 工具管理
    ├── toToolDef: 转换为 OpenAI 格式
    └── executeTool: 执行工具（带异常处理）
```

**扩展方式**：
```haskell
myTool :: ToolExecutor
myTool = ToolExecutor { ... }

-- 添加到内置工具列表
builtinTools = [echoTool, ..., myTool]
```

---

### 3. Agent.Hooks - 事件系统

**职责**：实现事件驱动的钩子机制

```
Hooks.hs
├── HookRegistration (Hook 注册项)
│   ├── hookId: 唯一标识
│   ├── hookEvent: 触发事件
│   ├── hookHandler: 处理函数
│   └── hookPriority: 优先级
├── HookRegistry (注册表)
│   ├── emptyRegistry: 空注册表
│   ├── registerHook: 注册 Hook
│   └── sortedHooks: 按优先级排序
├── 事件发射
│   └── emitEvent: 触发事件并执行 Hooks
└── 内置 Hooks
    ├── sessionRestoreHook: 恢复会话
    ├── sessionSaveHook: 保存会话
    ├── securityScanHook: 安全检查
    └── continuousLearnHook: 持续学习
```

**事件流**：
```
事件触发
  ↓
sortedHooks (按优先级排序)
  ↓
foldl 链式执行
  ↓
每个 Hook 可修改上下文或中止
  ↓
返回最终上下文
```

---

### 4. Agent.Core - 核心逻辑

**职责**：实现 Agent 的主要业务逻辑

```
Core.hs
├── AgentEnv (运行环境)
│   ├── envConfig: Agent 配置
│   ├── envTools: 工具列表
│   ├── envToolMap: 工具映射 (HashMap)
│   └── envRegistry: Hook 注册表
├── AgentM (Monad)
│   └── StateT AgentState IO
├── 初始化
│   └── initAgent: 创建 Agent 环境和状态
├── LLM 交互
│   └── callLLM: 调用 LLM API
├── 工具处理
│   └── handleToolCalls: 执行工具调用
├── 对话处理
│   └── processTurn: 处理一轮对话
└── 会话管理
    ├── startSession: 开始会话
    ├── endSession: 结束会话
    └── resetConversation: 重置对话
```

**核心流程**：
```haskell
processTurn env userInput = do
    1. 生成 turnId
    2. 触发 TurnStart Hook
    3. 触发 UserPromptSubmit Hook
    4. 添加用户消息到历史
    5. 调用 LLM
    6. 如果有工具调用:
       a. 触发 ToolCall Hook
       b. 执行工具
       c. 添加工具结果到历史
       d. 再次调用 LLM
    7. 触发 AssistantResponse Hook
    8. 添加助手回复到历史
    9. 触发 TurnEnd Hook
    10. 返回结果
```

---

### 5. Agent.Session - 会话管理

**职责**：处理会话持久化和用户交互

```
Session.hs
├── 会话持久化
│   ├── saveSessionToFile: 保存到 JSON 文件
│   └── loadSessionFromFile: 从文件加载
├── 交互循环
│   └── interactiveLoop: CLI 交互界面
└── 示例运行
    └── runAgentExample: 完整示例
```

**会话文件格式**：
```json
{
  "session_id": "uuid-here",
  "history": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "turn_count": 42
}
```

---

## 数据流详解

### 1. 用户输入处理

```
用户输入 "你好"
  ↓
TIO.getLine 读取输入
  ↓
processTurn env "你好"
  ↓
创建 HookContext (TurnStart)
  ↓
emitEvent TurnStart → 执行 Hooks
  ↓
检查 shouldAbort
  ├─ True → 返回错误
  └─ False → 继续
  ↓
创建 HookContext (UserPromptSubmit)
  ↓
emitEvent UserPromptSubmit
  ↓
修改状态: stateHistory ++ [Message User "你好"]
  ↓
callLLM env currentHistory
  ↓
获取 LLM 响应
  ↓
检查是否有 tool_calls
  ├─ 有 → 执行工具调用循环
  └─ 无 → 直接返回
  ↓
创建 HookContext (AssistantResponse)
  ↓
emitEvent AssistantResponse
  ↓
修改状态: stateHistory ++ [Message Assistant response]
  ↓
返回 Either Text Text
```

---

### 2. 工具调用循环

```
LLM 返回 tool_calls
  ↓
handleToolCalls env toolCalls
  ↓
对每个 ToolCall:
  ├─ 解析 tcArguments (JSON)
  ├─ 查找 toolName 在 envToolMap
  ├─ executeTool executor args
  │   ├─ try (execFunction args)
  │   ├─ Left err → ToolResult { success=False }
  │   └─ Right output → ToolResult { success=True }
  └─ 创建 Message Tool result
  ↓
添加消息到历史:
  ├─ Message Assistant (LLM 原始回复)
  └─ Message Tool (工具结果) × N
  ↓
再次 callLLM (让 LLM 处理工具结果)
  ↓
如果还有 tool_calls → 循环
否则 → 返回最终回复
```

---

### 3. Hook 执行链

```
emitEvent event ctx registry
  ↓
sortedHooks event registry
  ├─ 过滤: hookEvent == event
  └─ 排序: by hookPriority (升序)
  ↓
foldl (\accCtx hook -> ...) (pure ctx) hooks
  ↓
对每个 Hook:
  ├─ 检查 shouldAbort
  │   ├─ True → 跳过，传递当前 ctx
  │   └─ False → 执行 hookHandler
  ├─ hookHandler ctx
  │   ├─ 读取 ctx 数据
  │   ├─ 执行业务逻辑
  │   ├─ 可能修改 ctx
  │   └─ 返回新 ctx
  └─ 传递给下一个 Hook
  ↓
返回最终 HookContext
```

---

## Monad 设计

### AgentM Monad

```haskell
newtype AgentM a = AgentM 
    { runAgentM :: StateT AgentState IO a 
    }
```

**为什么这样设计？**

1. **StateT**: 管理 Agent 状态（历史、计数器等）
2. **IO**: 允许执行 IO 操作（API 调用、文件读写）
3. **newtype**: 类型安全，避免误用

**使用示例**：

```haskell
-- 获取状态
currentState <- get

-- 修改状态
modify $ \s -> s { stateTurnCount = stateTurnCount s + 1 }

-- 执行 IO
result <- liftIO $ callLLM env messages

-- 返回值
pure $ Right response
```

---

## 错误处理策略

### 1. 业务错误 - Either Monad

```haskell
processTurn :: AgentEnv -> Text -> AgentM (Either Text Text)
--                          成功: Text    失败: Text
```

### 2. 系统错误 - Exception

```haskell
result <- try (execFunction executor args) :: IO (Either SomeException Text)
case result of
    Left err -> -- 处理异常
    Right output -> -- 正常结果
```

### 3. 可选值 - Maybe

```haskell
data Message = Message
    { msgToolCallId :: Maybe Text  -- 可能为空
    , msgToolCalls :: Maybe [ToolCall]
    }
```

---

## 并发安全

### 不可变数据

所有数据结构都是不可变的，天然线程安全：

```haskell
-- ❌ 不可能：Haskell 数据不可变
stateHistory = stateHistory ++ [newMessage]

-- ✅ 创建新列表
let newHistory = stateHistory ++ [newMessage]
```

### STM (Software Transactional Memory)

未来可以扩展使用 STM：

```haskell
import Control.Concurrent.STM

-- 线程安全的共享状态
type TAgentState = TVar AgentState

updateState :: TAgentState -> (AgentState -> AgentState) -> STM ()
updateState tvar f = modifyTVar tvar f
```

---

## 扩展点

### 1. 添加新的 LLM 提供商

修改 `callLLM` 函数：

```haskell
callLLM :: AgentEnv -> [Message] -> IO LLMResponse
callLLM env messages = do
    let config = envConfig env
    case cfgModel config of
        "gpt-*" -> callOpenAI config messages
        "claude-*" -> callClaude config messages
        _ -> callCustomAPI config messages
```

### 2. 添加新的存储后端

实现会话持久化接口：

```haskell
class SessionStore m where
    saveSession :: AgentState -> m ()
    loadSession :: Text -> m (Maybe AgentState)

-- 文件存储
instance SessionStore IO where
    saveSession = saveSessionToFile
    loadSession = loadSessionFromFile

-- 数据库存储
instance SessionStore PG where
    saveSession = saveSessionToDB
    loadSession = loadSessionFromDB
```

### 3. 添加流式支持

```haskell
processTurnStream :: AgentEnv -> Text -> AgentM (ConduitT () Text IO ())
processTurnStream env userInput = do
    -- 返回流式数据源
    stream <- liftIO $ callLLMStream env messages
    pure $ processStream stream
```

---

## 性能优化建议

### 1. 严格求值

```haskell
import Control.Monad.State.Strict  -- 而非 Lazy
```

### 2. 高效数据结构

```haskell
-- 列表适合小数据
stateHistory :: [Message]

-- 大数据使用 Sequence
import qualified Data.Sequence as Seq
stateHistory :: Seq Message
```

### 3. 文本处理

```haskell
-- 使用 Text 而非 String
import qualified Data.Text as T
import qualified Data.Text.IO as TIO
```

### 4. 编译优化

```cabal
ghc-options: -O2 -flate-specialise -fspecialise-aggressively
```

---

## 测试策略

### 1. 单元测试

```haskell
testToolExecution :: Test
testToolExecution = TestCase $ do
    result <- executeTool echoTool testArgs
    assertEqual "Echo output" expected result
```

### 2. 属性测试

```haskell
prop_sessionPersist :: AgentState -> Property
prop_sessionPersist state = do
    -- 保存后加载应该相同
    saveSessionToFile state
    loaded <- loadSessionFromFile (stateSessionId state)
    loaded === Just state
```

### 3. 集成测试

```haskell
testFullConversation :: IO ()
testFullConversation = do
    (env, state) <- initAgent config tools
    result <- runAgentM (processTurn env "你好") state
    assertSuccess result
```

---

## 部署架构

### 开发环境

```
agent-course-hs/
├── src/           # 源代码
├── app/           # 可执行文件
├── test/          # 测试
└── cabal.project  # 本地配置
```

### 生产环境

```
┌─────────────────┐
│   Load Balancer │
└────────┬────────┘
         │
┌────────▼────────┐
│  Agent Service  │  (Haskell 编译的二进制)
│  - HTTP API     │
│  - WebSocket    │
└────────┬────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  (会话存储)
│     Redis       │  (缓存)
└─────────────────┘
```

---

## 监控与日志

### 结构化日志

```haskell
import Control.Monad.Logger

logTurn :: Text -> Text -> AgentM ()
logTurn userInput response = 
    logInfoN $ "Turn completed: input=" <> userInput <> ", response=" <> response
```

### 指标收集

```haskell
data AgentMetrics = AgentMetrics
    { metricTotalTurns :: Int
    , metricAvgResponseTime :: Double
    , metricToolCallCount :: Int
    }
```

---

## 安全考虑

### 1. 工具权限

```haskell
data ToolPermission = Allow | Deny | AskUser

checkPermission :: ToolExecutor -> AgentM ToolPermission
checkPermission tool = do
    if execName tool == "bash"
        then pure AskUser  -- Bash 需要用户确认
        else pure Allow
```

### 2. 输入验证

```haskell
validateInput :: Text -> Either Text Text
validateInput input
    | T.length input > 4000 = Left "输入过长"
    | T.any isControl input = Left "包含控制字符"
    | otherwise = Right input
```

### 3. API Key 管理

```haskell
-- 从环境变量读取，不硬编码
apiKey <- liftIO $ lookupEnv "OPENAI_API_KEY"
```

---

## 未来发展方向

1. **流式响应支持** - Conduit/Pipes
2. **多 Agent 协作** - 消息传递
3. **技能系统** - 可插拔能力
4. **MCP 协议** - Model Context Protocol
5. **图形界面** - Haskell GUI (Gtk/Qt)
6. **Web API** - Servant/WAI
7. **分布式部署** - Cloud Haskell

---

这份架构文档展示了 Haskell Agent 的完整设计思路和实现细节。每个模块都有清晰的职责，通过类型系统和 Monad 实现了安全、可维护的代码。
