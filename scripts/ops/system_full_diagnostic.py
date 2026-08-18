#!/usr/bin/env python3
"""
藝術史資料庫系統完整診斷工具
檢查從數據預處理到RAG系統到OpenWebUI的完整流程
"""

import json
import subprocess
import sys
from datetime import datetime


class SystemDiagnostic:
    def __init__(self):
        self.results = {"timestamp": datetime.now().isoformat(), "checks": []}

    def add_check(self, name, status, message, details=None):
        """添加檢查結果"""
        self.results["checks"].append(
            {
                "name": name,
                "status": status,  # "pass", "fail", "warning"
                "message": message,
                "details": details,
            }
        )

    def run_command(self, cmd, description):
        """運行命令並返回結果"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_docker_containers(self):
        """檢查所有Docker容器"""
        print("📦 檢查Docker容器...")

        cmd = "docker ps -a --filter 'name=art-history' --format '{{.Names}}\t{{.Status}}'"
        result = self.run_command(cmd, "Docker容器狀態")

        if result["success"]:
            containers = result["stdout"].strip().split("\n")
            healthy = 0
            total = len(containers)

            for container in containers:
                if container:
                    name, status = container.split("\t", 1)
                    is_healthy = "Up" in status and "healthy" in status
                    if is_healthy:
                        healthy += 1

            self.add_check(
                "Docker容器健康檢查",
                "pass" if healthy == total else "warning",
                f"{healthy}/{total} 容器健康",
                {"containers": containers},
            )
        else:
            self.add_check("Docker容器健康檢查", "fail", "無法獲取容器狀態", result)

    def check_neo4j_data(self):
        """檢查Neo4j數據"""
        print("🕸️ 檢查Neo4j知識圖譜...")

        # 嘗試不同的密碼
        passwords = ["password", "neo4j", "art_history_2024", "arthistory2024"]

        for pwd in passwords:
            cmd = f'docker exec art-history-neo4j cypher-shell -u neo4j -p {pwd} "MATCH (n) RETURN count(n) as total_nodes LIMIT 1"'
            result = self.run_command(cmd, "Neo4j節點統計")

            if result["success"]:
                try:
                    lines = result["stdout"].strip().split("\n")
                    if len(lines) >= 2:
                        count = lines[1].strip()
                        self.add_check(
                            "Neo4j數據檢查",
                            "pass" if int(count) > 0 else "warning",
                            f"知識圖譜包含 {count} 個節點",
                            {"password": pwd},
                        )

                        # 檢查關係數量
                        cmd2 = f'docker exec art-history-neo4j cypher-shell -u neo4j -p {pwd} "MATCH ()-[r]->() RETURN count(r) as total_relationships LIMIT 1"'
                        result2 = self.run_command(cmd2, "Neo4j關係統計")
                        if result2["success"]:
                            rel_count = result2["stdout"].strip().split("\n")[1].strip()
                            self.add_check(
                                "Neo4j關係檢查", "pass", f"知識圖譜包含 {rel_count} 個關係"
                            )
                        return
                except:
                    continue

        self.add_check("Neo4j數據檢查", "fail", "無法連接到Neo4j或密碼錯誤")

    def check_chromadb(self):
        """檢查ChromaDB"""
        print("🔍 檢查ChromaDB向量資料庫...")

        cmd = "curl -s http://localhost:8001/api/v1/heartbeat"
        result = self.run_command(cmd, "ChromaDB健康檢查")

        if "Unimplemented" in result["stdout"]:
            # Try v2 API
            self.add_check(
                "ChromaDB狀態",
                "warning",
                "ChromaDB運行中但使用新版API (v2)",
                {"note": "需要更新客戶端代碼使用v2 API"},
            )
        elif result["success"]:
            self.add_check("ChromaDB狀態", "pass", "ChromaDB運行正常")
        else:
            self.add_check("ChromaDB狀態", "fail", "ChromaDB無法訪問", result)

    def check_ollama_models(self):
        """檢查Ollama模型"""
        print("🤖 檢查Ollama模型...")

        cmd = "docker exec art-history-ollama ollama list"
        result = self.run_command(cmd, "Ollama模型列表")

        if result["success"]:
            models = result["stdout"].strip().split("\n")[1:]  # Skip header
            rag_models = [m for m in models if "rag" in m.lower()]

            self.add_check(
                "Ollama模型檢查",
                "pass" if len(models) > 0 else "warning",
                f"找到 {len(models)} 個模型，其中 {len(rag_models)} 個RAG組合模型",
                {"total": len(models), "rag_models": len(rag_models)},
            )
        else:
            self.add_check("Ollama模型檢查", "fail", "無法獲取Ollama模型列表", result)

    def check_rag_manager(self):
        """檢查RAG Manager"""
        print("⚙️ 檢查RAG Manager...")

        cmd = "curl -s http://localhost:8007/health"
        result = self.run_command(cmd, "RAG Manager健康檢查")

        if result["success"]:
            try:
                health = json.loads(result["stdout"])
                self.add_check(
                    "RAG Manager狀態",
                    "pass" if health.get("status") != "unhealthy" else "warning",
                    f"狀態: {health.get('status')}",
                    health,
                )
            except:
                self.add_check(
                    "RAG Manager狀態",
                    "warning",
                    "RAG Manager響應但格式異常",
                    {"response": result["stdout"]},
                )
        else:
            self.add_check("RAG Manager狀態", "fail", "RAG Manager無法訪問")

    def check_openwebui(self):
        """檢查OpenWebUI"""
        print("🖥️ 檢查OpenWebUI...")

        cmd = "curl -s http://localhost:8080/health"
        result = self.run_command(cmd, "OpenWebUI健康檢查")

        if result["success"] and "true" in result["stdout"]:
            self.add_check("OpenWebUI狀態", "pass", "OpenWebUI運行正常")
        else:
            self.add_check("OpenWebUI狀態", "fail", "OpenWebUI無法訪問")

    def check_data_files(self):
        """檢查數據文件"""
        print("📁 檢查數據文件...")

        import os

        data_paths = [
            ("./data/raw", "原始數據"),
            ("./data/processed", "處理後數據"),
            ("./data/raw/images", "圖像數據"),
            ("./data/processed/embeddings", "嵌入向量"),
        ]

        for path, desc in data_paths:
            if os.path.exists(path):
                try:
                    file_count = len(
                        [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                    )
                    self.add_check(
                        f"數據檢查: {desc}",
                        "pass" if file_count > 0 else "warning",
                        f"找到 {file_count} 個文件",
                    )
                except Exception as e:
                    self.add_check(f"數據檢查: {desc}", "warning", f"無法讀取: {e}")
            else:
                self.add_check(f"數據檢查: {desc}", "warning", "目錄不存在")

    def generate_report(self):
        """生成報告"""
        print("\n" + "=" * 60)
        print("📊 系統診斷報告")
        print("=" * 60)

        pass_count = sum(1 for c in self.results["checks"] if c["status"] == "pass")
        fail_count = sum(1 for c in self.results["checks"] if c["status"] == "fail")
        warn_count = sum(1 for c in self.results["checks"] if c["status"] == "warning")

        print(f"\n總計: {len(self.results['checks'])} 項檢查")
        print(f"  ✅ 通過: {pass_count}")
        print(f"  ⚠️  警告: {warn_count}")
        print(f"  ❌ 失敗: {fail_count}")

        print("\n詳細結果:")
        print("-" * 60)

        for check in self.results["checks"]:
            status_icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}[check["status"]]
            print(f"\n{status_icon} {check['name']}")
            print(f"   {check['message']}")
            if check.get("details"):
                details = check["details"]
                if isinstance(details, dict):
                    for key, value in details.items():
                        if not isinstance(value, (list, dict)):
                            print(f"   - {key}: {value}")

        print("\n" + "=" * 60)

        # 保存報告
        report_file = f"system_diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"📄 完整報告已保存到: {report_file}")

        return pass_count, fail_count, warn_count

    def run_all_checks(self):
        """運行所有檢查"""
        print("🔍 開始系統全面診斷...")
        print("時間:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 60)

        self.check_docker_containers()
        self.check_neo4j_data()
        self.check_chromadb()
        self.check_ollama_models()
        self.check_rag_manager()
        self.check_openwebui()
        self.check_data_files()

        return self.generate_report()


if __name__ == "__main__":
    diagnostic = SystemDiagnostic()
    pass_count, fail_count, warn_count = diagnostic.run_all_checks()

    # 返回適當的退出代碼
    if fail_count > 0:
        sys.exit(1)
    elif warn_count > 0:
        sys.exit(2)
    else:
        sys.exit(0)
