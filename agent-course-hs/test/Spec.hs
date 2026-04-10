{-# LANGUAGE OverloadedStrings #-}

module Main where

import Agent.Types
import Agent.Tools
import Test.HUnit

-- 测试工具执行
testEchoTool :: Test
testEchoTool = TestCase $ do
    let args = object ["message" .= ("Hello, World!" :: String)]
    result <- executeTool echoTool args
    assertEqual "Echo tool should return the message" 
        (ToolResult "echo" True "Echo: Hello, World!")
        result

-- 测试计算器工具
testCalculatorTool :: Test
testCalculatorTool = TestCase $ do
    let args = object ["expression" .= ("2 + 2" :: String)]
    result <- executeTool calculatorTool args
    assertBool "Calculator should return a result" 
        (trSuccess result)

-- 测试工具定义生成
testToolDefGeneration :: Test
testToolDefGeneration = TestCase $ do
    let toolDef = toToolDef echoTool
    assertEqual "Tool name should be 'echo'" 
        "echo"
        (toolName toolDef)
    assertBool "Tool should have description" 
        (not $ null $ toolDescription toolDef)

-- 测试错误处理
testToolErrorHandling :: Test
testToolErrorHandling = TestCase $ do
    let args = String "invalid"  -- 错误的参数类型
    result <- executeTool echoTool args
    assertBool "Should handle error gracefully" 
        (not $ trSuccess result)

-- 测试消息序列化
testMessageSerialization :: Test
testMessageSerialization = TestCase $ do
    let msg = Message User "Hello" Nothing Nothing
    let json = encode msg
    assertBool "Message should serialize to JSON" 
        (not $ null json)

-- 测试消息反序列化
testMessageDeserialization :: Test
testMessageDeserialization = TestCase $ do
    let json = "{\"role\": \"user\", \"content\": \"Hello\"}"
    let result = decode json :: Maybe Message
    case result of
        Just msg -> do
            assertEqual "Role should be User" User (msgRole msg)
            assertEqual "Content should match" "Hello" (msgContent msg)
        Nothing -> assertFailure "Failed to deserialize message"

-- 测试 Hook 上下文
testHookContext :: Test
testHookContext = TestCase $ do
    let ctx = HookContext
            { hcEvent = TurnStart
            , hcData = mempty
            , hcSessionId = Just "test-session"
            , hcTurnId = Just "test-turn"
            , hcShouldAbort = False
            , hcAbortReason = Nothing
            }
    assertEqual "Session ID should match" 
        (Just "test-session") 
        (hcSessionId ctx)
    assertBool "Should not abort by default" 
        (not $ hcShouldAbort ctx)

-- 所有测试
tests :: Test
tests = TestList 
    [ TestLabel "testEchoTool" testEchoTool
    , TestLabel "testCalculatorTool" testCalculatorTool
    , TestLabel "testToolDefGeneration" testToolDefGeneration
    , TestLabel "testToolErrorHandling" testToolErrorHandling
    , TestLabel "testMessageSerialization" testMessageSerialization
    , TestLabel "testMessageDeserialization" testMessageDeserialization
    , TestLabel "testHookContext" testHookContext
    ]

-- 运行测试
main :: IO ()
main = do
    putStrLn "Running Agent Tests..."
    putStrLn "======================"
    runTestTT tests
    putStrLn "\nAll tests completed!"
