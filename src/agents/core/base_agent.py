#!/usr/bin/env python3
"""
核心Agent基礎類別
提供所有Agent的通用接口和基礎功能
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class AgentStatus(Enum):
    """Agent狀態枚舉"""

    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


class MessageType(Enum):
    """消息類型枚舉"""

    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    COORDINATION_REQUEST = "coordination_request"
    RESULT_SHARING = "result_sharing"
    HEARTBEAT = "heartbeat"


@dataclass
class AgentMessage:
    """Agent間消息格式"""

    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    payload: dict[str, Any]
    timestamp: datetime
    priority: int = 5
    correlation_id: str | None = None
    expires_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式"""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        """從字典創建消息實例"""
        return cls(
            message_id=data["message_id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=MessageType(data["message_type"]),
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=data.get("priority", 5),
            correlation_id=data.get("correlation_id"),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
        )


@dataclass
class AgentCapability:
    """Agent能力描述"""

    name: str
    description: str
    input_types: list[str]
    output_types: list[str]
    resource_requirements: dict[str, Any]
    estimated_time: float  # 秒


@dataclass
class AgentMetrics:
    """Agent性能指標"""

    tasks_completed: int = 0
    tasks_failed: int = 0
    average_response_time: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_heartbeat: datetime | None = None
    uptime: float = 0.0


class BaseAgent(ABC):
    """
    Agent基礎抽象類
    所有具體Agent都應該繼承此類
    """

    def __init__(self, agent_id: str, name: str, description: str = ""):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.status = AgentStatus.INITIALIZING
        self.capabilities: list[AgentCapability] = []
        self.metrics = AgentMetrics()

        # 通信相關
        self.message_handlers: dict[MessageType, Callable] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.communication_hub = None

        # 配置和工具
        self.config: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}

        # 日誌
        self.logger = logging.getLogger(f"agent.{self.agent_id}")

        # 任務追蹤
        self.current_tasks: dict[str, Any] = {}
        self.task_history: list[dict[str, Any]] = []

        # 初始化消息處理器
        self._setup_default_handlers()

        self.logger.info(f"Agent {self.name} ({self.agent_id}) 初始化完成")

    def _setup_default_handlers(self):
        """設置默認消息處理器"""
        self.message_handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        self.message_handlers[MessageType.STATUS_UPDATE] = self._handle_status_update
        self.message_handlers[MessageType.ERROR_REPORT] = self._handle_error_report

    async def initialize(self, config: dict[str, Any] = None):
        """初始化Agent"""
        try:
            if config:
                self.config.update(config)

            # 子類特定初始化
            await self._initialize()

            # 註冊能力
            self.capabilities = await self._register_capabilities()

            self.status = AgentStatus.READY
            self.logger.info(f"Agent {self.name} 初始化成功")

        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Agent {self.name} 初始化失敗: {e}")
            raise

    @abstractmethod
    async def _initialize(self):
        """子類特定的初始化邏輯"""
        pass

    @abstractmethod
    async def _register_capabilities(self) -> list[AgentCapability]:
        """註冊Agent的能力"""
        pass

    async def start(self):
        """啟動Agent"""
        if self.status != AgentStatus.READY:
            raise RuntimeError(f"Agent {self.name} 未準備好，當前狀態: {self.status}")

        # 啟動消息處理循環
        asyncio.create_task(self._message_processing_loop())

        # 啟動心跳
        asyncio.create_task(self._heartbeat_loop())

        # 子類特定啟動邏輯
        await self._start()

        self.logger.info(f"Agent {self.name} 已啟動")

    @abstractmethod
    async def _start(self):
        """子類特定的啟動邏輯"""
        pass

    async def stop(self):
        """停止Agent"""
        self.status = AgentStatus.STOPPING

        # 完成當前任務
        await self._finish_current_tasks()

        # 子類特定停止邏輯
        await self._stop()

        self.status = AgentStatus.STOPPED
        self.logger.info(f"Agent {self.name} 已停止")

    @abstractmethod
    async def _stop(self):
        """子類特定的停止邏輯"""
        pass

    async def _finish_current_tasks(self):
        """完成當前任務"""
        if self.current_tasks:
            self.logger.info(f"等待 {len(self.current_tasks)} 個任務完成...")
            # 這裡可以實現更複雜的任務完成邏輯
            await asyncio.sleep(1)  # 簡單等待

    async def send_message(self, message: AgentMessage):
        """發送消息"""
        if self.communication_hub:
            await self.communication_hub.send_message(message)
        else:
            self.logger.warning("通信中樞未設置，消息無法發送")

    async def receive_message(self, message: AgentMessage):
        """接收消息"""
        await self.message_queue.put(message)

    async def _message_processing_loop(self):
        """消息處理循環"""
        while self.status != AgentStatus.STOPPED:
            try:
                # 等待消息，超時1秒
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)

                await self._process_message(message)

            except TimeoutError:
                # 超時是正常的，繼續循環
                continue
            except Exception as e:
                self.logger.error(f"消息處理錯誤: {e}")

    async def _process_message(self, message: AgentMessage):
        """處理單條消息"""
        try:
            handler = self.message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                await self._handle_unknown_message(message)

        except Exception as e:
            self.logger.error(f"處理消息失敗 {message.message_id}: {e}")

            # 發送錯誤響應
            error_response = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.ERROR_REPORT,
                payload={"error": str(e), "original_message_id": message.message_id},
                timestamp=datetime.now(),
                correlation_id=message.correlation_id,
            )
            await self.send_message(error_response)

    async def _handle_heartbeat(self, message: AgentMessage):
        """處理心跳消息"""
        response = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            message_type=MessageType.STATUS_UPDATE,
            payload={
                "status": self.status.value,
                "metrics": {
                    "tasks_completed": self.metrics.tasks_completed,
                    "tasks_failed": self.metrics.tasks_failed,
                    "average_response_time": self.metrics.average_response_time,
                },
            },
            timestamp=datetime.now(),
            correlation_id=message.correlation_id,
        )
        await self.send_message(response)

    async def _handle_status_update(self, message: AgentMessage):
        """處理狀態更新消息"""
        self.logger.debug(f"收到狀態更新: {message.payload}")

    async def _handle_error_report(self, message: AgentMessage):
        """處理錯誤報告"""
        self.logger.error(f"收到錯誤報告: {message.payload}")

    async def _handle_unknown_message(self, message: AgentMessage):
        """處理未知類型消息"""
        self.logger.warning(f"未知消息類型: {message.message_type}")

    async def _heartbeat_loop(self):
        """心跳循環"""
        while self.status != AgentStatus.STOPPED:
            try:
                self.metrics.last_heartbeat = datetime.now()
                await asyncio.sleep(30)  # 30秒心跳間隔
            except Exception as e:
                self.logger.error(f"心跳錯誤: {e}")

    def get_status(self) -> dict[str, Any]:
        """獲取Agent狀態信息"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.value,
            "capabilities": [cap.name for cap in self.capabilities],
            "current_tasks": len(self.current_tasks),
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "average_response_time": self.metrics.average_response_time,
                "last_heartbeat": self.metrics.last_heartbeat.isoformat()
                if self.metrics.last_heartbeat
                else None,
            },
        }

    def register_message_handler(self, message_type: MessageType, handler: Callable):
        """註冊消息處理器"""
        self.message_handlers[message_type] = handler
        self.logger.debug(f"註冊處理器: {message_type.value}")

    def add_tool(self, name: str, tool: Any):
        """添加工具"""
        self.tools[name] = tool
        self.logger.debug(f"添加工具: {name}")

    def get_tool(self, name: str) -> Any:
        """獲取工具"""
        return self.tools.get(name)

    async def execute_task(self, task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """執行任務 - 由子類實現具體邏輯"""
        self.current_tasks[task_id] = {
            "task_id": task_id,
            "start_time": datetime.now(),
            "data": task_data,
        }

        try:
            result = await self._execute_task(task_id, task_data)
            self.metrics.tasks_completed += 1
            self.task_history.append(
                {
                    "task_id": task_id,
                    "status": "completed",
                    "start_time": self.current_tasks[task_id]["start_time"],
                    "end_time": datetime.now(),
                    "result": result,
                }
            )
            return result
        except Exception as e:
            self.metrics.tasks_failed += 1
            self.task_history.append(
                {
                    "task_id": task_id,
                    "status": "failed",
                    "start_time": self.current_tasks[task_id]["start_time"],
                    "end_time": datetime.now(),
                    "error": str(e),
                }
            )
            raise
        finally:
            self.current_tasks.pop(task_id, None)

    @abstractmethod
    async def _execute_task(self, task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """子類實現的具體任務執行邏輯"""
        pass
