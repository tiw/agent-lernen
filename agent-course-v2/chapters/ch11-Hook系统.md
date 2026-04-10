# 第 11 章：Hook 系统 —— 让 Agent 可插拔

> **本章目标**：实现事件驱动的 Hook 框架，让 Agent 具备会话持久化、安全扫描、持续学习等可插拔能力
>
> 🎯 **里程碑进度**：▓▓▓▓▓▓▓▓▓▓▓░ 110% — Agent 拥有事件扩展能力

---

## 🧠 核心概念

### 什么是 Hook？

Hook（钩子）是一种**事件驱动的扩展机制**。它在 Agent 生命周期的关键节点触发用户自定义的逻辑，而无需修改核心代码。

```
用户发消息 → [Hook: 安全检查] → Agent 处理 → [Hook: 持久化] → 回复用户
```

### 核心架构

```
┌─────────────────────────────────────────────┐
│              EventBus                        │
│   发布/订阅模式的事件分发                     │
├─────────────────────────────────────────────┤
│            HookRegistry                      │
│   管理所有注册的 Hook                        │
├──────────┬──────────┬───────────────────────┤
│ session  │ security │ continuous            │
│ persist  │ scan     │ learn                 │
└──────────┴──────────┴───────────────────────┘
```

### 事件类型

| 事件 | 触发时机 | 典型用途 |
|------|----------|----------|
| **session_start** | 会话开始 | 加载历史、初始化 |
| **session_end** | 会话结束 | 保存历史、清理 |
| **user_message** | 用户发送消息后 | 安全检查、日志 |
| **tool_call** | 工具调用前 | 权限检查、审计 |
| **tool_result** | 工具返回后 | 结果过滤、日志 |
| **assistant_response** | Agent 回复后 | 记忆提取、持久化 |

---

## 💻 动手实现

### 项目结构

```
src/
├── agent.py              # ⚠️ 需要更新：加入 Hook 触发
└── hooks/
    ├── __init__.py
    ├── event_bus.py      # 🆕 事件总线
    ├── registry.py       # 🆕 Hook 注册表
    └── builtin.py        # 🆕 内置 Hook
```

### 代码 1：`src/hooks/__init__.py`

```python
"""Hook 模块入口"""
from hooks.event_bus import EventBus, HookEvent
from hooks.registry import HookRegistry
from hooks.builtin import (
    SessionPersistHook,
    SecurityScanHook,
    ContinuousLearnHook,
)

__all__ = [
    "EventBus", "HookEvent", "HookRegistry",
    "SessionPersistHook", "SecurityScanHook", "ContinuousLearnHook",
]
```

### 代码 2：`src/hooks/event_bus.py`

```python
"""
事件总线 —— 发布/订阅模式的事件分发。

从零手写 AI Agent 课程 · 第 11 章
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class HookEvent(Enum):
    """Hook 事件类型"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_MESSAGE = "user_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ASSISTANT_RESPONSE = "assistant_response"


@dataclass
class EventData:
    """事件数据"""
    event_type: HookEvent
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class EventBus:
    """
    事件总线。
    
    发布/订阅模式：
    - 发布者 emit 事件
    - 订阅者通过 on() 注册回调
    - 事件触发时，所有回调按注册顺序执行
    
    使用示例：
        bus = EventBus()
        bus.on(HookEvent.USER_MESSAGE, lambda e: print(e.data))
        bus.emit(HookEvent.USER_MESSAGE, {"text": "你好"})
    """
    
    def __init__(self):
        self._handlers: dict[HookEvent, list[Callable]] = {}
        self._event_history: list[EventData] = []
        self._max_history = 100  # 最多保留 100 条历史
    
    def on(
        self,
        event: HookEvent,
        handler: Callable[[EventData], Any],
    ) -> None:
        """
        注册事件处理器。
        
        Args:
            event: 事件类型
            handler: 回调函数，接收 EventData 参数
        """
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
    
    def off(
        self,
        event: HookEvent,
        handler: Optional[Callable] = None,
    ) -> None:
        """
        移除事件处理器。
        
        Args:
            event: 事件类型
            handler: 要移除的处理器（None 表示移除所有）
        """
        if event in self._handlers:
            if handler:
                self._handlers[event] = [
                    h for h in self._handlers[event] if h != handler
                ]
            else:
                self._handlers[event] = []
    
    def emit(self, event: HookEvent, data: dict[str, Any]) -> list[Any]:
        """
        触发事件。
        
        Args:
            event: 事件类型
            data: 事件数据
            
        Returns:
            所有处理器的返回值
        """
        event_data = EventData(event_type=event, data=data)
        
        # 记录历史
        self._event_history.append(event_data)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # 执行所有处理器
        results = []
        for handler in self._handlers.get(event, []):
            try:
                result = handler(event_data)
                results.append(result)
            except Exception as e:
                results.append(f"[Hook 错误] {e}")
        
        return results
    
    def get_history(
        self,
        event_type: Optional[HookEvent] = None,
        limit: int = 50,
    ) -> list[EventData]:
        """获取事件历史"""
        history = self._event_history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]
    
    def clear_history(self):
        """清空事件历史"""
        self._event_history.clear()
```

### 代码 3：`src/hooks/registry.py`

```python
"""
Hook 注册表 —— 管理所有注册的 Hook。

从零手写 AI Agent 课程 · 第 11 章
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from hooks.event_bus import EventBus, HookEvent


class Hook(ABC):
    """
    Hook 基类。
    
    每个 Hook 需要实现：
    - name: Hook 名称
    - events: 监听的事件类型列表
    - handle(): 事件处理逻辑
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def events(self) -> list[HookEvent]:
        pass
    
    @abstractmethod
    def handle(self, event_data) -> Optional[str]:
        """
        处理事件。
        
        Args:
            event_data: EventData 对象
            
        Returns:
            可选的处理结果
        """
        pass
    
    def register(self, bus: EventBus) -> None:
        """将 Hook 注册到事件总线"""
        for event in self.events:
            bus.on(event, self.handle)
    
    def unregister(self, bus: EventBus) -> None:
        """从事件总线移除 Hook"""
        for event in self.events:
            bus.off(event, self.handle)


class HookRegistry:
    """
    Hook 注册表。
    
    管理所有 Hook 的注册和注销。
    
    使用示例：
        registry = HookRegistry(bus)
        registry.register(SessionPersistHook())
        registry.register(SecurityScanHook())
        
        # 禁用某个 Hook
        registry.disable("security_scan")
        
        # 启用某个 Hook
        registry.enable("security_scan")
    """
    
    def __init__(self, bus: EventBus):
        self.bus = bus
        self._hooks: dict[str, Hook] = {}
        self._enabled: set[str] = set()
    
    def register(self, hook: Hook) -> None:
        """注册一个 Hook"""
        self._hooks[hook.name] = hook
        self._enabled.add(hook.name)
        hook.register(self.bus)
    
    def unregister(self, name: str) -> bool:
        """注销一个 Hook"""
        hook = self._hooks.pop(name, None)
        if hook:
            self._enabled.discard(name)
            hook.unregister(self.bus)
            return True
        return False
    
    def enable(self, name: str) -> bool:
        """启用 Hook"""
        if name in self._hooks:
            self._enabled.add(name)
            self._hooks[name].register(self.bus)
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """禁用 Hook"""
        if name in self._hooks:
            self._enabled.discard(name)
            self._hooks[name].unregister(self.bus)
            return True
        return False
    
    @property
    def hook_names(self) -> list[str]:
        return list(self._hooks.keys())
    
    @property
    def enabled_names(self) -> list[str]:
        return list(self._enabled)
    
    def status(self) -> dict:
        """获取所有 Hook 的状态"""
        return {
            name: "enabled" if name in self._enabled else "disabled"
            for name in self._hooks
        }
```

### 代码 4：`src/hooks/builtin.py`

```python
"""
内置 Hook —— 会话持久化、安全扫描、持续学习。

从零手写 AI Agent 课程 · 第 11 章
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from hooks.event_bus import EventBus, HookEvent, EventData
from hooks.registry import Hook


# ============================================================
# SessionPersistHook —— 会话持久化
# ============================================================

class SessionPersistHook(Hook):
    """
    会话持久化 Hook。
    
    在会话结束时自动保存对话历史到文件。
    下次会话开始时自动加载。
    """
    
    @property
    def name(self) -> str:
        return "session_persist"
    
    @property
    def events(self) -> list[HookEvent]:
        return [HookEvent.SESSION_START, HookEvent.SESSION_END]
    
    def __init__(self, save_dir: str = ".sessions"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
    
    def handle(self, event_data: EventData) -> Optional[str]:
        if event_data.event_type == HookEvent.SESSION_END:
            return self._save(event_data)
        elif event_data.event_type == HookEvent.SESSION_START:
            return self._load(event_data)
        return None
    
    def _save(self, event_data: EventData) -> str:
        """保存会话"""
        messages = event_data.get("messages", [])
        if not messages:
            return "无消息可保存"
        
        session_id = event_data.get("session_id", str(int(time.time())))
        filepath = os.path.join(self.save_dir, f"{session_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": session_id,
                "saved_at": time.time(),
                "message_count": len(messages),
                "messages": messages,
            }, f, ensure_ascii=False, indent=2)
        
        return f"会话已保存: {filepath} ({len(messages)} 条消息)"
    
    def _load(self, event_data: EventData) -> str:
        """加载会话"""
        session_id = event_data.get("session_id")
        if not session_id:
            return "无会话 ID，跳过加载"
        
        filepath = os.path.join(self.save_dir, f"{session_id}.json")
        if not os.path.exists(filepath):
            return f"未找到会话文件: {filepath}"
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 将加载的消息存入 event_data
        event_data.data["loaded_messages"] = data.get("messages", [])
        
        return f"会话已加载: {filepath} ({len(data.get('messages', []))} 条消息)"


# ============================================================
# SecurityScanHook —— 安全扫描
# ============================================================

class SecurityScanHook(Hook):
    """
    安全扫描 Hook。
    
    在工具调用前检查命令是否包含危险操作。
    """
    
    # 危险命令模式
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf /*",
        ":(){:|:&};:",       # fork bomb
        "> /dev/sda",
        "dd if=",
        "mkfs",
        "chmod 777 /",
        "chown -R /",
    ]
    
    @property
    def name(self) -> str:
        return "security_scan"
    
    @property
    def events(self) -> list[HookEvent]:
        return [HookEvent.TOOL_CALL]
    
    def handle(self, event_data: EventData) -> Optional[str]:
        tool_name = event_data.get("tool_name", "")
        tool_args = event_data.get("tool_args", {})
        
        # 只检查 bash 工具
        if tool_name != "bash":
            return None
        
        command = tool_args.get("command", "")
        
        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command:
                return f"🚫 安全拦截: 检测到危险命令模式 '{pattern}'"
        
        return None  # 安全检查通过


# ============================================================
# ContinuousLearnHook —— 持续学习
# ============================================================

class ContinuousLearnHook(Hook):
    """
    持续学习 Hook。
    
    在 Agent 回复后，自动记录有用的信息到学习日志。
    """
    
    @property
    def name(self) -> str:
        return "continuous_learn"
    
    @property
    def events(self) -> list[HookEvent]:
        return [HookEvent.ASSISTANT_RESPONSE]
    
    def __init__(self, log_file: str = "learning_log.jsonl"):
        self.log_file = log_file
    
    def handle(self, event_data: EventData) -> Optional[str]:
        response = event_data.get("response", "")
        user_input = event_data.get("user_input", "")
        
        if not response or not user_input:
            return None
        
        # 记录到学习日志
        entry = {
            "timestamp": time.time(),
            "user_input": user_input[:200],
            "response_length": len(response),
            "tool_calls": event_data.get("tool_call_count", 0),
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return None  # 静默记录，不干扰对话
```

### ⚠️ 更新 `src/agent.py`

主要变更：
1. 新增 `EventBus` 和 `HookRegistry` 初始化
2. 在 `chat()` 方法的关键节点触发事件

```python
# 在 Agent.__init__ 中添加
from hooks.event_bus import EventBus, HookEvent
from hooks.registry import HookRegistry

# ... 在 __init__ 中 ...
self.event_bus = EventBus()
self.hook_registry = HookRegistry(self.event_bus)
self._session_id = str(int(time.time()))

# 在 chat() 方法中添加 Hook 触发
def chat(self, user_input: str) -> str:
    # 触发 user_message 事件
    self.event_bus.emit(HookEvent.USER_MESSAGE, {
        "text": user_input,
    })
    
    # ... 原有工具调用循环 ...
    
    # 在工具调用前触发 tool_call 事件
    # 在工具调用后触发 tool_result 事件
    for tool_call in message.tool_calls:
        self.event_bus.emit(HookEvent.TOOL_CALL, {
            "tool_name": tool_name,
            "tool_args": tool_args,
        })
        
        result = self.tool_map[tool_name].execute(**tool_args)
        
        self.event_bus.emit(HookEvent.TOOL_RESULT, {
            "tool_name": tool_name,
            "result": result,
        })
    
    # 触发 assistant_response 事件
    self.event_bus.emit(HookEvent.ASSISTANT_RESPONSE, {
        "response": reply,
        "user_input": user_input,
        "tool_call_count": tool_call_count,
    })
    
    return reply
```

---

## 🧪 测试验证

```python
"""测试 Hook 系统"""
from hooks.event_bus import EventBus, HookEvent
from hooks.registry import HookRegistry, Hook
from hooks.builtin import (
    SessionPersistHook, SecurityScanHook, ContinuousLearnHook,
)


def test_event_bus():
    """测试事件总线"""
    bus = EventBus()
    
    results = []
    
    # 注册处理器
    def handler1(event):
        results.append(f"handler1: {event.data}")
        return "ok1"
    
    def handler2(event):
        results.append(f"handler2: {event.data}")
        return "ok2"
    
    bus.on(HookEvent.USER_MESSAGE, handler1)
    bus.on(HookEvent.USER_MESSAGE, handler2)
    
    # 触发事件
    bus.emit(HookEvent.USER_MESSAGE, {"text": "你好"})
    
    assert len(results) == 2
    print(f"✅ 事件触发: {results}")
    
    # 移除处理器
    bus.off(HookEvent.USER_MESSAGE, handler1)
    results.clear()
    bus.emit(HookEvent.USER_MESSAGE, {"text": "再次"})
    assert len(results) == 1
    print("✅ 移除处理器成功")


def test_security_scan():
    """测试安全扫描"""
    bus = EventBus()
    hook = SecurityScanHook()
    hook.register(bus)
    
    # 安全命令
    results = bus.emit(HookEvent.TOOL_CALL, {
        "tool_name": "bash",
        "tool_args": {"command": "ls -la"},
    })
    assert all(r is None for r in results)
    print("✅ 安全命令通过")
    
    # 危险命令
    results = bus.emit(HookEvent.TOOL_CALL, {
        "tool_name": "bash",
        "tool_args": {"command": "rm -rf /"},
    })
    assert any(r and "安全拦截" in str(r) for r in results)
    print("✅ 危险命令被拦截")


def test_session_persist():
    """测试会话持久化"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EventBus()
        hook = SessionPersistHook(save_dir=tmpdir)
        hook.register(bus)
        
        # 保存会话
        bus.emit(HookEvent.SESSION_END, {
            "session_id": "test_001",
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！"},
            ],
        })
        
        # 加载会话
        bus.emit(HookEvent.SESSION_START, {
            "session_id": "test_001",
        })
        
        print("✅ 会话持久化测试通过")


if __name__ == "__main__":
    print("=" * 50)
    print("事件总线测试")
    print("=" * 50)
    test_event_bus()
    
    print("\n" + "=" * 50)
    print("安全扫描测试")
    print("=" * 50)
    test_security_scan()
    
    print("\n" + "=" * 50)
    print("会话持久化测试")
    print("=" * 50)
    test_session_persist()
    
    print("\n🎉 全部测试通过！")
```

---

## ⚠️ 常见错误

### 错误 1：Hook 执行顺序不确定
**原因**：字典遍历顺序在 Python 3.7+ 是插入顺序，但多个 Hook 的注册顺序可能不同。
**解决**：如果需要确定顺序，使用 `OrderedDict` 或显式设置优先级。

### 错误 2：Hook 异常导致整个流程中断
**原因**：某个 Hook 抛出异常，没有捕获。
**解决**：`EventBus.emit()` 中已经用 try/except 包裹了每个处理器。

### 错误 3：会话文件过大
**原因**：长时间运行的会话积累了大量消息。
**解决**：在保存前压缩消息历史，或只保存摘要。

---

## 📝 本章小结

本章实现了 Hook 系统：

| 组件 | 作用 |
|------|------|
| **EventBus** | 发布/订阅模式的事件分发 |
| **HookRegistry** | 管理 Hook 的注册、启用、禁用 |
| **SessionPersistHook** | 自动保存/加载会话历史 |
| **SecurityScanHook** | 工具调用前的安全检查 |
| **ContinuousLearnHook** | 自动记录学习日志 |

### 当前局限性

- ❌ Hook 只能同步执行，不支持异步
- ❌ 没有 Hook 优先级机制
- ❌ 外部命令 Hook（调用外部脚本）未实现

**下一章**，我们将实现 CLI 终端界面——让 Agent 好用又好看。

---

## 🏋️ 课后练习

### 练习 1：实现外部命令 Hook
支持通过外部脚本处理事件：
```python
class ExternalCommandHook(Hook):
    def __init__(self, command: str):
        self.command = command
    
    def handle(self, event_data):
        import subprocess
        env = {"EVENT_TYPE": event_data.event_type.value}
        env.update({k.upper(): str(v) for k, v in event_data.data.items()})
        subprocess.run(self.command, env={**os.environ, **env})
```

### 练习 2：实现 Hook 链式拦截
让 Hook 可以阻止事件继续传播（类似中间件）。

### 练习 3：实现 Hook 性能监控
记录每个 Hook 的执行时间，找出性能瓶颈。

---

**下一章**：[第 12 章：CLI 终端界面 —— 让 Agent 好用](ch12-CLI终端界面.md)
