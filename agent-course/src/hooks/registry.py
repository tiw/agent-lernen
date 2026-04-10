from __future__ import annotations

"""
Hook 注册表 —— 管理 Hook 的注册、卸载和配置

参考 Claude Code 的 hooksConfigSnapshot.ts：
- 支持从配置文件加载
- 支持运行时动态注册
- 支持启用/禁用单个 Hook
"""

import importlib
import json
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
