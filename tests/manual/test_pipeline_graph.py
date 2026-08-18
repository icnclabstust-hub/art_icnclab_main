#!/usr/bin/env python3
"""
測試 OpenWebUI Pipeline 圖譜功能
"""

import os
import sys

# 添加當前目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openwebui_neo4j_graph_pipeline import Pipeline


def test_entity_extraction():
    """測試實體提取功能"""
    print("=" * 60)
    print("🧪 測試 1: 實體提取")
    print("=" * 60)

    pipeline = Pipeline()

    test_cases = [
        "達文西創作了哪些作品?",
        "米開朗基羅和拉斐爾有什麼關係?",
        "Leonardo da Vinci's works include Mona Lisa",
        "文藝復興時期的重要藝術家",
        "《蒙娜麗莎》是誰創作的?",
    ]

    for i, text in enumerate(test_cases, 1):
        entities = pipeline.extract_entities_from_text(text)
        print(f"\n{i}. 問題: {text}")
        print(f"   提取的實體: {entities}")

    print("\n✅ 實體提取測試完成\n")


def test_neo4j_connection():
    """測試 Neo4j 連接"""
    print("=" * 60)
    print("🧪 測試 2: Neo4j 連接")
    print("=" * 60)

    pipeline = Pipeline()

    import requests

    try:
        response = requests.get(pipeline.valves.NEO4J_URI, timeout=5)
        if response.status_code == 200:
            print(f"✅ Neo4j 連接成功: {pipeline.valves.NEO4J_URI}")
        else:
            print(f"❌ Neo4j 連接失敗: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 無法連接到 Neo4j: {str(e)}")
        print("\n💡 請確保 Neo4j 正在運行:")
        print("   docker-compose up -d neo4j")
        return False

    print("✅ Neo4j 連接測試完成\n")
    return True


def test_graph_query():
    """測試圖譜查詢"""
    print("=" * 60)
    print("🧪 測試 3: 圖譜查詢")
    print("=" * 60)

    pipeline = Pipeline()

    test_entities = [
        ["Leonardo da Vinci"],
        ["達文西", "Leonardo da Vinci"],
        ["Mona Lisa"],
        ["文藝復興", "Renaissance"],
    ]

    for i, entities in enumerate(test_entities, 1):
        print(f"\n{i}. 查詢實體: {entities}")

        graph_data = pipeline.query_neo4j_graph(entities, max_depth=2)

        if graph_data.get("error"):
            print(f"   ❌ 查詢錯誤: {graph_data['error']}")
        elif not graph_data.get("nodes"):
            print("   ⚠️ 未找到圖譜數據")
        else:
            print("   ✅ 找到圖譜:")
            print(f"      - 節點數量: {len(graph_data['nodes'])}")
            print(f"      - 關係數量: {len(graph_data['edges'])}")

            # 顯示節點
            if graph_data["nodes"]:
                print("      - 節點類型:")
                for node in graph_data["nodes"][:5]:
                    label = node.get("label", "Unknown")
                    name = node.get("name", "Unknown")
                    print(f"        • [{label}] {name}")

    print("\n✅ 圖譜查詢測試完成\n")


def test_mermaid_generation():
    """測試 Mermaid 圖表生成"""
    print("=" * 60)
    print("🧪 測試 4: Mermaid 圖表生成")
    print("=" * 60)

    pipeline = Pipeline()

    # 使用實際查詢結果
    entities = ["Leonardo da Vinci", "達文西"]
    print(f"\n查詢實體: {entities}")

    graph_data = pipeline.query_neo4j_graph(entities, max_depth=2)

    if graph_data.get("nodes"):
        mermaid = pipeline.format_mermaid_graph(graph_data)
        print("\n生成的 Mermaid 圖表:")
        print("-" * 60)
        print(mermaid)
        print("-" * 60)

        # 保存到文件
        output_file = "test_mermaid_output.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(mermaid)
        print(f"\n💾 圖表已保存到: {output_file}")
        print("   您可以在支持 Mermaid 的 Markdown 查看器中打開此文件")

    else:
        print("\n⚠️ 無法生成圖表(未找到圖譜數據)")

    print("\n✅ Mermaid 生成測試完成\n")


def test_model_matching():
    """測試模型匹配邏輯"""
    print("=" * 60)
    print("🧪 測試 5: 模型匹配邏輯")
    print("=" * 60)

    pipeline = Pipeline()

    test_models = [
        "llama31-graph-rag",
        "llama31-hybrid-rag",
        "llama31-advanced-rag",
        "llama31-agentic-rag",
        "llama31-self-rag",
        "llama31-vector-rag",
        "llama31-naive-rag",
        "qwen3-graph-rag",
        "qwen3-8b-hybrid-rag",
        "deepseek-advanced-rag",
        "gemma3-naive-rag",
        "llama3.1:8b",  # 非 RAG 模型
    ]

    print(f"\n當前配置: SUPPORTED_RAG_MODELS = '{pipeline.valves.SUPPORTED_RAG_MODELS}'")
    print("\n模型匹配結果:")

    for model in test_models:
        is_enabled = pipeline.is_graph_enabled_model(model)
        status = "✅ 支持" if is_enabled else "❌ 不支持"
        print(f"   {status} - {model}")

    print("\n✅ 模型匹配測試完成\n")


def test_database_stats():
    """測試數據庫統計"""
    print("=" * 60)
    print("🧪 測試 6: 數據庫統計")
    print("=" * 60)

    pipeline = Pipeline()

    queries = {
        "節點總數": "MATCH (n) RETURN count(n) as count",
        "關係總數": "MATCH ()-[r]->() RETURN count(r) as count",
        "藝術家數量": "MATCH (a:Artist) RETURN count(a) as count",
        "作品數量": "MATCH (a:Artwork) RETURN count(a) as count",
        "風格數量": "MATCH (s:Style) RETURN count(s) as count",
    }

    import requests

    print("")
    for name, query in queries.items():
        try:
            response = requests.post(
                f"{pipeline.valves.NEO4J_URI}/db/neo4j/tx/commit",
                auth=(pipeline.valves.NEO4J_USER, pipeline.valves.NEO4J_PASSWORD),
                json={"statements": [{"statement": query}]},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results") and result["results"][0].get("data"):
                    count = result["results"][0]["data"][0]["row"][0]
                    print(f"   {name}: {count}")
                else:
                    print(f"   {name}: 0 (無數據)")
            else:
                print(f"   {name}: 查詢失敗 (HTTP {response.status_code})")

        except Exception as e:
            print(f"   {name}: 錯誤 - {str(e)}")

    print("\n✅ 數據庫統計測試完成\n")


def run_all_tests():
    """運行所有測試"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "OpenWebUI Pipeline 圖譜功能測試" + " " * 10 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    # 測試 1: 實體提取
    test_entity_extraction()

    # 測試 2: Neo4j 連接
    if not test_neo4j_connection():
        print("\n❌ Neo4j 連接失敗,停止後續測試")
        print("\n💡 請先啟動 Neo4j:")
        print("   docker-compose up -d neo4j")
        return

    # 測試 3: 圖譜查詢
    test_graph_query()

    # 測試 4: Mermaid 生成
    test_mermaid_generation()

    # 測試 5: 模型匹配
    test_model_matching()

    # 測試 6: 數據庫統計
    test_database_stats()

    # 總結
    print("=" * 60)
    print("🎉 所有測試完成!")
    print("=" * 60)
    print("\n📝 下一步:")
    print("   1. 在 OpenWebUI 中上傳 Pipeline")
    print("   2. 配置 Pipeline 參數")
    print("   3. 選擇支持的 RAG 模型進行測試")
    print("   4. 提問並查看圖譜效果\n")

    print("📚 詳細指南:")
    print("   OpenWebUI_Pipeline_圖譜視覺化指南.md\n")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️ 測試被中斷")
    except Exception as e:
        print(f"\n\n❌ 測試出錯: {str(e)}")
        import traceback

        traceback.print_exc()
