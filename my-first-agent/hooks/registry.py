"""
hooks/registry.py —— Hook 注册表
管理 Hook 的注册、卸载和配置
参考 Claude Code 的 hooksConfigSnapshot.ts
从零手写 AI Agent 课程 · 第 11 章
"""

import importlib
import logging
import sys
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

# 支持直接运行和模块导入两种模式
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from hooks.event_bus import EventBus, HookCallback, HookEvent, HookContext
else:
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
        config: Union[dict[str, Any], None] = None,
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

    def load_from_config(self, config_path: Union[str, Path]) -> None:
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


# === 测试 ===
if __name__ == "__main__":
    async def test_registry():
        print("=== Hook 注册表测试 ===\n")

        bus = EventBus()
        registry = HookRegistry(bus)

        # 测试 1: 注册 Hook
        print("测试 1: 注册 Hook")

        def hook1(ctx: HookContext) -> None:
            print(f"  Hook1 执行：{ctx.event.value}")

        def hook2(ctx: HookContext) -> None:
            print(f"  Hook2 执行：{ctx.event.value}")

        registry.register("hook1", HookEvent.TOOL_CALL, hook1, priority=10)
        registry.register("hook2", HookEvent.TOOL_CALL, hook2, priority=20)
        print(f"  已注册：{len(registry._hooks)} 个 Hook\n")

        # 测试 2: 列出 Hook
        print("测试 2: 列出 Hook")
        for h in registry.list_hooks():
            print(f"  {h['name']} -> {h['event']} (priority={h['priority']})\n")

        # 测试 3: 禁用 Hook
        print("测试 3: 禁用 Hook")
        registry.disable("hook1")
        print(f"  活跃 Hook: {len(registry.active_hooks)}\n")

        # 测试 4: 触发事件
        print("测试 4: 触发事件")
        ctx = HookContext(
            event=HookEvent.TOOL_CALL,
            data={"tool_name": "bash"},
        )
        await bus.emit(HookEvent.TOOL_CALL, ctx)
        print()

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import asyncio
        asyncio.run(test_registry())
