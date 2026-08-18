#!/usr/bin/env python3
"""
簡單的 Neo4j 狀態檢查腳本
"""

import sys

try:
    from neo4j import GraphDatabase
except ImportError:
    print("❌ 缺少 neo4j 模組，正在安裝...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "neo4j"])
    from neo4j import GraphDatabase


def check_neo4j(uri="bolt://localhost:7687", user="neo4j", password="CHANGE_ME_NEO4J_PASSWORD"):
    """檢查 Neo4j 連接和狀態"""

    print("=" * 60)
    print("🔍 Neo4j 狀態檢查")
    print("=" * 60)

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # 1. 檢查版本
            result = session.run(
                "CALL dbms.components() YIELD versions RETURN versions[0] AS version"
            )
            version = result.single()["version"]
            print("\n✅ Neo4j 連接成功")
            print(f"📊 版本: {version}")

            # 2. 檢查節點數量
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            print(f"📚 總節點數: {node_count}")

            # 3. 檢查關係數量
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            print(f"🔗 總關係數: {rel_count}")

            # 4. 檢查標籤
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            print(f"\n📋 節點標籤 ({len(labels)} 種):")
            for label in labels:
                count_result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                count = count_result.single()["count"]
                print(f"   - {label}: {count} 個節點")

            # 5. 檢查索引
            print("\n🔧 現有索引:")
            result = session.run("SHOW INDEXES")
            indexes = list(result)

            if indexes:
                for idx in indexes:
                    print(
                        f"   - {idx.get('name', 'unnamed')}: {idx.get('type', 'unknown')} ({idx.get('state', 'unknown')})"
                    )
            else:
                print("   ⚠️  目前沒有索引")

            # 6. 檢查約束
            print("\n🔒 約束:")
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)

            if constraints:
                for cons in constraints:
                    print(f"   - {cons.get('name', 'unnamed')}")
            else:
                print("   ⚠️  目前沒有約束")

        driver.close()

        print("\n" + "=" * 60)
        print("✅ 檢查完成")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 連接失敗: {e}")
        print("\n請確認:")
        print("1. Neo4j 服務正在運行")
        print("2. 連接參數正確（URI, 用戶名, 密碼）")
        print("3. 防火牆允許連接")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="檢查 Neo4j 狀態")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="用戶名")
    parser.add_argument("--password", default="CHANGE_ME_NEO4J_PASSWORD", help="密碼")

    args = parser.parse_args()

    success = check_neo4j(args.uri, args.user, args.password)
    sys.exit(0 if success else 1)
