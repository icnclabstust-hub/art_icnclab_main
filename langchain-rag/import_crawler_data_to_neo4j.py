#!/usr/bin/env python3
"""
Neo4j爬蟲數據導入工具
將新收集的爬蟲數據導入Neo4j知識圖譜，並整合到GraphRAG系統
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable
except ImportError:
    print("❌ 需要安裝neo4j驅動: pip install neo4j")
    sys.exit(1)


class Neo4jCrawlerDataImporter:
    """Neo4j爬蟲數據導入器"""

    def __init__(
        self, uri="bolt://localhost:7687", username="neo4j", password="CHANGE_ME_NEO4J_PASSWORD"
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.import_stats = {
            "artists_created": 0,
            "artworks_created": 0,
            "museums_created": 0,
            "movements_created": 0,
            "relationships_created": 0,
            "total_processing_time": 0,
        }

    def connect(self) -> bool:
        """連接到Neo4j數據庫"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # 測試連接
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                if result.single()["test"] == 1:
                    logging.info("✅ 成功連接到Neo4j數據庫")
                    return True
        except ServiceUnavailable:
            logging.error("❌ 無法連接到Neo4j數據庫。請確保Neo4j服務正在運行。")
            return False
        except AuthError:
            logging.error("❌ Neo4j認證失敗。請檢查用戶名和密碼。")
            return False
        except Exception as e:
            logging.error(f"❌ 連接Neo4j時發生錯誤: {e}")
            return False

    def close(self):
        """關閉數據庫連接"""
        if self.driver:
            self.driver.close()

    def create_constraints_and_indexes(self):
        """創建約束和索引"""
        constraints_queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (w:Artwork) REQUIRE w.title IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Museum) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Style) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Period) REQUIRE p.name IS UNIQUE",
        ]

        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (a:Artist) ON (a.nationality)",
            "CREATE INDEX IF NOT EXISTS FOR (w:Artwork) ON (w.date)",
            "CREATE INDEX IF NOT EXISTS FOR (w:Artwork) ON (w.medium)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Museum) ON (m.location)",
        ]

        with self.driver.session() as session:
            for query in constraints_queries + index_queries:
                try:
                    session.run(query)
                    logging.info(f"✅ 執行成功: {query[:50]}...")
                except Exception as e:
                    logging.warning(f"⚠️ 執行失敗: {query[:50]}... - {e}")

    def import_europeana_data(self, file_path: str):
        """導入Europeana數據"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            with self.driver.session() as session:
                for item in data:
                    if not item.get("title"):
                        continue

                    # 創建藝術作品節點
                    artwork_query = """
                    MERGE (a:Artwork {title: $title})
                    SET a.source = 'Europeana',
                        a.description = $description,
                        a.date = $date,
                        a.type = $type,
                        a.url = $url,
                        a.created_at = datetime()
                    RETURN a
                    """

                    session.run(
                        artwork_query,
                        {
                            "title": item.get("title", ""),
                            "description": item.get("description", ""),
                            "date": item.get("date", ""),
                            "type": item.get("type", ""),
                            "url": item.get("edmIsShownAt", ""),
                        },
                    )
                    self.import_stats["artworks_created"] += 1

                    # 創建創作者節點和關係
                    if item.get("creator"):
                        creator_query = """
                        MERGE (artist:Artist {name: $name})
                        SET artist.source = 'Europeana',
                            artist.created_at = datetime()
                        WITH artist
                        MATCH (artwork:Artwork {title: $title})
                        MERGE (artist)-[:CREATED]->(artwork)
                        """

                        session.run(
                            creator_query, {"name": item.get("creator"), "title": item.get("title")}
                        )
                        self.import_stats["artists_created"] += 1
                        self.import_stats["relationships_created"] += 1

                    # 處理主題標籤
                    if item.get("subject"):
                        subjects = (
                            item["subject"]
                            if isinstance(item["subject"], list)
                            else [item["subject"]]
                        )
                        for subject in subjects:
                            subject_query = """
                            MERGE (s:Subject {name: $name})
                            SET s.source = 'Europeana',
                                s.created_at = datetime()
                            WITH s
                            MATCH (artwork:Artwork {title: $title})
                            MERGE (artwork)-[:HAS_SUBJECT]->(s)
                            """

                            session.run(
                                subject_query, {"name": subject.strip(), "title": item.get("title")}
                            )
                            self.import_stats["relationships_created"] += 1

            logging.info(f"✅ Europeana數據導入完成: {file_path}")

        except Exception as e:
            logging.error(f"❌ 導入Europeana數據失敗 {file_path}: {e}")

    def import_harvard_data(self, file_path: str):
        """導入Harvard數據"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            with self.driver.session() as session:
                if "objects" in file_path:
                    # 處理藝術作品
                    for item in data.get("records", []):
                        if not item.get("title"):
                            continue

                        artwork_query = """
                        MERGE (a:Artwork {title: $title})
                        SET a.source = 'Harvard Art Museums',
                            a.classification = $classification,
                            a.medium = $medium,
                            a.dated = $dated,
                            a.culture = $culture,
                            a.description = $description,
                            a.url = $url,
                            a.created_at = datetime()
                        RETURN a
                        """

                        session.run(
                            artwork_query,
                            {
                                "title": item.get("title", ""),
                                "classification": item.get("classification", ""),
                                "medium": item.get("medium", ""),
                                "dated": item.get("dated", ""),
                                "culture": item.get("culture", ""),
                                "description": item.get("description", ""),
                                "url": item.get("url", ""),
                            },
                        )
                        self.import_stats["artworks_created"] += 1

                        # 處理藝術家
                        if item.get("people"):
                            for person in item["people"]:
                                if person.get("role") in ["Artist", "Creator"] and person.get(
                                    "name"
                                ):
                                    artist_query = """
                                    MERGE (artist:Artist {name: $name})
                                    SET artist.source = 'Harvard Art Museums',
                                        artist.role = $role,
                                        artist.created_at = datetime()
                                    WITH artist
                                    MATCH (artwork:Artwork {title: $title})
                                    MERGE (artist)-[:CREATED]->(artwork)
                                    """

                                    session.run(
                                        artist_query,
                                        {
                                            "name": person.get("name"),
                                            "role": person.get("role"),
                                            "title": item.get("title"),
                                        },
                                    )
                                    self.import_stats["artists_created"] += 1
                                    self.import_stats["relationships_created"] += 1

                elif "people" in file_path:
                    # 處理人物數據
                    for person in data.get("records", []):
                        if not person.get("displayname"):
                            continue

                        person_query = """
                        MERGE (p:Artist {name: $name})
                        SET p.source = 'Harvard Art Museums',
                            p.birthyear = $birthyear,
                            p.deathyear = $deathyear,
                            p.nationality = $nationality,
                            p.biography = $biography,
                            p.url = $url,
                            p.created_at = datetime()
                        RETURN p
                        """

                        session.run(
                            person_query,
                            {
                                "name": person.get("displayname", ""),
                                "birthyear": person.get("birthyear"),
                                "deathyear": person.get("deathyear"),
                                "nationality": person.get("nationality", ""),
                                "biography": person.get("biography", ""),
                                "url": person.get("url", ""),
                            },
                        )
                        self.import_stats["artists_created"] += 1

                elif "exhibitions" in file_path:
                    # 處理展覽數據
                    for exhibition in data.get("records", []):
                        if not exhibition.get("title"):
                            continue

                        exhibition_query = """
                        MERGE (e:Exhibition {title: $title})
                        SET e.source = 'Harvard Art Museums',
                            e.begindate = $begindate,
                            e.enddate = $enddate,
                            e.venue = $venue,
                            e.description = $description,
                            e.url = $url,
                            e.created_at = datetime()
                        RETURN e
                        """

                        session.run(
                            exhibition_query,
                            {
                                "title": exhibition.get("title", ""),
                                "begindate": exhibition.get("begindate", ""),
                                "enddate": exhibition.get("enddate", ""),
                                "venue": exhibition.get("venue", ""),
                                "description": exhibition.get("description", ""),
                                "url": exhibition.get("url", ""),
                            },
                        )

            logging.info(f"✅ Harvard數據導入完成: {file_path}")

        except Exception as e:
            logging.error(f"❌ 導入Harvard數據失敗 {file_path}: {e}")

    def import_museum_data(self, file_path: str):
        """導入博物館數據"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            with self.driver.session() as session:
                for item in data:
                    if not item.get("title"):
                        continue

                    # 創建藝術作品
                    artwork_query = """
                    MERGE (a:Artwork {title: $title})
                    SET a.source = 'Metropolitan Museum',
                        a.medium = $medium,
                        a.date = $date,
                        a.department = $department,
                        a.culture = $culture,
                        a.url = $url,
                        a.created_at = datetime()
                    RETURN a
                    """

                    session.run(
                        artwork_query,
                        {
                            "title": item.get("title", ""),
                            "medium": item.get("medium", ""),
                            "date": item.get("objectDate", ""),
                            "department": item.get("department", ""),
                            "culture": item.get("culture", ""),
                            "url": item.get("objectURL", ""),
                        },
                    )
                    self.import_stats["artworks_created"] += 1

                    # 創建藝術家
                    if item.get("artistDisplayName"):
                        artist_query = """
                        MERGE (artist:Artist {name: $name})
                        SET artist.source = 'Metropolitan Museum',
                            artist.created_at = datetime()
                        WITH artist
                        MATCH (artwork:Artwork {title: $title})
                        MERGE (artist)-[:CREATED]->(artwork)
                        """

                        session.run(
                            artist_query,
                            {"name": item.get("artistDisplayName"), "title": item.get("title")},
                        )
                        self.import_stats["artists_created"] += 1
                        self.import_stats["relationships_created"] += 1

                    # 創建博物館節點
                    museum_query = """
                    MERGE (m:Museum {name: 'Metropolitan Museum of Art'})
                    SET m.location = 'New York',
                        m.source = 'Metropolitan Museum',
                        m.created_at = datetime()
                    WITH m
                    MATCH (artwork:Artwork {title: $title})
                    MERGE (m)-[:HOUSES]->(artwork)
                    """

                    session.run(museum_query, {"title": item.get("title")})
                    self.import_stats["museums_created"] += 1
                    self.import_stats["relationships_created"] += 1

            logging.info(f"✅ 博物館數據導入完成: {file_path}")

        except Exception as e:
            logging.error(f"❌ 導入博物館數據失敗 {file_path}: {e}")

    def discover_and_import_all_data(self):
        """發現並導入所有爬蟲數據"""
        start_time = time.time()

        # 導入Europeana數據
        europeana_files = list(Path("../data/raw/").glob("*europeana*.json"))
        for file_path in europeana_files:
            self.import_europeana_data(str(file_path))

        # 導入Harvard數據
        harvard_files = list(Path("harvard_data/").glob("*.json"))
        for file_path in harvard_files:
            if file_path.name != "modern_art.json":  # 排除舊數據
                self.import_harvard_data(str(file_path))

        # 導入博物館數據
        museum_files = list(Path("../data/raw/").glob("*met_museum*.json"))
        for file_path in museum_files:
            self.import_museum_data(str(file_path))

        self.import_stats["total_processing_time"] = time.time() - start_time

    def create_enhanced_relationships(self):
        """創建增強的關係"""
        enhancement_queries = [
            # 基於時期創建關係
            """
            MATCH (a:Artist), (w:Artwork)
            WHERE a.name = w.title OR w.title CONTAINS a.name
            AND NOT (a)-[:CREATED]->(w)
            MERGE (a)-[:CREATED]->(w)
            """,
            # 基於風格創建關係
            """
            MATCH (a1:Artist), (a2:Artist)
            WHERE a1.nationality = a2.nationality
            AND a1.name <> a2.name
            AND abs(coalesce(a1.birthyear, 1900) - coalesce(a2.birthyear, 1900)) <= 50
            MERGE (a1)-[:CONTEMPORARY_OF]->(a2)
            """,
            # 基於相同文化創建關係
            """
            MATCH (w1:Artwork), (w2:Artwork)
            WHERE w1.culture = w2.culture
            AND w1.title <> w2.title
            AND w1.culture IS NOT NULL
            MERGE (w1)-[:SAME_CULTURE]->(w2)
            """,
        ]

        with self.driver.session() as session:
            for query in enhancement_queries:
                try:
                    result = session.run(query)
                    relationships_created = result.consume().counters.relationships_created
                    self.import_stats["relationships_created"] += relationships_created
                    logging.info(f"✅ 創建了 {relationships_created} 個增強關係")
                except Exception as e:
                    logging.warning(f"⚠️ 創建增強關係時出錯: {e}")

    def get_graph_statistics(self) -> dict[str, Any]:
        """獲取圖譜統計信息"""
        stats_queries = {
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r]-() RETURN count(r) as count",
            "artists_count": "MATCH (n:Artist) RETURN count(n) as count",
            "artworks_count": "MATCH (n:Artwork) RETURN count(n) as count",
            "museums_count": "MATCH (n:Museum) RETURN count(n) as count",
            "exhibitions_count": "MATCH (n:Exhibition) RETURN count(n) as count",
        }

        stats = {}
        with self.driver.session() as session:
            for key, query in stats_queries.items():
                try:
                    result = session.run(query)
                    stats[key] = result.single()["count"]
                except Exception as e:
                    logging.warning(f"⚠️ 獲取統計信息失敗 {key}: {e}")
                    stats[key] = 0

        return stats


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🚀 Neo4j爬蟲數據導入工具")
    print("=" * 60)

    # 創建導入器
    importer = Neo4jCrawlerDataImporter()

    # 連接數據庫
    if not importer.connect():
        print("❌ 無法連接到Neo4j數據庫，請檢查連接設置")
        return

    try:
        # 創建約束和索引
        print("📋 創建數據庫約束和索引...")
        importer.create_constraints_and_indexes()

        # 導入數據
        print("📥 導入爬蟲數據...")
        importer.discover_and_import_all_data()

        # 創建增強關係
        print("🔗 創建增強關係...")
        importer.create_enhanced_relationships()

        # 顯示統計信息
        stats = importer.get_graph_statistics()
        import_stats = importer.import_stats

        print("\n📊 數據導入摘要:")
        print(f"   處理時間: {import_stats['total_processing_time']:.2f}s")
        print(f"   新增藝術家: {import_stats['artists_created']}")
        print(f"   新增藝術作品: {import_stats['artworks_created']}")
        print(f"   新增博物館: {import_stats['museums_created']}")
        print(f"   新增關係: {import_stats['relationships_created']}")

        print("\n📈 最終圖譜統計:")
        print(f"   總節點數: {stats.get('total_nodes', 0):,}")
        print(f"   總關係數: {stats.get('total_relationships', 0):,}")
        print(f"   藝術家數: {stats.get('artists_count', 0):,}")
        print(f"   藝術作品數: {stats.get('artworks_count', 0):,}")
        print(f"   博物館數: {stats.get('museums_count', 0):,}")
        print(f"   展覽數: {stats.get('exhibitions_count', 0):,}")

        print("\n🎉 Neo4j數據導入完成！")
        print("   您的知識圖譜現在包含完整的爬蟲數據")
        print("   可以通過GraphRAG進行複雜的關係查詢")

    finally:
        importer.close()


if __name__ == "__main__":
    main()
