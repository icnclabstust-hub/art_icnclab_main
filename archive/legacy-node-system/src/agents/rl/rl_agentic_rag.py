#!/usr/bin/env python3
"""
RL-based Agentic RAG 核心實現
使用 Deep Q-Network (DQN) 進行策略學習
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 數據結構 ====================


@dataclass
class RLState:
    """RL 狀態"""

    query_embedding: np.ndarray  # 查詢嵌入向量
    query_features: np.ndarray  # 查詢特徵
    history_features: np.ndarray  # 歷史特徵
    context_features: np.ndarray  # 上下文特徵

    def to_vector(self) -> np.ndarray:
        """轉換為向量表示"""
        return np.concatenate(
            [
                self.query_embedding,
                self.query_features,
                self.history_features,
                self.context_features,
            ]
        )


@dataclass
class Experience:
    """經驗元組"""

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


# ==================== Q-Network ====================


class QNetwork(nn.Module):
    """深度 Q 網絡"""

    def __init__(self, state_dim: int, action_dim: int, hidden_dims: list[int] = None):
        super().__init__()

        if hidden_dims is None:
            hidden_dims = [512, 256, 128]

        # 構建網絡層
        layers = []
        input_dim = state_dim

        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            input_dim = hidden_dim

        # 輸出層
        layers.append(nn.Linear(input_dim, action_dim))

        self.network = nn.Sequential(*layers)

    def forward(self, state):
        """前向傳播"""
        return self.network(state)


# ==================== Replay Buffer ====================


class ReplayBuffer:
    """經驗回放緩衝池"""

    def __init__(self, capacity: int = 100000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)  # 優先級經驗回放

    def push(self, experience: Experience, priority: float = 1.0):
        """添加經驗"""
        self.buffer.append(experience)
        self.priorities.append(priority)

    def sample(self, batch_size: int) -> list[Experience]:
        """採樣批次"""
        if len(self.buffer) < batch_size:
            return []

        # 使用優先級採樣（可選）
        priorities = np.array(self.priorities)
        probabilities = priorities / priorities.sum()

        indices = np.random.choice(len(self.buffer), batch_size, replace=False, p=probabilities)

        return [self.buffer[idx] for idx in indices]

    def __len__(self):
        return len(self.buffer)


# ==================== State Encoder ====================


class StateEncoder:
    """狀態編碼器"""

    def __init__(self, embedding_model_name: str = "BAAI/bge-m3"):
        from sentence_transformers import SentenceTransformer

        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.embedding_dim = 1024  # BGE-M3 維度

    def encode(self, query: str, context: dict) -> RLState:
        """編碼查詢為 RL 狀態"""

        # 1. 查詢嵌入 (1024維)
        query_embedding = self.embedding_model.encode(query)

        # 2. 查詢特徵 (20維)
        query_features = self._extract_query_features(query)

        # 3. 歷史特徵 (10維)
        history_features = self._extract_history_features(context)

        # 4. 上下文特徵 (10維)
        context_features = self._extract_context_features(context)

        return RLState(
            query_embedding=query_embedding,
            query_features=query_features,
            history_features=history_features,
            context_features=context_features,
        )

    def _extract_query_features(self, query: str) -> np.ndarray:
        """提取查詢特徵"""
        features = [
            len(query.split()),  # 查詢長度
            len(query),  # 字符數
            query.count("?"),  # 問號數量
            query.count("藝術"),  # 領域關鍵詞
            query.count("畫家"),
            query.count("風格"),
            query.count("時期"),
            int("什麼" in query or "what" in query.lower()),  # 意圖標記
            int("如何" in query or "how" in query.lower()),
            int("為什麼" in query or "why" in query.lower()),
            # ... 更多特徵
        ]
        # 填充到 20 維
        features.extend([0] * (20 - len(features)))
        return np.array(features[:20], dtype=np.float32)

    def _extract_history_features(self, context: dict) -> np.ndarray:
        """提取歷史特徵"""
        history = context.get("query_history", [])
        features = [
            len(history),  # 歷史查詢數
            context.get("avg_satisfaction", 0.5),  # 平均滿意度
            context.get("last_strategy_success", 0.5),  # 上次策略成功率
            context.get("time_since_last", 0),  # 距上次查詢時間
            # ... 更多特徵
        ]
        features.extend([0] * (10 - len(features)))
        return np.array(features[:10], dtype=np.float32)

    def _extract_context_features(self, context: dict) -> np.ndarray:
        """提取上下文特徵"""
        features = [
            context.get("user_expertise", 0.5),  # 用戶專業度
            context.get("time_of_day", 12) / 24.0,  # 時段標準化
            context.get("session_length", 0),  # 會話長度
            context.get("device_type", 0),  # 設備類型
            # ... 更多特徵
        ]
        features.extend([0] * (10 - len(features)))
        return np.array(features[:10], dtype=np.float32)

    @property
    def state_dim(self) -> int:
        """狀態維度"""
        return self.embedding_dim + 20 + 10 + 10  # 1064


# ==================== Reward Model ====================


class RewardModel:
    """獎勵計算模型"""

    def __init__(self):
        self.weights = {"confidence": 0.4, "speed": 0.3, "satisfaction": 0.2, "diversity": 0.1}

    def calculate(
        self,
        confidence: float,
        processing_time: float,
        user_feedback: float | None = None,
        diversity_score: float = 0.5,
    ) -> float:
        """
        計算獎勵

        Args:
            confidence: 置信度分數 (0-1)
            processing_time: 處理時間（秒）
            user_feedback: 用戶反饋 (0-1)，可選
            diversity_score: 多樣性分數 (0-1)

        Returns:
            reward: 獎勵值 (-1 到 1)
        """

        # 1. 置信度分數
        confidence_reward = confidence

        # 2. 速度分數（5秒內完成為最佳）
        max_acceptable_time = 5.0
        speed_reward = max(0, 1 - (processing_time / max_acceptable_time))

        # 3. 用戶滿意度
        if user_feedback is not None:
            satisfaction_reward = user_feedback
        else:
            # 啟發式估計
            satisfaction_reward = (confidence + speed_reward) / 2

        # 4. 多樣性獎勵
        diversity_reward = diversity_score

        # 5. 加權計算
        reward = (
            self.weights["confidence"] * confidence_reward
            + self.weights["speed"] * speed_reward
            + self.weights["satisfaction"] * satisfaction_reward
            + self.weights["diversity"] * diversity_reward
        )

        # 6. 應用懲罰
        if processing_time > 10.0:
            reward -= 0.5  # 超時懲罰
        if confidence < 0.3:
            reward -= 0.3  # 低置信度懲罰

        # 7. 標準化到 [-1, 1]
        reward = np.clip(reward, -1, 1)

        return reward


# ==================== RL Agent ====================


class RLAgenticRAG:
    """基於 DQN 的強化學習 Agentic RAG"""

    def __init__(
        self,
        state_dim: int = 1064,
        action_dim: int = 10,
        learning_rate: float = 0.0001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.995,
        buffer_capacity: int = 100000,
        batch_size: int = 64,
        target_update_freq: int = 1000,
    ):

        logger.info("🤖 初始化 RL-Agentic RAG...")

        # 設備
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"使用設備: {self.device}")

        # 狀態和動作空間
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Q 網絡
        self.q_network = QNetwork(state_dim, action_dim).to(self.device)
        self.target_network = QNetwork(state_dim, action_dim).to(self.device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        # 優化器
        self.optimizer = torch.optim.Adam(self.q_network.parameters(), lr=learning_rate)

        # 經驗回放
        self.replay_buffer = ReplayBuffer(capacity=buffer_capacity)

        # 超參數
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_min = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq

        # 組件
        self.state_encoder = StateEncoder()
        self.reward_model = RewardModel()

        # 訓練狀態
        self.is_training = False
        self.training_steps = 0
        self.episode = 0

        # 動作到策略的映射
        self.action_to_strategy = {
            0: "vector_rag",
            1: "graph_rag",
            2: "hybrid_rag",
            3: "advanced_rag",
            4: "agentic_rag",
            5: "self_rag",
            6: "adaptive_rag",
            7: "multimodal_rag",
            8: "dynamic_weight_0.3",
            9: "dynamic_weight_0.7",
        }

        # 統計信息
        self.stats = {
            "total_queries": 0,
            "action_counts": {i: 0 for i in range(action_dim)},
            "average_rewards": [],
            "average_losses": [],
        }

        logger.info("✅ RL-Agentic RAG 初始化完成")

    def select_action(self, state: np.ndarray, training: bool = False) -> int:
        """
        選擇動作（ε-greedy 策略）

        Args:
            state: 狀態向量
            training: 是否處於訓練模式

        Returns:
            action: 動作索引
        """
        # ε-greedy 探索
        if training and np.random.random() < self.epsilon:
            # 探索：隨機選擇
            action = np.random.randint(0, self.action_dim)
            logger.debug(f"🎲 探索模式：隨機選擇動作 {action}")
        else:
            # 利用：選擇最優動作
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.q_network(state_tensor)
                action = q_values.argmax().item()
                logger.debug(f"🎯 利用模式：選擇最優動作 {action} (Q={q_values[0][action]:.4f})")

        # 統計
        self.stats["action_counts"][action] += 1

        return action

    def train_step(self) -> float | None:
        """
        執行一步訓練

        Returns:
            loss: 訓練損失，如果緩衝區不足則返回 None
        """
        if len(self.replay_buffer) < self.batch_size:
            return None

        # 從經驗池採樣
        experiences = self.replay_buffer.sample(self.batch_size)

        # 轉換為張量
        states = torch.FloatTensor(np.array([exp.state for exp in experiences])).to(self.device)

        actions = torch.LongTensor([exp.action for exp in experiences]).to(self.device)

        rewards = torch.FloatTensor([exp.reward for exp in experiences]).to(self.device)

        next_states = torch.FloatTensor(np.array([exp.next_state for exp in experiences])).to(
            self.device
        )

        dones = torch.FloatTensor([exp.done for exp in experiences]).to(self.device)

        # 計算當前 Q 值
        current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1))

        # 計算目標 Q 值（雙 DQN）
        with torch.no_grad():
            # 使用當前網絡選擇動作
            next_actions = self.q_network(next_states).argmax(1, keepdim=True)
            # 使用目標網絡評估 Q 值
            next_q_values = self.target_network(next_states).gather(1, next_actions)
            target_q_values = (
                rewards.unsqueeze(1) + (1 - dones.unsqueeze(1)) * self.gamma * next_q_values
            )

        # 計算損失
        loss = F.mse_loss(current_q_values, target_q_values)

        # 反向傳播
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 1.0)
        self.optimizer.step()

        # 更新探索率
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        # 更新目標網絡
        self.training_steps += 1
        if self.training_steps % self.target_update_freq == 0:
            self.update_target_network()
            logger.info(f"🔄 目標網絡已更新 (step {self.training_steps})")

        return loss.item()

    def update_target_network(self):
        """更新目標網絡"""
        self.target_network.load_state_dict(self.q_network.state_dict())

    async def query(self, query_text: str, context: dict = None) -> dict[str, Any]:
        """
        執行查詢

        Args:
            query_text: 查詢文本
            context: 上下文信息

        Returns:
            result: 查詢結果
        """
        if context is None:
            context = {}

        # 1. 編碼狀態
        rl_state = self.state_encoder.encode(query_text, context)
        state_vector = rl_state.to_vector()

        # 2. 選擇動作（策略）
        action = self.select_action(state_vector, training=self.is_training)
        strategy_name = self.action_to_strategy[action]

        logger.info(f"📊 查詢: {query_text[:50]}...")
        logger.info(f"🎯 選擇策略: {strategy_name} (action={action})")

        # 3. 執行 RAG 查詢（這裡需要調用現有的 RAG 系統）
        start_time = time.time()
        rag_result = await self._execute_rag_strategy(strategy_name, query_text, context)
        processing_time = time.time() - start_time

        # 4. 計算獎勵
        reward = self.reward_model.calculate(
            confidence=rag_result.get("confidence_score", 0.5),
            processing_time=processing_time,
            user_feedback=context.get("user_feedback"),
            diversity_score=self._calculate_diversity(action, context),
        )

        logger.info(f"🎁 獎勵: {reward:.4f}")

        # 5. 存儲經驗（如果處於訓練模式）
        if self.is_training:
            # 下一個狀態（這裡簡化為當前狀態）
            next_state = state_vector
            done = True  # 單步交互

            experience = Experience(
                state=state_vector, action=action, reward=reward, next_state=next_state, done=done
            )
            self.replay_buffer.push(experience)

            # 訓練
            loss = self.train_step()
            if loss is not None:
                self.stats["average_losses"].append(loss)
                logger.debug(f"📉 Loss: {loss:.6f}, Epsilon: {self.epsilon:.4f}")

        # 6. 統計
        self.stats["total_queries"] += 1
        self.stats["average_rewards"].append(reward)

        # 7. 返回結果
        result = {
            "query": query_text,
            "strategy": strategy_name,
            "action": action,
            "reward": reward,
            "processing_time": processing_time,
            "rl_metadata": {
                "epsilon": self.epsilon,
                "training_steps": self.training_steps,
                "q_network_output": None,  # 可選：返回 Q 值
            },
            **rag_result,  # 包含 RAG 系統的返回結果
        }

        return result

    async def _execute_rag_strategy(self, strategy: str, query: str, context: dict) -> dict:
        """
        執行 RAG 策略（需要與現有系統集成）

        這裡是一個模擬實現，實際應該調用您現有的 RAG 系統
        """
        # TODO: 集成到現有的 RAG 系統
        # 例如：
        # from langchain_rag.integrated_rag_optimizer import IntegratedRAGOptimizer
        # optimizer = IntegratedRAGOptimizer()
        # result = await optimizer.query(query, strategy=strategy)

        # 模擬結果
        import asyncio

        await asyncio.sleep(0.1)  # 模擬處理時間

        return {
            "answer": f"這是使用 {strategy} 策略的回答",
            "sources": [],
            "confidence_score": 0.8,
            "metadata": {},
        }

    def _calculate_diversity(self, action: int, context: dict) -> float:
        """計算多樣性分數"""
        recent_actions = context.get("recent_actions", [])
        if len(recent_actions) == 0:
            return 0.5

        # 計算最近動作的唯一性
        unique_ratio = len(set(recent_actions)) / len(recent_actions)
        return unique_ratio

    def save(self, filepath: str):
        """保存模型"""
        torch.save(
            {
                "q_network_state_dict": self.q_network.state_dict(),
                "target_network_state_dict": self.target_network.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "training_steps": self.training_steps,
                "stats": self.stats,
            },
            filepath,
        )
        logger.info(f"💾 模型已保存到: {filepath}")

    def load(self, filepath: str):
        """載入模型"""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.q_network.load_state_dict(checkpoint["q_network_state_dict"])
        self.target_network.load_state_dict(checkpoint["target_network_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.epsilon = checkpoint["epsilon"]
        self.training_steps = checkpoint["training_steps"]
        self.stats = checkpoint["stats"]
        logger.info(f"📂 模型已載入: {filepath}")

    def get_stats(self) -> dict:
        """獲取統計信息"""
        return {
            "total_queries": self.stats["total_queries"],
            "training_steps": self.training_steps,
            "epsilon": self.epsilon,
            "action_distribution": {
                self.action_to_strategy[k]: v for k, v in self.stats["action_counts"].items()
            },
            "average_reward": np.mean(self.stats["average_rewards"][-100:])
            if self.stats["average_rewards"]
            else 0,
            "average_loss": np.mean(self.stats["average_losses"][-100:])
            if self.stats["average_losses"]
            else 0,
        }


# ==================== 測試代碼 ====================


async def test_rl_agent():
    """測試 RL Agent"""
    print("🧪 測試 RL-Agentic RAG")
    print("=" * 60)

    # 初始化
    agent = RLAgenticRAG()
    agent.is_training = True

    # 測試查詢
    test_queries = [
        "介紹文藝復興時期的藝術特色",
        "達文西和米開朗基羅的比較",
        "什麼是印象派藝術？",
        "分析巴洛克藝術的風格演變",
        "梵谷的向日葵有什麼特別之處？",
    ]

    # 執行多個 episode
    for episode in range(3):
        print(f"\n📊 Episode {episode + 1}")
        print("-" * 60)

        episode_rewards = []

        for query in test_queries:
            context = {"query_history": [], "user_expertise": 0.5, "recent_actions": []}

            result = await agent.query(query, context)

            print(f"\n查詢: {query}")
            print(f"策略: {result['strategy']}")
            print(f"獎勵: {result['reward']:.4f}")
            print(f"時間: {result['processing_time']:.4f}s")

            episode_rewards.append(result["reward"])

        avg_reward = np.mean(episode_rewards)
        print(f"\n📈 Episode {episode + 1} 平均獎勵: {avg_reward:.4f}")
        print(f"🎲 當前 Epsilon: {agent.epsilon:.4f}")

    # 統計信息
    print("\n" + "=" * 60)
    print("📊 最終統計")
    print("=" * 60)
    stats = agent.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # 保存模型
    agent.save("models/rl_agent_test.pt")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_rl_agent())
