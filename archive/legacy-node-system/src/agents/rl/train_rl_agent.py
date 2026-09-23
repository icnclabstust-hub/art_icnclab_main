#!/usr/bin/env python3
"""
RL Agent 訓練腳本
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from rl_agentic_rag import RLAgenticRAG
from torch.utils.tensorboard import SummaryWriter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RLTrainer:
    """RL 訓練器"""

    def __init__(
        self,
        agent: RLAgenticRAG,
        training_data_path: str,
        save_dir: str = "models/rl",
        log_dir: str = "runs/rl_training",
    ):

        self.agent = agent
        self.training_data_path = training_data_path
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # TensorBoard
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.writer = SummaryWriter(f"{log_dir}/{timestamp}")

        # 訓練數據
        self.training_queries = self._load_training_data()

        logger.info("✅ 訓練器初始化完成")
        logger.info(f"📚 載入 {len(self.training_queries)} 條訓練數據")

    def _load_training_data(self) -> list[dict]:
        """載入訓練數據"""
        try:
            with open(self.training_data_path, encoding="utf-8") as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            logger.warning(f"⚠️ 訓練數據文件不存在: {self.training_data_path}")
            logger.info("📝 生成模擬訓練數據...")
            return self._generate_mock_data()

    def _generate_mock_data(self) -> list[dict]:
        """生成模擬訓練數據"""
        mock_queries = [
            {"query": "介紹文藝復興時期的藝術特色", "context": {"user_expertise": 0.5}},
            {"query": "達文西和米開朗基羅的比較", "context": {"user_expertise": 0.7}},
            {"query": "什麼是印象派藝術？", "context": {"user_expertise": 0.3}},
            {"query": "分析巴洛克藝術的風格演變", "context": {"user_expertise": 0.8}},
            {"query": "梵谷的向日葵有什麼特別之處？", "context": {"user_expertise": 0.6}},
            {"query": "畢卡索受哪些藝術家影響？", "context": {"user_expertise": 0.7}},
            {"query": "蒙娜麗莎的微笑為何神秘？", "context": {"user_expertise": 0.5}},
            {"query": "現代藝術和當代藝術的區別", "context": {"user_expertise": 0.9}},
            {"query": "如何欣賞抽象畫？", "context": {"user_expertise": 0.4}},
            {"query": "洛可可風格的特點是什麼？", "context": {"user_expertise": 0.6}},
        ]
        return mock_queries * 100  # 重複以增加數據量

    async def train(
        self,
        num_episodes: int = 100,
        max_steps_per_episode: int = 50,
        save_interval: int = 10,
        eval_interval: int = 5,
    ):
        """
        訓練 RL Agent

        Args:
            num_episodes: 訓練回合數
            max_steps_per_episode: 每回合最大步數
            save_interval: 保存間隔（回合數）
            eval_interval: 評估間隔（回合數）
        """
        logger.info("🚀 開始訓練 RL Agent")
        logger.info("📊 訓練配置:")
        logger.info(f"  - Episodes: {num_episodes}")
        logger.info(f"  - Steps per Episode: {max_steps_per_episode}")
        logger.info(f"  - Save Interval: {save_interval}")
        logger.info(f"  - Eval Interval: {eval_interval}")

        self.agent.is_training = True
        global_step = 0

        for episode in range(num_episodes):
            episode_start_time = time.time()
            episode_rewards = []
            episode_losses = []

            # Episode 內的訓練
            for step in range(max_steps_per_episode):
                # 隨機選擇查詢
                query_data = np.random.choice(self.training_queries)
                query_text = query_data["query"]
                context = query_data.get("context", {})

                # 添加歷史動作
                context["recent_actions"] = [
                    self.agent.stats["action_counts"].get(i, 0)
                    for i in range(self.agent.action_dim)
                ]

                # 執行查詢
                result = await self.agent.query(query_text, context)

                # 記錄指標
                reward = result["reward"]
                episode_rewards.append(reward)

                # 記錄損失（如果有訓練步驟）
                if self.agent.stats["average_losses"]:
                    loss = self.agent.stats["average_losses"][-1]
                    episode_losses.append(loss)

                global_step += 1

                # TensorBoard 記錄
                self.writer.add_scalar("Reward/step", reward, global_step)
                if episode_losses:
                    self.writer.add_scalar("Loss/step", episode_losses[-1], global_step)
                self.writer.add_scalar("Epsilon/step", self.agent.epsilon, global_step)

            # Episode 統計
            episode_time = time.time() - episode_start_time
            avg_reward = np.mean(episode_rewards)
            avg_loss = np.mean(episode_losses) if episode_losses else 0

            logger.info(f"\n{'=' * 60}")
            logger.info(f"📊 Episode {episode + 1}/{num_episodes}")
            logger.info(f"  平均獎勵: {avg_reward:.4f}")
            logger.info(f"  平均損失: {avg_loss:.6f}")
            logger.info(f"  Epsilon: {self.agent.epsilon:.4f}")
            logger.info(f"  耗時: {episode_time:.2f}s")
            logger.info(f"  訓練步數: {self.agent.training_steps}")

            # TensorBoard 記錄
            self.writer.add_scalar("Reward/episode", avg_reward, episode)
            self.writer.add_scalar("Loss/episode", avg_loss, episode)
            self.writer.add_scalar("Epsilon/episode", self.agent.epsilon, episode)
            self.writer.add_scalar("Time/episode", episode_time, episode)

            # 動作分布
            action_dist = self.agent.stats["action_counts"]
            for action_id, count in action_dist.items():
                strategy_name = self.agent.action_to_strategy[action_id]
                self.writer.add_scalar(f"ActionCount/{strategy_name}", count, episode)

            # 定期評估
            if (episode + 1) % eval_interval == 0:
                await self._evaluate(episode + 1)

            # 定期保存
            if (episode + 1) % save_interval == 0:
                self._save_checkpoint(episode + 1)

        logger.info("\n" + "=" * 60)
        logger.info("🎉 訓練完成！")
        logger.info("=" * 60)

        # 保存最終模型
        final_path = self.save_dir / "rl_agent_final.pt"
        self.agent.save(str(final_path))

        # 關閉 TensorBoard
        self.writer.close()

        # 生成訓練報告
        self._generate_report()

    async def _evaluate(self, episode: int):
        """評估模型性能"""
        logger.info(f"\n🧪 評估模型 (Episode {episode})")

        # 暫時關閉訓練模式
        self.agent.is_training = False

        # 評估查詢
        eval_queries = self.training_queries[:20]  # 使用前 20 個查詢評估
        eval_rewards = []

        for query_data in eval_queries:
            result = await self.agent.query(query_data["query"], query_data.get("context", {}))
            eval_rewards.append(result["reward"])

        avg_eval_reward = np.mean(eval_rewards)
        logger.info(f"  評估平均獎勵: {avg_eval_reward:.4f}")

        # TensorBoard 記錄
        self.writer.add_scalar("Reward/eval", avg_eval_reward, episode)

        # 恢復訓練模式
        self.agent.is_training = True

    def _save_checkpoint(self, episode: int):
        """保存檢查點"""
        checkpoint_path = self.save_dir / f"rl_agent_episode_{episode}.pt"
        self.agent.save(str(checkpoint_path))
        logger.info(f"💾 檢查點已保存: {checkpoint_path}")

    def _generate_report(self):
        """生成訓練報告"""
        stats = self.agent.get_stats()

        report = {
            "training_completed": datetime.now().isoformat(),
            "total_queries": stats["total_queries"],
            "training_steps": stats["training_steps"],
            "final_epsilon": stats["epsilon"],
            "action_distribution": stats["action_distribution"],
            "final_average_reward": stats["average_reward"],
            "final_average_loss": stats["average_loss"],
        }

        report_path = self.save_dir / "training_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"\n📄 訓練報告已生成: {report_path}")
        logger.info(json.dumps(report, indent=2, ensure_ascii=False))


async def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="訓練 RL-Agentic RAG")
    parser.add_argument(
        "--data", type=str, default="data/training_queries.json", help="訓練數據路徑"
    )
    parser.add_argument("--episodes", type=int, default=100, help="訓練回合數")
    parser.add_argument("--steps", type=int, default=50, help="每回合步數")
    parser.add_argument("--save-dir", type=str, default="models/rl", help="模型保存目錄")
    parser.add_argument(
        "--log-dir", type=str, default="runs/rl_training", help="TensorBoard 日誌目錄"
    )

    args = parser.parse_args()

    # 初始化 Agent
    agent = RLAgenticRAG(
        state_dim=1064,
        action_dim=10,
        learning_rate=0.0001,
        gamma=0.99,
        epsilon_start=1.0,
        epsilon_end=0.05,
        epsilon_decay=0.995,
        buffer_capacity=100000,
        batch_size=64,
        target_update_freq=1000,
    )

    # 初始化訓練器
    trainer = RLTrainer(
        agent=agent, training_data_path=args.data, save_dir=args.save_dir, log_dir=args.log_dir
    )

    # 開始訓練
    await trainer.train(
        num_episodes=args.episodes,
        max_steps_per_episode=args.steps,
        save_interval=10,
        eval_interval=5,
    )


if __name__ == "__main__":
    asyncio.run(main())
