#!/usr/bin/env python3
"""
為 Neo4j 資料庫添加資料來源標記
標記資料來自 WikiArt、Met Museum 或其他來源
"""

import logging

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SourceMetadataAdder:
    def __init__(self):
        self.uri = "bolt://localhost:7687"
        self.username = "neo4j"
        self.password = "CHANGE_ME_NEO4J_PASSWORD"
        self.driver = None

        self.stats = {
            "artists_wikiart": 0,
            "artists_met": 0,
            "artworks_met": 0,
            "artworks_other": 0,
            "total_updated": 0,
        }

    def connect(self):
        """連接到 Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # 測試連接
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
            logger.info("✅ 成功連接到 Neo4j")
            return True
        except Exception as e:
            logger.error(f"❌ 連接失敗: {e}")
            return False

    def add_wikiart_source_to_artists(self):
        """為 WikiArt 藝術家添加來源標記"""
        logger.info("\n📊 為 WikiArt 藝術家添加來源...")

        with self.driver.session() as session:
            # 查詢並更新 WikiArt 藝術家
            query = """
            MATCH (a:Artist)
            WHERE a.url IS NOT NULL
              AND (a.url CONTAINS 'wikiart' OR a.url CONTAINS 'WikiArt')
              AND a.original_source IS NULL
            SET a.original_source = 'WikiArt',
                a.source_type = 'api',
                a.source_url = a.url
            RETURN count(a) as count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0

            self.stats["artists_wikiart"] = count
            logger.info(f"✅ 更新了 {count} 位 WikiArt 藝術家")

            return count

    def add_met_source_to_artists(self):
        """為 Met Museum 藝術家添加來源標記"""
        logger.info("\n📊 為 Met Museum 藝術家添加來源...")

        with self.driver.session() as session:
            # 查詢並更新 Met Museum 藝術家（透過作品關聯）
            query = """
            MATCH (a:Artist)<-[:CREATED_BY]-(w:Artwork)
            WHERE w.objectID IS NOT NULL
              AND a.original_source IS NULL
            WITH DISTINCT a
            SET a.original_source = 'Met Museum API',
                a.source_type = 'api'
            RETURN count(a) as count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0

            self.stats["artists_met"] = count
            logger.info(f"✅ 更新了 {count} 位 Met Museum 藝術家")

            return count

    def add_met_source_to_artworks(self):
        """為 Met Museum 作品添加來源標記"""
        logger.info("\n📊 為 Met Museum 作品添加來源...")

        with self.driver.session() as session:
            # 查詢並更新 Met Museum 作品
            query = """
            MATCH (w:Artwork)
            WHERE w.objectID IS NOT NULL
              AND w.original_source IS NULL
            SET w.original_source = 'Met Museum API',
                w.source_type = 'api',
                w.source_url = 'https://www.metmuseum.org/art/collection/search/' + toString(w.objectID)
            RETURN count(w) as count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0

            self.stats["artworks_met"] = count
            logger.info(f"✅ 更新了 {count} 件 Met Museum 作品")

            return count

    def add_other_source_to_artworks(self):
        """為其他來源的作品添加標記"""
        logger.info("\n📊 為其他來源作品添加來源...")

        with self.driver.session() as session:
            # 為沒有 objectID 的作品標記為其他來源
            query = """
            MATCH (w:Artwork)
            WHERE w.objectID IS NULL
              AND w.original_source IS NULL
            SET w.original_source = 'Internal Knowledge Base',
                w.source_type = 'curated'
            RETURN count(w) as count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0

            self.stats["artworks_other"] = count
            logger.info(f"✅ 更新了 {count} 件內部知識庫作品")

            return count

    def verify_updates(self):
        """驗證更新結果"""
        logger.info("\n📊 驗證更新結果...")

        with self.driver.session() as session:
            # 統計各來源的數量
            queries = {
                "WikiArt 藝術家": """
                    MATCH (a:Artist)
                    WHERE a.original_source = 'WikiArt'
                    RETURN count(a) as count
                """,
                "Met Museum 藝術家": """
                    MATCH (a:Artist)
                    WHERE a.original_source = 'Met Museum API'
                    RETURN count(a) as count
                """,
                "Met Museum 作品": """
                    MATCH (w:Artwork)
                    WHERE w.original_source = 'Met Museum API'
                    RETURN count(w) as count
                """,
                "內部知識庫作品": """
                    MATCH (w:Artwork)
                    WHERE w.original_source = 'Internal Knowledge Base'
                    RETURN count(w) as count
                """,
                "未標記的節點": """
                    MATCH (n)
                    WHERE n:Artist OR n:Artwork
                      AND n.original_source IS NULL
                    RETURN count(n) as count
                """,
            }

            logger.info("\n" + "=" * 60)
            logger.info("資料來源統計:")
            logger.info("=" * 60)

            for label, query in queries.items():
                result = session.run(query)
                record = result.single()
                count = record["count"] if record else 0
                logger.info(f"{label}: {count}")

    def add_source_collection_metadata(self):
        """為所有節點添加集合來源資訊"""
        logger.info("\n📊 添加資料庫集合標記...")

        with self.driver.session() as session:
            # 為所有已標記的節點添加 source_database 和 source_collection
            query = """
            MATCH (n)
            WHERE (n:Artist OR n:Artwork)
              AND n.original_source IS NOT NULL
              AND n.source_database IS NULL
            SET n.source_database = 'neo4j',
                n.source_collection = 'graph_database'
            RETURN count(n) as count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0

            logger.info(f"✅ 為 {count} 個節點添加了資料庫集合標記")
            return count

    def run(self):
        """執行所有更新"""
        logger.info("🚀 開始為 Neo4j 添加資料來源標記...\n")

        if not self.connect():
            return False

        try:
            # 1. 為 WikiArt 藝術家添加來源
            self.add_wikiart_source_to_artists()

            # 2. 為 Met Museum 藝術家添加來源
            self.add_met_source_to_artists()

            # 3. 為 Met Museum 作品添加來源
            self.add_met_source_to_artworks()

            # 4. 為其他作品添加來源
            self.add_other_source_to_artworks()

            # 5. 添加資料庫集合標記
            self.add_source_collection_metadata()

            # 6. 驗證更新
            self.verify_updates()

            # 計算總數
            self.stats["total_updated"] = (
                self.stats["artists_wikiart"]
                + self.stats["artists_met"]
                + self.stats["artworks_met"]
                + self.stats["artworks_other"]
            )

            # 顯示統計
            logger.info("\n" + "=" * 60)
            logger.info("更新統計:")
            logger.info("=" * 60)
            logger.info(f"WikiArt 藝術家: {self.stats['artists_wikiart']}")
            logger.info(f"Met Museum 藝術家: {self.stats['artists_met']}")
            logger.info(f"Met Museum 作品: {self.stats['artworks_met']}")
            logger.info(f"內部知識庫作品: {self.stats['artworks_other']}")
            logger.info(f"總更新數: {self.stats['total_updated']}")
            logger.info("=" * 60)

            logger.info("\n✅ 資料來源標記添加完成！")

            logger.info("\n💡 下一步:")
            logger.info("   1. 測試多資料庫檢索:")
            logger.info("      node test-multi-database-retrieval.js")
            logger.info("")
            logger.info("   2. 創建多資料庫 RAG 服務器")
            logger.info("   3. 更新 OpenWebUI v4.0")

            return True

        except Exception as e:
            logger.error(f"❌ 執行失敗: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            if self.driver:
                self.driver.close()
                logger.info("\n🔌 已關閉 Neo4j 連接")


def main():
    adder = SourceMetadataAdder()
    success = adder.run()

    if success:
        logger.info("\n🎉 成功！")
        return 0
    else:
        logger.error("\n❌ 失敗")
        return 1


if __name__ == "__main__":
    exit(main())
