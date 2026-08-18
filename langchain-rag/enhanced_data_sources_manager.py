#!/usr/bin/env python3
"""
增強資料來源管理器
支援多種資料來源的整合、質量評估和精準度優化
"""

import asyncio
import glob
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """資料來源類型"""

    MUSEUM_API = "museum_api"
    ACADEMIC_PAPER = "academic_paper"
    BOOK_DATABASE = "book_database"
    CULTURAL_HERITAGE = "cultural_heritage"
    WEB_CONTENT = "web_content"


class DataQuality(Enum):
    """資料品質等級"""

    VERY_HIGH = "very_high"  # 90-100分
    HIGH = "high"  # 75-89分
    MEDIUM = "medium"  # 50-74分
    LOW = "low"  # 25-49分
    VERY_LOW = "very_low"  # 0-24分


@dataclass
class DataSourceInfo:
    """資料來源資訊"""

    source_id: str
    name: str
    type: DataSourceType
    description: str
    api_endpoint: str | None = None
    requires_auth: bool = False
    update_frequency: str = "weekly"
    languages: list[str] = field(default_factory=lambda: ["en"])
    categories: list[str] = field(default_factory=list)
    priority: int = 5  # 1-10
    quality_score: float = 0.0
    last_updated: datetime | None = None


@dataclass
class DataRecord:
    """資料記錄"""

    record_id: str
    source_id: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    relevance_score: float = 0.0
    language: str = "en"
    timestamp: datetime = field(default_factory=datetime.now)
    categories: list[str] = field(default_factory=list)


class EnhancedDataSourcesManager:
    """增強資料來源管理器"""

    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = data_dir
        self.data_sources: dict[str, DataSourceInfo] = {}
        self.data_records: list[DataRecord] = []

        # 註冊所有資料來源
        self._register_data_sources()

    def _register_data_sources(self):
        """註冊所有支援的資料來源"""

        # Metropolitan Museum
        self.data_sources["met_museum"] = DataSourceInfo(
            source_id="met_museum",
            name="Metropolitan Museum of Art",
            type=DataSourceType.MUSEUM_API,
            description="大都會博物館藝術品收藏，提供高品質的藝術品圖像和詳細元數據",
            api_endpoint="https://collectionapi.metmuseum.org/public/collection/v1",
            requires_auth=False,
            update_frequency="weekly",
            languages=["en"],
            categories=["artwork", "museum", "visual_art", "renaissance", "baroque"],
            priority=9,
        )

        # Google Books
        self.data_sources["google_books"] = DataSourceInfo(
            source_id="google_books",
            name="Google Books API",
            type=DataSourceType.BOOK_DATABASE,
            description="Google圖書數據庫，包含大量藝術史相關書籍和學術資料",
            api_endpoint="https://www.googleapis.com/books/v1/volumes",
            requires_auth=False,
            update_frequency="monthly",
            languages=["en", "zh-TW", "zh-CN"],
            categories=["books", "literature", "academic", "art_theory"],
            priority=8,
        )

        # Europeana (NEW)
        self.data_sources["europeana"] = DataSourceInfo(
            source_id="europeana",
            name="Europeana Cultural Heritage",
            type=DataSourceType.CULTURAL_HERITAGE,
            description="歐洲數位文化遺產平台，提供來自歐洲博物館、圖書館的高品質文化資料",
            api_endpoint="https://api.europeana.eu/record/v2",
            requires_auth=True,
            update_frequency="weekly",
            languages=["en", "fr", "de", "es", "it"],
            categories=[
                "cultural_heritage",
                "european_art",
                "museum",
                "digital_collection",
                "medieval",
                "renaissance",
                "modern",
            ],
            priority=10,
        )

        # Google Scholar (NEW)
        self.data_sources["google_scholar"] = DataSourceInfo(
            source_id="google_scholar",
            name="Google Scholar Academic Papers",
            type=DataSourceType.ACADEMIC_PAPER,
            description="Google學術搜索，提供藝術史領域的學術論文和研究文獻",
            api_endpoint=None,  # Web scraping
            requires_auth=False,
            update_frequency="daily",
            languages=["en", "zh-TW", "zh-CN"],
            categories=[
                "academic",
                "research",
                "papers",
                "scholarly",
                "art_theory",
                "art_criticism",
            ],
            priority=9,
        )

        # Harvard Art Museums (NEW)
        self.data_sources["harvard_art_museums"] = DataSourceInfo(
            source_id="harvard_art_museums",
            name="Harvard Art Museums",
            type=DataSourceType.MUSEUM_API,
            description="哈佛藝術博物館API，提供高品質的學術收藏和研究資料，包含詳細的來源記錄和展覽歷史",
            api_endpoint="https://api.harvardartmuseums.org",
            requires_auth=True,
            update_frequency="daily",
            languages=["en"],
            categories=[
                "museum",
                "academic_collection",
                "research",
                "exhibition",
                "provenance",
                "scholarly",
            ],
            priority=10,
        )

    async def load_all_data(self) -> dict[str, Any]:
        """載入所有資料來源的資料"""
        logger.info("🔄 開始載入所有資料來源...")

        results = {
            "sources_loaded": 0,
            "total_records": 0,
            "quality_distribution": {},
            "source_statistics": {},
            "loading_errors": [],
        }

        for source_id, source_info in self.data_sources.items():
            try:
                logger.info(f"📂 載入 {source_info.name}...")

                # 尋找該資料來源的檔案
                source_files = self._find_source_files(source_id)

                if not source_files:
                    logger.warning(f"⚠️  {source_info.name} 沒有找到資料檔案")
                    continue

                # 載入最新的檔案
                latest_file = max(source_files, key=os.path.getctime)
                records = await self._load_source_file(latest_file, source_id)

                if records:
                    self.data_records.extend(records)
                    results["sources_loaded"] += 1
                    results["total_records"] += len(records)

                    # 統計這個來源的資料
                    results["source_statistics"][source_id] = {
                        "name": source_info.name,
                        "record_count": len(records),
                        "average_quality": sum(r.quality_score for r in records) / len(records),
                        "categories": list(set(cat for r in records for cat in r.categories)),
                        "languages": list(set(r.language for r in records)),
                        "latest_file": latest_file,
                    }

                    logger.info(f"✅ {source_info.name}: 載入 {len(records)} 筆記錄")
                else:
                    logger.warning(f"⚠️  {source_info.name}: 沒有有效記錄")

            except Exception as e:
                error_msg = f"載入 {source_info.name} 失敗: {str(e)}"
                logger.error(f"❌ {error_msg}")
                results["loading_errors"].append(error_msg)

        # 計算品質分佈
        results["quality_distribution"] = self._calculate_quality_distribution()

        # 更新資料來源品質分數
        await self._update_source_quality_scores()

        logger.info(
            f"✅ 資料載入完成: {results['sources_loaded']} 個來源，共 {results['total_records']} 筆記錄"
        )

        return results

    def _find_source_files(self, source_id: str) -> list[str]:
        """尋找特定資料來源的檔案"""
        patterns = [
            f"{source_id}_*.json",
            f"{source_id.replace('_', '-')}_*.json",
            f"*{source_id}*.json",
        ]

        # 特殊處理某些檔案命名格式
        if source_id == "harvard_art_museums":
            patterns.extend(["harvard_art_museums_*.json", "harvard-art-museums_*.json"])

        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(self.data_dir, pattern)))

        return files

    async def _load_source_file(self, file_path: str, source_id: str) -> list[DataRecord]:
        """載入單一資料檔案"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            records = []

            # 根據不同資料來源的格式處理資料
            if source_id == "met_museum":
                records = self._process_met_data(data, source_id)
            elif source_id == "google_books":
                records = self._process_books_data(data, source_id)
            elif source_id == "europeana":
                records = self._process_europeana_data(data, source_id)
            elif source_id == "google_scholar":
                records = self._process_scholar_data(data, source_id)
            elif source_id == "harvard_art_museums":
                records = self._process_harvard_data(data, source_id)
            else:
                # 通用處理
                records = self._process_generic_data(data, source_id)

            return records

        except Exception as e:
            logger.error(f"載入檔案 {file_path} 失敗: {e}")
            return []

    def _process_met_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理大都會博物館資料"""
        records = []
        items = data if isinstance(data, list) else data.get("data", [])

        for item in items:
            try:
                record_id = self._generate_record_id(source_id, item.get("objectID", ""))

                title = item.get("title", "無標題")
                content = f"{title}. "

                if item.get("artistDisplayName"):
                    content += f"藝術家: {item['artistDisplayName']}. "
                if item.get("medium"):
                    content += f"媒材: {item['medium']}. "
                if item.get("objectDate"):
                    content += f"年代: {item['objectDate']}. "
                if item.get("department"):
                    content += f"部門: {item['department']}. "

                # 品質評估
                quality_score = self._assess_met_quality(item)

                # 類別分析
                categories = self._categorize_met_item(item)

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content.strip(),
                    metadata=item,
                    quality_score=quality_score,
                    language="en",
                    categories=categories,
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理MET項目失敗: {e}")
                continue

        return records

    def _process_books_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理Google Books資料"""
        records = []
        books = data if isinstance(data, list) else data.get("data", [])

        for book in books:
            try:
                record_id = self._generate_record_id(source_id, book.get("id", ""))

                title = book.get("title", "無標題")
                authors = ", ".join(book.get("authors", []))
                description = book.get("description", "")

                content = f"{title}"
                if authors:
                    content += f" 作者: {authors}"
                if description:
                    content += f" 描述: {description[:500]}"

                # 品質評估
                quality_score = self._assess_book_quality(book)

                # 語言檢測
                language = book.get("language", "en")

                # 類別分析
                categories = book.get("categories", []) + ["books", "literature"]

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content,
                    metadata=book,
                    quality_score=quality_score,
                    language=language,
                    categories=categories,
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理Book項目失敗: {e}")
                continue

        return records

    def _process_europeana_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理Europeana資料"""
        records = []

        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        else:
            items = data if isinstance(data, list) else []

        for item in items:
            try:
                record_id = self._generate_record_id(source_id, item.get("europeanaId", ""))

                title = item.get("title", "無標題")
                creator = ", ".join(item.get("creator", []))
                description = item.get("description", "")

                content = f"{title}"
                if creator:
                    content += f" 創作者: {creator}"
                if description:
                    content += f" 描述: {description[:500]}"

                # 品質評估（使用預設的qualityScore或計算）
                quality_score = item.get("qualityScore", self._assess_europeana_quality(item))

                # 語言檢測
                language = item.get("language", "en")

                # 類別分析（使用預設的或分析）
                categories = item.get("artHistoryCategories", []) + [
                    "cultural_heritage",
                    "european_art",
                ]

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content,
                    metadata=item,
                    quality_score=quality_score,
                    language=language,
                    categories=categories,
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理Europeana項目失敗: {e}")
                continue

        return records

    def _process_scholar_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理Google Scholar資料"""
        records = []

        if isinstance(data, dict) and "data" in data:
            papers = data["data"]
        else:
            papers = data if isinstance(data, list) else []

        for paper in papers:
            try:
                record_id = self._generate_record_id(source_id, paper.get("title", ""))

                title = paper.get("title", "無標題")
                authors = ", ".join(paper.get("authors", []))
                abstract = paper.get("abstract", "")

                content = f"{title}"
                if authors:
                    content += f" 作者: {authors}"
                if abstract:
                    content += f" 摘要: {abstract[:500]}"

                # 品質評估（使用預設的academicScore或計算）
                quality_score = paper.get("academicScore", self._assess_scholar_quality(paper))

                # 語言檢測
                language = paper.get("language", "en")

                # 類別分析
                categories = paper.get("researchFields", []) + ["academic", "research"]

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content,
                    metadata=paper,
                    quality_score=quality_score,
                    language=language,
                    categories=categories,
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理Scholar項目失敗: {e}")
                continue

        return records

    def _process_harvard_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理Harvard Art Museums資料"""
        records = []

        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        else:
            items = data if isinstance(data, list) else []

        for item in items:
            try:
                record_id = self._generate_record_id(source_id, item.get("harvardId", ""))

                title = item.get("title", "無標題")

                # 建構詳細內容
                content = f"{title}. "

                if item.get("people"):
                    people_names = [
                        person.get("name", "") for person in item["people"] if person.get("name")
                    ]
                    if people_names:
                        content += f"藝術家: {', '.join(people_names)}. "

                if item.get("culture"):
                    content += f"文化: {item['culture']}. "

                if item.get("period"):
                    content += f"時期: {item['period']}. "

                if item.get("dated"):
                    content += f"年代: {item['dated']}. "

                if item.get("medium"):
                    content += f"媒材: {item['medium']}. "

                if item.get("description"):
                    content += f"描述: {item['description'][:500]}. "

                if item.get("commentary"):
                    content += f"評論: {item['commentary'][:300]}. "

                # 品質評估
                quality_score = item.get("qualityScore", self._assess_harvard_quality(item))

                # 語言檢測
                language = "en"  # Harvard主要是英文資料

                # 類別分析
                categories = item.get("artHistoryCategories", [])
                if not categories:
                    categories = self._categorize_harvard_item(item)

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content.strip(),
                    metadata=item,
                    quality_score=quality_score,
                    language=language,
                    categories=categories,
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理Harvard項目失敗: {e}")
                continue

        return records

    def _process_generic_data(self, data: Any, source_id: str) -> list[DataRecord]:
        """處理通用格式資料"""
        records = []
        items = data if isinstance(data, list) else [data]

        for i, item in enumerate(items):
            try:
                record_id = self._generate_record_id(source_id, str(i))

                # 嘗試提取基本欄位
                title = item.get("title") or item.get("name") or f"Record {i + 1}"
                content = item.get("content") or item.get("description") or str(item)[:500]

                record = DataRecord(
                    record_id=record_id,
                    source_id=source_id,
                    title=title,
                    content=content,
                    metadata=item,
                    quality_score=50.0,  # 預設品質分數
                    language="en",
                    categories=["generic"],
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"處理通用項目失敗: {e}")
                continue

        return records

    def _generate_record_id(self, source_id: str, item_id: str) -> str:
        """生成記錄ID"""
        combined = f"{source_id}:{item_id}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _assess_met_quality(self, item: dict[str, Any]) -> float:
        """評估MET資料品質"""
        score = 0

        # 基本資訊完整性
        if item.get("title"):
            score += 15
        if item.get("artistDisplayName"):
            score += 15
        if item.get("objectDate"):
            score += 10
        if item.get("medium"):
            score += 10

        # 圖像資源
        if item.get("primaryImage"):
            score += 20
        if item.get("primaryImageSmall"):
            score += 10

        # 詳細資訊
        if item.get("department"):
            score += 5
        if item.get("culture"):
            score += 5
        if item.get("period"):
            score += 5
        if item.get("dynasty"):
            score += 5

        return min(score, 100.0)

    def _assess_book_quality(self, book: dict[str, Any]) -> float:
        """評估書籍資料品質"""
        score = 0

        # 基本資訊
        if book.get("title"):
            score += 20
        if book.get("authors"):
            score += 15
        if book.get("publishedDate"):
            score += 10
        if book.get("publisher"):
            score += 10

        # 內容品質
        if book.get("description"):
            score += 20
        if book.get("categories"):
            score += 10
        if book.get("pageCount", 0) > 50:
            score += 10

        # 可及性
        if book.get("previewLink"):
            score += 5

        return min(score, 100.0)

    def _assess_europeana_quality(self, item: dict[str, Any]) -> float:
        """評估Europeana資料品質"""
        score = 0

        # 基本資訊
        if item.get("title"):
            score += 15
        if item.get("creator"):
            score += 15
        if item.get("date"):
            score += 10
        if item.get("description"):
            score += 15

        # 媒體資源
        if item.get("thumbnail"):
            score += 15
        if item.get("media"):
            score += 10

        # 元數據豐富度
        if item.get("subject"):
            score += 10
        if item.get("provider"):
            score += 5
        if item.get("rights"):
            score += 5

        return min(score, 100.0)

    def _assess_scholar_quality(self, paper: dict[str, Any]) -> float:
        """評估學術論文品質"""
        score = 0

        # 基本資訊
        if paper.get("title"):
            score += 20
        if paper.get("authors"):
            score += 15
        if paper.get("year"):
            score += 10
        if paper.get("abstract"):
            score += 15

        # 學術指標
        citations = paper.get("citationCount", 0)
        if citations > 100:
            score += 20
        elif citations > 50:
            score += 15
        elif citations > 10:
            score += 10
        elif citations > 1:
            score += 5

        # 資源可及性
        if paper.get("pdfUrl"):
            score += 20

        return min(score, 100.0)

    def _assess_harvard_quality(self, item: dict[str, Any]) -> float:
        """評估Harvard Art Museums資料品質"""
        score = 0

        # 基本資訊完整性 (35分)
        if item.get("title") and item.get("title") != "Untitled":
            score += 10
        if item.get("people") and len(item["people"]) > 0:
            score += 10
        if item.get("dated") or item.get("century"):
            score += 8
        if item.get("medium"):
            score += 7

        # 圖像資源 (20分)
        if item.get("primaryImage"):
            score += 12
        if item.get("images") and len(item["images"]) > 1:
            score += 8

        # 學術價值 (25分)
        if item.get("description"):
            score += 8
        if item.get("commentary"):
            score += 8
        if item.get("provenance"):
            score += 9

        # 收藏完整性 (20分)
        if item.get("accessionYear"):
            score += 5
        if item.get("exhibition"):
            score += 8
        if item.get("publication"):
            score += 7

        return min(score, 100.0)

    def _categorize_harvard_item(self, item: dict[str, Any]) -> list[str]:
        """分類Harvard Art Museums項目"""
        categories = ["harvard_collection", "museum"]

        # 按分類
        if item.get("classification"):
            categories.append(f"classification:{item['classification'].lower().replace(' ', '_')}")

        # 按文化
        if item.get("culture"):
            categories.append(f"culture:{item['culture'].lower().replace(' ', '_')}")

        # 按時期
        if item.get("period"):
            categories.append(f"period:{item['period'].lower().replace(' ', '_')}")

        # 按世紀
        if item.get("century"):
            categories.append(f"century:{item['century'].lower().replace(' ', '_')}")

        # 按部門
        if item.get("department"):
            categories.append(f"department:{item['department'].lower().replace(' ', '_')}")

        # 研究價值標籤
        research_value = item.get("researchValue", 0)
        if research_value > 80:
            categories.append("high_research_value")
        elif research_value > 50:
            categories.append("medium_research_value")

        return categories

    def _categorize_met_item(self, item: dict[str, Any]) -> list[str]:
        """分類MET項目"""
        categories = ["artwork", "museum"]

        department = item.get("department", "").lower()
        if "painting" in department:
            categories.append("painting")
        if "sculpture" in department:
            categories.append("sculpture")
        if "architecture" in department:
            categories.append("architecture")

        period = item.get("period", "").lower()
        if "renaissance" in period:
            categories.append("renaissance")
        if "baroque" in period:
            categories.append("baroque")
        if "medieval" in period:
            categories.append("medieval")

        return categories

    def _calculate_quality_distribution(self) -> dict[str, int]:
        """計算品質分佈"""
        distribution = {quality.value: 0 for quality in DataQuality}

        for record in self.data_records:
            if record.quality_score >= 90:
                distribution[DataQuality.VERY_HIGH.value] += 1
            elif record.quality_score >= 75:
                distribution[DataQuality.HIGH.value] += 1
            elif record.quality_score >= 50:
                distribution[DataQuality.MEDIUM.value] += 1
            elif record.quality_score >= 25:
                distribution[DataQuality.LOW.value] += 1
            else:
                distribution[DataQuality.VERY_LOW.value] += 1

        return distribution

    async def _update_source_quality_scores(self):
        """更新資料來源品質分數"""
        for source_id, source_info in self.data_sources.items():
            source_records = [r for r in self.data_records if r.source_id == source_id]

            if source_records:
                avg_quality = sum(r.quality_score for r in source_records) / len(source_records)
                source_info.quality_score = avg_quality
                source_info.last_updated = datetime.now()

    def get_high_quality_records(self, min_quality: float = 75.0) -> list[DataRecord]:
        """取得高品質記錄"""
        return [record for record in self.data_records if record.quality_score >= min_quality]

    def get_records_by_category(self, category: str) -> list[DataRecord]:
        """依類別取得記錄"""
        return [record for record in self.data_records if category in record.categories]

    def get_records_by_language(self, language: str) -> list[DataRecord]:
        """依語言取得記錄"""
        return [record for record in self.data_records if record.language == language]

    def get_source_statistics(self) -> dict[str, Any]:
        """取得資料來源統計"""
        stats = {}

        for source_id, source_info in self.data_sources.items():
            source_records = [r for r in self.data_records if r.source_id == source_id]

            stats[source_id] = {
                "name": source_info.name,
                "type": source_info.type.value,
                "priority": source_info.priority,
                "record_count": len(source_records),
                "avg_quality": source_info.quality_score,
                "categories": list(set(cat for r in source_records for cat in r.categories)),
                "languages": list(set(r.language for r in source_records)),
                "last_updated": source_info.last_updated.isoformat()
                if source_info.last_updated
                else None,
            }

        return stats

    async def export_enhanced_dataset(self, output_path: str = "data/output/enhanced_dataset.json"):
        """匯出增強的資料集"""
        dataset = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_sources": len(self.data_sources),
                "total_records": len(self.data_records),
                "quality_distribution": self._calculate_quality_distribution(),
                "source_statistics": self.get_source_statistics(),
            },
            "data_sources": {
                source_id: {
                    "name": info.name,
                    "type": info.type.value,
                    "priority": info.priority,
                    "quality_score": info.quality_score,
                    "categories": info.categories,
                }
                for source_id, info in self.data_sources.items()
            },
            "records": [
                {
                    "record_id": record.record_id,
                    "source_id": record.source_id,
                    "title": record.title,
                    "content": record.content,
                    "quality_score": record.quality_score,
                    "relevance_score": record.relevance_score,
                    "language": record.language,
                    "categories": record.categories,
                    "timestamp": record.timestamp.isoformat(),
                }
                for record in self.data_records
            ],
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 增強資料集已匯出至: {output_path}")
        return output_path


# 使用示例
if __name__ == "__main__":

    async def main():
        manager = EnhancedDataSourcesManager()

        # 載入所有資料
        results = await manager.load_all_data()
        print(f"載入結果: {json.dumps(results, indent=2, ensure_ascii=False)}")

        # 取得高品質記錄
        high_quality = manager.get_high_quality_records(min_quality=80.0)
        print(f"高品質記錄數: {len(high_quality)}")

        # 匯出增強資料集
        dataset_path = await manager.export_enhanced_dataset()
        print(f"資料集匯出至: {dataset_path}")

    asyncio.run(main())
