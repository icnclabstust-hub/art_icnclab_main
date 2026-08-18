#!/usr/bin/env python3
"""
CUDA數據整合器
將新收集的爬蟲數據整合到CUDA加速RAG系統中
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# 添加當前目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from cuda_art_history_integration import CUDAArtHistoryProcessor
except ImportError as e:
    logging.error(f"無法導入CUDA模組: {e}")
    sys.exit(1)


class CUDADataIntegrator:
    """CUDA數據整合器"""

    def __init__(self):
        self.processor = CUDAArtHistoryProcessor()
        self.data_sources = {"europeana": [], "harvard": [], "specialized": [], "museums": []}
        self.integration_stats = {
            "total_documents": 0,
            "europeana_count": 0,
            "harvard_count": 0,
            "specialized_count": 0,
            "museum_count": 0,
            "processing_time": 0,
        }

    def discover_data_files(self) -> dict[str, list[str]]:
        """發現可用的數據文件"""
        logging.info("🔍 發現數據文件...")

        # 檢查父目錄的數據
        parent_data_dir = Path("../data/raw/")
        if parent_data_dir.exists():
            for file_path in parent_data_dir.glob("*.json"):
                if "europeana" in file_path.name:
                    self.data_sources["europeana"].append(str(file_path))
                elif "specialized" in file_path.name:
                    self.data_sources["specialized"].append(str(file_path))
                elif any(museum in file_path.name for museum in ["met_museum", "museum"]):
                    self.data_sources["museums"].append(str(file_path))

        # 檢查Harvard數據
        harvard_dir = Path("harvard_data/")
        if harvard_dir.exists():
            for file_path in harvard_dir.glob("*.json"):
                if file_path.name != "modern_art.json":  # 排除舊數據
                    self.data_sources["harvard"].append(str(file_path))

        # 統計發現的文件
        total_files = sum(len(files) for files in self.data_sources.values())
        logging.info(f"📊 發現數據文件總數: {total_files}")
        for source, files in self.data_sources.items():
            if files:
                logging.info(f"   {source}: {len(files)} 個文件")

        return self.data_sources

    def process_europeana_data(self, file_path: str) -> list[dict]:
        """處理Europeana數據"""
        documents = []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    content_parts = []

                    if item.get("title"):
                        content_parts.append(f"作品: {item['title']}")

                    if item.get("creator"):
                        content_parts.append(f"創作者: {item['creator']}")

                    if item.get("description"):
                        content_parts.append(f"描述: {item['description']}")

                    if item.get("subject"):
                        subjects = (
                            item["subject"]
                            if isinstance(item["subject"], list)
                            else [item["subject"]]
                        )
                        content_parts.append(f"主題: {', '.join(subjects)}")

                    if item.get("date"):
                        content_parts.append(f"時期: {item['date']}")

                    if item.get("type"):
                        content_parts.append(f"類型: {item['type']}")

                    content = ". ".join(content_parts)

                    if content:
                        documents.append(
                            {
                                "content": content,
                                "type": "europeana_artwork",
                                "title": item.get("title", ""),
                                "id": item.get("id", ""),
                                "url": item.get("edmIsShownAt", ""),
                                "source": "Europeana Cultural Heritage",
                            }
                        )

            logging.info(f"✅ Europeana數據處理完成: {len(documents)} 個文檔")

        except Exception as e:
            logging.error(f"❌ 處理Europeana數據失敗 {file_path}: {e}")

        return documents

    def process_museum_data(self, file_path: str) -> list[dict]:
        """處理博物館數據"""
        documents = []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    content_parts = []

                    if item.get("title"):
                        content_parts.append(f"作品: {item['title']}")

                    if item.get("artistDisplayName"):
                        content_parts.append(f"藝術家: {item['artistDisplayName']}")

                    if item.get("medium"):
                        content_parts.append(f"媒材: {item['medium']}")

                    if item.get("objectDate"):
                        content_parts.append(f"創作時間: {item['objectDate']}")

                    if item.get("department"):
                        content_parts.append(f"部門: {item['department']}")

                    if item.get("culture"):
                        content_parts.append(f"文化: {item['culture']}")

                    content = ". ".join(content_parts)

                    if content:
                        documents.append(
                            {
                                "content": content,
                                "type": "museum_artwork",
                                "title": item.get("title", ""),
                                "id": item.get("objectID", ""),
                                "url": item.get("objectURL", ""),
                                "source": "Metropolitan Museum",
                            }
                        )

            logging.info(f"✅ 博物館數據處理完成: {len(documents)} 個文檔")

        except Exception as e:
            logging.error(f"❌ 處理博物館數據失敗 {file_path}: {e}")

        return documents

    def process_specialized_data(self, file_path: str) -> list[dict]:
        """處理專業藝術數據"""
        documents = []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    content_parts = []

                    # 根據數據結構靈活處理
                    for key, value in item.items():
                        if key in ["title", "name"] and value:
                            content_parts.append(f"標題: {value}")
                        elif key in ["description", "summary"] and value:
                            content_parts.append(f"描述: {value}")
                        elif key in ["artist", "creator", "author"] and value:
                            content_parts.append(f"創作者: {value}")
                        elif key in ["date", "year", "period"] and value:
                            content_parts.append(f"時期: {value}")
                        elif key in ["style", "movement"] and value:
                            content_parts.append(f"風格: {value}")

                    content = ". ".join(content_parts)

                    if content:
                        documents.append(
                            {
                                "content": content,
                                "type": "specialized_art",
                                "title": item.get("title", item.get("name", "")),
                                "id": item.get("id", ""),
                                "url": item.get("url", ""),
                                "source": "Specialized Art Database",
                            }
                        )

            logging.info(f"✅ 專業數據處理完成: {len(documents)} 個文檔")

        except Exception as e:
            logging.error(f"❌ 處理專業數據失敗 {file_path}: {e}")

        return documents

    def integrate_all_data(self) -> bool:
        """整合所有數據到CUDA系統"""
        logging.info("🚀 開始整合所有數據到CUDA系統...")
        start_time = time.time()

        all_documents = []

        # 處理Europeana數據
        for file_path in self.data_sources["europeana"]:
            documents = self.process_europeana_data(file_path)
            all_documents.extend(documents)
            self.integration_stats["europeana_count"] += len(documents)

        # 處理Harvard數據（使用現有的處理邏輯）
        harvard_documents = self.processor._load_harvard_documents()
        all_documents.extend(harvard_documents)
        self.integration_stats["harvard_count"] += len(harvard_documents)

        # 處理博物館數據
        for file_path in self.data_sources["museums"]:
            documents = self.process_museum_data(file_path)
            all_documents.extend(documents)
            self.integration_stats["museum_count"] += len(documents)

        # 處理專業數據
        for file_path in self.data_sources["specialized"]:
            documents = self.process_specialized_data(file_path)
            all_documents.extend(documents)
            self.integration_stats["specialized_count"] += len(documents)

        self.integration_stats["total_documents"] = len(all_documents)

        if all_documents:
            # 初始化CUDA RAG系統
            success = self.processor.initialize_with_documents(all_documents)

            processing_time = time.time() - start_time
            self.integration_stats["processing_time"] = processing_time

            logging.info(f"✅ 數據整合完成，總處理時間: {processing_time:.2f}s")
            return success
        else:
            logging.warning("⚠️ 沒有找到可處理的數據")
            return False

    def get_integration_summary(self) -> dict:
        """獲取整合摘要"""
        return {
            "integration_stats": self.integration_stats,
            "cuda_status": self.processor.get_system_status(),
            "data_sources": {k: len(v) for k, v in self.data_sources.items()},
        }

    def test_integrated_system(self) -> dict:
        """測試整合後的系統"""
        test_queries = [
            "告訴我關於文藝復興時期的藝術作品",
            "有哪些巴洛克風格的雕塑？",
            "Europeana收藏中有哪些重要的文化遺產？",
            "Harvard Art Museums有什麼著名的展覽？",
            "Metropolitan Museum的印象派作品有哪些？",
        ]

        logging.info("🧪 測試整合後的CUDA系統...")
        test_results = self.processor.benchmark_performance(test_queries)

        return test_results


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🚀 CUDA數據整合器")
    print("=" * 60)

    # 創建整合器
    integrator = CUDADataIntegrator()

    # 發現數據文件
    data_sources = integrator.discover_data_files()

    if not any(data_sources.values()):
        print("❌ 沒有找到可處理的數據文件")
        return

    # 整合數據
    success = integrator.integrate_all_data()

    if success:
        # 顯示整合摘要
        summary = integrator.get_integration_summary()
        stats = summary["integration_stats"]

        print("\n📊 整合摘要:")
        print(f"   總文檔數: {stats['total_documents']:,}")
        print(f"   Europeana: {stats['europeana_count']:,}")
        print(f"   Harvard: {stats['harvard_count']:,}")
        print(f"   博物館: {stats['museum_count']:,}")
        print(f"   專業數據: {stats['specialized_count']:,}")
        print(f"   處理時間: {stats['processing_time']:.2f}s")

        # 測試系統
        test_results = integrator.test_integrated_system()
        print("\n🧪 系統測試結果:")
        print(f"   平均查詢時間: {test_results['average_time']:.3f}s")
        print(f"   總測試時間: {test_results['total_time']:.3f}s")
        print(f"   測試查詢數: {test_results['test_queries']}")

        print("\n🎉 CUDA增強藝術史資料庫整合完成！")
        print(f"   您的系統現在包含 {stats['total_documents']:,} 個藝術史文檔")
        print("   支援GPU加速查詢和生成")

    else:
        print("❌ 數據整合失敗")


if __name__ == "__main__":
    main()
