#!/usr/bin/env python3
"""
自動化網路爬蟲系統
專門收集藝術史資料並自動傳送給多模態RAG系統
重點：文藝復興和巴洛克時期
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue

import requests
import schedule

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
    handlers=[logging.FileHandler("automated_crawler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """爬蟲配置"""

    # Harvard API
    harvard_api_key: str = "CHANGE_ME_HARVARD_API_KEY"

    # 時期設定
    focus_periods: list[str] = None

    # 排程設定
    auto_crawl_interval_hours: int = 24  # 每24小時自動爬一次
    batch_size: int = 50  # 每批次處理數量

    # 資料來源
    enable_harvard: bool = True
    enable_met: bool = True
    enable_europeana: bool = False  # Europeana需要額外API key

    # 輸出設定
    output_dir: str = "./automated_crawler_data"

    # RAG系統設定
    neo4j_enabled: bool = True
    chromadb_enabled: bool = True
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "your_password"  # noqa: S105 -- 佔位字串，非真實密碼
    chromadb_url: str = "http://localhost:8000"

    def __post_init__(self):
        if self.focus_periods is None:
            self.focus_periods = ["renaissance", "baroque"]


class ArtPeriodDefinitions:
    """藝術時期定義"""

    PERIODS = {
        "renaissance": {
            "name": "文藝復興",
            "display_name": "Renaissance",
            "date_range": (1400, 1600),
            "keywords": [
                "Renaissance",
                "Early Renaissance",
                "High Renaissance",
                "Italian Renaissance",
                "Northern Renaissance",
                "文藝復興",
            ],
            "artists": [
                "Leonardo da Vinci",
                "Michelangelo",
                "Raphael",
                "Botticelli",
                "Titian",
                "Donatello",
                "Brunelleschi",
                "Masaccio",
                "Piero della Francesca",
                "Mantegna",
                "Bellini",
                "Giotto",
                "Albrecht Dürer",
            ],
            "priority": 1,
        },
        "baroque": {
            "name": "巴洛克",
            "display_name": "Baroque",
            "date_range": (1600, 1750),
            "keywords": ["Baroque", "Caravaggism", "Dutch Golden Age", "巴洛克", "荷蘭黃金時代"],
            "artists": [
                "Caravaggio",
                "Rembrandt",
                "Rubens",
                "Velázquez",
                "Vermeer",
                "Bernini",
                "Artemisia Gentileschi",
                "Poussin",
                "Claude Lorrain",
                "Frans Hals",
                "Ribera",
                "Zurbarán",
            ],
            "priority": 1,
        },
        "rococo": {
            "name": "洛可可",
            "display_name": "Rococo",
            "date_range": (1730, 1780),
            "keywords": ["Rococo", "洛可可"],
            "artists": ["Watteau", "Boucher", "Fragonard", "Tiepolo"],
            "priority": 2,
        },
    }


class HarvardCrawler:
    """Harvard Art Museums 爬蟲"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.harvardartmuseums.org"
        self.session = requests.Session()
        self.api_calls = 0

    def search_objects(self, params: dict, max_results: int = 100) -> list[dict]:
        """搜索藝術品"""
        objects = []
        page = 1

        params["apikey"] = self.api_key
        params["size"] = min(100, max_results)

        while len(objects) < max_results:
            params["page"] = page

            try:
                response = self.session.get(f"{self.base_url}/object", params=params, timeout=30)
                self.api_calls += 1

                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])

                    if not records:
                        break

                    objects.extend(records)

                    # 檢查是否還有更多頁面
                    info = data.get("info", {})
                    if page >= info.get("pages", 1):
                        break

                    page += 1
                    time.sleep(0.5)  # 避免API限制
                else:
                    logger.warning(f"Harvard API 返回狀態碼: {response.status_code}")
                    break

            except Exception as e:
                logger.error(f"Harvard API 請求錯誤: {e}")
                break

        return objects[:max_results]

    def search_by_artist(self, artist_name: str, max_results: int = 50) -> list[dict]:
        """根據藝術家搜索"""
        params = {"person": artist_name}
        return self.search_objects(params, max_results)

    def search_by_keyword(self, keyword: str, max_results: int = 50) -> list[dict]:
        """根據關鍵詞搜索"""
        params = {"keyword": keyword}
        return self.search_objects(params, max_results)

    def search_by_century(self, century: int, max_results: int = 50) -> list[dict]:
        """根據世紀搜索"""
        params = {"century": century}
        return self.search_objects(params, max_results)


class MetMuseumCrawler:
    """Metropolitan Museum 爬蟲"""

    def __init__(self):
        self.base_url = "https://collectionapi.metmuseum.org/public/collection/v1"
        self.session = requests.Session()

    def search_by_artist(self, artist_name: str, max_results: int = 50) -> list[dict]:
        """根據藝術家搜索"""
        objects = []

        try:
            # 搜索作品ID
            search_url = f"{self.base_url}/search"
            params = {"q": artist_name, "hasImages": "true"}

            response = self.session.get(search_url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                object_ids = data.get("objectIDs", [])[:max_results]

                # 獲取作品詳情
                for obj_id in object_ids:
                    try:
                        obj_url = f"{self.base_url}/objects/{obj_id}"
                        obj_response = self.session.get(obj_url, timeout=10)

                        if obj_response.status_code == 200:
                            obj_data = obj_response.json()
                            objects.append(obj_data)
                            time.sleep(0.3)  # 避免過於頻繁

                    except Exception as e:
                        logger.warning(f"獲取Met作品 {obj_id} 失敗: {e}")
                        continue

        except Exception as e:
            logger.error(f"Met Museum 搜索錯誤: {e}")

        return objects


class DataProcessor:
    """資料處理器"""

    def __init__(self):
        pass

    def normalize_artwork(self, artwork: dict, source: str) -> dict:
        """標準化藝術品資料"""
        if source == "harvard":
            return self._normalize_harvard(artwork)
        elif source == "met":
            return self._normalize_met(artwork)
        else:
            return artwork

    def _normalize_harvard(self, artwork: dict) -> dict:
        """標準化Harvard資料"""
        return {
            "id": f"harvard_{artwork.get('id', '')}",
            "source": "harvard",
            "title": artwork.get("title", "Untitled"),
            "artist": self._extract_artist(artwork.get("people", [])),
            "date": artwork.get("dated", ""),
            "period": artwork.get("period", ""),
            "culture": artwork.get("culture", ""),
            "medium": artwork.get("medium", ""),
            "dimensions": artwork.get("dimensions", ""),
            "description": artwork.get("description", ""),
            "image_url": artwork.get("primaryimageurl", ""),
            "url": artwork.get("url", ""),
            "century": artwork.get("century", ""),
            "classification": artwork.get("classification", ""),
            "technique": artwork.get("technique", ""),
            "raw_data": artwork,
        }

    def _normalize_met(self, artwork: dict) -> dict:
        """標準化Met資料"""
        return {
            "id": f"met_{artwork.get('objectID', '')}",
            "source": "met",
            "title": artwork.get("title", "Untitled"),
            "artist": artwork.get("artistDisplayName", ""),
            "date": artwork.get("objectDate", ""),
            "period": artwork.get("period", ""),
            "culture": artwork.get("culture", ""),
            "medium": artwork.get("medium", ""),
            "dimensions": artwork.get("dimensions", ""),
            "description": artwork.get("objectName", ""),
            "image_url": artwork.get("primaryImage", ""),
            "url": artwork.get("objectURL", ""),
            "classification": artwork.get("classification", ""),
            "department": artwork.get("department", ""),
            "raw_data": artwork,
        }

    def _extract_artist(self, people: list[dict]) -> str:
        """從Harvard people欄位提取藝術家名稱"""
        if not people:
            return ""

        for person in people:
            if person.get("role") in ["Artist", "Painter", "Sculptor"]:
                return person.get("name", "")

        return people[0].get("name", "") if people else ""

    def deduplicate(self, artworks: list[dict]) -> list[dict]:
        """去除重複資料"""
        seen_ids = set()
        unique_artworks = []

        for artwork in artworks:
            artwork_id = artwork.get("id")
            if artwork_id and artwork_id not in seen_ids:
                seen_ids.add(artwork_id)
                unique_artworks.append(artwork)

        return unique_artworks


class RAGSystemIntegration:
    """RAG系統整合"""

    def __init__(self, config: CrawlerConfig):
        self.config = config

    def send_to_neo4j(self, artworks: list[dict]) -> bool:
        """傳送資料到Neo4j"""
        if not self.config.neo4j_enabled:
            return True

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                self.config.neo4j_url, auth=(self.config.neo4j_user, self.config.neo4j_password)
            )

            with driver.session() as session:
                for artwork in artworks:
                    session.run(
                        """
                        MERGE (a:Artwork {id: $id})
                        SET a.title = $title,
                            a.artist = $artist,
                            a.date = $date,
                            a.period = $period,
                            a.source = $source,
                            a.image_url = $image_url,
                            a.description = $description
                    """,
                        artwork,
                    )

            driver.close()
            logger.info(f"✅ 成功傳送 {len(artworks)} 件作品到 Neo4j")
            return True

        except Exception as e:
            logger.error(f"❌ Neo4j 傳送失敗: {e}")
            return False

    def send_to_chromadb(self, artworks: list[dict]) -> bool:
        """傳送資料到ChromaDB"""
        if not self.config.chromadb_enabled:
            return True

        try:
            import chromadb

            client = chromadb.HttpClient(
                host=self.config.chromadb_url.replace("http://", "").split(":")[0],
                port=int(self.config.chromadb_url.split(":")[-1]),
            )

            collection = client.get_or_create_collection(name="art_history")

            # 準備資料
            ids = [artwork["id"] for artwork in artworks]
            documents = [
                f"{artwork['title']} by {artwork['artist']}. {artwork['description']}"
                for artwork in artworks
            ]
            metadatas = [
                {
                    "title": artwork["title"],
                    "artist": artwork["artist"],
                    "period": artwork["period"],
                    "source": artwork["source"],
                }
                for artwork in artworks
            ]

            collection.add(ids=ids, documents=documents, metadatas=metadatas)

            logger.info(f"✅ 成功傳送 {len(artworks)} 件作品到 ChromaDB")
            return True

        except Exception as e:
            logger.error(f"❌ ChromaDB 傳送失敗: {e}")
            return False


class AutomatedCrawlerSystem:
    """自動化爬蟲系統"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化爬蟲
        self.harvard_crawler = (
            HarvardCrawler(config.harvard_api_key) if config.enable_harvard else None
        )
        self.met_crawler = MetMuseumCrawler() if config.enable_met else None

        # 初始化處理器
        self.processor = DataProcessor()
        self.rag_integration = RAGSystemIntegration(config)

        # 資料佇列
        self.data_queue = Queue()

        # 統計
        self.stats = {
            "total_crawled": 0,
            "total_processed": 0,
            "total_sent_to_rag": 0,
            "last_crawl_time": None,
        }

    def crawl_period(self, period_id: str) -> list[dict]:
        """爬取特定時期資料"""
        if period_id not in ArtPeriodDefinitions.PERIODS:
            logger.warning(f"未知時期: {period_id}")
            return []

        period = ArtPeriodDefinitions.PERIODS[period_id]
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🎨 開始爬取: {period['name']} ({period['display_name']})")
        logger.info(f"{'=' * 60}")

        all_artworks = []

        # Harvard爬取
        if self.harvard_crawler:
            logger.info(f"\n📚 Harvard Art Museums - {period['name']}")

            # 依藝術家爬取
            for artist in period["artists"][:10]:
                logger.info(f"  搜索藝術家: {artist}")
                artworks = self.harvard_crawler.search_by_artist(artist, max_results=30)

                # 標準化資料
                normalized = [self.processor.normalize_artwork(a, "harvard") for a in artworks]
                all_artworks.extend(normalized)
                logger.info(f"  ✅ 找到 {len(artworks)} 件作品")

            # 依關鍵詞爬取
            for keyword in period["keywords"][:3]:
                logger.info(f"  搜索關鍵詞: {keyword}")
                artworks = self.harvard_crawler.search_by_keyword(keyword, max_results=20)

                normalized = [self.processor.normalize_artwork(a, "harvard") for a in artworks]
                all_artworks.extend(normalized)
                logger.info(f"  ✅ 找到 {len(artworks)} 件作品")

        # Met Museum爬取
        if self.met_crawler:
            logger.info(f"\n🏛️ Met Museum - {period['name']}")

            for artist in period["artists"][:5]:
                logger.info(f"  搜索藝術家: {artist}")
                artworks = self.met_crawler.search_by_artist(artist, max_results=20)

                normalized = [self.processor.normalize_artwork(a, "met") for a in artworks]
                all_artworks.extend(normalized)
                logger.info(f"  ✅ 找到 {len(artworks)} 件作品")

        # 去除重複
        unique_artworks = self.processor.deduplicate(all_artworks)
        logger.info(f"\n✅ {period['name']} 共獲取 {len(unique_artworks)} 件獨特作品")

        return unique_artworks

    def process_and_send(self, artworks: list[dict]):
        """處理並傳送資料到RAG系統"""
        if not artworks:
            return

        logger.info(f"\n📤 開始傳送 {len(artworks)} 件作品到RAG系統...")

        # 傳送到Neo4j
        neo4j_success = self.rag_integration.send_to_neo4j(artworks)

        # 傳送到ChromaDB
        chromadb_success = self.rag_integration.send_to_chromadb(artworks)

        if neo4j_success and chromadb_success:
            self.stats["total_sent_to_rag"] += len(artworks)
            logger.info("✅ 成功傳送所有資料到RAG系統")
        else:
            logger.warning("⚠️ 部分資料傳送失敗")

    def save_artworks(self, artworks: list[dict], period_id: str):
        """保存藝術品資料"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{period_id}_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(artworks, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 資料已保存: {filepath}")

    def run_single_crawl(self):
        """執行單次爬取"""
        logger.info("\n" + "=" * 60)
        logger.info("🚀 開始執行自動化爬蟲任務")
        logger.info("=" * 60)

        start_time = datetime.now()
        all_artworks = []

        # 爬取每個重點時期
        for period_id in self.config.focus_periods:
            artworks = self.crawl_period(period_id)
            all_artworks.extend(artworks)

            # 保存資料
            self.save_artworks(artworks, period_id)

            # 立即傳送到RAG系統
            self.process_and_send(artworks)

            self.stats["total_crawled"] += len(artworks)

        # 更新統計
        self.stats["last_crawl_time"] = start_time.isoformat()
        self.stats["total_processed"] += len(all_artworks)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 輸出摘要
        logger.info("\n" + "=" * 60)
        logger.info("📊 爬取任務完成")
        logger.info("=" * 60)
        logger.info(f"總計爬取: {len(all_artworks)} 件作品")
        logger.info(f"傳送到RAG: {self.stats['total_sent_to_rag']} 件")
        logger.info(f"耗時: {duration:.2f} 秒")

        # 保存統計
        self._save_stats()

    def _save_stats(self):
        """保存統計資料"""
        stats_file = self.output_dir / "crawler_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def start_scheduled_crawl(self):
        """啟動排程爬取"""
        logger.info("\n⏰ 啟動自動排程爬蟲")
        logger.info(f"爬取間隔: 每 {self.config.auto_crawl_interval_hours} 小時")
        logger.info(f"重點時期: {', '.join(self.config.focus_periods)}")

        # 立即執行一次
        self.run_single_crawl()

        # 設定排程
        schedule.every(self.config.auto_crawl_interval_hours).hours.do(self.run_single_crawl)

        # 持續運行
        logger.info("\n✅ 排程爬蟲已啟動，按 Ctrl+C 停止")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分鐘檢查一次
        except KeyboardInterrupt:
            logger.info("\n\n⏹️ 爬蟲系統已停止")


def main():
    """主函數"""
    print("\n🤖 自動化藝術史資料爬蟲系統")
    print("=" * 60)
    print("功能：")
    print("  ✅ 自動從網路收集藝術史資料")
    print("  ✅ 重點收集：文藝復興 & 巴洛克時期")
    print("  ✅ 自動處理並傳送到RAG系統")
    print("  ✅ 支援排程自動執行")
    print("=" * 60)

    # 配置
    config = CrawlerConfig(
        focus_periods=["renaissance", "baroque"],
        auto_crawl_interval_hours=24,
        output_dir="./automated_crawler_data",
        # RAG系統配置
        neo4j_enabled=True,
        chromadb_enabled=True,
        neo4j_url="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your_neo4j_password",  # noqa: S106 -- 佔位字串，非真實密碼
        chromadb_url="http://localhost:8000",
    )

    # 詢問用戶
    mode = input("\n選擇模式 (1=立即執行一次, 2=啟動自動排程): ").strip()

    # 創建系統
    system = AutomatedCrawlerSystem(config)

    if mode == "1":
        system.run_single_crawl()
    else:
        system.start_scheduled_crawl()


if __name__ == "__main__":
    main()
