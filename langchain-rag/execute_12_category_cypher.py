#!/usr/bin/env python3
"""
執行12大分類Cypher腳本
直接在Neo4j數據庫中執行生成的Cypher腳本
"""

import logging

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CypherExecutor:
    """Cypher腳本執行器"""

    def __init__(
        self, uri="bolt://localhost:7687", username="neo4j", password="CHANGE_ME_NEO4J_PASSWORD"
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None

    def connect(self):
        """連接到Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            logger.info("✅ 已連接到Neo4j")
            return True
        except Exception as e:
            logger.error(f"❌ 連接Neo4j失敗: {e}")
            return False

    def close(self):
        """關閉連接"""
        if self.driver:
            self.driver.close()

    def execute_cypher_file(self, file_path: str):
        """執行Cypher檔案"""
        if not self.driver:
            logger.error("❌ 未連接到Neo4j")
            return False

        try:
            # 讀取Cypher檔案
            with open(file_path, encoding="utf-8") as f:
                cypher_content = f.read()

            # 分割為多個語句
            statements = self.split_cypher_statements(cypher_content)

            logger.info(f"📝 準備執行 {len(statements)} 個Cypher語句")

            with self.driver.session() as session:
                for i, statement in enumerate(statements):
                    if statement.strip():
                        try:
                            logger.info(
                                f"   執行語句 {i + 1}/{len(statements)}: {statement[:50]}..."
                            )
                            result = session.run(statement)
                            summary = result.consume()

                            # 記錄執行結果
                            if summary.counters.nodes_created > 0:
                                logger.info(f"   ✅ 創建了 {summary.counters.nodes_created} 個節點")
                            if summary.counters.relationships_created > 0:
                                logger.info(
                                    f"   ✅ 創建了 {summary.counters.relationships_created} 個關係"
                                )
                            if summary.counters.nodes_deleted > 0:
                                logger.info(f"   🗑️ 刪除了 {summary.counters.nodes_deleted} 個節點")
                            if summary.counters.relationships_deleted > 0:
                                logger.info(
                                    f"   🗑️ 刪除了 {summary.counters.relationships_deleted} 個關係"
                                )

                        except Exception as e:
                            logger.error(f"   ❌ 語句執行失敗: {e}")
                            logger.error(f"   語句內容: {statement}")

            logger.info("✅ Cypher腳本執行完成！")
            return True

        except Exception as e:
            logger.error(f"❌ 執行Cypher檔案失敗: {e}")
            return False

    def split_cypher_statements(self, cypher_content: str) -> list[str]:
        """將Cypher內容分割為多個語句"""
        statements = []
        lines = cypher_content.split("\n")
        current_statement = []

        for line in lines:
            line = line.strip()

            # 跳過註釋和空行
            if line.startswith("//") or not line:
                # 如果當前語句不為空，完成它
                if current_statement:
                    statements.append("\n".join(current_statement))
                    current_statement = []
                continue

            current_statement.append(line)

            # 如果行以;結尾，結束當前語句
            if line.endswith(";"):
                statements.append("\n".join(current_statement))
                current_statement = []

        # 添加最後一個語句（如果存在）
        if current_statement:
            statements.append("\n".join(current_statement))

        return statements

    def verify_database_state(self):
        """驗證數據庫狀態"""
        if not self.driver:
            logger.error("❌ 未連接到Neo4j")
            return

        try:
            with self.driver.session() as session:
                # 檢查總節點數
                result = session.run("MATCH (n) RETURN count(n) as total_nodes")
                total_nodes = result.single()["total_nodes"]

                # 檢查分類節點數
                result = session.run(
                    "MATCH (n) WHERE exists(n.category) RETURN n.category as category, count(n) as count ORDER BY count DESC"
                )
                categories = [(record["category"], record["count"]) for record in result]

                # 檢查總關係數
                result = session.run("MATCH ()-[r]->() RETURN count(r) as total_relationships")
                total_relationships = result.single()["total_relationships"]

                logger.info("🔍 數據庫狀態驗證:")
                logger.info(f"   總節點數: {total_nodes}")
                logger.info(f"   總關係數: {total_relationships}")
                logger.info("   分類分佈:")
                for category, count in categories:
                    logger.info(f"     {category}: {count} 個節點")

        except Exception as e:
            logger.error(f"❌ 驗證數據庫狀態失敗: {e}")


def main():
    """主函數"""
    print("🚀 執行12大分類Neo4j Cypher腳本")
    print("=" * 50)

    # 初始化執行器
    executor = CypherExecutor(
        uri="bolt://localhost:7687", username="neo4j", password="CHANGE_ME_NEO4J_PASSWORD"
    )

    if not executor.connect():
        print("❌ 無法連接到Neo4j，請檢查:")
        print("   1. Neo4j服務是否已啟動")
        print("   2. 連接參數是否正確")
        print("   3. 用戶名密碼是否正確")
        return

    try:
        # 執行Cypher腳本
        cypher_file = "create_12_category_neo4j_graph.cypher"
        success = executor.execute_cypher_file(cypher_file)

        if success:
            print("\n🎉 12大分類Neo4j數據庫更新成功！")

            # 驗證結果
            print("\n🔍 驗證數據庫狀態...")
            executor.verify_database_state()

        else:
            print("\n❌ 數據庫更新失敗")

    finally:
        executor.close()


if __name__ == "__main__":
    main()
