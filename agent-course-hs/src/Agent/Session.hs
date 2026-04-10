{-# LANGUAGE OverloadedStrings #-}

module Agent.Session where

import Agent.Types
import Agent.Core
import Agent.Tools

import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.Text.IO as TIO
import qualified Data.ByteString.Lazy.Char8 as BSL
import Data.Aeson
import Data.Aeson.Encode.Pretty (encodePretty)
import Control.Exception (try, SomeException)
import System.Directory (createDirectoryIfMissing, doesFileExist)

-- | 会话保存路径
sessionDir :: FilePath
sessionDir = ".agent-sessions"

-- | 保存会话到文件
saveSessionToFile :: AgentState -> IO ()
saveSessionToFile state = do
    createDirectoryIfMissing True sessionDir
    let sessionData = object
            [ "session_id" .= stateSessionId state
            , "history" .= stateHistory state
            , "turn_count" .= stateTurnCount state
            ]
    
    result <- try (BSL.writeFile (sessionDir <> "/" <> T.unpack (stateSessionId state) <> ".json") $ encodePretty sessionData)
        :: IO (Either SomeException ())
    case result of
        Left err -> putStrLn $ "保存会话失败: " <> show err
        Right _ -> putStrLn $ "会话已保存: " <> sessionDir <> "/" <> T.unpack (stateSessionId state) <> ".json"

-- | 从文件加载会话
loadSessionFromFile :: Text -> IO (Maybe AgentState)
loadSessionFromFile sessionId = do
    let filePath = sessionDir <> "/" <> T.unpack sessionId <> ".json"
    exists <- doesFileExist filePath
    
    if exists
        then do
            result <- try (readFile filePath) :: IO (Either SomeException String)
            case result of
                Left err -> do
                    putStrLn $ "加载会话失败: " <> show err
                    pure Nothing
                Right content -> do
                    case decode (BSL.pack content) of
                        Just (obj :: Value) -> do
                            -- 解析会话数据
                            hist <- obj .:? "history" .?= []
                            turns <- obj .:? "turn_count" .?= (0 :: Int)
                            pure $ Just $ AgentState
                                { stateSessionId = sessionId
                                , stateTurnId = Nothing
                                , stateHistory = hist
                                , stateTurnCount = turns
                                }
                        Nothing -> do
                            putStrLn "会话数据解析失败"
                            pure Nothing
        else pure Nothing

-- | 交互式对话循环
interactiveLoop :: AgentEnv -> AgentState -> IO ()
interactiveLoop env state = do
    putStrLn "\n🤖 Agent 已启动！输入 'quit' 退出，'reset' 重置对话"
    putStrLn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    let loop currentState = do
            putStr "\n你: "
            input <- TIO.getLine
            
            case T.toLower input of
                "quit" -> do
                    putStrLn "\n👋 再见！"
                    pure ()
                "exit" -> do
                    putStrLn "\n👋 再见！"
                    pure ()
                "q" -> do
                    putStrLn "\n👋 再见！"
                    pure ()
                "reset" -> do
                    let resetState = currentState 
                            { stateHistory = take 1 (stateHistory currentState)
                            , stateTurnCount = 0
                            }
                    putStrLn "\n✅ 对话已重置"
                    loop resetState
                _ -> do
                    -- 处理用户输入
                    result <- runAgentM (processTurn env input) currentState
                    
                    case result of
                        (Right response, newState) -> do
                            putStrLn $ "\n🤖: " <> T.unpack response
                            loop newState
                        (Left error, newState) -> do
                            putStrLn $ "\n❌ 错误: " <> T.unpack error
                            loop newState
    
    loop state

-- | 运行 Agent 示例
runAgentExample :: IO ()
runAgentExample = do
    -- 创建配置
    let config = AgentConfig
            { cfgSystemPrompt = "你是一个简洁的 AI 助手。回答要简短、准确。"
            , cfgModel = "gpt-4o-mini"
            , cfgApiKey = Nothing  -- 从环境变量读取
            , cfgApiBaseUrl = Nothing
            }
    
    -- 初始化工具
    let tools = [echoTool, calculatorTool]
    
    -- 初始化 Agent
    (env, state) <- initAgent config tools
    
    -- 开始会话
    runAgentM (startSession env) state
    
    -- 进入交互循环
    interactiveLoop env state
    
    -- 结束会话
    finalState <- runAgentM (endSession env) state
    saveSessionToFile finalState
    pure ()
