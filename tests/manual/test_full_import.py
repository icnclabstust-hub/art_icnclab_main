#!/usr/bin/env python3
"""
測試完整匯入流程
模擬 importer.py 的行為來診斷問題
"""

import traceback

import chromadb
import requests


def test_full_import_workflow():
    """測試完整的匯入工作流程"""

    print("=" * 60)
    print("測試完整匯入流程")
    print("=" * 60)
    print()

    # 1. 連接 ChromaDB
    print("1️⃣ 連接 ChromaDB...")
    try:
        client = chromadb.HttpClient(host="localhost", port=8000)
        heartbeat = client.heartbeat()
        print(f"   ✅ 連接成功 (heartbeat: {heartbeat})")
    except Exception as e:
        print(f"   ❌ 連接失敗: {e}")
        traceback.print_exc()
        return False

    print()

    # 2. 取得或建立 collection
    print("2️⃣ 取得或建立 Collection...")
    collection_name = "art_history_collection"
    try:
        collection = client.get_or_create_collection(name=collection_name)
        print(f"   ✅ Collection: {collection.name}")
        print(f"   目前文檔數: {collection.count()}")
    except Exception as e:
        print(f"   ❌ Collection 失敗: {e}")
        traceback.print_exc()
        return False

    print()

    # 3. 生成嵌入向量
    print("3️⃣ 使用 Ollama 生成嵌入向量...")
    test_text = "測試文本：漢寶德是一位著名的建築師和教育家"
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": test_text},
            timeout=30,
        )

        if response.status_code == 200:
            embedding = response.json().get("embedding")
            print("   ✅ 嵌入生成成功")
            print(f"   嵌入維度: {len(embedding)}")
        else:
            print(f"   ❌ Ollama API 錯誤: {response.status_code}")
            print(f"   回應: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ 嵌入生成失敗: {e}")
        traceback.print_exc()
        return False

    print()

    # 4. 插入測試資料到 ChromaDB
    print("4️⃣ 插入測試資料到 ChromaDB...")
    test_id = "test_full_import_001"

    # 先清理可能存在的舊資料
    try:
        collection.delete(ids=[test_id])
    except:
        pass

    try:
        collection.add(
            ids=[test_id],
            documents=[test_text],
            embeddings=[embedding],
            metadatas=[
                {"title": "測試作品", "artist": "漢寶德", "period": "現代", "source": "test"}
            ],
        )
        print("   ✅ 資料插入成功")
        print(f"   Collection 文檔數: {collection.count()}")

    except Exception as e:
        print(f"   ❌ 插入失敗: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        traceback.print_exc()

        # 如果是維度問題，提供更多資訊
        if "dimension" in str(e).lower():
            print()
            print("   🔍 維度不匹配診斷:")
            print(f"      - 生成的嵌入維度: {len(embedding)}")
            print(f"      - 錯誤訊息: {e}")
            print()
            print("   💡 可能的解決方案:")
            print("      1. 刪除現有 collection 並重新建立")
            print("      2. 使用不同的 collection 名稱")
            print("      3. 確認所有嵌入使用相同的模型")

        return False

    print()

    # 5. 查詢測試資料
    print("5️⃣ 查詢測試資料...")
    try:
        results = collection.get(ids=[test_id])
        print("   ✅ 查詢成功")
        print(f"   文檔: {results['documents'][0][:50]}...")
        print(f"   Metadata: {results['metadatas'][0]}")

    except Exception as e:
        print(f"   ❌ 查詢失敗: {e}")
        traceback.print_exc()

    print()

    # 6. 清理測試資料
    print("6️⃣ 清理測試資料...")
    try:
        collection.delete(ids=[test_id])
        print("   ✅ 清理成功")

    except Exception as e:
        print(f"   ⚠️  清理失敗: {e}")

    print()
    print("=" * 60)
    print("✅ 完整匯入流程測試通過！")
    print("=" * 60)

    return True


def check_collection_dimension():
    """檢查現有 collection 的維度設定"""

    print("\n" + "=" * 60)
    print("檢查現有 Collection 的維度")
    print("=" * 60)
    print()

    try:
        client = chromadb.HttpClient(host="localhost", port=8000)
        collections = client.list_collections()

        for col in collections:
            print(f"📦 Collection: {col.name}")
            print(f"   文檔數: {col.count()}")

            # 如果有文檔，取得第一個的嵌入維度
            if col.count() > 0:
                try:
                    result = col.get(limit=1, include=["embeddings"])
                    if result.get("embeddings"):
                        emb = result["embeddings"][0]
                        if emb is not None and hasattr(emb, "__len__"):
                            print(f"   嵌入維度: {len(emb)}")
                        else:
                            print("   嵌入維度: 無法確定")
                except Exception as e:
                    print(f"   嵌入維度: 無法取得 ({e})")
            print()

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    # 執行測試
    success = test_full_import_workflow()

    # 檢查 collection 維度
    check_collection_dimension()

    # 返回結果
    import sys

    sys.exit(0 if success else 1)
