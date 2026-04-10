# 快速开始指南

## 5 分钟上手 Haskell Agent

### 步骤 1：环境准备

```bash
# 安装 Haskell 工具链（如果还没有）
curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh

# 按照提示安装 ghcup，然后：
ghcup install ghc 9.4.7
ghcup install cabal 3.10.2.1
ghcup set ghc 9.4.7
ghcup set cabal 3.10.2.1

# 验证安装
ghc --version
cabal --version
```

### 步骤 2：构建项目

```bash
cd agent-course-hs

# 更新包索引
cabal update

# 构建项目
cabal build
```

### 步骤 3：运行示例

```bash
# 运行交互式 Agent（模拟模式）
cabal run agent-example
```

你会看到：
```
🤖 Agent 已启动！输入 'quit' 退出，'reset' 重置对话
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你: 你好
```

### 步骤 4：配置真实 API（可选）

```bash
# 设置 OpenAI API Key
export OPENAI_API_KEY="sk-your-key-here"

# 或者使用其他兼容 OpenAI API 的服务
export OPENAI_BASE_URL="https://api.your-service.com/v1"
```

---

## 核心概念速成

### 1. Agent 是什么？

Agent = 配置 + 工具 + Hook 系统 + 状态管理

```
┌──────────────────────────────────────┐
│           Agent                      │
├──────────────────────────────────────┤
│  AgentConfig  │ 系统提示、模型、API  │
│  AgentState   │ 历史、会话 ID        │
│  ToolExecutor │ 工具定义和执行器     │
│  HookRegistry │ 事件钩子注册表       │
└──────────────────────────────────────┘
```

### 2. 消息流转

```
用户输入
  ↓
Message User "你好"
  ↓
[TurnStart Hook]
  ↓
[UserPromptSubmit Hook]
  ↓
LLM API 调用
  ↓
Message Assistant "你好！我是助手"
  ↓
[AssistantResponse Hook]
  ↓
[TurnEnd Hook]
  ↓
返回给用户
```

### 3. 工具调用流程

```
用户: "帮我计算 2+2"
  ↓
LLM: 我需要调用 calculator 工具
  ↓
ToolCall { tcFunctionName = "calculator" }
  ↓
[ToolCall Hook] → 安全检查
  ↓
executeTool calculator {"expression": "2+2"}
  ↓
ToolResult { trOutput = "计算结果: 4" }
  ↓
Message Tool "计算结果: 4"
  ↓
LLM 处理工具结果
  ↓
Message Assistant "2+2=4"
```

---

## 代码导览

### 类型系统 (`src/Agent/Types.hs`)

这是整个系统的"合同"，定义了所有数据结构：

```haskell
-- 消息角色（谁说的）
data Role = System | User | Assistant | Tool

-- 聊天消息
data Message = Message
    { msgRole :: Role
    , msgContent :: Text
    , msgToolCallId :: Maybe Text
    , msgToolCalls :: Maybe [ToolCall]
    }
```

**学习点**：`Maybe` 类型表示可能为空的值，比 `None` 更安全。

---

### 工具系统 (`src/Agent/Tools.hs`)

每个工具是一个 `ToolExecutor` 记录：

```haskell
data ToolExecutor = ToolExecutor
    { execName :: Text              -- 工具名称
    , execDescription :: Text       -- 工具描述
    , execParameters :: Value       -- JSON Schema
    , execFunction :: Value -> IO Text  -- 执行函数
    }
```

**创建自定义工具**：

```haskell
weatherTool :: ToolExecutor
weatherTool = ToolExecutor
    { execName = "weather"
    , execDescription = "查询天气"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "city" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("城市名称" :: Text)
                ]
            ]
        ]
    , execFunction = \args -> do
        -- 实际应调用天气 API
        pure "晴天，25°C"
    }
```

---

### Hook 系统 (`src/Agent/Hooks.hs`)

Hook = 事件触发器 + 处理函数

```haskell
-- Hook 处理函数类型
type HookHandler = HookContext -> IO HookContext

-- 示例：日志 Hook
loggingHook :: HookHandler
loggingHook ctx = do
    putStrLn $ "[Hook] 事件: " ++ show (hcEvent ctx)
    pure ctx  -- 返回可能修改后的上下文
```

**注册 Hook**：

```haskell
let registry = registerHook 
    "my_logger"        -- Hook ID
    TurnStart          -- 触发事件
    loggingHook        -- 处理函数
    50                 -- 优先级（数字越小越先执行）
    emptyRegistry      -- 注册表
```

---

### 核心逻辑 (`src/Agent/Core.hs`)

使用 `StateT` monad 管理状态：

```haskell
-- Agent Monad
newtype AgentM a = AgentM 
    { runAgentM :: StateT AgentState IO a 
    }

-- 处理一轮对话
processTurn :: AgentEnv -> Text -> AgentM (Either Text Text)
processTurn env userInput = do
    -- 获取当前状态
    currentState <- get
    
    -- 修改状态
    modify $ \s -> s { stateTurnCount = stateTurnCount s + 1 }
    
    -- 执行 IO 操作
    result <- liftIO $ callLLM env messages
    
    -- 返回结果
    pure $ Right response
```

**学习点**：
- `get` - 获取当前状态
- `modify` - 更新状态
- `liftIO` - 在 Monad 中执行 IO
- `pure` - 返回值

---

## 常见任务

### 添加新工具

1. 编辑 `src/Agent/Tools.hs`
2. 添加新的 `ToolExecutor`
3. 加入 `builtinTools` 列表

```haskell
-- 添加到这里
builtinTools :: [ToolExecutor]
builtinTools = [echoTool, calculatorTool, bashTool, readFileTool, yourNewTool]
```

### 添加新 Hook

1. 编辑 `src/Agent/Hooks.hs`
2. 定义 `HookHandler`
3. 在 `registerBuiltinHooks` 中注册

### 修改 Agent 行为

编辑 `src/Agent/Core.hs` 中的 `processTurn` 函数。

---

## 调试技巧

### 1. 打印调试信息

```haskell
processTurn env userInput = do
    liftIO $ putStrLn $ "[DEBUG] 用户输入: " ++ show userInput
    -- ... 其他代码
```

### 2. 查看状态

```haskell
processTurn env userInput = do
    state <- get
    liftIO $ print state  -- 打印当前状态
```

### 3. GHCi 交互式调试

```bash
# 启动 GHCi
cabal repl

# 在 GHCi 中
> :load Agent.Core
> :type processTurn
> :info AgentState
```

---

## 性能优化

### 1. 启用优化

```bash
# 在 agent-hs.cabal 中
ghc-options: -O2
```

### 2. 严格求值

```haskell
-- 使用严格版本的 State Monad
import Control.Monad.State.Strict
```

### 3. 避免不必要的复制

```haskell
-- ❌ 不好：复制整个列表
let newHistory = oldHistory ++ [newMessage]

-- ✅ 更好：使用 Data.Sequence
import qualified Data.Sequence as Seq
let newHistory = oldHistory |> newMessage
```

---

## 测试

### 单元测试示例

创建 `test/TestTools.hs`:

```haskell
module Main where

import Agent.Tools
import Test.HUnit
import Data.Aeson

testEchoTool :: Test
testEchoTool = TestCase $ do
    let args = object ["message" .= ("hello" :: String)]
    result <- executeTool echoTool args
    assertBool "Echo should return message" 
        (trOutput result == "Echo: hello")

main :: IO ()
main = do
    runTestTT testEchoTool
    return ()
```

运行测试：

```bash
cabal test
```

---

## 部署

### 编译可执行文件

```bash
cabal install --installdir=./dist
```

生成 `./dist/agent-example`，可以独立运行。

### Docker 部署

```dockerfile
FROM haskell:9.4 as builder
WORKDIR /app
COPY . .
RUN cabal update && cabal build

FROM debian:bullseye-slim
COPY --from=builder /app/dist/build/agent-example/agent-example /usr/local/bin/
CMD ["agent-example"]
```

---

## 常见问题

### Q: 编译错误 "Could not find module"

```bash
cabal clean
cabal update
cabal build
```

### Q: 如何查看生成的文档？

```bash
cabal haddock --open
```

### Q: 运行时找不到模块

确保在 `agent-hs.cabal` 的 `exposed-modules` 中列出了模块。

---

## 下一步

1. 📖 阅读 `README.md` 了解完整架构
2. 🔍 查看 `HASKELL_VS_PYTHON.md` 对比学习
3. 💻 修改代码，添加自己的工具
4. 🚀 集成真实的 LLM API

---

## 获取帮助

- 📚 [Learn You a Haskell](http://learnyouahaskell.com/) - Haskell 入门教程
- 📖 [Real World Haskell](http://book.realworldhaskell.org/) - 实战指南
- 💬 [Haskell Discord](https://discord.gg/haskell) - 社区支持

祝你学习愉快！🎉
