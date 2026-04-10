"""
team/message_bus.py —— 多智能体消息总线
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Agent 间消息"""
    sender: str
    receiver: str
    content: str
    timestamp: float = field(default_factory=time.time)
    message_type: str = "direct"  # "direct" | "broadcast" | "system"

    def __repr__(self) -> str:
        return f"Message({self.sender} → {self.receiver})"


class MessageBus:
    """消息总线"""

    def __init__(self):
        self._queues: dict = {}
        self._message_log: list = []
        self._subscribers: dict = {}

    def register_agent(self, agent_id: str) -> None:
        """注册 Agent"""
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()
            logger.info(f"Agent registered on message bus: {agent_id}")

    async def send(self, message: Message) -> None:
        """发送消息"""
        self._message_log.append(message)

        if message.message_type == "broadcast":
            for agent_id, queue in self._queues.items():
                if agent_id != message.sender:
                    await queue.put(message)
            logger.info(f"Broadcast from {message.sender}: {message.content[:50]}...")
        else:
            queue = self._queues.get(message.receiver)
            if queue:
                await queue.put(message)
                logger.info(f"Message {message.sender} → {message.receiver}: {message.content[:50]}...")
            else:
                logger.warning(f"Receiver not found: {message.receiver}")

    async def receive(self, agent_id: str, timeout: float = 5.0) -> Optional[Message]:
        """接收消息"""
        queue = self._queues.get(agent_id)
        if not queue:
            return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def get_history(self, agent_id: str = None, limit: int = 50) -> list:
        """获取消息历史"""
        messages = self._message_log
        if agent_id:
            messages = [
                m for m in messages
                if m.sender == agent_id or m.receiver == agent_id or m.message_type == "broadcast"
            ]
        return messages[-limit:]

    @property
    def message_count(self) -> int:
        return len(self._message_log)
