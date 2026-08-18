#!/usr/bin/env python3
"""
測試 Neo4j 圖譜視覺化功能
"""

import json
from typing import Any

import requests


class GraphVisualizationTester:
    def __init__(self):
        self.neo4j_url = "http://localhost:7474"
        self.neo4j_auth = ("neo4j", "CHANGE_ME_NEO4J_PASSWORD")

    def test_neo4j_connection(self) -> bool:
        """測試 Neo4j 連接"""
        print("🔍 測試 Neo4j 連接...")
        try:
            response = requests.get(self.neo4j_url, timeout=5)
            if response.status_code == 200:
                print("✅ Neo4j 連接成功")
                return True
            else:
                print(f"❌ Neo4j 連接失敗: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Neo4j 連接錯誤: {str(e)}")
            return False

    def test_graph_query(self, entity_names: list[str]) -> dict[str, Any]:
        """測試圖譜查詢"""
        print(f"\n🔍 測試圖譜查詢: {entity_names}")

        cypher_query = """
        MATCH (source)
        WHERE source.name IN $entity_names
           OR source.title IN $entity_names
        OPTIONAL MATCH path = (source)-[r*1..2]-(related)
        WITH source, relationships(path) as rels, nodes(path) as nodes_in_path
        UNWIND rels as rel
        WITH DISTINCT source, rel, startNode(rel) as start, endNode(rel) as end
        RETURN
            collect(DISTINCT {
                id: id(source),
                label: labels(source)[0],
                name: coalesce(source.name, source.title, '未知'),
                properties: properties(source)
            }) as source_nodes,
            collect(DISTINCT {
                id: id(start),
                label: labels(start)[0],
                name: coalesce(start.name, start.title, '未知'),
                properties: properties(start)
            }) +
            collect(DISTINCT {
                id: id(end),
                label: labels(end)[0],
                name: coalesce(end.name, end.title, '未知'),
                properties: properties(end)
            }) as all_nodes,
            collect(DISTINCT {
                source: id(start),
                target: id(end),
                relationship: type(rel),
                properties: properties(rel)
            }) as edges
        """

        try:
            response = requests.post(
                f"{self.neo4j_url}/db/neo4j/tx/commit",
                auth=self.neo4j_auth,
                json={
                    "statements": [
                        {"statement": cypher_query, "parameters": {"entity_names": entity_names}}
                    ]
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results") and result["results"][0].get("data"):
                    data = result["results"][0]["data"][0]["row"]

                    # 合併節點並去重
                    nodes_dict = {}
                    for node_list in [data[0], data[1]]:
                        for node in node_list:
                            node_id = node.get("id")
                            if node_id and node_id not in nodes_dict:
                                nodes_dict[node_id] = node

                    graph_data = {
                        "nodes": list(nodes_dict.values()),
                        "edges": data[2],
                        "entity_count": len(nodes_dict),
                        "relationship_count": len(data[2]),
                    }

                    print("✅ 查詢成功:")
                    print(f"   - 節點數量: {graph_data['entity_count']}")
                    print(f"   - 關係數量: {graph_data['relationship_count']}")

                    return graph_data
                else:
                    print("⚠️ 查詢成功但無數據")
                    return {"nodes": [], "edges": []}
            else:
                print(f"❌ 查詢失敗: HTTP {response.status_code}")
                print(f"   響應: {response.text}")
                return {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            print(f"❌ 查詢錯誤: {str(e)}")
            return {"error": str(e)}

    def format_mermaid_graph(self, graph_data: dict) -> str:
        """生成 Mermaid 圖表"""
        if not graph_data.get("nodes"):
            return "無圖譜數據"

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        mermaid_lines = ["```mermaid", "graph TD"]

        # 節點定義
        node_map = {}
        for i, node in enumerate(nodes[:20]):
            node_id = f"N{i}"
            node_label = node.get("label", "Entity")
            node_name = node.get("name", "未知")[:20]

            if node_label == "Artist":
                style = f"{node_id}[👨‍🎨 {node_name}]"
            elif node_label == "Artwork":
                style = f"{node_id}[🖼️ {node_name}]"
            elif node_label == "Style":
                style = f"{node_id}{{{node_name}}}"
            elif node_label == "Period":
                style = f"{node_id}{{{node_name}}}"
            else:
                style = f"{node_id}[{node_name}]"

            mermaid_lines.append(f"    {style}")
            node_map[node.get("id")] = node_id

        # 邊定義
        for edge in edges[:30]:
            source = node_map.get(edge.get("source"))
            target = node_map.get(edge.get("target"))
            rel_type = edge.get("relationship", "related")

            if source and target:
                rel_translations = {
                    "CREATED": "創作",
                    "INFLUENCED": "影響",
                    "BELONGS_TO": "屬於",
                    "EXHIBITED_AT": "展出於",
                    "STUDIED_UNDER": "師從",
                    "CONTEMPORARY_OF": "同時代",
                }
                rel_label = rel_translations.get(rel_type, rel_type)
                mermaid_lines.append(f"    {source} -->|{rel_label}| {target}")

        mermaid_lines.append("```")
        return "\n".join(mermaid_lines)

    def check_database_content(self) -> dict[str, Any]:
        """檢查數據庫內容"""
        print("\n🔍 檢查數據庫內容...")

        queries = {
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
            "artists": "MATCH (a:Artist) RETURN count(a) as count",
            "artworks": "MATCH (a:Artwork) RETURN count(a) as count",
            "styles": "MATCH (s:Style) RETURN count(s) as count",
            "periods": "MATCH (p:Period) RETURN count(p) as count",
        }

        results = {}
        for key, query in queries.items():
            try:
                response = requests.post(
                    f"{self.neo4j_url}/db/neo4j/tx/commit",
                    auth=self.neo4j_auth,
                    json={"statements": [{"statement": query}]},
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("results") and result["results"][0].get("data"):
                        count = result["results"][0]["data"][0]["row"][0]
                        results[key] = count
                        print(f"   - {key}: {count}")
                else:
                    results[key] = "error"
            except Exception as e:
                results[key] = f"error: {str(e)}"

        return results

    def get_sample_entities(self) -> list[str]:
        """獲取樣本實體名稱"""
        print("\n🔍 獲取樣本實體...")

        query = """
        MATCH (n)
        WHERE n.name IS NOT NULL OR n.title IS NOT NULL
        RETURN DISTINCT coalesce(n.name, n.title) as name, labels(n)[0] as label
        LIMIT 10
        """

        try:
            response = requests.post(
                f"{self.neo4j_url}/db/neo4j/tx/commit",
                auth=self.neo4j_auth,
                json={"statements": [{"statement": query}]},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results") and result["results"][0].get("data"):
                    entities = []
                    for row in result["results"][0]["data"]:
                        name = row["row"][0]
                        label = row["row"][1]
                        entities.append(name)
                        print(f"   - [{label}] {name}")
                    return entities
            return []
        except Exception as e:
            print(f"❌ 獲取實體錯誤: {str(e)}")
            return []

    def run_all_tests(self):
        """運行所有測試"""
        print("=" * 60)
        print("🧪 Neo4j 圖譜視覺化功能測試")
        print("=" * 60)

        # 測試1: 連接
        if not self.test_neo4j_connection():
            print("\n❌ Neo4j 未運行,測試中止")
            print("\n💡 請先啟動 Neo4j:")
            print("   docker-compose up -d neo4j")
            return

        # 測試2: 數據庫內容
        db_stats = self.check_database_content()
        if db_stats.get("total_nodes", 0) == 0:
            print("\n⚠️ 數據庫為空,無法測試圖譜功能")
            print("\n💡 請先導入數據:")
            print("   python import_to_neo4j.py")
            return

        # 測試3: 獲取樣本實體
        sample_entities = self.get_sample_entities()
        if not sample_entities:
            print("\n⚠️ 無法找到實體")
            return

        # 測試4: 圖譜查詢
        test_cases = [
            sample_entities[:1],  # 單個實體
            sample_entities[:3],  # 多個實體
        ]

        for i, entities in enumerate(test_cases, 1):
            print(f"\n{'=' * 60}")
            print(f"測試案例 {i}: {entities}")
            print("=" * 60)

            graph_data = self.test_graph_query(entities)

            if graph_data.get("nodes"):
                print("\n📊 Mermaid 圖表:")
                print(self.format_mermaid_graph(graph_data))

                # 保存結果
                output_file = f"graph_test_case_{i}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(graph_data, f, ensure_ascii=False, indent=2)
                print(f"\n💾 圖譜數據已保存到: {output_file}")
            else:
                print("\n⚠️ 無圖譜數據")

        print("\n" + "=" * 60)
        print("✅ 測試完成!")
        print("=" * 60)

        print("\n📝 總結:")
        print(f"   - 數據庫節點總數: {db_stats.get('total_nodes', 0)}")
        print(f"   - 數據庫關係總數: {db_stats.get('total_relationships', 0)}")
        print(f"   - 藝術家數量: {db_stats.get('artists', 0)}")
        print(f"   - 作品數量: {db_stats.get('artworks', 0)}")

        print("\n🎯 下一步:")
        print("   1. 在 OpenWebUI 中上傳新的函數文件")
        print("   2. 選擇支持圖譜的模型組合 (如 Enhanced RAG)")
        print("   3. 提問測試,例如: '達文西創作了哪些作品?'")


if __name__ == "__main__":
    tester = GraphVisualizationTester()
    tester.run_all_tests()
