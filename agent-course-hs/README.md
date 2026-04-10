# Agent Haskell 实现

这是使用 Haskell 从零实现的 AI Agent，对应 Python 版本的 `agent.py` 功能。

## 功能特性

✅ **核心对话系统**
- 支持系统提示词（System Prompt）
- 对话历史管理
- 多轮对话支持

✅ **工具调用机制**
- 工具注册与发现
- 工具定义生成（OpenAI 格式）
- 工具执行与结果处理
- 内置工具：Echo、Calculator、Bash、ReadFile

✅ **Hook 事件系统**
- 事件总线（EventBus）
- Hook 注册表（HookRegistry）
- 优先级调度
- 内置 Hook：
  - Session Restore/Save（会话持久化）
  - Security Scan（安全扫描）
  - Continuous Learn（持续学习）

✅ **会话管理**
- 会话 ID 生成
- 对话历史持久化
- 会话恢复

✅ **类型安全**
- 完整的类型定义
- JSON 序列化/反序列化
- 错误处理

## 项目结构

```
agent-course-hs/
├── agent-hs.cabal              # Cabal 构建配置
├── src/
│   └── Agent/
│       ├── Types.hs           # 核心类型定义
│       ├── Tools.hs           # 工具系统
│       ├── Hooks.hs           # Hook 事件系统
│       ├── Core.hs            # Agent 核心逻辑
│       └── Session.hs         # 会话管理
└── app/
    └── Main.hs                # 主程序入口
```

## 类型系统

### 核心类型

```haskell
-- 消息角色
data Role = System | User | Assistant | Tool

-- 聊天消息
data Message = Message
    { msgRole :: Role
    , msgContent :: Text
    , msgToolCallId :: Maybe Text
    , msgToolCalls :: Maybe [ToolCall]
    }

-- 工具调用
data ToolCall = ToolCall
    { tcId :: Text
    , tcFunctionName :: Text
    , tcArguments :: Text
    }

-- Agent 配置
data AgentConfig = AgentConfig
    { cfgSystemPrompt :: Text
    , cfgModel :: Text
    , cfgApiKey :: Maybe Text
    , cfgApiBaseUrl :: Maybe Text
    }
```

### Hook 系统类型

```haskell
-- Hook 事件类型
data HookEvent 
    = SessionStart
    | SessionEnd
    | TurnStart
    | TurnEnd
    | ToolCall
    | UserPromptSubmit
    | AssistantResponse

-- Hook 上下文
data HookContext = HookContext
    { hcEvent :: HookEvent
    , hcData :: HM.HashMap Text Value
    , hcSessionId :: Maybe Text
    , hcTurnId :: Maybe Text
    , hcShouldAbort :: Bool
    , hcAbortReason :: Maybe Text
    }
```

## 安装与运行

### 前置要求

- GHC 8.10+ 
- Cabal 3.4+

### 安装依赖

```bash
cd agent-course-hs
cabal update
cabal build
```

### 运行示例

```bash
# 运行交互式 Agent
cabal run agent-example
```

### 设置 API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
cabal run agent-example
```

## 使用示例

### 基本对话

```haskell
import Agent.Core
import Agent.Types
import Agent.Tools

main :: IO ()
main = do
    let config = AgentConfig
            { cfgSystemPrompt = "你是一个有用的 AI 助手"
            , cfgModel = "gpt-4o-mini"
            , cfgApiKey = Just "your-key"
            , cfgApiBaseUrl = Nothing
            }
    
    let tools = [echoTool, calculatorTool]
    
    (env, state) <- initAgent config tools
    runAgentM (startSession env) state
    
    result <- runAgentM (processTurn env "你好！") state
    case result of
        (Right response, newState) -> 
            putStrLn $ "Agent: " ++ show response
        (Left error, newState) ->
            putStrLn $ "错误: " ++ show error
```

### 自定义工具

```haskell
-- 创建一个自定义工具
myCustomTool :: ToolExecutor
myCustomTool = ToolExecutor
    { execName = "my_tool"
    , execDescription = "我的自定义工具"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "input" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("输入参数" :: Text)
                ]
            ]
        , "required" .= (["input"] :: [Text])
        ]
    , execFunction = \args -> do
        case args of
            Object obj -> do
                case lookup "input" obj of
                    Just (String input) -> 
                        pure $ "处理结果: " <> input
                    _ -> pure "Error: missing 'input' parameter"
            _ -> pure "Error: expected object"
    }

-- 使用自定义工具
let tools = [myCustomTool]
(env, state) <- initAgent config tools
```

### 自定义 Hook

```haskell
-- 创建一个自定义 Hook
myLoggingHook :: HookHandler
myLoggingHook ctx = do
    let eventName = hcEvent ctx
    putStrLn $ "[Hook] 事件触发: " ++ show eventName
    pure ctx  -- 返回修改后的上下文

-- 注册 Hook
let registry = registerHook "my_logger" TurnStart myLoggingHook 50 emptyRegistry
```

## 与 Python 版本对比

| 功能 | Python 版本 | Haskell 版本 |
|------|------------|-------------|
| 对话管理 | `Agent.messages` | `AgentState.stateHistory` |
| 工具注册 | `tool_map` | `envToolMap` (HashMap) |
| Hook 系统 | `EventBus` + `HookRegistry` | 相同架构，函数式实现 |
| 会话持久化 | JSON 文件 | JSON 文件（aeson） |
| 类型安全 | 动态类型 | 静态强类型 |
| 错误处理 | 异常 | Either Monad |
| 并发 | asyncio | async + STM |

## 架构设计

### Monad 设计模式

使用 `StateT` monad transformer 管理 Agent 状态：

```haskell
newtype AgentM a = AgentM 
    { runAgentM :: StateT AgentState IO a 
    }
```

### 事件驱动架构

```
用户输入
  ↓
TurnStart Hook
  ↓
UserPromptSubmit Hook
  ↓
LLM 调用
  ↓
[ToolCall Hook → 工具执行]（循环）
  ↓
AssistantResponse Hook
  ↓
TurnEnd Hook
```

## 扩展开发

### 添加新工具

1. 在 `Agent/Tools.hs` 中定义 `ToolExecutor`
2. 实现 `execFunction`
3. 添加到 `builtinTools` 列表

### 添加新 Hook

1. 在 `Agent/Hooks.hs` 中定义 `HookHandler`
2. 使用 `registerHook` 注册
3. 设置优先级（数字越小优先级越高）

### 集成真实 LLM API

修改 `callLLM` 函数，使用 `http-conduit` 或 `req` 库调用真实的 OpenAI/Claude API。

## 技术栈

- **aeson**: JSON 处理
- **text**: 高效文本处理
- **mtl**: Monad 转换器
- **transformers**: 标准 monad 转换器
- **uuid**: UUID 生成
- **unordered-containers**: 高效 HashMap
- **async**: 异步编程

## 课程对应

- **第 1-2 章**: 最小可用 Agent - `Agent.Core` 基础对话
- **第 3 章**: 工具调用 - `Agent.Tools` 工具系统
- **第 11 章**: Hook 系统 - `Agent.Hooks` 事件驱动
- **第 6 章**: 记忆系统 - `Agent.Session` 会话管理

## License

MIT
