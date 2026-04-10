{-# LANGUAGE DeriveGeneric #-}
{-# LANGUAGE OverloadedStrings #-}

module Agent.Types where

import Data.Aeson
import Data.Text (Text)
import GHC.Generics (Generic)
import qualified Data.HashMap.Strict as HM
import qualified Data.Vector as V

-- | 消息角色
data Role = System | User | Assistant | Tool
    deriving (Show, Eq, Generic)

instance ToJSON Role where
    toJSON = String . \case
        System -> "system"
        User -> "user"
        Assistant -> "assistant"
        Tool -> "tool"

instance FromJSON Role where
    parseJSON = withText "Role" $ \case
        "system" -> pure System
        "user" -> pure User
        "assistant" -> pure Assistant
        "tool" -> pure Tool
        r -> fail $ "Unknown role: " <> show r

-- | 工具调用信息
data ToolCall = ToolCall
    { tcId :: Text
    , tcFunctionName :: Text
    , tcArguments :: Text  -- JSON string
    } deriving (Show, Eq, Generic)

instance ToJSON ToolCall where
    toJSON (ToolCall tid tname targs) = object
        [ "id" .= tid
        , "type" .= ("function" :: Text)
        , "function" .= object
            [ "name" .= tname
            , "arguments" .= targs
            ]
        ]

instance FromJSON ToolCall where
    parseJSON = withObject "ToolCall" $ \v -> ToolCall
        <$> v .: "id"
        <*> (v .: "function" >>= (.: "name"))
        <*> (v .: "function" >>= (.: "arguments"))

-- | 聊天消息
data Message = Message
    { msgRole :: Role
    , msgContent :: Text
    , msgToolCallId :: Maybe Text  -- 仅在 role=tool 时使用
    , msgToolCalls :: Maybe [ToolCall]  -- 仅在 role=assistant 时可能有
    } deriving (Show, Eq, Generic)

instance ToJSON Message where
    toJSON (Message role content mToolCallId mToolCalls) = 
        let base = object
                [ "role" .= role
                , "content" .= content
                ]
        in case (mToolCallId, mToolCalls) of
            (Just tid, _) -> base <> object ["tool_call_id" .= tid]
            (_, Just tcs) -> base <> object ["tool_calls" .= tcs]
            _ -> base

instance FromJSON Message where
    parseJSON = withObject "Message" $ \v -> Message
        <$> v .: "role"
        <*> v .: "content"
        <*> v .:? "tool_call_id"
        <*> v .:? "tool_calls"

-- | 工具定义
data ToolDef = ToolDef
    { toolName :: Text
    , toolDescription :: Text
    , toolParameters :: Value  -- JSON Schema
    } deriving (Show, Eq, Generic)

instance ToJSON ToolDef where
    toJSON (ToolDef tname tdesc tparams) = object
        [ "type" .= ("function" :: Text)
        , "function" .= object
            [ "name" .= tname
            , "description" .= tdesc
            , "parameters" .= tparams
            ]
        ]

-- | LLM 响应
data LLMResponse = LLMResponse
    { llmContent :: Text
    , llmToolCalls :: Maybe [ToolCall]
    } deriving (Show, Eq, Generic)

instance FromJSON LLMResponse where
    parseJSON = withObject "LLMResponse" $ \v -> do
        choices <- v .: "choices"
        case choices of
            (c:_) -> do
                message <- c .: "message"
                content <- message .:? "content" .?= ""
                toolCalls <- message .:? "tool_calls"
                pure $ LLMResponse content toolCalls
            [] -> fail "Empty choices"

-- | Agent 配置
data AgentConfig = AgentConfig
    { cfgSystemPrompt :: Text
    , cfgModel :: Text
    , cfgApiKey :: Maybe Text
    , cfgApiBaseUrl :: Maybe Text
    } deriving (Show, Eq, Generic)

-- | 工具执行结果
data ToolResult = ToolResult
    { trToolName :: Text
    , trSuccess :: Bool
    , trOutput :: Text
    } deriving (Show, Eq)

-- | Hook 事件类型
data HookEvent 
    = SessionStart
    | SessionEnd
    | TurnStart
    | TurnEnd
    | ToolCall
    | UserPromptSubmit
    | AssistantResponse
    deriving (Show, Eq, Ord, Enum, Bounded)

-- | Hook 上下文
data HookContext = HookContext
    { hcEvent :: HookEvent
    , hcData :: HM.HashMap Text Value
    , hcSessionId :: Maybe Text
    , hcTurnId :: Maybe Text
    , hcShouldAbort :: Bool
    , hcAbortReason :: Maybe Text
    } deriving (Show, Eq)

-- | Hook 函数类型
type HookHandler = HookContext -> IO HookContext

-- | Agent 状态
data AgentState = AgentState
    { stateSessionId :: Text
    , stateTurnId :: Maybe Text
    , stateHistory :: [Message]
    , stateTurnCount :: Int
    } deriving (Show, Eq)
