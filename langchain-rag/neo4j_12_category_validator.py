#!/usr/bin/env python3
"""
Neo4j 12大分類驗證器
驗證12大分類節點是否正確創建並提供查詢測試
"""

import json
import logging
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("❌ Neo4j驅動未安裝，請執行: pip install neo4j")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4j12CategoryValidator:
    """Neo4j 12大分類驗證器"""

    def __init__(self, uri="bolt://localhost:7687", username="neo4j", password="password"):
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

    def execute_query(self, cypher: str) -> list[dict]:
        """執行Cypher查詢"""
        if not self.driver:
            logger.error("❌ 未連接到Neo4j")
            return []

        try:
            with self.driver.session() as session:
                result = session.run(cypher)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"❌ 查詢執行失敗: {e}")
            return []

    def validate_12_categories(self) -> dict[str, Any]:
        """驗證12大分類節點"""
        print("🔍 驗證12大分類節點結構...")
        print("=" * 50)

        validation_results = {
            "categories_found": {},
            "total_nodes": 0,
            "total_relationships": 0,
            "category_stats": {},
            "sample_nodes": {},
            "validation_status": "success",
        }

        # 1. 檢查總節點數
        total_nodes_query = "MATCH (n) RETURN count(n) as total_nodes"
        total_result = self.execute_query(total_nodes_query)
        if total_result:
            validation_results["total_nodes"] = total_result[0]["total_nodes"]
            print(f"📊 總節點數: {validation_results['total_nodes']}")

        # 2. 檢查總關係數
        total_rels_query = "MATCH ()-[r]->() RETURN count(r) as total_relationships"
        rel_result = self.execute_query(total_rels_query)
        if rel_result:
            validation_results["total_relationships"] = rel_result[0]["total_relationships"]
            print(f"🔗 總關係數: {validation_results['total_relationships']}")

        # 3. 檢查12大分類
        categories_expected = [
            "People",
            "Artworks",
            "Movements",
            "Techniques",
            "Themes",
            "Chronology",
            "Places",
            "Institutions",
            "Events",
            "Sources",
            "Concepts",
            "Translations",
        ]

        print("\n🏷️ 分類驗證:")
        for category in categories_expected:
            category_query = f"MATCH (n {{category: '{category}'}}) RETURN count(n) as count, collect(DISTINCT labels(n)[0]) as labels"
            category_result = self.execute_query(category_query)

            if category_result and category_result[0]["count"] > 0:
                count = category_result[0]["count"]
                labels = category_result[0]["labels"]
                validation_results["categories_found"][category] = {
                    "count": count,
                    "labels": labels,
                }
                print(f"   ✅ {category}: {count} 個節點 (標籤: {', '.join(labels)})")
            else:
                print(f"   ❌ {category}: 未找到節點")
                validation_results["validation_status"] = "partial_failure"

        # 4. 檢查具體節點標籤
        print("\n🏷️ 節點標籤統計:")
        labels_query = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """
        labels_result = self.execute_query(labels_query)
        for result in labels_result:
            label = result["label"]
            count = result["count"]
            print(f"   {label}: {count} 個節點")
            validation_results["category_stats"][label] = count

        # 5. 抽樣檢查每個分類的節點
        print("\n🔍 節點內容抽樣:")
        for category in categories_expected:
            sample_query = f"""
            MATCH (n {{category: '{category}'}})
            RETURN n
            LIMIT 1
            """
            sample_result = self.execute_query(sample_query)
            if sample_result:
                sample_node = sample_result[0]["n"]
                node_properties = dict(sample_node)
                validation_results["sample_nodes"][category] = node_properties

                # 顯示關鍵屬性
                key_props = ["name", "title", "chinese_name"]
                display_props = []
                for prop in key_props:
                    if prop in node_properties:
                        display_props.append(f"{prop}: {node_properties[prop]}")

                if display_props:
                    print(f"   {category}: {', '.join(display_props)}")
                else:
                    print(f"   {category}: {list(node_properties.keys())[:3]}")

        return validation_results

    def test_12_category_queries(self):
        """測試12大分類的典型查詢"""
        print("\n🧪 測試12大分類GraphRAG查詢:")
        print("=" * 50)

        test_queries = [
            {
                "name": "人物-作品關係",
                "query": """
                MATCH (artist:Artist)-[r]->(artwork)
                WHERE artwork.category = 'Artworks'
                RETURN artist.name as artist_name,
                       type(r) as relationship,
                       artwork.title as artwork_title
                LIMIT 5
                """,
                "description": "查詢藝術家創作的作品",
            },
            {
                "name": "技法-作品關係",
                "query": """
                MATCH (technique)-[r]->(artwork)
                WHERE technique.category = 'Techniques' AND artwork.category = 'Artworks'
                RETURN technique.name as technique_name,
                       technique.chinese_name as chinese_name,
                       artwork.title as artwork_title
                LIMIT 5
                """,
                "description": "查詢技法與作品的關係",
            },
            {
                "name": "地點-人物關係",
                "query": """
                MATCH (place)-[r]->(person)
                WHERE place.category = 'Places' AND person.category = 'People'
                RETURN place.name as place_name,
                       type(r) as relationship,
                       person.name as person_name
                LIMIT 5
                """,
                "description": "查詢地點與人物的關係",
            },
            {
                "name": "時間-流派關係",
                "query": """
                MATCH (period)-[r]->(movement)
                WHERE period.category = 'Chronology' AND movement.category = 'Movements'
                RETURN period.name as period_name,
                       movement.name as movement_name,
                       movement.chinese_name as chinese_name
                LIMIT 5
                """,
                "description": "查詢時間與藝術流派的關係",
            },
            {
                "name": "術語翻譯關係",
                "query": """
                MATCH (translation)
                WHERE translation.category = 'Translations'
                RETURN translation.italian_term as italian_term,
                       translation.chinese_term as chinese_term,
                       translation.english_term as english_term
                LIMIT 5
                """,
                "description": "查詢義大利-中文-英文術語對照",
            },
            {
                "name": "機構-人物關係",
                "query": """
                MATCH (institution)-[r]-(person)
                WHERE institution.category = 'Institutions' AND person.category = 'People'
                RETURN institution.name as institution_name,
                       type(r) as relationship,
                       person.name as person_name
                LIMIT 5
                """,
                "description": "查詢機構與人物的關係",
            },
        ]

        test_results = {}

        for test in test_queries:
            print(f"\n📝 {test['name']}:")
            print(f"   描述: {test['description']}")

            results = self.execute_query(test["query"])
            test_results[test["name"]] = results

            if results:
                print(f"   結果: 找到 {len(results)} 條記錄")
                for i, result in enumerate(results[:3]):
                    result_items = []
                    for key, value in result.items():
                        if value is not None:
                            result_items.append(f"{key}: {value}")
                    print(f"   {i + 1}. {' | '.join(result_items)}")
                if len(results) > 3:
                    print(f"   ... 還有 {len(results) - 3} 條記錄")
            else:
                print("   結果: ❌ 未找到相關數據")

        return test_results

    def generate_summary_report(self, validation_results: dict, test_results: dict):
        """生成總結報告"""
        print("\n📋 12大分類Neo4j驗證報告")
        print("=" * 50)

        print(f"🎯 驗證狀態: {validation_results['validation_status']}")
        print("📊 數據統計:")
        print(f"   總節點數: {validation_results['total_nodes']}")
        print(f"   總關係數: {validation_results['total_relationships']}")
        print(f"   發現分類: {len(validation_results['categories_found'])}/12")

        print("\n✅ 成功創建的分類:")
        for category, info in validation_results["categories_found"].items():
            print(f"   {category}: {info['count']} 個節點")

        print("\n🔧 GraphRAG查詢測試:")
        successful_queries = 0
        for query_name, results in test_results.items():
            if results:
                successful_queries += 1
                print(f"   ✅ {query_name}: {len(results)} 條結果")
            else:
                print(f"   ❌ {query_name}: 無結果")

        print("\n📈 總體評估:")
        if validation_results["total_nodes"] >= 30 and successful_queries >= 4:
            print("   🎉 12大分類Neo4j圖譜構建成功！")
            print("   📚 現在可以使用新的分類體系進行GraphRAG查詢")
        elif validation_results["total_nodes"] > 0:
            print("   ⚠️  部分成功，建議檢查缺失的分類和關係")
        else:
            print("   ❌ 構建失敗，請檢查Neo4j連接和腳本執行")


def main():
    """主函數"""
    print("🔍 Neo4j 12大分類驗證器")
    print("=" * 50)

    # 初始化驗證器
    validator = Neo4j12CategoryValidator(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="CHANGE_ME_NEO4J_PASSWORD",  # 請根據您的Neo4j密碼修改
    )

    if not validator.connect():
        print("❌ 無法連接到Neo4j，請檢查:")
        print("   1. Neo4j服務是否已啟動")
        print("   2. 連接參數是否正確")
        print("   3. 用戶名密碼是否正確")
        return

    try:
        # 執行驗證
        validation_results = validator.validate_12_categories()

        # 執行測試查詢
        test_results = validator.test_12_category_queries()

        # 生成總結報告
        validator.generate_summary_report(validation_results, test_results)

        # 保存驗證結果
        with open("neo4j_12_category_validation_report.json", "w", encoding="utf-8") as f:
            report_data = {
                "validation_results": validation_results,
                "test_results": test_results,
                "timestamp": "2024-01-01",  # 您可以添加實際時間戳
            }
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

        print("\n💾 驗證報告已保存: neo4j_12_category_validation_report.json")

    finally:
        validator.close()


if __name__ == "__main__":
    main()
