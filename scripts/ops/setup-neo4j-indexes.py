#!/usr/bin/env python3
"""
Neo4j 索引設置腳本
為藝術史資料庫創建向量索引和全文索引，提升檢索精確度
"""

import logging
import sys

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jIndexSetup:
    """Neo4j 索引設置工具"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "CHANGE_ME_NEO4J_PASSWORD",
    ):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logger.info(f"✅ 連接到 Neo4j: {uri}")

    def close(self):
        """關閉連接"""
        if self.driver:
            self.driver.close()

    def check_neo4j_version(self) -> str:
        """檢查 Neo4j 版本"""
        with self.driver.session() as session:
            result = session.run(
                "CALL dbms.components() YIELD versions RETURN versions[0] AS version"
            )
            version = result.single()["version"]
            logger.info(f"📊 Neo4j 版本: {version}")
            return version

    def list_existing_indexes(self):
        """列出現有索引"""
        with self.driver.session() as session:
            result = session.run("SHOW INDEXES")
            indexes = []
            for record in result:
                indexes.append(
                    {
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "state": record.get("state"),
                        "labels": record.get("labelsOrTypes"),
                        "properties": record.get("properties"),
                    }
                )

            if indexes:
                logger.info(f"\n📋 現有索引 ({len(indexes)} 個):")
                for idx in indexes:
                    logger.info(
                        f"  - {idx['name']} ({idx['type']}): {idx['labels']} - {idx['properties']}"
                    )
            else:
                logger.info("📋 目前沒有索引")

            return indexes

    def create_vector_indexes(self):
        """創建向量索引"""
        logger.info("\n🔧 創建向量索引...")

        vector_indexes = [
            {
                "name": "artist_name_embeddings",
                "label": "Artist",
                "property": "name_embedding",
                "dimensions": 1536,  # OpenAI text-embedding-3-small
                "similarity": "cosine",
            },
            {
                "name": "artwork_title_embeddings",
                "label": "Artwork",
                "property": "title_embedding",
                "dimensions": 1536,
                "similarity": "cosine",
            },
            {
                "name": "movement_embeddings",
                "label": "Movement",
                "property": "description_embedding",
                "dimensions": 1536,
                "similarity": "cosine",
            },
        ]

        with self.driver.session() as session:
            for idx_config in vector_indexes:
                try:
                    # 檢查索引是否已存在
                    check_query = f"SHOW INDEXES WHERE name = '{idx_config['name']}'"
                    exists = session.run(check_query).single()

                    if exists:
                        logger.info(f"  ⚠️  向量索引已存在: {idx_config['name']}")
                        continue

                    # 創建向量索引
                    create_query = f"""
                    CREATE VECTOR INDEX {idx_config["name"]} IF NOT EXISTS
                    FOR (n:{idx_config["label"]})
                    ON (n.{idx_config["property"]})
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {idx_config["dimensions"]},
                            `vector.similarity_function`: '{idx_config["similarity"]}'
                        }}
                    }}
                    """

                    session.run(create_query)
                    logger.info(f"  ✅ 創建向量索引: {idx_config['name']}")

                except Exception as e:
                    logger.error(f"  ❌ 創建向量索引失敗 {idx_config['name']}: {e}")

    def create_fulltext_indexes(self):
        """創建全文索引"""
        logger.info("\n🔧 創建全文索引...")

        fulltext_indexes = [
            {
                "name": "artist_fulltext",
                "labels": ["Artist"],
                "properties": ["name", "biography", "nationality", "birth_place"],
            },
            {
                "name": "artwork_fulltext",
                "labels": ["Artwork"],
                "properties": ["title", "description", "medium", "subject"],
            },
            {
                "name": "movement_fulltext",
                "labels": ["Movement"],
                "properties": ["name", "characteristics", "description"],
            },
            {
                "name": "period_fulltext",
                "labels": ["Period"],
                "properties": ["name", "description", "characteristics"],
            },
        ]

        with self.driver.session() as session:
            for idx_config in fulltext_indexes:
                try:
                    # 檢查索引是否已存在
                    check_query = f"SHOW INDEXES WHERE name = '{idx_config['name']}'"
                    exists = session.run(check_query).single()

                    if exists:
                        logger.info(f"  ⚠️  全文索引已存在: {idx_config['name']}")
                        continue

                    # 創建全文索引
                    labels = ", ".join(f"n:{label}" for label in idx_config["labels"])
                    properties = ", ".join(f"n.{prop}" for prop in idx_config["properties"])

                    create_query = f"""
                    CREATE FULLTEXT INDEX {idx_config["name"]} IF NOT EXISTS
                    FOR ({labels})
                    ON EACH [{properties}]
                    """

                    session.run(create_query)
                    logger.info(f"  ✅ 創建全文索引: {idx_config['name']}")

                except Exception as e:
                    logger.error(f"  ❌ 創建全文索引失敗 {idx_config['name']}: {e}")

    def create_property_indexes(self):
        """創建屬性索引（用於快速查找）"""
        logger.info("\n🔧 創建屬性索引...")

        property_indexes = [
            {"name": "artist_name_idx", "label": "Artist", "property": "name"},
            {"name": "artwork_title_idx", "label": "Artwork", "property": "title"},
            {"name": "artwork_year_idx", "label": "Artwork", "property": "year"},
            {"name": "movement_name_idx", "label": "Movement", "property": "name"},
        ]

        with self.driver.session() as session:
            for idx_config in property_indexes:
                try:
                    # 檢查索引是否已存在
                    check_query = f"SHOW INDEXES WHERE name = '{idx_config['name']}'"
                    exists = session.run(check_query).single()

                    if exists:
                        logger.info(f"  ⚠️  屬性索引已存在: {idx_config['name']}")
                        continue

                    # 創建屬性索引
                    create_query = f"""
                    CREATE INDEX {idx_config["name"]} IF NOT EXISTS
                    FOR (n:{idx_config["label"]})
                    ON (n.{idx_config["property"]})
                    """

                    session.run(create_query)
                    logger.info(f"  ✅ 創建屬性索引: {idx_config['name']}")

                except Exception as e:
                    logger.error(f"  ❌ 創建屬性索引失敗 {idx_config['name']}: {e}")

    def create_constraints(self):
        """創建唯一性約束"""
        logger.info("\n🔧 創建唯一性約束...")

        constraints = [
            {"name": "artist_name_unique", "label": "Artist", "property": "name"},
            {"name": "artwork_id_unique", "label": "Artwork", "property": "artwork_id"},
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    # 檢查約束是否已存在
                    check_query = "SHOW CONSTRAINTS"
                    existing = session.run(check_query)
                    exists = any(record.get("name") == constraint["name"] for record in existing)

                    if exists:
                        logger.info(f"  ⚠️  約束已存在: {constraint['name']}")
                        continue

                    # 創建唯一性約束
                    create_query = f"""
                    CREATE CONSTRAINT {constraint["name"]} IF NOT EXISTS
                    FOR (n:{constraint["label"]})
                    REQUIRE n.{constraint["property"]} IS UNIQUE
                    """

                    session.run(create_query)
                    logger.info(f"  ✅ 創建約束: {constraint['name']}")

                except Exception as e:
                    logger.error(f"  ❌ 創建約束失敗 {constraint['name']}: {e}")

    def test_indexes(self):
        """測試索引功能"""
        logger.info("\n🧪 測試索引功能...")

        with self.driver.session() as session:
            # 測試全文索引
            try:
                result = session.run("""
                    CALL db.index.fulltext.queryNodes('artist_fulltext', '達文西')
                    YIELD node, score
                    RETURN count(node) as count
                """)
                count = result.single()["count"]
                logger.info(f"  ✅ 全文索引測試: 找到 {count} 個結果")
            except Exception as e:
                logger.warning(f"  ⚠️  全文索引測試失敗: {e}")

            # 測試向量索引（如果有嵌入數據）
            try:
                # 檢查是否有嵌入數據
                check_result = session.run("""
                    MATCH (a:Artist)
                    WHERE a.name_embedding IS NOT NULL
                    RETURN count(a) as count
                """)
                embedding_count = check_result.single()["count"]

                if embedding_count > 0:
                    logger.info(f"  ℹ️  發現 {embedding_count} 個節點有嵌入向量")
                else:
                    logger.info("  ℹ️  目前沒有節點有嵌入向量，需要先生成嵌入")

            except Exception as e:
                logger.warning(f"  ⚠️  向量數據檢查失敗: {e}")

    def generate_sample_embeddings(self):
        """生成示例嵌入數據（用於測試）"""
        logger.info("\n🎨 生成示例嵌入數據...")

        try:
            from langchain_openai import OpenAIEmbeddings

            embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

            with self.driver.session() as session:
                # 獲取前10個藝術家
                result = session.run("""
                    MATCH (a:Artist)
                    RETURN a.name as name, id(a) as node_id
                    LIMIT 10
                """)

                count = 0
                for record in result:
                    name = record["name"]
                    node_id = record["node_id"]

                    # 生成嵌入
                    embedding = embeddings_model.embed_query(name)

                    # 更新節點
                    session.run(
                        """
                        MATCH (a:Artist)
                        WHERE id(a) = $node_id
                        SET a.name_embedding = $embedding
                    """,
                        {"node_id": node_id, "embedding": embedding},
                    )

                    count += 1
                    logger.info(f"  ✅ 生成嵌入: {name}")

                logger.info(f"  🎉 完成 {count} 個節點的嵌入生成")

        except ImportError:
            logger.warning("  ⚠️  需要安裝 langchain-openai: pip install langchain-openai")
        except Exception as e:
            logger.error(f"  ❌ 生成嵌入失敗: {e}")

    def setup_all(self, generate_embeddings: bool = False):
        """執行所有設置"""
        logger.info("\n" + "=" * 60)
        logger.info("🚀 Neo4j 索引設置開始")
        logger.info("=" * 60)

        # 1. 檢查版本
        self.check_neo4j_version()

        # 2. 列出現有索引
        self.list_existing_indexes()

        # 3. 創建索引
        self.create_property_indexes()
        self.create_fulltext_indexes()
        self.create_vector_indexes()

        # 4. 創建約束
        self.create_constraints()

        # 5. 生成示例嵌入（可選）
        if generate_embeddings:
            self.generate_sample_embeddings()

        # 6. 測試索引
        self.test_indexes()

        # 7. 再次列出索引
        logger.info("\n📋 設置完成後的索引列表:")
        self.list_existing_indexes()

        logger.info("\n" + "=" * 60)
        logger.info("✅ Neo4j 索引設置完成")
        logger.info("=" * 60)


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="設置 Neo4j 索引")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j 用戶名")
    parser.add_argument("--password", default="CHANGE_ME_NEO4J_PASSWORD", help="Neo4j 密碼")
    parser.add_argument(
        "--generate-embeddings", action="store_true", help="生成示例嵌入數據（需要 OpenAI API）"
    )
    parser.add_argument("--list-only", action="store_true", help="僅列出現有索引")

    args = parser.parse_args()

    # 創建設置工具
    setup = Neo4jIndexSetup(uri=args.uri, username=args.user, password=args.password)

    try:
        if args.list_only:
            # 僅列出索引
            setup.check_neo4j_version()
            setup.list_existing_indexes()
        else:
            # 執行完整設置
            setup.setup_all(generate_embeddings=args.generate_embeddings)

    except Exception as e:
        logger.error(f"❌ 設置失敗: {e}")
        sys.exit(1)
    finally:
        setup.close()


if __name__ == "__main__":
    main()
