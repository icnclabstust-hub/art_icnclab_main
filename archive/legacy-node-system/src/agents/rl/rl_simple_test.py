#!/usr/bin/env python3
"""
RL-Agentic RAG 簡化測試版本
不依賴 PyTorch，使用純 Python 和 NumPy 演示核心概念
"""

import json
import logging
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """經驗元組"""

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class SimpleQNetwork:
    """簡化的 Q 網絡（使用線性模型代替神經網絡）"""

    def __init__(self, state_dim: int, action_dim: int):
        self.state_dim = state_dim
        self.action_dim = action_dim

        # 使用簡單的權重矩陣
        self.weights = np.random.randn(state_dim, action_dim) * 0.01
        self.bias = np.zeros(action_dim)

    def forward(self, state: np.ndarray) -> np.ndarray:
        """前向傳播"""
        return np.dot(state, self.weights) + self.bias

    def update(self, state: np.ndarray, action: int, td_error: float, lr: float):
        """簡單的梯度更新"""
        grad = np.outer(state, np.zeros(self.action_dim))
        grad[:, action] = state

        self.weights += lr * td_error * grad
        self.bias[action] += lr * td_error


class SimpleReplayBuffer:
    """簡化的經驗回放緩衝池"""

    def __init__(self, capacity: int = 1000):
        self.buffer = deque(maxlen=capacity)

    def push(self, experience: Experience):
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> list[Experience]:
        if len(self.buffer) < batch_size:
            return []
        return random.sample(list(self.buffer), batch_size)

    def __len__(self):
        return len(self.buffer)


class SimpleStateEncoder:
    """簡化的狀態編碼器"""

    def __init__(self):
        # 模擬的詞彙表
        self.vocab = {
            "藝術": 1,
            "文藝復興": 2,
            "達文西": 3,
            "米開朗基羅": 4,
            "印象派": 5,
            "梵谷": 6,
            "畢卡索": 7,
            "巴洛克": 8,
            "什麼": 10,
            "如何": 11,
            "為什麼": 12,
            "介紹": 13,
            "比較": 14,
            "分析": 15,
            "特色": 16,
            "風格": 17,
        }

    def encode(self, query: str, context: dict) -> np.ndarray:
        """簡化的編碼方法"""
        # 1. 基於詞彙的編碼 (20維)
        vocab_features = np.zeros(20)
        for word, idx in self.vocab.items():
            if word in query:
                vocab_features[idx] = 1.0

        # 2. 查詢特徵 (10維)
        query_features = np.array(
            [
                len(query.split()),  # 查詢長度
                len(query),  # 字符數
                int("?" in query),  # 是否有問號
                int("什麼" in query),
                int("如何" in query),
                int("為什麼" in query),
                int("藝術" in query),
                int("畫家" in query),
                context.get("user_expertise", 0.5),
                0.0,  # 填充
            ],
            dtype=np.float32,
        )

        # 合併特徵
        state = np.concatenate([vocab_features, query_features])
        return state

    @property
    def state_dim(self) -> int:
        return 30  # 20 + 10


class SimpleRewardModel:
    """簡化的獎勵模型"""

    def calculate(self, confidence: float, processing_time: float) -> float:
        """計算獎勵"""
        # 速度分數
        speed_score = max(0, 1 - (processing_time / 5.0))

        # 加權計算
        reward = 0.6 * confidence + 0.4 * speed_score

        # 懲罰
        if processing_time > 10.0:
            reward -= 0.5
        if confidence < 0.3:
            reward -= 0.3

        return np.clip(reward, -1, 1)


class SimpleRLAgent:
    """簡化的 RL Agent（使用 Q-learning 代替 DQN）"""

    def __init__(
        self,
        state_dim: int = 30,
        action_dim: int = 10,
        learning_rate: float = 0.01,
        gamma: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
    ):

        logger.info("🤖 初始化簡化版 RL Agent...")

        self.state_dim = state_dim
        self.action_dim = action_dim
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

        # Q 網絡
        self.q_network = SimpleQNetwork(state_dim, action_dim)

        # 經驗回放
        self.replay_buffer = SimpleReplayBuffer(capacity=1000)

        # 組件
        self.state_encoder = SimpleStateEncoder()
        self.reward_model = SimpleRewardModel()

        # 策略映射
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

        # 統計
        self.stats = {
            "total_queries": 0,
            "action_counts": {i: 0 for i in range(action_dim)},
            "rewards_history": [],
            "training_steps": 0,
        }

        logger.info("✅ 簡化版 RL Agent 初始化完成")

    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """ε-greedy 策略選擇動作"""
        if training and np.random.random() < self.epsilon:
            # 探索
            return np.random.randint(0, self.action_dim)
        else:
            # 利用
            q_values = self.q_network.forward(state)
            return np.argmax(q_values)

    def train_step(self, batch_size: int = 32):
        """訓練一步"""
        experiences = self.replay_buffer.sample(batch_size)
        if not experiences:
            return None

        total_loss = 0.0

        for exp in experiences:
            # 計算當前 Q 值
            q_values = self.q_network.forward(exp.state)
            current_q = q_values[exp.action]

            # 計算目標 Q 值
            next_q_values = self.q_network.forward(exp.next_state)
            next_q_max = np.max(next_q_values) if not exp.done else 0
            target_q = exp.reward + self.gamma * next_q_max

            # TD error
            td_error = target_q - current_q

            # 更新網絡
            self.q_network.update(exp.state, exp.action, td_error, self.learning_rate)

            total_loss += td_error**2

        # 更新 epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        self.stats["training_steps"] += 1

        return total_loss / len(experiences)

    def query(self, query_text: str, context: dict = None) -> dict[str, Any]:
        """執行查詢"""
        if context is None:
            context = {}

        # 1. 編碼狀態
        state = self.state_encoder.encode(query_text, context)

        # 2. 選擇動作
        action = self.select_action(state, training=True)
        strategy = self.action_to_strategy[action]

        logger.info(f"查詢: {query_text[:40]}...")
        logger.info(f"選擇策略: {strategy} (action={action})")

        # 3. 模擬執行（實際應調用真實的 RAG 系統）
        start_time = time.time()
        confidence = 0.7 + np.random.random() * 0.2  # 模擬置信度 0.7-0.9
        time.sleep(0.1)  # 模擬處理時間
        processing_time = time.time() - start_time

        # 4. 計算獎勵
        reward = self.reward_model.calculate(confidence, processing_time)

        logger.info(f"置信度: {confidence:.4f}, 時間: {processing_time:.4f}s")
        logger.info(f"獎勵: {reward:.4f}")

        # 5. 存儲經驗
        next_state = state  # 簡化版本
        done = True
        experience = Experience(state, action, reward, next_state, done)
        self.replay_buffer.push(experience)

        # 6. 訓練
        if len(self.replay_buffer) >= 32:
            loss = self.train_step(batch_size=32)
            if loss is not None:
                logger.debug(f"Loss: {loss:.6f}, Epsilon: {self.epsilon:.4f}")

        # 7. 統計
        self.stats["total_queries"] += 1
        self.stats["action_counts"][action] += 1
        self.stats["rewards_history"].append(reward)

        return {
            "query": query_text,
            "strategy": strategy,
            "action": action,
            "confidence": confidence,
            "reward": reward,
            "processing_time": processing_time,
            "epsilon": self.epsilon,
        }

    def get_stats(self) -> dict:
        """獲取統計信息"""
        recent_rewards = self.stats["rewards_history"][-100:]

        return {
            "total_queries": self.stats["total_queries"],
            "training_steps": self.stats["training_steps"],
            "epsilon": self.epsilon,
            "average_reward": np.mean(recent_rewards) if recent_rewards else 0,
            "action_distribution": {
                self.action_to_strategy[k]: v for k, v in self.stats["action_counts"].items()
            },
        }


def test_simple_rl_agent():
    """測試簡化版 RL Agent"""
    print("\n" + "=" * 70)
    print("🧪 測試簡化版 RL-Agentic RAG")
    print("=" * 70)

    # 初始化
    agent = SimpleRLAgent()

    # 測試查詢
    test_queries = [
        "介紹文藝復興時期的藝術特色",
        "達文西和米開朗基羅的比較",
        "什麼是印象派藝術？",
        "分析巴洛克藝術的風格演變",
        "梵谷的向日葵有什麼特別之處？",
        "畢卡索受哪些藝術家影響？",
        "蒙娜麗莎的微笑為何神秘？",
        "現代藝術和當代藝術的區別",
        "如何欣賞抽象畫？",
        "洛可可風格的特點是什麼？",
    ]

    # 執行多個 episode
    num_episodes = 3
    queries_per_episode = 10

    for episode in range(num_episodes):
        print(f"\n{'=' * 70}")
        print(f"📊 Episode {episode + 1}/{num_episodes}")
        print("=" * 70)

        episode_rewards = []

        for i in range(queries_per_episode):
            query = test_queries[i % len(test_queries)]

            context = {
                "user_expertise": 0.5 + np.random.random() * 0.3,
            }

            print(f"\n--- 查詢 {i + 1}/{queries_per_episode} ---")
            result = agent.query(query, context)

            episode_rewards.append(result["reward"])

            # 顯示重要信息
            print(f"策略: {result['strategy']}")
            print(f"獎勵: {result['reward']:.4f}")
            print(f"Epsilon: {result['epsilon']:.4f}")

        # Episode 統計
        avg_reward = np.mean(episode_rewards)
        print(f"\n📈 Episode {episode + 1} 平均獎勵: {avg_reward:.4f}")
        print(f"🎲 當前探索率: {agent.epsilon:.4f}")

    # 最終統計
    print("\n" + "=" * 70)
    print("📊 最終統計")
    print("=" * 70)

    stats = agent.get_stats()
    print(f"\n總查詢數: {stats['total_queries']}")
    print(f"訓練步數: {stats['training_steps']}")
    print(f"平均獎勵: {stats['average_reward']:.4f}")
    print(f"最終 Epsilon: {stats['epsilon']:.4f}")

    print("\n策略使用分布:")
    for strategy, count in sorted(
        stats["action_distribution"].items(), key=lambda x: x[1], reverse=True
    ):
        percentage = (count / stats["total_queries"]) * 100
        print(f"  {strategy:20s}: {count:3d} 次 ({percentage:5.1f}%)")

    # 繪製獎勵趨勢
    print("\n獎勵趨勢 (最近20次):")
    recent_rewards = agent.stats["rewards_history"][-20:]
    for i, reward in enumerate(recent_rewards, 1):
        bar_length = int(reward * 50) if reward > 0 else 0
        bar = "█" * bar_length
        print(f"  {i:2d}. {bar} {reward:.3f}")

    print("\n" + "=" * 70)
    print("✅ 測試完成！")
    print("=" * 70)

    # 保存結果
    results = {
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "final_stats": stats,
        "rewards_history": [float(r) for r in agent.stats["rewards_history"]],
        "notes": "這是使用純 Python/NumPy 的簡化版本，演示 RL 概念",
    }

    with open("rl_simple_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n📄 測試結果已保存到: rl_simple_test_results.json")


if __name__ == "__main__":
    test_simple_rl_agent()
