#!/usr/bin/env python3
"""
Neo4j 全文索引創建腳本
為 Artist 和 Artwork 節點創建全文索引以支援模糊匹配
"""

import logging
import os

from neo4j import GraphDatabase

# 配置日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Neo4j 連接配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "CHANGE_ME_NEO4J_PASSWORD")


def create_fulltext_indexes():
    """創建全文索引"""
    driver = None
    try:
        # 連接 Neo4j
        logger.info(f"連接 Neo4j: {NEO4J_URI}")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        logger.info("✅ Neo4j 連接成功")

        with driver.session() as session:
            # 檢查現有索引
            logger.info("\n📋 檢查現有索引...")
            result = session.run("SHOW INDEXES")
            existing_indexes = [record["name"] for record in result]
            logger.info(f"現有索引: {existing_indexes}")

            # 定義要創建的全文索引
            indexes_to_create = [
                {
                    "name": "artist_name_fulltext",
                    "query": "CREATE FULLTEXT INDEX artist_name_fulltext IF NOT EXISTS FOR (n:Artist) ON EACH [n.name]",
                    "description": "Artist 名稱全文索引",
                },
                {
                    "name": "artwork_title_fulltext",
                    "query": "CREATE FULLTEXT INDEX artwork_title_fulltext IF NOT EXISTS FOR (n:Artwork) ON EACH [n.title]",
                    "description": "Artwork 標題全文索引",
                },
                {
                    "name": "artwork_description_fulltext",
                    "query": "CREATE FULLTEXT INDEX artwork_description_fulltext IF NOT EXISTS FOR (n:Artwork) ON EACH [n.description]",
                    "description": "Artwork 描述全文索引",
                },
            ]

            # 創建索引
            logger.info("\n🔨 創建全文索引...")
            for index_def in indexes_to_create:
                try:
                    if index_def["name"] in existing_indexes:
                        logger.info(f"   ⏭️  {index_def['description']} 已存在，跳過")
                    else:
                        session.run(index_def["query"])
                        logger.info(f"   ✅ {index_def['description']} 創建成功")
                except Exception as e:
                    logger.error(f"   ❌ {index_def['description']} 創建失敗: {e}")

            # 等待索引上線
            logger.info("\n⏳ 等待索引上線...")
            import time

            time.sleep(2)  # 給索引一些時間來初始化

            # 驗證索引
            logger.info("\n✅ 驗證索引...")
            result = session.run("SHOW INDEXES")
            all_indexes = []
            for record in result:
                index_info = {
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "state": record.get("state"),
                    "labels": record.get("labelsOrTypes", []),
                }
                all_indexes.append(index_info)
                if "fulltext" in index_info["name"].lower():
                    logger.info(
                        f"   📌 {index_info['name']}: "
                        f"{index_info['type']} | "
                        f"狀態: {index_info['state']} | "
                        f"標籤: {index_info['labels']}"
                    )

            # 測試全文搜索
            logger.info("\n🧪 測試全文搜索...")
            test_searches = [
                ("Leonardo", "測試 'Leonardo' 搜索藝術家"),
                ("Vinci~", "測試 'Vinci~' 模糊搜索藝術家"),
                ("Mona", "測試 'Mona' 搜索作品"),
            ]

            for search_term, description in test_searches:
                try:
                    # 測試藝術家搜索
                    artist_query = """
                    CALL db.index.fulltext.queryNodes('artist_name_fulltext', $search_term)
                    YIELD node, score
                    RETURN node.name AS name, score
                    LIMIT 3
                    """
                    result = session.run(artist_query, search_term=search_term)
                    records = list(result)

                    if records:
                        logger.info(f"   ✅ {description}")
                        for record in records:
                            logger.info(f"      - {record['name']} (分數: {record['score']:.2f})")
                    else:
                        logger.info(f"   ℹ️  {description} - 無結果")

                    # 測試作品搜索
                    artwork_query = """
                    CALL db.index.fulltext.queryNodes('artwork_title_fulltext', $search_term)
                    YIELD node, score
                    RETURN node.title AS title, score
                    LIMIT 3
                    """
                    result = session.run(artwork_query, search_term=search_term)
                    records = list(result)

                    if records:
                        for record in records:
                            logger.info(f"      - {record['title']} (分數: {record['score']:.2f})")

                except Exception as e:
                    logger.error(f"   ❌ {description} 失敗: {e}")

            logger.info("\n" + "=" * 80)
            logger.info("🎉 全文索引設置完成！")
            logger.info("=" * 80)
            logger.info("\n使用方法示例:")
            logger.info(
                "1. 精確搜索: CALL db.index.fulltext.queryNodes('artist_name_fulltext', 'Leonardo')"
            )
            logger.info(
                "2. 模糊搜索: CALL db.index.fulltext.queryNodes('artist_name_fulltext', 'Leonarda~')"
            )
            logger.info(
                "3. 多詞搜索: CALL db.index.fulltext.queryNodes('artist_name_fulltext', 'Leonardo Vinci')"
            )
            logger.info("\n支援的查詢操作符:")
            logger.info("  - ~  : 模糊匹配 (最多2個字符差異)")
            logger.info("  - *  : 前綴匹配")
            logger.info("  - AND/OR : 布林運算")
            logger.info('  - "..." : 精確短語匹配')

    except Exception as e:
        logger.error(f"❌ 創建全文索引失敗: {e}")
        raise
    finally:
        if driver:
            driver.close()
            logger.info("\n✅ Neo4j 連接已關閉")


def check_index_statistics():
    """檢查索引統計信息"""
    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

        with driver.session() as session:
            # 統計節點數量
            logger.info("\n📊 數據庫統計:")

            artist_count = session.run("MATCH (a:Artist) RETURN count(a) as count").single()[
                "count"
            ]
            logger.info(f"   藝術家節點: {artist_count}")

            artwork_count = session.run("MATCH (a:Artwork) RETURN count(a) as count").single()[
                "count"
            ]
            logger.info(f"   作品節點: {artwork_count}")

            # 採樣數據
            logger.info("\n📋 藝術家名稱採樣 (前5個):")
            result = session.run("MATCH (a:Artist) RETURN a.name as name LIMIT 5")
            for record in result:
                logger.info(f"   - {record['name']}")

            logger.info("\n📋 作品標題採樣 (前5個):")
            result = session.run("MATCH (a:Artwork) RETURN a.title as title LIMIT 5")
            for record in result:
                logger.info(f"   - {record['title']}")

    except Exception as e:
        logger.error(f"❌ 統計查詢失敗: {e}")
    finally:
        if driver:
            driver.close()


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Neo4j 全文索引創建工具")
    logger.info("=" * 80)

    # 顯示配置
    logger.info("\n配置信息:")
    logger.info(f"   Neo4j URI: {NEO4J_URI}")
    logger.info(f"   用戶: {NEO4J_USER}")

    # 檢查統計
    check_index_statistics()

    # 創建索引
    create_fulltext_indexes()
