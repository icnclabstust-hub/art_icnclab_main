#!/usr/bin/env python3
"""
Agent間通信中樞
負責消息路由、廣播、持久化等功能
"""

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import redis.asyncio as redis

from agents.core.base_agent import AgentMessage


class RoutingStrategy(Enum):
    """路由策略"""

    DIRECT = "direct"  # 直接路由
    BROADCAST = "broadcast"  # 廣播
    ROUND_ROBIN = "round_robin"  # 輪詢
    LOAD_BALANCED = "load_balanced"  # 負載均衡
    TOPIC_BASED = "topic_based"  # 基於主題


@dataclass
class MessageRoute:
    """消息路由配置"""

    pattern: str  # 路由模式
    strategy: RoutingStrategy
    targets: list[str]  # 目標Agent列表
    conditions: dict[str, Any] = None  # 路由條件


class CommunicationHub:
    """
    通信中樞
    處理Agent間的所有通信需求
    """

    def __init__(self, redis_config: dict[str, Any] = None):
        self.logger = logging.getLogger("communication_hub")

        # Agent註冊表
        self.registered_agents: dict[str, Any] = {}
        self.agent_capabilities: dict[str, list[str]] = {}

        # 消息路由
        self.routes: list[MessageRoute] = []
        self.routing_table: dict[str, str] = {}

        # 消息持久化和緩存
        self.redis_client = None
        self.redis_config = redis_config or {"host": "localhost", "port": 6379, "db": 1}

        # 消息隊列
        self.message_queues: dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        self.processing_tasks: dict[str, asyncio.Task] = {}

        # 訂閱模式
        self.topic_subscribers: dict[str, set[str]] = defaultdict(set)
        self.pattern_subscribers: dict[str, set[str]] = defaultdict(set)

        # 消息統計
        self.message_stats = {"sent": 0, "received": 0, "failed": 0, "broadcast": 0}

        # 錯誤處理
        self.error_handlers: list[Callable] = []
        self.dead_letter_queue: asyncio.Queue = asyncio.Queue()

        self.logger.info("通信中樞初始化完成")

    async def initialize(self):
        """初始化通信中樞"""
        try:
            # 連接Redis
            if self.redis_config:
                self.redis_client = redis.Redis(**self.redis_config)
                await self.redis_client.ping()
                self.logger.info("Redis連接成功")

            # 啟動消息處理循環
            asyncio.create_task(self._message_processing_loop())
            asyncio.create_task(self._dead_letter_processing_loop())
            asyncio.create_task(self._cleanup_expired_messages())

            self.logger.info("通信中樞啟動完成")

        except Exception as e:
            self.logger.error(f"通信中樞初始化失敗: {e}")
            raise

    async def register_agent(self, agent_id: str, agent_info: dict[str, Any]):
        """註冊Agent"""
        self.registered_agents[agent_id] = {
            "agent_id": agent_id,
            "name": agent_info.get("name"),
            "capabilities": agent_info.get("capabilities", []),
            "registered_at": datetime.now(),
            "last_seen": datetime.now(),
            "status": "online",
        }

        # 為Agent創建專用隊列
        if agent_id not in self.message_queues:
            self.message_queues[agent_id] = asyncio.Queue()

        # 啟動該Agent的消息處理任務
        if agent_id not in self.processing_tasks:
            self.processing_tasks[agent_id] = asyncio.create_task(
                self._process_agent_messages(agent_id)
            )

        self.logger.info(f"Agent {agent_id} 註冊成功")

    async def unregister_agent(self, agent_id: str):
        """註銷Agent"""
        if agent_id in self.registered_agents:
            self.registered_agents[agent_id]["status"] = "offline"

            # 停止消息處理任務
            if agent_id in self.processing_tasks:
                self.processing_tasks[agent_id].cancel()
                del self.processing_tasks[agent_id]

            # 清理訂閱
            for topic, subscribers in self.topic_subscribers.items():
                subscribers.discard(agent_id)

            self.logger.info(f"Agent {agent_id} 註銷成功")

    async def send_message(self, message: AgentMessage):
        """發送消息"""
        try:
            await self._validate_message(message)
            await self._route_message(message)
            self.message_stats["sent"] += 1

        except Exception as e:
            self.logger.error(f"發送消息失敗 {message.message_id}: {e}")
            self.message_stats["failed"] += 1
            await self._handle_message_error(message, str(e))

    async def _validate_message(self, message: AgentMessage):
        """驗證消息格式"""
        if not message.message_id:
            raise ValueError("消息ID不能為空")

        if not message.sender_id:
            raise ValueError("發送者ID不能為空")

        if message.receiver_id != "*" and message.receiver_id not in self.registered_agents:
            raise ValueError(f"接收者 {message.receiver_id} 未註冊")

        # 檢查消息是否過期
        if message.expires_at and message.expires_at < datetime.now():
            raise ValueError("消息已過期")

    async def _route_message(self, message: AgentMessage):
        """路由消息"""
        if message.receiver_id == "*":
            # 廣播消息
            await self._broadcast_message(message)
        else:
            # 直接發送
            await self._send_direct_message(message)

        # 持久化消息
        if self.redis_client:
            await self._persist_message(message)

    async def _send_direct_message(self, message: AgentMessage):
        """直接發送消息到指定Agent"""
        receiver_id = message.receiver_id

        if receiver_id not in self.registered_agents:
            raise ValueError(f"接收者 {receiver_id} 不存在")

        if self.registered_agents[receiver_id]["status"] != "online":
            # 離線消息處理
            await self._handle_offline_message(message)
            return

        # 添加到Agent的消息隊列
        await self.message_queues[receiver_id].put(message)
        self.logger.debug(f"消息 {message.message_id} 已路由到 {receiver_id}")

    async def _broadcast_message(self, message: AgentMessage):
        """廣播消息到所有在線Agent"""
        online_agents = [
            agent_id
            for agent_id, info in self.registered_agents.items()
            if info["status"] == "online" and agent_id != message.sender_id
        ]

        for agent_id in online_agents:
            # 創建廣播消息副本
            broadcast_msg = AgentMessage(
                message_id=f"{message.message_id}_{agent_id}",
                sender_id=message.sender_id,
                receiver_id=agent_id,
                message_type=message.message_type,
                payload=message.payload,
                timestamp=message.timestamp,
                priority=message.priority,
                correlation_id=message.correlation_id,
                expires_at=message.expires_at,
            )

            await self.message_queues[agent_id].put(broadcast_msg)

        self.message_stats["broadcast"] += 1
        self.logger.info(f"廣播消息 {message.message_id} 到 {len(online_agents)} 個Agent")

    async def _process_agent_messages(self, agent_id: str):
        """處理特定Agent的消息隊列"""
        queue = self.message_queues[agent_id]

        while agent_id in self.registered_agents:
            try:
                # 等待消息
                message = await asyncio.wait_for(queue.get(), timeout=1.0)

                # 檢查Agent是否還在線
                if self.registered_agents[agent_id]["status"] != "online":
                    await self._handle_offline_message(message)
                    continue

                # 發送給Agent
                await self._deliver_message(agent_id, message)
                self.message_stats["received"] += 1

            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"處理Agent {agent_id} 消息時出錯: {e}")

    async def _deliver_message(self, agent_id: str, message: AgentMessage):
        """將消息交付給Agent"""
        # 這裡需要與Agent實例進行交互
        # 在實際實現中，會調用Agent的receive_message方法
        self.logger.debug(f"交付消息 {message.message_id} 給 {agent_id}")

    async def _message_processing_loop(self):
        """主消息處理循環"""
        while True:
            try:
                # 這裡可以實現全局消息處理邏輯
                # 比如清理過期消息、統計分析等
                await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"消息處理循環錯誤: {e}")

    async def _dead_letter_processing_loop(self):
        """死信隊列處理循環"""
        while True:
            try:
                # 處理死信隊列中的消息
                message = await asyncio.wait_for(self.dead_letter_queue.get(), timeout=10.0)
                await self._handle_dead_letter(message)

            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"死信處理錯誤: {e}")

    async def _cleanup_expired_messages(self):
        """清理過期消息"""
        while True:
            try:
                if self.redis_client:
                    # 清理Redis中的過期消息
                    await self._cleanup_redis_messages()

                await asyncio.sleep(300)  # 5分鐘清理一次

            except Exception as e:
                self.logger.error(f"消息清理錯誤: {e}")

    async def _persist_message(self, message: AgentMessage):
        """持久化消息到Redis"""
        if not self.redis_client:
            return

        try:
            key = f"message:{message.message_id}"
            data = json.dumps(message.to_dict(), default=str)

            # 設置TTL為24小時
            await self.redis_client.setex(key, 86400, data)

        except Exception as e:
            self.logger.error(f"消息持久化失敗: {e}")

    async def _handle_offline_message(self, message: AgentMessage):
        """處理離線消息"""
        # 可以選擇丟棄或放入死信隊列
        await self.dead_letter_queue.put(message)
        self.logger.warning(f"消息 {message.message_id} 發送給離線Agent {message.receiver_id}")

    async def _handle_dead_letter(self, message: AgentMessage):
        """處理死信消息"""
        # 實現死信處理邏輯
        # 比如重試、記錄、通知等
        self.logger.warning(f"處理死信消息: {message.message_id}")

    async def _handle_message_error(self, message: AgentMessage, error: str):
        """處理消息錯誤"""
        for handler in self.error_handlers:
            try:
                await handler(message, error)
            except Exception as e:
                self.logger.error(f"錯誤處理器執行失敗: {e}")

    async def _cleanup_redis_messages(self):
        """清理Redis中的過期消息"""
        try:
            # 掃描所有消息鍵
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match="message:*", count=100)

                for key in keys:
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -1:  # 沒有過期時間的鍵
                        await self.redis_client.expire(key, 86400)

                if cursor == 0:
                    break

        except Exception as e:
            self.logger.error(f"Redis清理失敗: {e}")

    # 主題訂閱相關方法
    async def subscribe_to_topic(self, agent_id: str, topic: str):
        """訂閱主題"""
        self.topic_subscribers[topic].add(agent_id)
        self.logger.info(f"Agent {agent_id} 訂閱主題 {topic}")

    async def unsubscribe_from_topic(self, agent_id: str, topic: str):
        """取消訂閱主題"""
        self.topic_subscribers[topic].discard(agent_id)
        self.logger.info(f"Agent {agent_id} 取消訂閱主題 {topic}")

    async def publish_to_topic(self, topic: str, message: AgentMessage):
        """發布消息到主題"""
        subscribers = self.topic_subscribers[topic]
        for agent_id in subscribers:
            topic_message = AgentMessage(
                message_id=f"{message.message_id}_{agent_id}",
                sender_id=message.sender_id,
                receiver_id=agent_id,
                message_type=message.message_type,
                payload={**message.payload, "topic": topic},
                timestamp=message.timestamp,
                priority=message.priority,
                correlation_id=message.correlation_id,
            )
            await self.message_queues[agent_id].put(topic_message)

        self.logger.info(f"發布消息到主題 {topic}，{len(subscribers)} 個訂閱者")

    def get_statistics(self) -> dict[str, Any]:
        """獲取通信統計"""
        return {
            "registered_agents": len(self.registered_agents),
            "online_agents": len(
                [a for a in self.registered_agents.values() if a["status"] == "online"]
            ),
            "message_stats": self.message_stats.copy(),
            "queue_sizes": {
                agent_id: queue.qsize() for agent_id, queue in self.message_queues.items()
            },
            "topic_subscribers": {
                topic: len(subscribers) for topic, subscribers in self.topic_subscribers.items()
            },
        }

    def add_error_handler(self, handler: Callable):
        """添加錯誤處理器"""
        self.error_handlers.append(handler)
