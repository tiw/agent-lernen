# Python → Haskell 速查表

## 基础语法对比

### 1. 变量定义

**Python**
```python
name = "Agent"
version = 1.0
tools = []
config = None
```

**Haskell**
```haskell
name :: String
name = "Agent"

version :: Double
version = 1.0

tools :: [ToolExecutor]
tools = []

config :: Maybe AgentConfig
config = Nothing
```

---

### 2. 函数定义

**Python**
```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b
```

**Haskell**
```haskell
greet :: String -> String
greet name = "Hello, " ++ name ++ "!"

add :: Int -> Int -> Int
add a b = a + b
```

---

### 3. 条件判断

**Python**
```python
if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
else:
    grade = "C"
```

**Haskell**
```haskell
grade = if score >= 90 then "A"
        else if score >= 80 then "B"
        else "C"

-- 或使用模式匹配
grade'
    | score >= 90 = "A"
    | score >= 80 = "B"
    | otherwise   = "C"
```

---

### 4. 循环

**Python**
```python
# for 循环
for i in range(5):
    print(i)

# while 循环
while condition:
    do_something()

# 列表推导
squares = [x**2 for x in range(10)]
```

**Haskell**
```haskell
-- map / foreach
mapM_ print [0..4]

-- 递归
loop condition = do
    if condition
        then do
            doSomething
            loop newCondition
        else pure ()

-- 列表推导
squares = [x^2 | x <- [0..9]]
```

---

## 数据结构对比

### 5. 列表/数组

**Python**
```python
items = [1, 2, 3]
items.append(4)
first = items[0]
rest = items[1:]
```

**Haskell**
```haskell
items = [1, 2, 3]
newItems = items ++ [4]  -- 不可变，创建新列表
first = head items
rest = tail items

-- 模式匹配解构
case items of
    (x:xs) -> ...  -- x 是第一个，xs 是剩余
    [] -> ...      -- 空列表
```

---

### 6. 字典/HashMap

**Python**
```python
data = {"name": "Agent", "version": 1.0}
name = data.get("name", "Unknown")
data["status"] = "running"
```

**Haskell**
```haskell
import qualified Data.HashMap.Strict as HM

data = HM.fromList [("name", "Agent"), ("version", 1.0)]
name = HM.lookup "name" data  -- 返回 Maybe Text

newData = HM.insert "status" "running" data
```

---

### 7. 类/数据记录

**Python**
```python
class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
        self.tool_call_id = None
    
    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content
        }
```

**Haskell**
```haskell
data Message = Message
    { msgRole :: Role
    , msgContent :: Text
    , msgToolCallId :: Maybe Text
    } deriving (Show, Generic)

-- 自动派生 JSON
instance ToJSON Message
instance FromJSON Message

-- 创建实例
msg = Message 
    { msgRole = User
    , msgContent = "Hello"
    , msgToolCallId = Nothing
    }

-- 更新字段
newMsg = msg { msgContent = "Updated" }
```

---

## 错误处理对比

### 8. 异常处理

**Python**
```python
try:
    result = risky_operation()
except Exception as e:
    print(f"Error: {e}")
    result = default_value
finally:
    cleanup()
```

**Haskell**
```haskell
import Control.Exception (try, SomeException)

do
    result <- try (riskyOperation) :: IO (Either SomeException Result)
    case result of
        Left err -> do
            putStrLn $ "Error: " ++ show err
            pure defaultValue
        Right val -> pure val
```

---

### 9. 可选值

**Python**
```python
def get_user(user_id):
    user = db.find(user_id)
    if user is None:
        return "User not found"
    return user.name
```

**Haskell**
```haskell
getUser :: UserId -> IO String
getUser userId = do
    user <- findUser userId  -- 返回 Maybe User
    case user of
        Nothing -> pure "User not found"
        Just u -> pure (userName u)
```

---

## Monad 和 IO

### 10. 状态管理

**Python**
```python
class Counter:
    def __init__(self):
        self.count = 0
    
    def increment(self):
        self.count += 1
        return self.count
```

**Haskell**
```haskell
import Control.Monad.State

type CounterM = State Int

increment :: CounterM Int
increment = do
    modify (+1)
    get

-- 运行
result = execState increment 0  -- 返回 1
```

---

### 11. IO 操作

**Python**
```python
def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None
```

**Haskell**
```haskell
import System.IO.Error (catchIOError)

readFile' :: FilePath -> IO (Maybe String)
readFile' path = 
    catchIOError (Just <$> readFile path) 
                 (\_ -> pure Nothing)
```

---

## Agent 特定对比

### 12. Agent 初始化

**Python**
```python
class Agent:
    def __init__(self, system_prompt, model, tools=None):
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model = model
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}
```

**Haskell**
```haskell
initAgent :: AgentConfig -> [ToolExecutor] -> IO (AgentEnv, AgentState)
initAgent config tools = do
    sessionId <- show <$> UUID.nextRandom
    let env = AgentEnv
            { envConfig = config
            , envTools = tools
            , envToolMap = HM.fromList $ map (\t -> (execName t, t)) tools
            , envRegistry = registerBuiltinHooks emptyRegistry
            }
    let state = AgentState
            { stateSessionId = T.pack sessionId
            , stateTurnId = Nothing
            , stateHistory = [Message System (cfgSystemPrompt config) Nothing Nothing]
            , stateTurnCount = 0
            }
    pure (env, state)
```

---

### 13. 对话处理

**Python**
```python
def chat(self, user_input: str) -> str:
    self.messages.append({"role": "user", "content": user_input})
    
    response = self.client.chat.completions.create(
        model=self.model,
        messages=self.messages,
    )
    
    reply = response.choices[0].message.content
    self.messages.append({"role": "assistant", "content": reply})
    return reply
```

**Haskell**
```haskell
processTurn :: AgentEnv -> Text -> AgentM (Either Text Text)
processTurn env userInput = do
    -- 添加用户消息
    modify $ \s -> s
        { stateHistory = stateHistory s ++ [Message User userInput Nothing Nothing]
        }
    
    -- 调用 LLM
    currentHistory <- gets stateHistory
    llmResponse <- liftIO $ callLLM env currentHistory
    
    let reply = llmContent llmResponse
    
    -- 添加助手回复
    modify $ \s -> s
        { stateHistory = stateHistory s ++ [Message Assistant reply Nothing Nothing]
        }
    
    pure $ Right reply
```

---

### 14. 工具调用

**Python**
```python
if message.tool_calls:
    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        if tool_name in self.tool_map:
            result = self.tool_map[tool_name].execute(**tool_args)
        else:
            result = f"[错误] 未知工具: {tool_name}"
        
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        })
```

**Haskell**
```haskell
handleToolCalls :: AgentEnv -> [ToolCall] -> IO [Message]
handleToolCalls env toolCalls = mapM handleOne toolCalls
  where
    handleOne :: ToolCall -> IO Message
    handleOne tc = do
        let toolName = tcFunctionName tc
        let args = either (const Null) id (decode (tcArguments tc))
        
        case HM.lookup toolName (envToolMap env) of
            Just executor -> do
                result <- executeTool executor args
                pure $ Message Tool (trOutput result) (Just $ tcId tc) Nothing
            Nothing -> 
                pure $ Message Tool ("[错误] 未知工具: " <> toolName) (Just $ tcId tc) Nothing
```

---

### 15. Hook 系统

**Python**
```python
async def emit(self, event: HookEvent, ctx: HookContext):
    handlers = sorted(
        [h for h in self.handlers if h.event == event],
        key=lambda h: h.priority
    )
    
    for handler in handlers:
        if ctx.should_abort:
            break
        ctx = await handler(ctx)
    
    return ctx
```

**Haskell**
```haskell
emitEvent :: HookEvent -> HookContext -> HookRegistry -> IO HookContext
emitEvent event ctx registry = do
    let hooks = sortedHooks event registry
    foldl (\accCtx hook -> do
        currentCtx <- accCtx
        if hcShouldAbort currentCtx
            then pure currentCtx
            else hookHandler hook currentCtx
        ) (pure ctx) hooks
```

---

## JSON 处理对比

### 16. 序列化

**Python**
```python
import json

data = {"name": "Agent", "version": 1.0}
json_str = json.dumps(data)
```

**Haskell**
```haskell
import Data.Aeson

data = object ["name" .= ("Agent" :: String), "version" .= (1.0 :: Double)]
jsonStr = encode data
```

---

### 17. 反序列化

**Python**
```python
json_str = '{"name": "Agent", "version": 1.0}'
data = json.loads(json_str)
name = data.get("name")
```

**Haskell**
```haskell
jsonStr = "{\"name\": \"Agent\", \"version\": 1.0}"
result = decode jsonStr :: Maybe Value

case result of
    Just (Object obj) -> do
        name <- HM.lookup "name" obj
        ...
    Nothing -> ...
```

---

## 并发对比

### 18. 异步操作

**Python**
```python
import asyncio

async def fetch_data():
    await asyncio.sleep(1)
    return "data"

async def main():
    result = await fetch_data()
    print(result)

asyncio.run(main())
```

**Haskell**
```haskell
import Control.Concurrent.Async

fetchData :: IO String
fetchData = do
    threadDelay 1000000  -- 1 秒
    pure "data"

main :: IO ()
main = do
    result <- fetchData
    putStrLn result

-- 并发执行
main' = do
    [r1, r2] <- mapConcurrently fetchData [1..2]
    print (r1, r2)
```

---

## 常用操作速查

### 19. 字符串操作

**Python**
```python
text = "hello world"
upper = text.upper()
parts = text.split(" ")
joined = "-".join(parts)
length = len(text)
```

**Haskell**
```haskell
import qualified Data.Text as T

text = "hello world"
upper = T.toUpper text
parts = T.splitOn " " text
joined = T.intercalate "-" parts
length = T.length text
```

---

### 20. 文件操作

**Python**
```python
# 读取
with open("file.txt") as f:
    content = f.read()

# 写入
with open("file.txt", "w") as f:
    f.write("content")
```

**Haskell**
```haskell
-- 读取
content <- readFile "file.txt"

-- 写入
writeFile "file.txt" "content"

-- 带错误处理
result <- try (readFile "file.txt") :: IO (Either SomeException String)
```

---

## 快速参考表

| Python | Haskell | 说明 |
|--------|---------|------|
| `None` | `Nothing` | 空值 |
| `List[T]` | `[T]` | 列表 |
| `Dict[K,V]` | `HashMap K V` | 字典 |
| `Optional[T]` | `Maybe T` | 可选值 |
| `Union[A,B]` | `Either A B` | 联合类型 |
| `class` | `data` | 数据类型 |
| `def` | 函数签名 + 实现 | 函数定义 |
| `try/except` | `try/catch` | 异常处理 |
| `for x in xs` | `mapM_ f xs` | 遍历 |
| `async/await` | `liftIO` / `async` | 异步 |
| `self.x` | `x record` | 字段访问 |
| `dict.get(k)` | `HashMap.lookup k` | 查找 |

---

## Monad 速查

| Monad | 用途 | 关键操作 |
|-------|------|---------|
| `IO` | 输入输出 | `liftIO`, `readFile` |
| `Maybe` | 可选值 | `return`, `>>=` |
| `Either e` | 错误处理 | `Left`, `Right` |
| `State s` | 状态管理 | `get`, `modify`, `put` |
| `Reader r` | 配置读取 | `ask`, `asks` |
| `Writer w` | 日志输出 | `tell`, `listen` |

---

## 学习路线

### 第 1 周：基础语法
- [ ] 变量和函数
- [ ] 模式匹配
- [ ] 列表操作
- [ ] 类型系统

### 第 2 周：高级类型
- [ ] Maybe 和 Either
- [ ] 代数数据类型 (ADT)
- [ ] 类型类 (Typeclass)
- [ ] Functor/Applicative

### 第 3 周：Monad
- [ ] IO Monad
- [ ] State Monad
- [ ] Monad Transformers
- [ ] do 语法糖

### 第 4 周：实战
- [ ] 理解 Agent 代码
- [ ] 添加新工具
- [ ] 添加新 Hook
- [ ] 编写测试

---

祝学习顺利！🚀
