#!/usr/bin/env python3
"""
多模態RAG實驗框架測試腳本
測試各個服務的連通性和基礎功能
"""

import time
from datetime import datetime

import requests
import yaml


def test_service_health(url, service_name):
    """測試服務健康狀態"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=10)
        response_time = time.time() - start_time

        if response.status_code == 200:
            print(f"✅ {service_name}: 健康 ({response_time:.2f}s)")
            return True
        else:
            print(f"❌ {service_name}: 錯誤 (狀態碼: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ {service_name}: 連接失敗 - {str(e)}")
        return False


def test_chromadb():
    """測試ChromaDB"""
    print("\n🔍 測試ChromaDB...")

    # 檢查心跳
    if test_service_health("http://localhost:8000/api/v1/heartbeat", "ChromaDB心跳"):
        try:
            # 測試集合列表
            response = requests.get("http://localhost:8000/api/v1/collections", timeout=10)
            collections = response.json()
            print(f"📊 當前集合數量: {len(collections)}")
            return True
        except Exception as e:
            print(f"❌ ChromaDB API測試失敗: {e}")
    return False


def test_qdrant():
    """測試Qdrant"""
    print("\n🔍 測試Qdrant...")

    if test_service_health("http://localhost:6333/collections", "Qdrant集合API"):
        try:
            response = requests.get("http://localhost:6333/collections", timeout=10)
            data = response.json()
            collections = data.get("result", {}).get("collections", [])
            print(f"📊 Qdrant集合數量: {len(collections)}")
            return True
        except Exception as e:
            print(f"❌ Qdrant API測試失敗: {e}")
    return False


def test_weaviate():
    """測試Weaviate"""
    print("\n🔍 測試Weaviate...")

    if test_service_health("http://localhost:8081/v1/meta", "Weaviate Meta API"):
        try:
            response = requests.get("http://localhost:8081/v1/schema", timeout=10)
            schema = response.json()
            classes = schema.get("classes", [])
            print(f"📊 Weaviate類別數量: {len(classes)}")
            return True
        except Exception as e:
            print(f"❌ Weaviate Schema測試失敗: {e}")
    return False


def test_neo4j():
    """測試Neo4j"""
    print("\n🔍 測試Neo4j...")

    return test_service_health("http://localhost:7474", "Neo4j瀏覽器")


def test_mlflow():
    """測試MLflow"""
    print("\n🔍 測試MLflow...")

    # MLflow可能需要更多時間啟動
    for attempt in range(3):
        if test_service_health("http://localhost:5000", "MLflow"):
            try:
                # 嘗試獲取實驗列表
                response = requests.get(
                    "http://localhost:5000/api/2.0/mlflow/experiments/search", timeout=10
                )
                if response.status_code == 200:
                    experiments = response.json().get("experiments", [])
                    print(f"📊 MLflow實驗數量: {len(experiments)}")
                    return True
            except Exception as e:
                print(f"❌ MLflow API測試失敗: {e}")

        if attempt < 2:
            print(f"⏳ MLflow尚未準備好，等待30秒... (嘗試 {attempt + 1}/3)")
            time.sleep(30)

    return False


def test_monitoring():
    """測試監控服務"""
    print("\n🔍 測試監控服務...")

    return test_service_health("http://localhost:9100/metrics", "Prometheus Node Exporter")


def test_openwebui():
    """測試OpenWebUI"""
    print("\n🔍 測試OpenWebUI...")

    return test_service_health("http://localhost:8080", "OpenWebUI")


def load_experiment_config():
    """載入實驗配置"""
    try:
        with open("../context/experiments/experiment-config.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("✅ 實驗配置載入成功")
        return config
    except Exception as e:
        print(f"❌ 實驗配置載入失敗: {e}")
        return None


def main():
    """主測試函數"""
    print("🚀 多模態RAG系統實驗框架測試")
    print("=" * 50)
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 載入配置
    config = load_experiment_config()
    if not config:
        print("❌ 無法載入實驗配置，退出測試")
        return

    # 測試各項服務
    results = {
        "chromadb": test_chromadb(),
        "qdrant": test_qdrant(),
        "weaviate": test_weaviate(),
        "neo4j": test_neo4j(),
        "mlflow": test_mlflow(),
        "monitoring": test_monitoring(),
        "openwebui": test_openwebui(),
    }

    # 統計結果
    print("\n" + "=" * 50)
    print("📊 測試結果摘要:")

    healthy_services = sum(1 for status in results.values() if status)
    total_services = len(results)

    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {service.upper()}: {'健康' if status else '異常'}")

    print(
        f"\n🎯 系統健康度: {healthy_services}/{total_services} ({healthy_services / total_services * 100:.1f}%)"
    )

    # 建議
    if healthy_services >= total_services * 0.8:
        print("🎉 系統狀況良好，可以開始實驗！")
    elif healthy_services >= total_services * 0.6:
        print("⚠️ 系統部分異常，建議修復後再進行實驗")
    else:
        print("🚨 系統存在重大問題，需要修復後才能進行實驗")

    # 輸出配置摘要
    if config:
        print("\n📋 實驗配置摘要:")
        rag_count = len(config.get("experiment_matrix", {}).get("rag_frameworks", {}))
        llm_count = len(config.get("experiment_matrix", {}).get("llm_models", {}))
        total_combinations = rag_count * llm_count
        print(f"   - RAG框架: {rag_count}種")
        print(f"   - LLM模型: {llm_count}種")
        print(f"   - 實驗組合: {total_combinations}個")


if __name__ == "__main__":
    main()
