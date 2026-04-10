{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE DeriveGeneric #-}

module Agent.Tools where

import Agent.Types
import Data.Aeson
import Data.Text (Text)
import qualified Data.Text as T
import GHC.Generics (Generic)
import System.Process (readProcess)
import Control.Exception (try, SomeException)

-- | 工具执行器
data ToolExecutor = ToolExecutor
    { execName :: Text
    , execDescription :: Text
    , execParameters :: Value
    , execFunction :: Value -> IO Text  -- 接收 JSON 参数，返回结果文本
    }

-- | 创建工具定义
toToolDef :: ToolExecutor -> ToolDef
toToolDef executor = ToolDef
    { toolName = execName executor
    , toolDescription = execDescription executor
    , toolParameters = execParameters executor
    }

-- | 执行工具
executeTool :: ToolExecutor -> Value -> IO ToolResult
executeTool executor args = do
    result <- try (execFunction executor args) :: IO (Either SomeException Text)
    case result of
        Left err -> pure $ ToolResult (execName executor) False (T.pack $ show err)
        Right output -> pure $ ToolResult (execName executor) True output

-- | 内置工具：Echo
echoTool :: ToolExecutor
echoTool = ToolExecutor
    { execName = "echo"
    , execDescription = "回显输入文本"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "message" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("要回显的消息" :: Text)
                ]
            ]
        , "required" .= (["message"] :: [Text])
        ]
    , execFunction = \args -> do
        case args of
            Object obj -> do
                case lookup "message" obj of
                    Just (String msg) -> pure $ "Echo: " <> msg
                    _ -> pure "Error: missing 'message' parameter"
            _ -> pure "Error: expected object"
    }

-- | 内置工具：计算器
calculatorTool :: ToolExecutor
calculatorTool = ToolExecutor
    { execName = "calculator"
    , execDescription = "执行简单的数学计算"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "expression" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("数学表达式，如 '2 + 2'" :: Text)
                ]
            ]
        , "required" .= (["expression"] :: [Text])
        ]
    , execFunction = \args -> do
        case args of
            Object obj -> do
                case lookup "expression" obj of
                    Just (String expr) -> 
                        -- 简化实现：实际应使用安全的表达式解析器
                        pure $ "计算结果: " <> expr <> " (需实现解析器)"
                    _ -> pure "Error: missing 'expression' parameter"
            _ -> pure "Error: expected object"
    }

-- | 内置工具：Bash 命令执行
bashTool :: ToolExecutor
bashTool = ToolExecutor
    { execName = "bash"
    , execDescription = "执行 Bash 命令（注意安全风险）"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "command" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("要执行的 Bash 命令" :: Text)
                ]
            ]
        , "required" .= (["command"] :: [Text])
        ]
    , execFunction = \args -> do
        case args of
            Object obj -> do
                case lookup "command" obj of
                    Just (String cmd) -> do
                        result <- try (readProcess "bash" ["-c", T.unpack cmd] "") 
                            :: IO (Either SomeException String)
                        case result of
                            Left err -> pure $ T.pack $ "执行失败: " ++ show err
                            Right output -> pure $ T.pack output
                    _ -> pure "Error: missing 'command' parameter"
            _ -> pure "Error: expected object"
    }

-- | 内置工具：文件读取
readFileTool :: ToolExecutor
readFileTool = ToolExecutor
    { execName = "read_file"
    , execDescription = "读取文件内容"
    , execParameters = object
        [ "type" .= ("object" :: Text)
        , "properties" .= object
            [ "path" .= object
                [ "type" .= ("string" :: Text)
                , "description" .= ("文件路径" :: Text)
                ]
            ]
        , "required" .= (["path"] :: [Text])
        ]
    , execFunction = \args -> do
        case args of
            Object obj -> do
                case lookup "path" obj of
                    Just (String path) -> do
                        result <- try (readFile (T.unpack path)) 
                            :: IO (Either SomeException String)
                        case result of
                            Left err -> pure $ T.pack $ "读取失败: " ++ show err
                            Right content -> pure $ T.pack content
                    _ -> pure "Error: missing 'path' parameter"
            _ -> pure "Error: expected object"
    }

-- | 所有内置工具
builtinTools :: [ToolExecutor]
builtinTools = [echoTool, calculatorTool, bashTool, readFileTool]
