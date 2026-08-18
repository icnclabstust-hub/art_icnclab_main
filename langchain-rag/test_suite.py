#!/usr/bin/env python3
"""
藝術史資料庫自動化測試套件
包含單元測試、整合測試和端對端測試
"""

import json
import os
import sys
import time
import unittest
from datetime import datetime
from typing import Any

import requests

# 測試配置
TEST_CONFIG = {
    "api_base_url": "http://localhost:8008",
    "neo4j_url": "bolt://localhost:7687",
    "neo4j_user": "neo4j",
    "neo4j_password": "CHANGE_ME_NEO4J_PASSWORD",
    "test_data_dir": "./test_data",
}


class TestDataQualityMonitor(unittest.TestCase):
    """資料品質監控測試"""

    def setUp(self):
        """測試前設置"""
        from data_quality_monitor import DataQualityMonitor

        self.monitor = DataQualityMonitor(output_dir="test_quality_reports")

    def test_completeness_assessment(self):
        """測試完整性評估"""
        test_records = [
            {
                "title": "Test Artwork",
                "description": "Test description",
                "date": "2020",
                "creator": "Test Artist",
                "medium": "Oil on canvas",
            }
        ]

        score = self.monitor._assess_completeness(test_records)
        self.assertGreater(score, 90, "完整度分數應大於90")
        self.assertLessEqual(score, 100, "完整度分數不應超過100")

    def test_accuracy_assessment(self):
        """測試準確性評估"""
        test_records = [
            {
                "title": "Test",
                "date": "1889",
                "quality_score": 95,
                "description": "Valid description with good length",
            }
        ]

        score = self.monitor._assess_accuracy(test_records)
        self.assertGreater(score, 0, "準確性分數應大於0")
        self.assertLessEqual(score, 100, "準確性分數不應超過100")

    def test_quality_report_generation(self):
        """測試品質報告生成"""
        test_records = [
            {
                "id": "001",
                "title": "The Starry Night",
                "description": "Famous painting by Van Gogh",
                "date": "1889",
                "creator": "Vincent van Gogh",
                "quality_score": 95,
            }
        ]

        report = self.monitor.assess_data_quality(test_records, "test_source")

        self.assertEqual(report.source_id, "test_source")
        self.assertEqual(report.total_records, 1)
        self.assertGreater(report.overall_score, 0)
        self.assertIn("completeness", report.quality_scores)
        self.assertIn("accuracy", report.quality_scores)


class TestSummarizationAgent(unittest.TestCase):
    """摘要翻譯Agent測試"""

    def setUp(self):
        """測試前設置"""
        from summarization_translation_agent import (
            SummarizationTranslationAgent,
            SummaryLevel,
            TranslationLanguage,
        )

        self.agent = SummarizationTranslationAgent()
        self.SummaryLevel = SummaryLevel
        self.TranslationLanguage = TranslationLanguage

    def test_brief_summary_generation(self):
        """測試簡要摘要生成"""
        text = (
            "The Starry Night is an oil-on-canvas painting by Dutch Post-Impressionist "
            "painter Vincent van Gogh. Painted in June 1889, it depicts the view from "
            "the east-facing window of his asylum room at Saint-Rémy-de-Provence."
        )

        result = self.agent.generate_summary(text, self.SummaryLevel.BRIEF)

        self.assertIsNotNone(result.summary)
        self.assertLessEqual(result.word_count, 100, "簡要摘要應少於100字")
        self.assertEqual(result.level, self.SummaryLevel.BRIEF)

    def test_terminology_database(self):
        """測試術語資料庫"""
        translation = self.agent.terminology_db.get_translation("Renaissance", "zh-TW")

        self.assertEqual(translation, "文藝復興")

    def test_translation_with_terminology(self):
        """測試專業術語翻譯"""
        text = "Renaissance art is characterized by realism and Chiaroscuro technique."

        result = self.agent.translate(
            text, self.TranslationLanguage.ZH_TW, preserve_terminology=True
        )

        self.assertIsNotNone(result.translated_text)
        self.assertIn("Renaissance", result.terminology_used)
        self.assertGreater(result.confidence_score, 0)


class TestDataMapper(unittest.TestCase):
    """資料映射器測試"""

    def setUp(self):
        """測試前設置"""
        from data_mapper import ArtHistoryDataMapper
        from enhanced_art_history_schema import NodeType

        self.mapper = ArtHistoryDataMapper()
        self.NodeType = NodeType

    def test_artwork_type_determination(self):
        """測試作品類型判斷"""
        painting_item = {"dcType": "Painting", "dcFormat": "Oil on canvas"}

        artwork_type = self.mapper._determine_artwork_type(painting_item)
        self.assertEqual(artwork_type, self.NodeType.PAINTING)

    def test_entity_creation(self):
        """測試實體創建"""
        test_item = {
            "dcTitle": "Test Artwork",
            "dcCreator": "Test Artist",
            "dcDate": "1889",
            "dcDescription": "Test description",
            "dcType": "Painting",
        }

        entities, relationships = self.mapper.map_single_item(test_item)

        self.assertGreater(len(entities), 0, "應該創建至少一個實體")
        self.assertTrue(any(e.entity_type == self.NodeType.ARTWORK for e in entities))

    def test_deduplication(self):
        """測試去重功能"""
        from enhanced_graph_builder import EnhancedArtEntity

        entities = [
            EnhancedArtEntity(self.NodeType.ARTIST, "Van Gogh", {}),
            EnhancedArtEntity(self.NodeType.ARTIST, "Van Gogh", {}),
            EnhancedArtEntity(self.NodeType.ARTIST, "Monet", {}),
        ]

        unique_entities = self.mapper._deduplicate_entities(entities)
        self.assertEqual(len(unique_entities), 2, "去重後應該只有2個實體")


class TestCrawlerIntegration(unittest.TestCase):
    """爬蟲整合測試"""

    def setUp(self):
        """測試前設置"""
        self.harvard_api_key = os.getenv("HARVARD_API_KEY", "test_key")

    def test_harvard_crawler_initialization(self):
        """測試Harvard爬蟲初始化"""
        from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig

        config = HarvardCrawlerConfig(api_key=self.harvard_api_key, delay_seconds=1.0)

        crawler = HarvardArtMuseumsCrawler(config)
        self.assertIsNotNone(crawler)
        self.assertEqual(crawler.config.api_key, self.harvard_api_key)

    @unittest.skipIf(not os.getenv("HARVARD_API_KEY"), "需要Harvard API密鑰")
    def test_harvard_api_connection(self):
        """測試Harvard API連接"""
        from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig

        config = HarvardCrawlerConfig(api_key=self.harvard_api_key, delay_seconds=1.0)

        crawler = HarvardArtMuseumsCrawler(config)

        # 測試獲取分類
        response = crawler.get_classifications()
        self.assertIsNotNone(response)
        self.assertIn("records", response)


class TestAPIEndpoints(unittest.TestCase):
    """API端點測試"""

    def setUp(self):
        """測試前設置"""
        self.api_url = TEST_CONFIG["api_base_url"]
        self.timeout = 10

    def test_health_check(self):
        """測試健康檢查端點"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=self.timeout)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"API服務未運行: {e}")

    def test_query_endpoint(self):
        """測試查詢端點"""
        try:
            response = requests.post(
                f"{self.api_url}/api/v1/query",
                json={"query": "介紹文藝復興藝術", "strategy": "hybrid_balanced", "top_k": 5},
                timeout=self.timeout,
            )

            self.assertIn(response.status_code, [200, 404])

            if response.status_code == 200:
                data = response.json()
                self.assertIn("status", data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"API服務未運行: {e}")


class TestDatabaseConnections(unittest.TestCase):
    """資料庫連接測試"""

    def test_neo4j_connection(self):
        """測試Neo4j連接"""
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                TEST_CONFIG["neo4j_url"],
                auth=(TEST_CONFIG["neo4j_user"], TEST_CONFIG["neo4j_password"]),
            )

            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                self.assertEqual(record["test"], 1)

            driver.close()
        except Exception as e:
            self.skipTest(f"Neo4j未運行: {e}")


class TestPerformance(unittest.TestCase):
    """性能測試"""

    def test_quality_assessment_performance(self):
        """測試品質評估性能"""
        from data_quality_monitor import DataQualityMonitor

        monitor = DataQualityMonitor()

        # 生成測試資料
        test_records = [
            {
                "id": f"test_{i}",
                "title": f"Test Artwork {i}",
                "description": f"Description {i}",
                "date": "2020",
                "creator": f"Artist {i}",
            }
            for i in range(100)
        ]

        start_time = time.time()
        monitor.assess_data_quality(test_records, "performance_test")
        end_time = time.time()

        processing_time = end_time - start_time
        self.assertLess(processing_time, 5.0, "100條記錄的評估應在5秒內完成")

    def test_summarization_performance(self):
        """測試摘要生成性能"""
        from summarization_translation_agent import SummarizationTranslationAgent, SummaryLevel

        agent = SummarizationTranslationAgent()

        text = (
            "The Starry Night is an oil-on-canvas painting by Dutch Post-Impressionist "
            "painter Vincent van Gogh. " * 10
        )

        start_time = time.time()
        agent.generate_summary(text, SummaryLevel.BRIEF)
        end_time = time.time()

        processing_time = end_time - start_time
        self.assertLess(processing_time, 2.0, "簡要摘要生成應在2秒內完成")


def generate_test_report(results: unittest.TestResult) -> dict[str, Any]:
    """生成測試報告"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": results.testsRun,
            "passed": results.testsRun - len(results.failures) - len(results.errors),
            "failed": len(results.failures),
            "errors": len(results.errors),
            "skipped": len(results.skipped),
            "success_rate": (results.testsRun - len(results.failures) - len(results.errors))
            / results.testsRun
            * 100
            if results.testsRun > 0
            else 0,
        },
        "failures": [
            {"test": str(test), "traceback": traceback} for test, traceback in results.failures
        ],
        "errors": [
            {"test": str(test), "traceback": traceback} for test, traceback in results.errors
        ],
        "skipped": [{"test": str(test), "reason": reason} for test, reason in results.skipped],
    }

    return report


def main():
    """主測試函數"""
    print("🧪 藝術史資料庫自動化測試套件")
    print("=" * 70)
    print()

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    test_classes = [
        TestDataQualityMonitor,
        TestSummarizationAgent,
        TestDataMapper,
        TestCrawlerIntegration,
        TestAPIEndpoints,
        TestDatabaseConnections,
        TestPerformance,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    results = runner.run(suite)

    print()
    print("=" * 70)
    print("📊 測試結果摘要")
    print("=" * 70)
    print(f"總測試數: {results.testsRun}")
    print(f"✅ 通過: {results.testsRun - len(results.failures) - len(results.errors)}")
    print(f"❌ 失敗: {len(results.failures)}")
    print(f"⚠️  錯誤: {len(results.errors)}")
    print(f"⏭️  跳過: {len(results.skipped)}")

    if results.testsRun > 0:
        success_rate = (
            (results.testsRun - len(results.failures) - len(results.errors))
            / results.testsRun
            * 100
        )
        print(f"📈 成功率: {success_rate:.1f}%")

    # 生成JSON報告
    report = generate_test_report(results)
    report_path = "test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 詳細報告已保存到: {report_path}")

    # 根據測試結果返回退出碼
    return 0 if results.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
