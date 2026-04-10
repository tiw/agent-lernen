{-# LANGUAGE OverloadedStrings #-}

module Agent.Hooks where

import Agent.Types
import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.HashMap.Strict as HM
import Data.Aeson (Value(..), encode)
import Data.List (sortBy)
import Data.Ord (comparing)

-- | Hook 注册项
data HookRegistration = HookRegistration
    { hookId :: Text
    , hookEvent :: HookEvent
    , hookHandler :: HookHandler
    , hookPriority :: Int  -- 数字越小优先级越高
    } deriving (Show)

-- | Hook 注册表
data HookRegistry = HookRegistry
    { registryHooks :: [HookRegistration]
    } deriving (Show)

-- | 创建空注册表
emptyRegistry :: HookRegistry
emptyRegistry = HookRegistry []

-- | 注册 Hook
registerHook :: Text -> HookEvent -> HookHandler -> Int -> HookRegistry -> HookRegistry
registerHook hid event handler priority registry =
    registry { registryHooks = HookRegistration hid event handler priority : registryHooks registry }

-- | 按优先级排序的 Hook 列表
sortedHooks :: HookEvent -> HookRegistry -> [HookRegistration]
sortedHooks event registry = 
    sortBy (comparing hookPriority) $
    filter (\h -> hookEvent h == event) $
    registryHooks registry

-- | 发射事件到所有注册的 Hook
emitEvent :: HookEvent -> HookContext -> HookRegistry -> IO HookContext
emitEvent event ctx registry = do
    let hooks = sortedHooks event registry
    foldl (\accCtx hook -> do
        currentCtx <- accCtx
        if hcShouldAbort currentCtx
            then pure currentCtx
            else hookHandler hook currentCtx
        ) (pure ctx) hooks

-- | 内置 Hook：会话恢复
sessionRestoreHook :: HookHandler
sessionRestoreHook ctx = do
    let sessionId = hcSessionId ctx
    case sessionId of
        Just sid -> do
            -- 实际应从文件/数据库加载历史
            -- 这里简化为返回空历史
            let restoredHistory = [] :: [Message]
            let newData = HM.insert "history" (Array $ foldr (\_ acc -> acc) mempty []) $ hcData ctx
            pure $ ctx { hcData = newData }
        Nothing -> pure ctx

-- | 内置 Hook：会话保存
sessionSaveHook :: HookHandler
sessionSaveHook ctx = do
    let sessionId = hcSessionId ctx
    let history = hcData ctx
    -- 实际应保存到文件/数据库
    case sessionId of
        Just sid -> do
            putStrLn $ "[Hook] 保存会话: " <> T.unpack sid
            pure ctx
        Nothing -> pure ctx

-- | 内置 Hook：安全扫描
securityScanHook :: HookHandler
securityScanHook ctx = do
    let toolName = HM.lookup "tool_name" (hcData ctx)
    case toolName of
        Just (String name) -> do
            -- 简单的安全检查示例
            let dangerousCommands = ["rm -rf /", "sudo", "chmod 777"]
            let toolInput = HM.lookup "tool_input" (hcData ctx)
            
            case toolInput of
                Just (Object inputObj) -> do
                    let cmdStr = case lookup "command" inputObj of
                            Just (String cmd) -> T.unpack cmd
                            _ -> ""
                    
                    if any (`isInfixOf` cmdStr) dangerousCommands
                        then pure $ ctx 
                            { hcShouldAbort = True
                            , hcAbortReason = Just $ "危险命令被拦截: " <> T.pack cmdStr
                            }
                        else pure ctx
                _ -> pure ctx
        _ -> pure ctx
  where
    isInfixOf sub = any (isPrefixOf sub) . tails
    isPrefixOf [] _ = True
    isPrefixOf _ [] = False
    isPrefixOf (x:xs) (y:ys) = x == y && isPrefixOf xs ys
    tails [] = [[]]
    tails xs@(_:xs') = xs : tails xs'

-- | 内置 Hook：持续学习
continuousLearnHook :: HookHandler
continuousLearnHook ctx = do
    let inputData = hcData ctx
    let userInput = HM.lookup "input" inputData
    let response = HM.lookup "response" inputData
    
    case (userInput, response) of
        (Just (String input), Just (String resp)) -> do
            -- 实际应存储到学习数据库
            putStrLn $ "[Hook] 学习样本已记录"
            pure ctx
        _ -> pure ctx

-- | 注册所有内置 Hook
registerBuiltinHooks :: HookRegistry -> HookRegistry
registerBuiltinHooks registry =
    let r1 = registerHook "session_restore" SessionStart sessionRestoreHook 10 registry
        r2 = registerHook "session_save" SessionEnd sessionSaveHook 10 r1
        r3 = registerHook "security_scan" ToolCall securityScanHook 1 r2
        r4 = registerHook "continuous_learn" TurnEnd continuousLearnHook 200 r3
    in r4
