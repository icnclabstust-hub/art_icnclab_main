#!/usr/bin/env python3
"""
為 Neo4j 節點生成嵌入向量
使用本地模型，不需要 OpenAI API
"""

import logging
import sys

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """嵌入向量生成器"""

    def __init__(
        self,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="CHANGE_ME_NEO4J_PASSWORD",
        model_name="BAAI/bge-small-zh-v1.5",  # 中文優化的輕量級模型
    ):
        # 連接 Neo4j
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        logger.info(f"✅ 連接到 Neo4j: {neo4j_uri}")

        # 載入嵌入模型
        logger.info(f"📥 載入嵌入模型: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.info(f"✅ 模型載入完成，向量維度: {self.model.get_sentence_embedding_dimension()}")

    def close(self):
        """關閉連接"""
        if self.driver:
            self.driver.close()

    def generate_artist_embeddings(self, limit=50):
        """為藝術家生成嵌入"""
        logger.info(f"\n🎨 開始為藝術家生成嵌入（限制 {limit} 個）...")

        with self.driver.session() as session:
            # 獲取藝術家
            result = session.run(f"""
                MATCH (a:Artist)
                WHERE a.name_embedding IS NULL
                RETURN a.name as name, id(a) as node_id, a.biography as biography
                LIMIT {limit}
            """)

            artists = list(result)
            logger.info(f"找到 {len(artists)} 個需要生成嵌入的藝術家")

            if not artists:
                logger.info("所有藝術家已有嵌入向量")
                return

            # 生成嵌入
            for artist in tqdm(artists, desc="生成藝術家嵌入"):
                name = artist["name"]
                node_id = artist["node_id"]
                biography = artist.get("biography", "")

                # 組合文本：名稱 + 簡介
                text = f"{name} {biography[:200]}" if biography else name

                # 生成嵌入
                embedding = self.model.encode(text).tolist()

                # 更新節點
                session.run(
                    """
                    MATCH (a:Artist)
                    WHERE id(a) = $node_id
                    SET a.name_embedding = $embedding
                """,
                    {"node_id": node_id, "embedding": embedding},
                )

            logger.info(f"✅ 完成 {len(artists)} 個藝術家的嵌入生成")

    def generate_artwork_embeddings(self, limit=100):
        """為作品生成嵌入"""
        logger.info(f"\n🖼️  開始為作品生成嵌入（限制 {limit} 個）...")

        with self.driver.session() as session:
            # 獲取作品
            result = session.run(f"""
                MATCH (w:Artwork)
                WHERE w.title_embedding IS NULL AND w.title IS NOT NULL
                RETURN w.title as title, id(w) as node_id, w.description as description
                LIMIT {limit}
            """)

            artworks = list(result)
            logger.info(f"找到 {len(artworks)} 個需要生成嵌入的作品")

            if not artworks:
                logger.info("所有作品已有嵌入向量")
                return

            # 生成嵌入
            for artwork in tqdm(artworks, desc="生成作品嵌入"):
                title = artwork["title"]
                node_id = artwork["node_id"]
                description = artwork.get("description", "")

                # 組合文本：標題 + 描述
                text = f"{title} {description[:200]}" if description else title

                # 生成嵌入
                embedding = self.model.encode(text).tolist()

                # 更新節點
                session.run(
                    """
                    MATCH (w:Artwork)
                    WHERE id(w) = $node_id
                    SET w.title_embedding = $embedding
                """,
                    {"node_id": node_id, "embedding": embedding},
                )

            logger.info(f"✅ 完成 {len(artworks)} 個作品的嵌入生成")

    def verify_embeddings(self):
        """驗證嵌入生成"""
        logger.info("\n🔍 驗證嵌入生成...")

        with self.driver.session() as session:
            # 檢查藝術家
            result = session.run("""
                MATCH (a:Artist)
                WHERE a.name_embedding IS NOT NULL
                RETURN count(a) as count
            """)
            artist_count = result.single()["count"]
            logger.info(f"✅ 藝術家有嵌入: {artist_count} 個")

            # 檢查作品
            result = session.run("""
                MATCH (w:Artwork)
                WHERE w.title_embedding IS NOT NULL
                RETURN count(w) as count
            """)
            artwork_count = result.single()["count"]
            logger.info(f"✅ 作品有嵌入: {artwork_count} 個")

    def test_vector_search(self):
        """測試向量搜索"""
        logger.info("\n🧪 測試向量搜索...")

        test_queries = ["Leonardo da Vinci", "達文西", "印象派", "Renaissance painting"]

        for query in test_queries:
            logger.info(f"\n查詢: {query}")

            # 生成查詢向量
            query_embedding = self.model.encode(query).tolist()

            with self.driver.session() as session:
                # 向量搜索藝術家
                result = session.run(
                    """
                    CALL db.index.vector.queryNodes('artist_name_embeddings', 3, $embedding)
                    YIELD node, score
                    RETURN node.name as name, score
                """,
                    {"embedding": query_embedding},
                )

                results = list(result)
                if results:
                    logger.info(f"  找到 {len(results)} 個相關藝術家:")
                    for r in results:
                        logger.info(f"    - {r['name']} (分數: {r['score']:.3f})")
                else:
                    logger.info("  未找到結果")


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="生成 Neo4j 嵌入向量")
    parser.add_argument("--artists", type=int, default=50, help="生成嵌入的藝術家數量")
    parser.add_argument("--artworks", type=int, default=100, help="生成嵌入的作品數量")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5", help="嵌入模型名稱")
    parser.add_argument("--test-only", action="store_true", help="僅測試向量搜索")

    args = parser.parse_args()

    # 創建生成器
    generator = EmbeddingGenerator(model_name=args.model)

    try:
        if args.test_only:
            # 僅測試
            generator.test_vector_search()
        else:
            # 生成嵌入
            generator.generate_artist_embeddings(limit=args.artists)
            generator.generate_artwork_embeddings(limit=args.artworks)

            # 驗證
            generator.verify_embeddings()

            # 測試
            generator.test_vector_search()

        logger.info("\n✅ 所有操作完成")

    except Exception as e:
        logger.error(f"❌ 錯誤: {e}")
        sys.exit(1)
    finally:
        generator.close()


if __name__ == "__main__":
    main()
