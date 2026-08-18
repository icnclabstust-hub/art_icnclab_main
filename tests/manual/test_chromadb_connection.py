#!/usr/bin/env python3
"""
ChromaDB 連接診斷腳本
用於測試和診斷 ChromaDB 連接問題
"""

import sys
import traceback

import chromadb


def test_chromadb_connection(host="localhost", port=8000):
    """測試 ChromaDB 連接"""

    print("=" * 60)
    print("ChromaDB 連接診斷測試")
    print("=" * 60)
    print()

    # 1. 檢查 ChromaDB 版本
    print("1️⃣ ChromaDB 版本:")
    try:
        print(f"   版本: {chromadb.__version__}")
        print("   ✅ ChromaDB 模組已安裝")
    except Exception as e:
        print(f"   ❌ 無法取得版本: {e}")
        return False

    print()

    # 2. 測試基本連接
    print(f"2️⃣ 測試連接到 {host}:{port}")
    try:
        client = chromadb.HttpClient(host=host, port=port)
        heartbeat = client.heartbeat()
        print("   ✅ 連接成功")
        print(f"   Heartbeat: {heartbeat}")
    except Exception as e:
        print(f"   ❌ 連接失敗: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        traceback.print_exc()
        return False

    print()

    # 3. 測試列出 collections
    print("3️⃣ 列出現有 Collections:")
    try:
        collections = client.list_collections()
        print(f"   ✅ 成功列出 {len(collections)} 個 collections")
        for col in collections:
            print(f"      - {col.name} (count: {col.count()})")
    except Exception as e:
        print(f"   ❌ 列出失敗: {e}")
        traceback.print_exc()

    print()

    # 4. 測試建立/取得 collection
    print("4️⃣ 測試建立/取得 Collection:")
    collection_name = "art_history_collection"
    try:
        collection = client.get_or_create_collection(name=collection_name)
        print(f"   ✅ Collection '{collection_name}' 建立成功")
        print(f"   目前文檔數量: {collection.count()}")
    except Exception as e:
        print(f"   ❌ Collection 建立失敗: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        traceback.print_exc()
        return False

    print()

    # 5. 測試插入資料
    print("5️⃣ 測試插入測試資料:")
    try:
        # 先清空測試資料
        test_id = "test_doc_123"
        try:
            collection.delete(ids=[test_id])
        except:
            pass

        # 插入測試文檔
        collection.add(
            documents=["這是一個測試文檔"],
            metadatas=[{"source": "test", "type": "diagnostic"}],
            ids=[test_id],
        )
        print("   ✅ 測試資料插入成功")
        print(f"   Collection 文檔數量: {collection.count()}")

        # 測試查詢
        results = collection.get(ids=[test_id])
        print("   ✅ 測試資料查詢成功")
        print(f"   查詢結果: {results['documents'][0][:50]}...")

        # 清理測試資料
        collection.delete(ids=[test_id])
        print("   ✅ 測試資料清理成功")

    except Exception as e:
        print(f"   ❌ 資料操作失敗: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        traceback.print_exc()
        return False

    print()

    # 6. 測試完整的匯入流程（模擬）
    print("6️⃣ 測試完整匯入流程:")
    try:
        # 模擬 importer.py 的連接方式
        import_client = chromadb.HttpClient(host=host, port=port)
        import_collection = import_client.get_or_create_collection(name="art_history_collection")
        print("   ✅ 匯入器連接方式成功")
        print(f"   Collection: {import_collection.name}")
        print(f"   Count: {import_collection.count()}")
    except Exception as e:
        print(f"   ❌ 匯入器連接方式失敗: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        traceback.print_exc()
        return False

    print()
    print("=" * 60)
    print("✅ 所有測試通過！ChromaDB 連接正常")
    print("=" * 60)

    return True


def test_with_different_apis():
    """測試不同的 ChromaDB API 版本"""

    print("\n" + "=" * 60)
    print("測試不同的 ChromaDB API")
    print("=" * 60)
    print()

    # 測試 Settings 方式（較新版本）
    print("🔍 測試 Settings API:")
    try:
        from chromadb.config import Settings

        client = chromadb.Client(
            Settings(
                chroma_api_impl="rest", chroma_server_host="localhost", chroma_server_http_port=8000
            )
        )
        print("   ✅ Settings API 可用")
        print(f"   Heartbeat: {client.heartbeat()}")
    except Exception as e:
        print(f"   ℹ️  Settings API 不可用: {e}")

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ChromaDB 連接診斷工具")
    parser.add_argument("--host", default="localhost", help="ChromaDB 主機")
    parser.add_argument("--port", type=int, default=8000, help="ChromaDB 端口")

    args = parser.parse_args()

    # 執行主要測試
    success = test_chromadb_connection(args.host, args.port)

    # 執行額外測試
    test_with_different_apis()

    # 返回結果
    sys.exit(0 if success else 1)
