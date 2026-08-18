#!/usr/bin/env python3
"""
藝術史多模態RAG實驗套件
完整的實驗設計和執行框架
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# 導入MCP系統
from mcp_agent_system import MCPAgentSystem


@dataclass
class ExperimentConfig:
    """實驗配置"""

    name: str
    rag_framework: str
    llm_model: str
    data_modality: str
    test_dataset: str
    parameters: dict[str, Any]


@dataclass
class ExperimentResult:
    """實驗結果"""

    config: ExperimentConfig
    metrics: dict[str, float]
    execution_time: float
    success: bool
    error_message: str | None = None
    detailed_results: dict[str, Any] = None


class ArtHistoryDataset:
    """藝術史數據集管理"""

    def __init__(self, data_dir: str = "data/experiments"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("art_history_dataset")

    def create_baseline_dataset(self) -> dict[str, list[dict]]:
        """創建基準測試數據集"""

        # 西方藝術史問題集
        western_art_questions = [
            {
                "id": "west_001",
                "question": "米開朗基羅的《大衛》創作於哪個時期？有什麼藝術特點？",
                "category": "renaissance",
                "difficulty": "medium",
                "expected_keywords": ["文藝復興", "大理石", "人體比例", "佛羅倫薩", "1501-1504"],
                "reference_answer": "米開朗基羅的《大衛》創作於1501-1504年的文藝復興盛期。該作品體現了完美的人體比例，展現了理想化的男性美，雕工精湛，細節豐富，是文藝復興雕塑藝術的典範。",
            },
            {
                "id": "west_002",
                "question": "莫內的《睡蓮》系列體現了印象派的哪些特徵？",
                "category": "impressionism",
                "difficulty": "medium",
                "expected_keywords": ["光影變化", "色彩", "筆觸", "戶外寫生", "瞬間印象"],
                "reference_answer": "莫內的《睡蓮》系列典型地體現了印象派的核心特徵：注重光線的變化效果，運用鮮明的色彩對比，筆觸自由奔放，追求捕捉瞬間的視覺印象，並且採用戶外直接寫生的方式創作。",
            },
            {
                "id": "west_003",
                "question": "畢卡索的立體主義分為哪幾個階段？",
                "category": "modern",
                "difficulty": "hard",
                "expected_keywords": ["分析立體主義", "綜合立體主義", "幾何形體", "多角度", "拼貼"],
                "reference_answer": "畢卡索的立體主義主要分為兩個階段：分析立體主義（1907-1912）將對象分解為幾何形體，從多個角度同時呈現；綜合立體主義（1912-1920）開始運用拼貼技法，重新組合各種材料和形式。",
            },
        ]

        # 東方藝術史問題集
        eastern_art_questions = [
            {
                "id": "east_001",
                "question": "宋代山水畫三家（李成、關仝、范寬）的風格特點是什麼？",
                "category": "chinese_painting",
                "difficulty": "hard",
                "expected_keywords": ["李成", "關仝", "范寬", "筆法", "構圖", "意境"],
                "reference_answer": "宋代山水畫三家各有特色：李成善畫寒林平遠，筆法清潤；關仝擅長描繪關陝山川，筆力雄健；范寬以雄渾厚重著稱，代表作《溪山行旅圖》展現北方山川的壯闊氣勢。",
            },
            {
                "id": "east_002",
                "question": "浮世繪對歐洲印象派的影響體現在哪些方面？",
                "category": "japanese_art",
                "difficulty": "medium",
                "expected_keywords": ["構圖", "色彩", "線條", "平面化", "裝飾性"],
                "reference_answer": "浮世繪對歐洲印象派的影響主要體現在：大膽的構圖方式，鮮豔的色彩運用，簡潔有力的線條表現，平面化的空間處理，以及強烈的裝飾性特徵，這些都深刻影響了印象派畫家的創作理念。",
            },
        ]

        # 跨文化比較問題集
        comparative_questions = [
            {
                "id": "comp_001",
                "question": "比較東西方雕塑在材料和技法上的異同",
                "category": "comparative",
                "difficulty": "hard",
                "expected_keywords": ["材料", "技法", "文化差異", "表現形式"],
                "reference_answer": "東方雕塑多用木材、青銅，技法注重神韻表達；西方雕塑偏愛大理石、青銅，追求形體的寫實和理想化。兩者都體現各自的文化審美特徵和哲學思想。",
            }
        ]

        dataset = {
            "baseline_300": {
                "western_art": western_art_questions * 34,  # 擴展到100題
                "eastern_art": eastern_art_questions * 50,  # 擴展到100題
                "comparative": comparative_questions * 100,  # 擴展到100題
            }
        }

        # 保存數據集
        dataset_path = self.data_dir / "baseline_dataset.json"
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        self.logger.info(f"基準數據集已保存到: {dataset_path}")
        return dataset

    def create_multimodal_dataset(self) -> dict[str, list[dict]]:
        """創建多模態測試數據集"""

        multimodal_data = {
            "text_image_pairs": [
                {
                    "id": "multi_001",
                    "question": "分析這幅畫的筆觸特點和色彩運用",
                    "image_path": "images/monet_impression_sunrise.jpg",
                    "image_description": "莫內《印象·日出》，展現了印象派的典型特徵",
                    "category": "painting_analysis",
                    "expected_analysis": "該畫運用了印象派典型的筆觸技法，色彩豐富...",
                },
                {
                    "id": "multi_002",
                    "question": "描述雕塑的姿態表達和藝術意義",
                    "image_path": "images/rodin_thinker.jpg",
                    "image_description": "羅丹《思想者》雕塑",
                    "category": "sculpture_analysis",
                    "expected_analysis": "雕塑呈現深思的姿態，體現了人類理性思考的力量...",
                },
            ],
            "audio_text_pairs": [
                {
                    "id": "audio_001",
                    "question": "根據講座內容分析藝術品特點",
                    "audio_path": "audio/art_lecture_01.mp3",
                    "transcript": "今天我們來討論文藝復興時期的雕塑藝術...",
                    "category": "lecture_analysis",
                    "expected_summary": "講座介紹了文藝復興雕塑的特點...",
                }
            ],
        }

        # 保存多模態數據集
        dataset_path = self.data_dir / "multimodal_dataset.json"
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(multimodal_data, f, ensure_ascii=False, indent=2)

        return multimodal_data


class ExperimentEvaluator:
    """實驗評估器"""

    def __init__(self):
        self.logger = logging.getLogger("experiment_evaluator")

    def evaluate_response(self, question: dict[str, Any], response: str) -> dict[str, float]:
        """評估回答質量"""
        metrics = {}

        # 1. 關鍵詞匹配度
        expected_keywords = question.get("expected_keywords", [])
        keyword_matches = sum(1 for keyword in expected_keywords if keyword in response)
        metrics["keyword_coverage"] = (
            keyword_matches / len(expected_keywords) if expected_keywords else 0.0
        )

        # 2. 長度合理性
        response_length = len(response)
        if 50 <= response_length <= 500:
            metrics["length_appropriateness"] = 1.0
        elif response_length < 50:
            metrics["length_appropriateness"] = response_length / 50
        else:
            metrics["length_appropriateness"] = max(0.5, 1.0 - (response_length - 500) / 1000)

        # 3. 結構完整性（簡單檢查是否有句號結尾等）
        metrics["structural_completeness"] = (
            1.0 if response.endswith(("。", ".", "！", "!")) else 0.7
        )

        # 4. 綜合評分
        metrics["overall_score"] = (
            metrics["keyword_coverage"] * 0.5
            + metrics["length_appropriateness"] * 0.3
            + metrics["structural_completeness"] * 0.2
        )

        return metrics


class ArtHistoryExperimentSuite:
    """藝術史實驗套件"""

    def __init__(self):
        self.logger = logging.getLogger("art_history_experiments")
        self.mcp_system = MCPAgentSystem()
        self.dataset = ArtHistoryDataset()
        self.evaluator = ExperimentEvaluator()

        # 實驗配置
        self.rag_frameworks = [
            "vector_rag",
            "advanced_rag",
            "graph_rag",
            "multimodal_rag",
            "self_reflection_rag",
        ]

        self.llm_models = [
            "openai",  # GPT-4
            "anthropic",  # Claude-3
            "ollama",  # 開源LLM
            "specialized",  # 專業化模型
        ]

        self.experiment_results = []

    async def initialize_system(self):
        """初始化實驗系統"""
        try:
            self.logger.info("正在初始化MCP實驗系統...")
            await self.mcp_system.start_system()
            self.logger.info("MCP系統初始化完成")

            # 創建數據集
            self.logger.info("正在準備實驗數據集...")
            self.baseline_dataset = self.dataset.create_baseline_dataset()
            self.multimodal_dataset = self.dataset.create_multimodal_dataset()
            self.logger.info("數據集準備完成")

        except Exception as e:
            self.logger.error(f"系統初始化失敗: {str(e)}")
            raise

    async def run_single_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """執行單個實驗"""
        start_time = time.time()

        try:
            self.logger.info(f"開始實驗: {config.name}")

            # 獲取測試數據
            if config.test_dataset == "baseline_300":
                test_questions = []
                for category_questions in self.baseline_dataset["baseline_300"].values():
                    test_questions.extend(category_questions[:5])  # 每類取5個問題測試
            else:
                test_questions = []

            results = []

            # 對每個問題執行RAG查詢
            for question in test_questions:
                try:
                    # 使用MCP系統執行查詢
                    rag_result = await self.mcp_system.run_mcp_rag_experiment(
                        query=question["question"], vector_db="chromadb", llm_model=config.llm_model
                    )

                    if rag_result["success"]:
                        # 評估答案質量
                        metrics = self.evaluator.evaluate_response(question, rag_result["answer"])

                        results.append(
                            {
                                "question_id": question["id"],
                                "category": question["category"],
                                "metrics": metrics,
                                "response": rag_result["answer"],
                                "response_time": rag_result["metadata"]["total_time"],
                            }
                        )

                    else:
                        # 記錄失敗
                        results.append(
                            {
                                "question_id": question["id"],
                                "category": question["category"],
                                "error": rag_result["error"],
                                "metrics": {"overall_score": 0.0},
                            }
                        )

                except Exception as e:
                    self.logger.error(f"問題 {question['id']} 執行失敗: {str(e)}")
                    results.append(
                        {
                            "question_id": question["id"],
                            "error": str(e),
                            "metrics": {"overall_score": 0.0},
                        }
                    )

            # 計算整體指標
            execution_time = time.time() - start_time

            if results:
                avg_score = sum(r["metrics"]["overall_score"] for r in results) / len(results)
                avg_response_time = sum(r.get("response_time", 0) for r in results) / len(results)
                success_rate = sum(1 for r in results if "error" not in r) / len(results)

                metrics = {
                    "overall_accuracy": avg_score,
                    "average_response_time": avg_response_time,
                    "success_rate": success_rate,
                    "total_questions": len(results),
                }
            else:
                metrics = {
                    "overall_accuracy": 0.0,
                    "average_response_time": 0.0,
                    "success_rate": 0.0,
                    "total_questions": 0,
                }

            return ExperimentResult(
                config=config,
                metrics=metrics,
                execution_time=execution_time,
                success=True,
                detailed_results=results,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"實驗 {config.name} 失敗: {str(e)}")

            return ExperimentResult(
                config=config,
                metrics={},
                execution_time=execution_time,
                success=False,
                error_message=str(e),
            )

    async def run_phase1_baseline_experiments(self) -> list[ExperimentResult]:
        """執行Phase 1: 基準性能測試"""
        self.logger.info("🔬 開始執行Phase 1: 基準性能測試")

        phase1_results = []

        # 生成實驗配置矩陣
        experiment_configs = []
        for rag_framework in self.rag_frameworks[:2]:  # 先測試前兩個框架
            for llm_model in self.llm_models[:2]:  # 先測試前兩個模型
                config = ExperimentConfig(
                    name=f"baseline_{rag_framework}_{llm_model}",
                    rag_framework=rag_framework,
                    llm_model=llm_model,
                    data_modality="text_only",
                    test_dataset="baseline_300",
                    parameters={"top_k": 5, "temperature": 0.3},
                )
                experiment_configs.append(config)

        self.logger.info(f"將執行 {len(experiment_configs)} 個基準實驗")

        # 執行實驗
        for i, config in enumerate(experiment_configs):
            self.logger.info(f"進度: {i + 1}/{len(experiment_configs)} - {config.name}")

            result = await self.run_single_experiment(config)
            phase1_results.append(result)

            # 記錄結果
            if result.success:
                self.logger.info(
                    f"✅ {config.name} - 準確率: {result.metrics['overall_accuracy']:.2%}"
                )
            else:
                self.logger.error(f"❌ {config.name} - 失敗: {result.error_message}")

            # 短暫休息避免系統過載
            await asyncio.sleep(1)

        return phase1_results

    async def run_phase2_multimodal_experiments(
        self, phase1_results: list[ExperimentResult]
    ) -> list[ExperimentResult]:
        """執行Phase 2: 多模態能力測試"""
        self.logger.info("🔬 開始執行Phase 2: 多模態能力測試")

        # 基於Phase 1結果選擇最佳組合
        successful_results = [r for r in phase1_results if r.success]
        if not successful_results:
            self.logger.error("Phase 1 沒有成功的實驗，跳過 Phase 2")
            return []

        # 選擇準確率最高的配置
        best_result = max(successful_results, key=lambda r: r.metrics.get("overall_accuracy", 0))
        best_config = best_result.config

        self.logger.info(
            f"選擇最佳配置進行多模態測試: {best_config.rag_framework} + {best_config.llm_model}"
        )

        phase2_results = []

        # 多模態測試配置
        modality_configs = [
            {"modality": "text_only", "description": "純文本模式"},
            {"modality": "text_image", "description": "文本+圖像模式"},
        ]

        for modality_config in modality_configs:
            config = ExperimentConfig(
                name=f"multimodal_{modality_config['modality']}_{best_config.rag_framework}_{best_config.llm_model}",
                rag_framework=best_config.rag_framework,
                llm_model=best_config.llm_model,
                data_modality=modality_config["modality"],
                test_dataset="multimodal_200",
                parameters=best_config.parameters,
            )

            self.logger.info(f"執行多模態實驗: {modality_config['description']}")
            result = await self.run_single_experiment(config)
            phase2_results.append(result)

        return phase2_results

    def generate_experiment_report(
        self, all_results: list[list[ExperimentResult]]
    ) -> dict[str, Any]:
        """生成實驗報告"""
        report = {
            "experiment_summary": {
                "total_experiments": sum(len(phase_results) for phase_results in all_results),
                "successful_experiments": sum(
                    sum(1 for r in phase_results if r.success) for phase_results in all_results
                ),
                "experiment_date": datetime.now().isoformat(),
                "phases_completed": len(all_results),
            },
            "phase_results": [],
            "best_configurations": [],
            "recommendations": [],
        }

        # 分析各階段結果
        for i, phase_results in enumerate(all_results):
            phase_name = f"Phase {i + 1}"
            successful_results = [r for r in phase_results if r.success]

            if successful_results:
                avg_accuracy = sum(
                    r.metrics.get("overall_accuracy", 0) for r in successful_results
                ) / len(successful_results)
                avg_response_time = sum(
                    r.metrics.get("average_response_time", 0) for r in successful_results
                ) / len(successful_results)

                best_result = max(
                    successful_results, key=lambda r: r.metrics.get("overall_accuracy", 0)
                )

                phase_report = {
                    "phase": phase_name,
                    "total_experiments": len(phase_results),
                    "successful_experiments": len(successful_results),
                    "average_accuracy": avg_accuracy,
                    "average_response_time": avg_response_time,
                    "best_configuration": {
                        "rag_framework": best_result.config.rag_framework,
                        "llm_model": best_result.config.llm_model,
                        "accuracy": best_result.metrics.get("overall_accuracy", 0),
                    },
                }

                report["phase_results"].append(phase_report)
                report["best_configurations"].append(best_result.config)

        # 生成建議
        if report["best_configurations"]:
            best_overall = max(
                [r for phase_results in all_results for r in phase_results if r.success],
                key=lambda r: r.metrics.get("overall_accuracy", 0),
                default=None,
            )

            if best_overall:
                report["recommendations"] = [
                    f"推薦RAG框架: {best_overall.config.rag_framework}",
                    f"推薦LLM模型: {best_overall.config.llm_model}",
                    f"預期準確率: {best_overall.metrics.get('overall_accuracy', 0):.2%}",
                    f"平均響應時間: {best_overall.metrics.get('average_response_time', 0):.2f}秒",
                ]

        return report

    async def run_quick_demo_experiment(self) -> dict[str, Any]:
        """運行快速演示實驗"""
        self.logger.info("🚀 開始運行快速演示實驗...")

        try:
            # 初始化系統
            await self.initialize_system()

            # 運行簡化版實驗
            phase1_results = await self.run_phase1_baseline_experiments()

            # 生成報告
            report = self.generate_experiment_report([phase1_results])

            self.logger.info("✅ 快速演示實驗完成")
            return report

        except Exception as e:
            self.logger.error(f"❌ 演示實驗失敗: {str(e)}")
            return {"error": str(e)}
        finally:
            # 清理系統
            if hasattr(self, "mcp_system"):
                await self.mcp_system.shutdown_system()


async def main():
    """主程序 - 運行演示實驗"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 創建實驗套件
    experiment_suite = ArtHistoryExperimentSuite()

    # 運行演示實驗
    results = await experiment_suite.run_quick_demo_experiment()

    # 輸出結果
    print("\n" + "=" * 60)
    print("📊 實驗結果摘要")
    print("=" * 60)

    if "error" in results:
        print(f"❌ 實驗失敗: {results['error']}")
    else:
        summary = results["experiment_summary"]
        print(f"📝 總實驗數: {summary['total_experiments']}")
        print(f"✅ 成功實驗: {summary['successful_experiments']}")
        print(
            f"📈 成功率: {summary['successful_experiments'] / summary['total_experiments'] * 100:.1f}%"
        )

        if results["recommendations"]:
            print("\n🎯 推薦配置:")
            for rec in results["recommendations"]:
                print(f"   • {rec}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
