#!/usr/bin/env python3
"""
測試增強型檢索功能
直接測試向量搜索、全文搜索和混合檢索
"""

import logging
import sys
import time

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleRetrieverTester:
    """簡化的檢索測試器"""

    def __init__(self):
        # 連接 Neo4j
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687", auth=("neo4j", "CHANGE_ME_NEO4J_PASSWORD")
        )
        logger.info("✅ 連接到 Neo4j")

        # 載入嵌入模型
        logger.info("📥 載入嵌入模型...")
        self.model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        logger.info("✅ 模型載入完成")

    def close(self):
        if self.driver:
            self.driver.close()

    def vector_search(self, query, top_k=5):
        """向量搜索"""
        logger.info(f"\n🔍 向量搜索: {query}")

        # 生成查詢向量
        query_embedding = self.model.encode(query).tolist()

        with self.driver.session() as session:
            # 搜索藝術家
            result = session.run(
                """
                CALL db.index.vector.queryNodes('artist_name_embeddings', $top_k, $embedding)
                YIELD node, score
                RETURN node.name as name,
                       node.biography as biography,
                       labels(node) as labels,
                       score
                ORDER BY score DESC
            """,
                {"embedding": query_embedding, "top_k": top_k},
            )

            artists = list(result)

            # 搜索作品
            result = session.run(
                """
                CALL db.index.vector.queryNodes('artwork_title_embeddings', $top_k, $embedding)
                YIELD node, score
                RETURN node.title as title,
                       node.description as description,
                       labels(node) as labels,
                       score
                ORDER BY score DESC
            """,
                {"embedding": query_embedding, "top_k": top_k},
            )

            artworks = list(result)

            return {"artists": artists, "artworks": artworks}

    def fulltext_search(self, query, top_k=5):
        """全文搜索"""
        logger.info(f"\n📝 全文搜索: {query}")

        with self.driver.session() as session:
            # 搜索藝術家
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('artist_fulltext', $query)
                YIELD node, score
                RETURN node.name as name,
                       node.biography as biography,
                       labels(node) as labels,
                       score
                ORDER BY score DESC
                LIMIT $top_k
            """,
                {"query": query, "top_k": top_k},
            )

            artists = list(result)

            # 搜索作品
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('artwork_fulltext', $query)
                YIELD node, score
                RETURN node.title as title,
                       node.description as description,
                       labels(node) as labels,
                       score
                ORDER BY score DESC
                LIMIT $top_k
            """,
                {"query": query, "top_k": top_k},
            )

            artworks = list(result)

            return {"artists": artists, "artworks": artworks}

    def hybrid_search(self, query, top_k=5):
        """混合搜索（向量 + 全文）"""
        logger.info(f"\n🎯 混合搜索: {query}")

        # 分別執行向量和全文搜索
        vector_results = self.vector_search(query, top_k)
        fulltext_results = self.fulltext_search(query, top_k)

        # 合併結果（簡單版本，實際應該做更複雜的融合和去重）
        return {"vector": vector_results, "fulltext": fulltext_results}

    def print_results(self, results, result_type="artists"):
        """打印結果"""
        if result_type == "artists":
            items = results.get("artists", [])
            for i, item in enumerate(items, 1):
                name = item.get("name", "Unknown")
                score = item.get("score", 0)
                bio = item.get("biography", "")[:100] if item.get("biography") else "無簡介"
                logger.info(f"  [{i}] {name} (分數: {score:.3f})")
                logger.info(f"      {bio}...")
        else:
            items = results.get("artworks", [])
            for i, item in enumerate(items, 1):
                title = item.get("title", "Unknown")
                score = item.get("score", 0)
                desc = item.get("description", "")[:100] if item.get("description") else "無描述"
                logger.info(f"  [{i}] {title} (分數: {score:.3f})")
                logger.info(f"      {desc}...")


def main():
    """主函數"""
    tester = SimpleRetrieverTester()

    try:
        # 測試查詢
        test_queries = [
            ("達文西", "中文藝術家查詢"),
            ("Leonardo da Vinci", "英文藝術家查詢"),
            ("印象派", "藝術流派查詢"),
            ("蒙娜麗莎", "中文作品查詢"),
            ("Renaissance painting", "英文藝術風格查詢"),
        ]

        for query, description in test_queries:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"測試: {description}")
            logger.info(f"查詢: {query}")
            logger.info(f"{'=' * 60}")

            # 1. 向量搜索
            start_time = time.time()
            vector_results = tester.vector_search(query, top_k=3)
            vector_time = time.time() - start_time

            logger.info(f"\n📊 向量搜索結果 ({vector_time:.3f}秒):")
            logger.info("\n藝術家:")
            tester.print_results(vector_results, "artists")
            logger.info("\n作品:")
            tester.print_results(vector_results, "artworks")

            # 2. 全文搜索
            start_time = time.time()
            fulltext_results = tester.fulltext_search(query, top_k=3)
            fulltext_time = time.time() - start_time

            logger.info(f"\n📊 全文搜索結果 ({fulltext_time:.3f}秒):")
            logger.info("\n藝術家:")
            tester.print_results(fulltext_results, "artists")
            logger.info("\n作品:")
            tester.print_results(fulltext_results, "artworks")

            logger.info("\n" + "=" * 60 + "\n")

        logger.info("✅ 所有測試完成")

    except Exception as e:
        logger.error(f"❌ 錯誤: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        tester.close()


if __name__ == "__main__":
    main()
