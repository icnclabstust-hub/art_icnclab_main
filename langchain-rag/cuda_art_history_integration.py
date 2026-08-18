#!/usr/bin/env python3
"""
CUDA增強藝術史資料庫集成模組
將GPU加速整合到現有RAG系統中
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# 添加當前目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 導入現有模組
try:
    from cuda_enhanced_rag import CUDAEnhancedRAG, CUDARAGConfig, check_cuda_environment
except ImportError as e:
    logging.warning(f"CUDA模組未完全安裝: {e}")


class CUDAArtHistoryProcessor:
    """CUDA增強的藝術史數據處理器"""

    def __init__(self):
        self.cuda_info = check_cuda_environment()
        self.config = CUDARAGConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            batch_size=32 if self.cuda_info.get("cuda_available") else 8,
            top_k=10,
            similarity_threshold=0.65,
        )
        self.rag_system = None
        self.performance_metrics = {
            "initialization_time": 0,
            "total_documents_processed": 0,
            "total_queries": 0,
            "average_processing_speed": 0,
        }

    def initialize_with_harvard_data(self) -> bool:
        """使用Harvard數據初始化CUDA RAG系統"""
        try:
            logging.info("🎨 初始化CUDA增強藝術史系統...")
            start_time = time.time()

            # 檢查CUDA RAG系統是否可用
            if not self.cuda_info.get("cuda_available"):
                logging.warning("⚠️ CUDA不可用，某些功能將受限")
                return False

            # 創建CUDA RAG系統
            self.rag_system = CUDAEnhancedRAG(self.config)

            # 加載Harvard數據
            harvard_documents = self._load_harvard_documents()
            if harvard_documents:
                self.rag_system.initialize_from_documents(harvard_documents)
                self.performance_metrics["total_documents_processed"] = len(harvard_documents)

            initialization_time = time.time() - start_time
            self.performance_metrics["initialization_time"] = initialization_time

            logging.info(f"✅ CUDA系統初始化完成，耗時: {initialization_time:.2f}s")
            return True

        except Exception as e:
            logging.error(f"❌ CUDA系統初始化失敗: {e}")
            return False

    def initialize_with_documents(self, documents: list[dict]) -> bool:
        """使用自定義文檔列表初始化CUDA RAG系統"""
        try:
            logging.info(f"🎨 初始化CUDA增強藝術史系統，文檔數: {len(documents)}")
            start_time = time.time()

            # 檢查CUDA RAG系統是否可用
            if not self.cuda_info.get("cuda_available"):
                logging.warning("⚠️ CUDA不可用，某些功能將受限")
                return False

            # 創建CUDA RAG系統
            self.rag_system = CUDAEnhancedRAG(self.config)

            # 初始化系統
            if documents:
                self.rag_system.initialize_from_documents(documents)
                self.performance_metrics["total_documents_processed"] = len(documents)

            initialization_time = time.time() - start_time
            self.performance_metrics["initialization_time"] = initialization_time

            logging.info(f"✅ CUDA系統初始化完成，耗時: {initialization_time:.2f}s")
            return True

        except Exception as e:
            logging.error(f"❌ CUDA系統初始化失敗: {e}")
            return False

    def _load_harvard_documents(self) -> list[dict]:
        """加載Harvard藝術史文檔"""
        documents = []

        # 檢查擴展的Harvard數據
        data_dirs = [
            "expanded_harvard_data",
            "final_expanded_data/harvard",
            "unified_crawler_data/harvard",
        ]

        for data_dir in data_dirs:
            if os.path.exists(data_dir):
                documents.extend(self._process_harvard_directory(data_dir))

        logging.info(f"📚 加載了 {len(documents)} 個Harvard文檔")
        return documents

    def _process_harvard_directory(self, data_dir: str) -> list[dict]:
        """處理Harvard數據目錄"""
        documents = []

        # 處理不同類型的文件
        for file_path in Path(data_dir).glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # 根據文件名判斷數據類型
                if "objects" in file_path.name:
                    documents.extend(self._process_artwork_data(data))
                elif "people" in file_path.name:
                    documents.extend(self._process_people_data(data))
                elif "exhibitions" in file_path.name:
                    documents.extend(self._process_exhibition_data(data))

            except Exception as e:
                logging.warning(f"⚠️ 處理文件失敗 {file_path}: {e}")

        return documents

    def _process_artwork_data(self, artworks: list[dict]) -> list[dict]:
        """處理藝術作品數據"""
        documents = []

        for artwork in artworks:
            # 創建富文本描述
            content_parts = []

            # 基本信息
            if artwork.get("title"):
                content_parts.append(f"作品: {artwork['title']}")

            if artwork.get("people"):
                artists = [
                    p.get("name", "")
                    for p in artwork["people"]
                    if p.get("role") in ["Artist", "Creator"]
                ]
                if artists:
                    content_parts.append(f"藝術家: {', '.join(artists)}")

            if artwork.get("classification"):
                content_parts.append(f"分類: {artwork['classification']}")

            if artwork.get("medium"):
                content_parts.append(f"媒材: {artwork['medium']}")

            if artwork.get("dated"):
                content_parts.append(f"創作時間: {artwork['dated']}")

            if artwork.get("culture"):
                content_parts.append(f"文化: {artwork['culture']}")

            if artwork.get("description"):
                content_parts.append(f"描述: {artwork['description']}")

            # 合併內容
            content = ". ".join(content_parts)

            if content:
                documents.append(
                    {
                        "content": content,
                        "type": "artwork",
                        "title": artwork.get("title", ""),
                        "id": artwork.get("id"),
                        "url": artwork.get("url", ""),
                        "source": "Harvard Art Museums",
                    }
                )

        return documents

    def _process_people_data(self, people: list[dict]) -> list[dict]:
        """處理人物數據"""
        documents = []

        for person in people:
            content_parts = []

            if person.get("displayname"):
                content_parts.append(f"人物: {person['displayname']}")

            if person.get("birthyear") or person.get("deathyear"):
                years = f"{person.get('birthyear', '?')}-{person.get('deathyear', '?')}"
                content_parts.append(f"生卒年: {years}")

            if person.get("nationality"):
                content_parts.append(f"國籍: {person['nationality']}")

            if person.get("biography"):
                content_parts.append(f"生平: {person['biography']}")

            content = ". ".join(content_parts)

            if content:
                documents.append(
                    {
                        "content": content,
                        "type": "person",
                        "name": person.get("displayname", ""),
                        "id": person.get("id"),
                        "url": person.get("url", ""),
                        "source": "Harvard Art Museums",
                    }
                )

        return documents

    def _process_exhibition_data(self, exhibitions: list[dict]) -> list[dict]:
        """處理展覽數據"""
        documents = []

        for exhibition in exhibitions:
            content_parts = []

            if exhibition.get("title"):
                content_parts.append(f"展覽: {exhibition['title']}")

            if exhibition.get("begindate") or exhibition.get("enddate"):
                dates = f"{exhibition.get('begindate', '')}-{exhibition.get('enddate', '')}"
                content_parts.append(f"展期: {dates}")

            if exhibition.get("venue"):
                content_parts.append(f"地點: {exhibition['venue']}")

            if exhibition.get("description"):
                content_parts.append(f"描述: {exhibition['description']}")

            content = ". ".join(content_parts)

            if content:
                documents.append(
                    {
                        "content": content,
                        "type": "exhibition",
                        "title": exhibition.get("title", ""),
                        "id": exhibition.get("id"),
                        "url": exhibition.get("url", ""),
                        "source": "Harvard Art Museums",
                    }
                )

        return documents

    def enhanced_query(self, question: str, mode: str = "cuda") -> dict:
        """增強查詢功能"""
        start_time = time.time()

        if mode == "cuda" and self.rag_system:
            # 使用CUDA加速查詢
            result = self.rag_system.query(question)
            result["mode"] = "cuda_accelerated"
        else:
            # 降級到基本查詢
            result = self._fallback_query(question)
            result["mode"] = "cpu_fallback"

        query_time = time.time() - start_time
        self.performance_metrics["total_queries"] += 1

        # 添加性能信息
        result["performance"].update({"total_query_time": query_time, "cuda_info": self.cuda_info})

        return result

    def _fallback_query(self, question: str) -> dict:
        """CPU降級查詢"""
        return {
            "question": question,
            "answer": "CUDA系統不可用，這是簡化的回答。請檢查GPU環境配置。",
            "sources": [],
            "performance": {"search_time": 0, "generation_time": 0, "mode": "cpu_fallback"},
        }

    def get_system_status(self) -> dict:
        """獲取系統狀態"""
        status = {
            "cuda_available": self.cuda_info.get("cuda_available", False),
            "cuda_info": self.cuda_info,
            "rag_system_ready": self.rag_system is not None,
            "performance_metrics": self.performance_metrics,
        }

        if self.rag_system:
            status.update(self.rag_system.get_performance_summary())

        return status

    def benchmark_performance(self, test_queries: list[str] = None) -> dict:
        """性能基準測試"""
        if test_queries is None:
            test_queries = [
                "Harvard Art Museums有哪些文藝復興時期的作品？",
                "告訴我關於梵高的資料",
                "有哪些重要的藝術展覽？",
            ]

        results = {
            "test_queries": len(test_queries),
            "total_time": 0,
            "average_time": 0,
            "cuda_speedup": 0,
            "queries_results": [],
        }

        start_time = time.time()

        for query in test_queries:
            query_start = time.time()
            result = self.enhanced_query(query)
            query_time = time.time() - query_start

            results["queries_results"].append(
                {"query": query, "time": query_time, "mode": result.get("mode", "unknown")}
            )

        total_time = time.time() - start_time
        results["total_time"] = total_time
        results["average_time"] = total_time / len(test_queries)

        return results


def main():
    """主測試函數"""
    logging.basicConfig(level=logging.INFO)

    print("🚀 CUDA增強藝術史資料庫集成測試")
    print("=" * 60)

    # 創建處理器
    processor = CUDAArtHistoryProcessor()

    # 顯示CUDA信息
    status = processor.get_system_status()
    print(f"🔧 CUDA狀態: {status['cuda_available']}")
    if status["cuda_info"].get("device_name"):
        print(f"🎮 GPU: {status['cuda_info']['device_name']}")
        print(f"💾 GPU內存: {status['cuda_info'].get('memory_total_gb', 0):.1f} GB")

    # 初始化系統
    success = processor.initialize_with_harvard_data()
    if not success:
        print("❌ 系統初始化失敗")
        return

    # 測試查詢
    test_query = "Harvard Art Museums有哪些著名的藝術作品？"
    print(f"\n🔍 測試查詢: {test_query}")

    result = processor.enhanced_query(test_query)
    print(f"📋 查詢模式: {result.get('mode', 'unknown')}")
    print(f"⏱️ 查詢時間: {result['performance'].get('total_query_time', 0):.3f}s")
    print(f"📊 找到來源: {len(result.get('sources', []))}")

    # 性能基準測試
    print("\n🏃 執行性能基準測試...")
    benchmark = processor.benchmark_performance()
    print("📈 基準結果:")
    print(f"   平均查詢時間: {benchmark['average_time']:.3f}s")
    print(f"   總測試時間: {benchmark['total_time']:.3f}s")

    # 最終狀態
    final_status = processor.get_system_status()
    print("\n📊 最終系統狀態:")
    print(f"   處理文檔數: {final_status['performance_metrics']['total_documents_processed']}")
    print(f"   總查詢數: {final_status['performance_metrics']['total_queries']}")
    print(f"   CUDA可用: {final_status['cuda_available']}")


if __name__ == "__main__":
    main()
