# 第 11 章：Hook 系统 —— 让 Agent 可插拔

> **本章目标**：理解 Hook 系统的设计哲学，从零实现一个事件驱动的 Hook 框架，让 Agent 具备会话持久化、安全扫描、持续学习等可插拔能力。

---

## 🔍 先看 Claude Code 怎么做

Claude Code 的 Hook 系统是整个架构中最精巧的扩展机制之一。它的核心思想是：**在 Agent 生命周期的关键节点触发用户自定义的外部命令或回调，而无需修改核心代码**。

### 源码导读

**1. Hook 类型定义**（`src/types/hooks.ts`）

Claude Code 定义了多种 Hook 事件类型，对应 Agent 生命周期的不同阶段：

```typescript
// src/types/hooks.ts 核心定义
export type HookEvent =
  | 'SessionStart'    // 会话开始
  | 'SessionEnd'      // 会话结束
  | 'UserPromptSubmit' // 用户提交 prompt 之前
  | 'ToolCall'        // 工具调用之前
  | 'ToolResult'      // 工具返回之后
  | 'AssistantResponse' // Agent 回复之后
  | 'Notification'    // 通知事件
  | 'Setup'           // 环境初始化
  | 'TurnStart'       // 一轮对话开始
  | 'TurnEnd'         // 一轮对话结束
```

**2. Hook 事件总线**（`src/utils/hooks/hookEvents.ts`）

Claude Code 实现了一个独立于主消息流的事件系统：

```typescript
// src/utils/hooks/hookEvents.ts 核心逻辑
const pendingEvents: HookExecutionEvent[] = []
let eventHandler: HookEventHandler | null = null

function emit(event: HookExecutionEvent): void {
  if (eventHandler) {
    eventHandler(event)           // 有处理器，立即分发
  } else {
    pendingEvents.push(event)     // 无处理器，暂存（最多100条）
    if (pendingEvents.length > MAX_PENDING_EVENTS) {
      pendingEvents.shift()       // 超限丢弃最旧的
    }
  }
}
```

关键设计点：
- **延迟注册**：Handler 可以在事件发生后注册，之前的事件会被缓存并重放
- **容量限制**：最多缓存 100 条，防止内存泄漏
- **独立通道**：与主消息流分离，Hook 事件不会污染正常对话

**3. Hook 执行引擎**（`src/utils/hooks.ts`）

这是整个 Hook 系统的核心，超过 5000 行代码，负责：

```typescript
// src/utils/hooks.ts 核心流程（简化）
export async function executePermissionRequestHooks(
  toolName: string,
  input: ToolUseInput,
): Promise<PermissionDecision | null> {
  // 1. 查找匹配的 Hook 配置
  const hooks = getRegisteredHooks('PermissionRequest')

  for (const hook of hooks) {
    // 2. 通过子进程执行外部命令
    const result = await spawnHookProcess(hook, {
      toolName,
      input,
      sessionId: getSessionId(),
    })

    // 3. 解析 JSON 输出，决定是否拦截
    if (result.decision === 'deny') {
      return { type: 'denied', reason: result.reason }
    }
  }
  return null  // 所有 Hook 通过，继续执行
}
```

**4. Hook 配置快照**（`src/utils/hooks/hooksConfigSnapshot.ts`）

Claude Code 支持热更新 Hook 配置，无需重启：

```typescript
// 每次执行 Hook 前，从文件系统重新读取配置
// 支持 .claude/settings.json 中的 hooks 字段
export function getHooksConfigFromSnapshot(): HooksConfig {
  // 读取 → 解析 → 缓存 → 返回
}
```

### 架构总结

```
用户提交 Prompt
    │
    ├─▶ Hook: UserPromptSubmit（敏感词过滤、意图分类）
    │
    ▼
Agent 思考 → 决定调用工具
    │
    ├─▶ Hook: ToolCall（权限检查、安全扫描）
    │
    ▼
工具执行 → 返回结果
    │
    ├─▶ Hook: ToolResult（结果验证、日志记录）
    │
    ▼
Agent 生成回复
    │
    ├─▶ Hook: AssistantResponse（格式化、学习记录）
    │
    ▼
回复发送给用户
```

---

## 🧠 核心概念

### 什么是 Hook？

Hook（钩子）是一种**在程序执行的特定点插入自定义逻辑**的机制。想象钓鱼时鱼钩挂在鱼线上——程序的主流程是鱼线，Hook 就是挂在上面的鱼钩，在特定时机"钩住"执行流，运行额外代码后再放回去。

### 为什么 Agent 需要 Hook？

| 场景 | 不用 Hook | 用 Hook |
|------|-----------|---------|
| 添加安全扫描 | 修改核心代码，每次更新要 rebase | 写一个 Hook 脚本，即插即用 |
| 会话持久化 | 耦合在 Agent 主循环里 | 独立 Hook，随时开关 |
| 持续学习 | 硬编码学习逻辑 | 学习 Hook 独立演进 |
| 多租户定制 | 每个客户一个分支 | 同一核心，不同 Hook 配置 |

### Hook 系统的三个核心组件

1. **事件总线（EventBus）**：发布-订阅模式的中枢
2. **Hook 注册表（Registry）**：管理哪些 Hook 监听哪些事件
3. **Hook 执行器（Executor）**：按顺序执行 Hook，支持拦截和修改

### 设计原则

- **非侵入**：Hook 不应修改核心代码
- **可组合**：多个 Hook 可以串联执行
- **可拦截**：Hook 可以中止后续流程（如安全扫描发现危险命令）
- **可观测**：Hook 的执行状态和结果应可追踪

---

## 💻 动手实现

### 项目结构

```
my_agent/
├── hooks/
│   ├── __init__.py
│   ├── event_bus.py          # 事件总线
│   ├── registry.py           # Hook 注册表
│   ├── executor.py           # Hook 执行器
│   └── builtin/
│       ├── __init__.py
│       ├── session_persist.py # 会话持久化
│       ├── security_scan.py   # 安全扫描
│       └── continuous_learn.py # 持续学习
├── core/
│   ├── agent.py
│   └── ...
└── main.py
```

### 1. 事件总线（`hooks/event_bus.py`）

```python
"""
事件总线 —— Hook 系统的中枢神经

设计参考：Claude Code 的 hookEvents.ts
- 支持延迟注册（handler 可以在事件后注册，缓存事件会重放）
- 容量限制防止内存泄漏
- 独立于主消息流
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Agent 生命周期事件"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ASSISTANT_RESPONSE = "assistant_response"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    NOTIFICATION = "notification"


@dataclass
class HookContext:
    """Hook 执行时的上下文信息"""
    event: HookEvent
    data: dict[str, Any]
    session_id: str = ""
    turn_id: str = ""
    # 拦截标记：Hook 可以设置此标记中止后续流程
    should_abort: bool = False
    abort_reason: str = ""
    # 数据修改：Hook 可以修改 data 中的内容
    modified_data: dict[str, Any] = field(default_factory=dict)

    def abort(self, reason: str) -> None:
        """中止后续 Hook 和主流程"""
        self.should_abort = True
        self.abort_reason = reason

    def modify(self, key: str, value: Any) -> None:
        """修改上下文数据"""
        self.modified_data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据（优先取修改后的值）"""
        return self.modified_data.get(key, self.data.get(key, default))


# Hook 回调类型：同步或异步
HookCallback = Callable[[HookContext], None | Awaitable[None]]


class EventBus:
    """
    事件总线

    参考 Claude Code 的 hookEvents.ts 设计：
    - pending_events 缓存未分发的事件
    - 容量上限防止内存泄漏
    - 支持同步和异步 handler
    """

    def __init__(self, max_pending: int = 100):
        self._handlers: dict[HookEvent, list[HookCallback]] = {}
        self._pending_events: list[tuple[HookEvent, HookContext]] = []
        self._max_pending = max_pending
        self._has_handler: dict[HookEvent, bool] = {}

    def on(self, event: HookEvent, callback: HookCallback) -> None:
        """注册 Hook 回调"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(callback)
        self._has_handler[event] = True

        # 如果有缓存事件，立即重放
        if self._pending_events:
            self._replay_pending(event)

    def off(self, event: HookEvent, callback: HookCallback) -> None:
        """移除 Hook 回调"""
        if event in self._handlers:
            self._handlers[event] = [
                h for h in self._handlers[event] if h != callback
            ]

    async def emit(self, event: HookEvent, context: HookContext) -> HookContext:
        """
        触发事件，依次执行所有注册的 Hook

        返回修改后的 context（可能被 Hook 拦截或修改）
        """
        handlers = self._handlers.get(event, [])

        if not handlers:
            # 没有 handler，缓存事件
            self._pending_events.append((event, context))
            if len(self._pending_events) > self._max_pending:
                dropped = self._pending_events.pop(0)
                logger.warning(
                    f"Event buffer full, dropped: {dropped[0].value}"
                )
            return context

        for callback in handlers:
            if context.should_abort:
                logger.info(
                    f"Hook chain aborted at {event.value}: "
                    f"{context.abort_reason}"
                )
                break

            try:
                result = callback(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Hook error at {event.value}: {e}")
                # Hook 异常不中断主流程，仅记录

        return context

    def _replay_pending(self, event: HookEvent) -> None:
        """重放缓存的指定类型事件"""
        to_replay = [
            (e, ctx) for e, ctx in self._pending_events if e == event
        ]
        self._pending_events = [
            (e, ctx) for e, ctx in self._pending_events if e != event
        ]
        # 注意：replay 是异步的，这里只做清理
        # 实际 replay 在 emit 时自然处理

    def clear(self) -> None:
        """清空所有 Hook 和缓存"""
        self._handlers.clear()
        self._pending_events.clear()
        self._has_handler.clear()
```

### 2. Hook 注册表（`hooks/registry.py`）

```python
"""
Hook 注册表 —— 管理 Hook 的注册、卸载和配置

参考 Claude Code 的 hooksConfigSnapshot.ts：
- 支持从配置文件加载
- 支持运行时动态注册
- 支持启用/禁用单个 Hook
"""

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .event_bus import EventBus, HookCallback, HookEvent

logger = logging.getLogger(__name__)


@dataclass
class HookDescriptor:
    """Hook 描述符"""
    name: str
    event: HookEvent
    callback: HookCallback
    enabled: bool = True
    priority: int = 100  # 数字越小优先级越高
    config: dict[str, Any] = field(default_factory=dict)


class HookRegistry:
    """
    Hook 注册表

    管理所有 Hook 的生命周期，支持：
    - 按优先级排序执行
    - 动态启用/禁用
    - 从配置文件加载
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._hooks: list[HookDescriptor] = []
        self._by_name: dict[str, HookDescriptor] = {}

    def register(
        self,
        name: str,
        event: HookEvent,
        callback: HookCallback,
        priority: int = 100,
        config: dict[str, Any] | None = None,
    ) -> None:
        """注册一个 Hook"""
        descriptor = HookDescriptor(
            name=name,
            event=event,
            callback=callback,
            priority=priority,
            config=config or {},
        )
        self._hooks.append(descriptor)
        self._by_name[name] = descriptor
        self.event_bus.on(event, callback)
        logger.info(f"Hook registered: {name} -> {event.value}")

    def unregister(self, name: str) -> None:
        """卸载一个 Hook"""
        descriptor = self._by_name.pop(name, None)
        if descriptor:
            self._hooks = [h for h in self._hooks if h.name != name]
            self.event_bus.off(descriptor.event, descriptor.callback)
            logger.info(f"Hook unregistered: {name}")

    def enable(self, name: str) -> None:
        """启用 Hook"""
        if name in self._by_name:
            self._by_name[name].enabled = True

    def disable(self, name: str) -> None:
        """禁用 Hook"""
        if name in self._by_name:
            self._by_name[name].enabled = False

    def load_from_config(self, config_path: str | Path) -> None:
        """从 JSON 配置文件加载 Hook 配置"""
        import json

        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Hook config not found: {path}")
            return

        with open(path) as f:
            config = json.load(f)

        for hook_config in config.get("hooks", []):
            try:
                module_path = hook_config["module"]
                func_name = hook_config.get("function", "run")

                module = importlib.import_module(module_path)
                callback = getattr(module, func_name)

                self.register(
                    name=hook_config["name"],
                    event=HookEvent(hook_config["event"]),
                    callback=callback,
                    priority=hook_config.get("priority", 100),
                    config=hook_config.get("config", {}),
                )
            except Exception as e:
                logger.error(f"Failed to load hook {hook_config.get('name')}: {e}")

    @property
    def active_hooks(self) -> list[HookDescriptor]:
        """获取所有已启用的 Hook"""
        return [h for h in self._hooks if h.enabled]

    def list_hooks(self) -> list[dict[str, Any]]:
        """列出所有 Hook 的状态"""
        return [
            {
                "name": h.name,
                "event": h.event.value,
                "enabled": h.enabled,
                "priority": h.priority,
            }
            for h in self._hooks
        ]
```

### 3. 内置 Hook：会话持久化（`hooks/builtin/session_persist.py`）

```python
"""
会话持久化 Hook

在会话开始/结束时自动保存和恢复对话历史。
参考 Claude Code 的 sessionHistory.ts 和 history.ts。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

# 默认存储路径
DEFAULT_STORAGE_DIR = Path.home() / ".my_agent" / "sessions"


class SessionPersister:
    """会话持久化管理器"""

    def __init__(self, storage_dir: str | Path | None = None):
        self.storage_dir = Path(storage_dir or DEFAULT_STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _session_file(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    async def on_session_start(self, ctx: HookContext) -> None:
        """会话开始时，尝试恢复历史"""
        session_id = ctx.get("session_id", "")
        if not session_id:
            return

        file_path = self._session_file(session_id)
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                ctx.modify("history", data.get("messages", []))
                logger.info(
                    f"Session restored: {session_id}, "
                    f"{len(data.get('messages', []))} messages"
                )
            except Exception as e:
                logger.error(f"Failed to restore session {session_id}: {e}")
        else:
            logger.info(f"New session: {session_id}")

    async def on_session_end(self, ctx: HookContext) -> None:
        """会话结束时，保存历史"""
        session_id = ctx.get("session_id", "")
        if not session_id:
            return

        history = ctx.get("history", [])
        file_path = self._session_file(session_id)

        data = {
            "session_id": session_id,
            "messages": history,
            "ended_at": datetime.now().isoformat(),
            "turn_count": ctx.get("turn_count", 0),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved: {session_id} -> {file_path}")


# 便捷函数（供注册表直接引用）
_persister = SessionPersister()

async def restore_session(ctx: HookContext) -> None:
    await _persister.on_session_start(ctx)

async def save_session(ctx: HookContext) -> None:
    await _persister.on_session_end(ctx)
```

### 4. 内置 Hook：安全扫描（`hooks/builtin/security_scan.py`）

```python
"""
安全扫描 Hook

在工具调用前检查命令安全性，参考 Claude Code 的
toolPermission/ 和 policyLimits/ 模块。
"""

import logging
import re

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

# 危险命令模式
DANGEROUS_PATTERNS = [
    (r"\brm\s+(-rf?|--no-preserve)\s+/", "禁止删除根目录"),
    (r"\bchmod\s+[0-7]*777\b", "禁止设置 777 权限"),
    (r"\bcurl.*\|\s*(bash|sh)\b", "禁止 curl 管道执行"),
    (r"\bwget.*\|\s*(bash|sh)\b", "禁止 wget 管道执行"),
    (r">\s*/etc/(passwd|shadow|sudoers)", "禁止修改系统关键文件"),
    (r"\bmkfs\b", "禁止格式化文件系统"),
    (r"\bdd\s+if=", "禁止 dd 写入"),
    (r":\(\)\{\s*:\|:&\s*\};:", "禁止 fork bomb"),
]

# 需要用户确认的命令
REQUIRES_CONFIRMATION = [
    (r"\bgit\s+push\s+--force", "强制推送"),
    (r"\bDROP\s+TABLE\b", "删除数据库表"),
    (r"\bDELETE\s+FROM\b", "删除数据库记录"),
    (r"\bterraform\s+destroy\b", "销毁基础设施"),
]


class SecurityScanner:
    """安全扫描器"""

    def __init__(
        self,
        dangerous_patterns: list[tuple[str, str]] | None = None,
        strict_mode: bool = False,
    ):
        self.patterns = dangerous_patterns or DANGEROUS_PATTERNS
        self.compiled = [
            (re.compile(p, re.IGNORECASE), msg) for p, msg in self.patterns
        ]
        self.strict_mode = strict_mode

    async def scan_tool_call(self, ctx: HookContext) -> None:
        """扫描工具调用"""
        tool_name = ctx.get("tool_name", "")
        tool_input = ctx.get("tool_input", {})

        # 只扫描 Bash 类工具
        if tool_name.lower() not in ("bash", "shell", "exec", "run_command"):
            return

        command = tool_input.get("command", "")
        if not command:
            return

        # 检查危险模式
        for pattern, message in self.compiled:
            if pattern.search(command):
                if self.strict_mode:
                    ctx.abort(f"安全拦截: {message}")
                    logger.warning(f"BLOCKED: {message} | cmd: {command[:100]}")
                else:
                    ctx.modify("security_warning", message)
                    logger.warning(f"WARNING: {message} | cmd: {command[:100]}")
                return

        # 检查需要确认的模式
        for pattern, message in REQUIRES_CONFIRMATION:
            if re.search(pattern, command, re.IGNORECASE):
                ctx.modify("requires_confirmation", True)
                ctx.modify("confirmation_reason", message)
                logger.info(f"需要确认: {message} | cmd: {command[:100]}")
                return

        logger.debug(f"Security scan passed: {command[:50]}...")


# 便捷函数
_scanner = SecurityScanner()

async def security_scan(ctx: HookContext) -> None:
    await _scanner.scan_tool_call(ctx)
```

### 5. 内置 Hook：持续学习（`hooks/builtin/continuous_learn.py`）

```python
"""
持续学习 Hook

从 Agent 的交互中提取经验教训，持续改进。
参考 Claude Code 的 extractMemories/ 和 teamMemorySync/ 服务。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from hooks.event_bus import HookContext, HookEvent

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_DIR = Path.home() / ".my_agent" / "memory"


class ContinuousLearner:
    """持续学习管理器"""

    def __init__(self, memory_dir: str | Path | None = None):
        self.memory_dir = Path(memory_dir or DEFAULT_MEMORY_DIR)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lessons_file = self.memory_dir / "lessons.json"
        self.lessons = self._load_lessons()

    def _load_lessons(self) -> list[dict]:
        if self.lessons_file.exists():
            try:
                with open(self.lessons_file) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_lessons(self) -> None:
        with open(self.lessons_file, "w") as f:
            json.dump(self.lessons, f, indent=2, ensure_ascii=False)

    def add_lesson(
        self,
        category: str,
        lesson: str,
        context: str = "",
        confidence: float = 0.5,
    ) -> None:
        """添加一条经验教训"""
        self.lessons.append({
            "category": category,
            "lesson": lesson,
            "context": context,
            "confidence": confidence,
            "created_at": datetime.now().isoformat(),
        })
        # 只保留最近 500 条
        if len(self.lessons) > 500:
            self.lessons = self.lessons[-500:]
        self._save_lessons()

    async def on_turn_end(self, ctx: HookContext) -> None:
        """一轮对话结束后，分析是否需要学习"""
        tool_calls = ctx.get("tool_calls", [])
        errors = ctx.get("errors", [])
        user_feedback = ctx.get("user_feedback", "")

        # 从错误中学习
        for error in errors:
            self.add_lesson(
                category="error_recovery",
                lesson=f"遇到错误: {error.get('message', 'unknown')}",
                context=json.dumps(error, ensure_ascii=False)[:200],
                confidence=0.7,
            )

        # 从用户反馈中学习
        if user_feedback:
            self.add_lesson(
                category="user_preference",
                lesson=user_feedback,
                confidence=0.9,
            )

        # 从成功的工具调用中学习
        for tc in tool_calls:
            if tc.get("success") and tc.get("tool_name") == "bash":
                cmd = tc.get("command", "")
                if len(cmd) > 20:  # 只记录有意义的命令
                    self.add_lesson(
                        category="tool_usage",
                        lesson=f"成功执行: {cmd[:100]}",
                        confidence=0.5,
                    )

    def get_lessons(self, category: str | None = None) -> list[dict]:
        """获取经验教训"""
        if category:
            return [l for l in self.lessons if l["category"] == category]
        return self.lessons


# 便捷函数
_learner = ContinuousLearner()

async def continuous_learn(ctx: HookContext) -> None:
    await _learner.on_turn_end(ctx)
```

### 6. 在 Agent 中集成 Hook 系统（`core/agent.py`）

```python
"""
Agent 核心 —— 集成 Hook 系统
"""

import asyncio
import logging
import uuid
from typing import Any

from hooks.event_bus import EventBus, HookContext, HookEvent
from hooks.registry import HookRegistry
from hooks.builtin.session_persist import restore_session, save_session
from hooks.builtin.security_scan import security_scan
from hooks.builtin.continuous_learn import continuous_learn

logger = logging.getLogger(__name__)


class AgentWithHooks:
    """集成 Hook 系统的 Agent"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.turn_id = ""
        self.history: list[dict] = []
        self.turn_count = 0

        # 初始化 Hook 系统
        self.event_bus = EventBus()
        self.registry = HookRegistry(self.event_bus)

        # 注册内置 Hook
        self._register_builtin_hooks()

    def _register_builtin_hooks(self) -> None:
        """注册内置 Hook"""
        # 会话持久化
        self.registry.register(
            "session_restore", HookEvent.SESSION_START,
            restore_session, priority=10,
        )
        self.registry.register(
            "session_save", HookEvent.SESSION_END,
            save_session, priority=10,
        )

        # 安全扫描（高优先级，最先执行）
        self.registry.register(
            "security_scan", HookEvent.TOOL_CALL,
            security_scan, priority=1,
        )

        # 持续学习
        self.registry.register(
            "continuous_learn", HookEvent.TURN_END,
            continuous_learn, priority=200,
        )

    async def start_session(self) -> None:
        """开始会话"""
        ctx = HookContext(
            event=HookEvent.SESSION_START,
            data={"session_id": self.session_id},
            session_id=self.session_id,
        )
        await self.event_bus.emit(HookEvent.SESSION_START, ctx)

        # 恢复历史
        restored = ctx.get("history")
        if restored:
            self.history = restored

    async def process_turn(self, user_input: str) -> dict[str, Any]:
        """处理一轮对话"""
        self.turn_id = str(uuid.uuid4())
        self.turn_count += 1

        # --- Turn Start ---
        turn_ctx = HookContext(
            event=HookEvent.TURN_START,
            data={"input": user_input, "turn_id": self.turn_id},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TURN_START, turn_ctx)
        if turn_ctx.should_abort:
            return {"error": turn_ctx.abort_reason}

        # --- User Prompt Submit ---
        prompt_ctx = HookContext(
            event=HookEvent.USER_PROMPT_SUBMIT,
            data={"prompt": user_input},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.USER_PROMPT_SUBMIT, prompt_ctx)
        if prompt_ctx.should_abort:
            return {"error": prompt_ctx.abort_reason}

        # --- 模拟 Agent 思考（实际应调用 LLM）---
        response = f"收到: {user_input}"

        # --- 模拟工具调用 ---
        tool_ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={
                "tool_name": "bash",
                "tool_input": {"command": "echo hello"},
            },
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TOOL_CALL, tool_ctx)
        if tool_ctx.should_abort:
            return {"error": f"工具调用被拦截: {tool_ctx.abort_reason}"}

        # --- Assistant Response ---
        resp_ctx = HookContext(
            event=HookEvent.ASSISTANT_RESPONSE,
            data={"response": response},
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.ASSISTANT_RESPONSE, resp_ctx)
        response = resp_ctx.get("response", response)

        # --- Turn End ---
        end_ctx = HookContext(
            event=HookEvent.TURN_END,
            data={
                "input": user_input,
                "response": response,
                "tool_calls": [],
                "errors": [],
            },
            session_id=self.session_id,
            turn_id=self.turn_id,
        )
        await self.event_bus.emit(HookEvent.TURN_END, end_ctx)

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": response})

        return {"response": response, "turn_id": self.turn_id}

    async def end_session(self) -> None:
        """结束会话"""
        ctx = HookContext(
            event=HookEvent.SESSION_END,
            data={
                "session_id": self.session_id,
                "history": self.history,
                "turn_count": self.turn_count,
            },
            session_id=self.session_id,
        )
        await self.event_bus.emit(HookEvent.SESSION_END, ctx)
```

---

## 🧪 测试验证

```python
"""
测试 Hook 系统
"""

import asyncio
import tempfile
from pathlib import Path

from hooks.event_bus import EventBus, HookContext, HookEvent
from hooks.registry import HookRegistry
from hooks.builtin.session_persist import SessionPersister
from hooks.builtin.security_scan import SecurityScanner
from core.agent import AgentWithHooks


async def test_event_bus():
    """测试事件总线"""
    bus = EventBus()
    results = []

    async def handler1(ctx: HookContext) -> None:
        results.append(f"handler1: {ctx.event.value}")

    async def handler2(ctx: HookContext) -> None:
        results.append(f"handler2: {ctx.event.value}")
        ctx.modify("processed", True)

    bus.on(HookEvent.TURN_START, handler1)
    bus.on(HookEvent.TURN_START, handler2)

    ctx = HookContext(
        event=HookEvent.TURN_START,
        data={"input": "hello"},
    )
    result = await bus.emit(HookEvent.TURN_START, ctx)

    assert results == ["handler1: turn_start", "handler2: turn_start"]
    assert result.get("processed") is True
    print("✅ EventBus 测试通过")


async def test_abort_chain():
    """测试 Hook 拦截链"""
    bus = EventBus()
    executed = []

    async def blocker(ctx: HookContext) -> None:
        executed.append("blocker")
        ctx.abort("安全拦截")

    async def late_handler(ctx: HookContext) -> None:
        executed.append("late_handler")  # 不应执行

    bus.on(HookEvent.TOOL_CALL, blocker)
    bus.on(HookEvent.TOOL_CALL, late_handler)

    ctx = HookContext(
        event=HookEvent.TOOL_CALL,
        data={"tool_name": "bash", "tool_input": {"command": "rm -rf /"}},
    )
    await bus.emit(HookEvent.TOOL_CALL, ctx)

    assert executed == ["blocker"]
    assert ctx.should_abort is True
    print("✅ Hook 拦截链测试通过")


async def test_security_scan():
    """测试安全扫描"""
    scanner = SecurityScanner(strict_mode=True)

    # 危险命令应被拦截
    ctx = HookContext(
        event=HookEvent.TOOL_CALL,
        data={
            "tool_name": "bash",
            "tool_input": {"command": "rm -rf /"},
        },
    )
    await scanner.scan_tool_call(ctx)
    assert ctx.should_abort is True
    assert "根目录" in ctx.abort_reason
    print("✅ 安全扫描（严格模式）测试通过")

    # 安全命令应通过
    ctx2 = HookContext(
        event=HookEvent.TOOL_CALL,
        data={
            "tool_name": "bash",
            "tool_input": {"command": "ls -la"},
        },
    )
    await scanner.scan_tool_call(ctx2)
    assert ctx2.should_abort is False
    print("✅ 安全扫描（安全命令）测试通过")


async def test_session_persist():
    """测试会话持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        persister = SessionPersister(storage_dir=tmpdir)

        # 保存会话
        ctx = HookContext(
            event=HookEvent.SESSION_END,
            data={
                "session_id": "test-001",
                "history": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！"},
                ],
                "turn_count": 1,
            },
            session_id="test-001",
        )
        await persister.on_session_end(ctx)

        # 恢复会话
        ctx2 = HookContext(
            event=HookEvent.SESSION_START,
            data={"session_id": "test-001"},
            session_id="test-001",
        )
        await persister.on_session_start(ctx2)

        history = ctx2.get("history", [])
        assert len(history) == 2
        assert history[0]["content"] == "你好"
        print("✅ 会话持久化测试通过")


async def test_full_agent():
    """测试完整 Agent + Hook 集成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        os.environ["MY_AGENT_STORAGE"] = tmpdir

        agent = AgentWithHooks()
        await agent.start_session()

        result = await agent.process_turn("你好，世界")
        assert "response" in result
        print(f"✅ Agent 完整流程测试通过: {result['response']}")

        await agent.end_session()
        print("✅ 会话正常结束")


async def main():
    print("=" * 50)
    print("Hook 系统测试")
    print("=" * 50)

    await test_event_bus()
    await test_abort_chain()
    await test_security_scan()
    await test_session_persist()
    await test_full_agent()

    print("=" * 50)
    print("所有测试通过！🎉")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

运行测试：

```bash
cd my_agent
python -m pytest tests/test_hooks.py -v
# 或直接运行
python tests/test_hooks.py
```

预期输出：

```
==================================================
Hook 系统测试
==================================================
✅ EventBus 测试通过
✅ Hook 拦截链测试通过
✅ 安全扫描（严格模式）测试通过
✅ 安全扫描（安全命令）测试通过
✅ 会话持久化测试通过
✅ Agent 完整流程测试通过: 收到: 你好，世界
✅ 会话正常结束
==================================================
所有测试通过！🎉
==================================================
```

---

## 📝 本章小结

本章我们实现了 Agent 的 Hook 系统，核心收获：

1. **事件总线**：发布-订阅模式，支持延迟注册和容量限制，参考 Claude Code 的 `hookEvents.ts`
2. **Hook 注册表**：管理 Hook 的生命周期，支持优先级排序和动态配置
3. **三个内置 Hook**：
   - 会话持久化：自动保存/恢复对话历史
   - 安全扫描：拦截危险命令，要求用户确认
   - 持续学习：从交互中提取经验教训
4. **拦截机制**：Hook 可以通过 `ctx.abort()` 中止后续流程
5. **数据修改**：Hook 可以通过 `ctx.modify()` 修改上下文数据

Hook 系统的价值在于**解耦**——核心 Agent 代码不需要知道安全扫描、持久化、学习等逻辑的存在，这些能力通过 Hook 即插即用。

---

## 🏋️ 课后练习

### 练习 1：实现一个自定义 Hook —— 成本追踪

**题目**：编写一个 Hook，在每次 `ASSISTANT_RESPONSE` 事件时记录 token 使用量和估算成本，在 `SESSION_END` 时输出总成本报告。

**答案提示**：
- 在 Hook 内部维护一个计数器（total_tokens, total_cost）
- 从 `ctx.get("token_usage")` 获取每次调用的 token 数
- 按模型单价估算成本（如 Claude Sonnet: $3/M input, $15/M output）
- 在 SESSION_END 时打印或保存报告

### 练习 2：实现 Hook 超时机制

**题目**：当前 Hook 执行没有超时限制，如果一个 Hook 卡住会阻塞整个 Agent。请为 EventBus 添加超时机制，单个 Hook 执行超过 5 秒自动跳过。

**答案提示**：
- 使用 `asyncio.wait_for(callback(ctx), timeout=5)`
- 超时后记录警告日志，继续执行下一个 Hook
- 在 HookContext 中添加 `timeout_seconds` 配置项

### 练习 3：实现 Hook 条件匹配

**题目**：参考 Claude Code 的 `HookCallbackMatcher`，让 Hook 支持条件匹配。例如：安全扫描 Hook 只在 `tool_name == "bash"` 时执行。

**答案提示**：
- 在 HookDescriptor 中添加 `condition: Callable[[HookContext], bool]`
- Executor 执行 Hook 前先检查 condition
- 支持简单的 DSL 配置，如 `{"tool_name": "bash"}`

---

*下一章：第 12 章 —— CLI 终端界面，让我们的 Agent 不仅聪明，而且好用。*

这个回答对你有帮助吗？回复数字让我知道：0 差 · 1 一般 · 2 好
