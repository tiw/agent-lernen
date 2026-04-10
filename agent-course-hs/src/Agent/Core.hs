{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE DeriveGeneric #-}

module Agent.Core where

import Agent.Types
import Agent.Tools
import Agent.Hooks

import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.Text.IO as TIO
import qualified Data.Text.Encoding as TE
import qualified Data.HashMap.Strict as HM
import Data.Aeson
import Data.Aeson.Text (encodeToTextBuilder)
import Data.UUID (UUID)
import qualified Data.UUID.V4 as UUID
import Control.Monad.State.Strict
import Control.Monad.IO.Class
import System.Environment (lookupEnv)

-- | Agent 运行时环境
data AgentEnv = AgentEnv
    { envConfig :: AgentConfig
    , envTools :: [ToolExecutor]
    , envToolMap :: HM.HashMap Text ToolExecutor
    , envRegistry :: HookRegistry
    }

-- | Agent Monad
newtype AgentM a = AgentM 
    { runAgentM :: StateT AgentState IO a 
    } deriving (Functor, Applicative, Monad, MonadState AgentState, MonadIO)

-- | 创建工具映射
buildToolMap :: [ToolExecutor] -> HM.HashMap Text ToolExecutor
buildToolMap = HM.fromList . map (\t -> (execName t, t))

-- | 初始化 Agent
initAgent :: AgentConfig -> [ToolExecutor] -> IO (AgentEnv, AgentState)
initAgent config tools = do
    sessionId <- show <$> UUID.nextRandom
    let env = AgentEnv
            { envConfig = config
            , envTools = tools
            , envToolMap = buildToolMap tools
            , envRegistry = registerBuiltinHooks emptyRegistry
            }
    let state = AgentState
            { stateSessionId = T.pack sessionId
            , stateTurnId = Nothing
            , stateHistory = [Message System (cfgSystemPrompt config) Nothing Nothing]
            , stateTurnCount = 0
            }
    pure (env, state)

-- | 调用 LLM API（简化实现）
callLLM :: AgentEnv -> [Message] -> IO LLMResponse
callLLM env messages = do
    let config = envConfig env
    let model = cfgModel config
    let apiKey = cfgApiKey config
    let toolDefs = map toToolDef (envTools env)
    
    -- 构建请求体
    let requestBody = object
            [ "model" .= model
            , "messages" .= messages
            , "tools" .= if null toolDefs then Null else toolDefs
            ]
    
    -- 实际应调用 OpenAI API
    -- 这里返回模拟响应
    pure $ LLMResponse "这是一个模拟响应" Nothing

-- | 处理工具调用
handleToolCalls :: AgentEnv -> [ToolCall] -> IO [Message]
handleToolCalls env toolCalls = do
    results <- mapM handleOne toolCalls
    pure results
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

-- | 处理一轮对话
processTurn :: AgentEnv -> Text -> AgentM (Either Text Text)
processTurn env userInput = do
    -- 生成 turn ID
    turnId <- liftIO $ show <$> UUID.nextRandom
    
    -- 更新状态
    modify $ \s -> s
        { stateTurnId = Just (T.pack turnId)
        , stateTurnCount = stateTurnCount s + 1
        }
    
    currentState <- get
    let sessionId = stateSessionId currentState
    let turnId' = stateTurnId currentState
    
    -- --- Turn Start Hook ---
    let turnCtx = HookContext
            { hcEvent = TurnStart
            , hcData = HM.fromList [("input", String userInput), ("turn_id", String $ T.pack turnId)]
            , hcSessionId = Just sessionId
            , hcTurnId = turnId'
            , hcShouldAbort = False
            , hcAbortReason = Nothing
            }
    
    turnResult <- liftIO $ emitEvent TurnStart turnCtx (envRegistry env)
    if hcShouldAbort turnResult
        then pure $ Left $ "Turn 被中断: " <> maybe "" id (hcAbortReason turnResult)
        else do
            -- --- User Prompt Submit Hook ---
            let promptCtx = HookContext
                    { hcEvent = UserPromptSubmit
                    , hcData = HM.fromList [("prompt", String userInput)]
                    , hcSessionId = Just sessionId
                    , hcTurnId = turnId'
                    , hcShouldAbort = False
                    , hcAbortReason = Nothing
                    }
            
            promptResult <- liftIO $ emitEvent UserPromptSubmit promptCtx (envRegistry env)
            if hcShouldAbort promptResult
                then pure $ Left $ "Prompt 被中断: " <> maybe "" id (hcAbortReason promptResult)
                else do
                    -- 添加用户消息到历史
                    modify $ \s -> s
                        { stateHistory = stateHistory s ++ [Message User userInput Nothing Nothing]
                        }
                    
                    -- 调用 LLM（模拟）
                    currentHistory <- gets stateHistory
                    llmResponse <- liftIO $ callLLM env currentHistory
                    
                    case llmToolCalls llmResponse of
                        Just toolCalls -> do
                            -- --- Tool Call Hook ---
                            let toolCtx = HookContext
                                    { hcEvent = ToolCall
                                    , hcData = HM.fromList 
                                        [ ("tool_name", String $ tcFunctionName $ head toolCalls)
                                        , ("tool_input", String $ tcArguments $ head toolCalls)
                                        ]
                                    , hcSessionId = Just sessionId
                                    , hcTurnId = turnId'
                                    , hcShouldAbort = False
                                    , hcAbortReason = Nothing
                                    }
                            
                            toolResult <- liftIO $ emitEvent ToolCall toolCtx (envRegistry env)
                            if hcShouldAbort toolResult
                                then pure $ Left $ "工具调用被拦截: " <> maybe "" id (hcAbortReason toolResult)
                                else do
                                    -- 执行工具调用
                                    toolMessages <- liftIO $ handleToolCalls env toolCalls
                                    
                                    -- 添加消息到历史
                                    modify $ \s -> s
                                        { stateHistory = stateHistory s 
                                            ++ [Message Assistant (llmContent llmResponse) Nothing (Just toolCalls)]
                                            ++ toolMessages
                                        }
                                    
                                    -- 递归处理 LLM 对工具结果的响应
                                    updatedHistory <- gets stateHistory
                                    finalResponse <- liftIO $ callLLM env updatedHistory
                                    
                                    -- --- Assistant Response Hook ---
                                    let respCtx = HookContext
                                            { hcEvent = AssistantResponse
                                            , hcData = HM.fromList [("response", String $ llmContent finalResponse)]
                                            , hcSessionId = Just sessionId
                                            , hcTurnId = turnId'
                                            , hcShouldAbort = False
                                            , hcAbortReason = Nothing
                                            }
                                    
                                    respResult <- liftIO $ emitEvent AssistantResponse respCtx (envRegistry env)
                                    let finalReply = case HM.lookup "response" (hcData respResult) of
                                            Just (String r) -> r
                                            _ -> llmContent finalResponse
                                    
                                    -- 添加助手回复到历史
                                    modify $ \s -> s
                                        { stateHistory = stateHistory s ++ [Message Assistant finalReply Nothing Nothing]
                                        }
                                    
                                    pure $ Right finalReply
                            
                        Nothing -> do
                            -- 直接回复
                            let reply = llmContent llmResponse
                            
                            -- --- Assistant Response Hook ---
                            let respCtx = HookContext
                                    { hcEvent = AssistantResponse
                                    , hcData = HM.fromList [("response", String reply)]
                                    , hcSessionId = Just sessionId
                                    , hcTurnId = turnId'
                                    , hcShouldAbort = False
                                    , hcAbortReason = Nothing
                                    }
                            
                            respResult <- liftIO $ emitEvent AssistantResponse respCtx (envRegistry env)
                            let finalReply = case HM.lookup "response" (hcData respResult) of
                                    Just (String r) -> r
                                    _ -> reply
                            
                            -- 添加助手回复到历史
                            modify $ \s -> s
                                { stateHistory = stateHistory s ++ [Message Assistant finalReply Nothing Nothing]
                                }
                            
                            pure $ Right finalReply

-- | 重置对话历史
resetConversation :: AgentM ()
resetConversation = do
    config <- gets stateHistory
    case config of
        (sysMsg:_) -> modify $ \s -> s { stateHistory = [sysMsg] }
        [] -> pure ()

-- | 开始会话
startSession :: AgentEnv -> AgentM ()
startSession env = do
    sessionId <- gets stateSessionId
    let ctx = HookContext
            { hcEvent = SessionStart
            , hcData = HM.fromList [("session_id", String sessionId)]
            , hcSessionId = Just sessionId
            , hcTurnId = Nothing
            , hcShouldAbort = False
            , hcAbortReason = Nothing
            }
    liftIO $ emitEvent SessionStart ctx (envRegistry env)
    pure ()

-- | 结束会话
endSession :: AgentEnv -> AgentM ()
endSession env = do
    currentState <- get
    let sessionId = stateSessionId currentState
    let history = stateHistory currentState
    let turnCount = stateTurnCount currentState
    
    let ctx = HookContext
            { hcEvent = SessionEnd
            , hcData = HM.fromList 
                [ ("session_id", String sessionId)
                , ("history", toJSON history)
                , ("turn_count", Number $ fromIntegral turnCount)
                ]
            , hcSessionId = Just sessionId
            , hcTurnId = Nothing
            , hcShouldAbort = False
            , hcAbortReason = Nothing
            }
    liftIO $ emitEvent SessionEnd ctx (envRegistry env)
    pure ()
