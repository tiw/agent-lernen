"""
team/message_bus.py —— 消息总线
参考 Claude Code 的团队通信机制
从零手写 AI Agent 课程 · 第 10 章
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息"""
    sender: str
    receiver: str
    content: str
    timestamp: float = field(default_factory=time.time)


class MessageBus:
    """
    消息总线

    参考 Claude Code 的团队通信：
    - Agent 间直接消息
    - 广播消息
    - 消息队列
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._subscribers: dict[str, list[Callable]] = {}
        self._message_count = 0

    def register_agent(self, agent_id: str) -> None:
        """注册 Agent"""
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()
            logger.info(f"Registered agent: {agent_id}")

    async def send(self, message: Message) -> None:
        """发送消息"""
        if message.receiver not in self._queues:
            logger.warning(f"Receiver not found: {message.receiver}")
            return

        await self._queues[message.receiver].put(message)
        self._message_count += 1
        logger.debug(f"Message: {message.sender} → {message.receiver}")

        # 通知订阅者
        if message.receiver in self._subscribers:
            for callback in self._subscribers[message.receiver]:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")

    async def receive(self, agent_id: str) -> Optional[Message]:
        """接收消息"""
        if agent_id not in self._queues:
            return None

        try:
            return self._queues[agent_id].get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def broadcast(self, sender: str, content: str, exclude: list[str] = None) -> None:
        """广播消息"""
        exclude = exclude or []
        for agent_id in self._queues:
            if agent_id not in exclude:
                await self.send(Message(sender=sender, receiver=agent_id, content=content))

    def subscribe(self, agent_id: str, callback: Callable[[Message], None]) -> None:
        """订阅消息"""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        self._subscribers[agent_id].append(callback)

    @property
    def message_count(self) -> int:
        return self._message_count


# === 测试 ===
if __name__ == "__main__":
    async def test_message_bus():
        print("=== 消息总线测试 ===\n")

        bus = MessageBus()

        # 测试 1: 注册 Agent
        print("测试 1: 注册 Agent")
        bus.register_agent("agent1")
        bus.register_agent("agent2")
        print(f"  已注册 Agent: {list(bus._queues.keys())}\n")

        # 测试 2: 发送消息
        print("测试 2: 发送消息")
        await bus.send(Message(sender="agent1", receiver="agent2", content="Hello!"))
        print(f"  消息数：{bus.message_count}\n")

        # 测试 3: 接收消息
        print("测试 3: 接收消息")
        msg = await bus.receive("agent2")
        print(f"  收到：{msg.sender} → {msg.content}\n")

        # 测试 4: 广播
        print("测试 4: 广播")
        await bus.broadcast("coordinator", "Meeting at 3pm", exclude=["agent1"])
        print(f"  消息数：{bus.message_count}\n")

        print("✅ 所有测试完成！")

    import sys
    import os
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        asyncio.run(test_message_bus())
