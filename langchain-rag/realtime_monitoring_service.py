#!/usr/bin/env python3
"""
實時性能監控服務
提供Web界面和API端點來實時監控增強型自適應策略
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# 添加當前目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not available, monitoring service will be limited")

from adaptive_strategy_monitor import AdaptiveStrategyMonitor
from enhanced_adaptive_strategies import EnhancedAdaptiveManager, QueryContext


class RealTimeMonitoringService:
    """實時監控服務"""

    def __init__(
        self, adaptive_manager: EnhancedAdaptiveManager, host: str = "127.0.0.1", port: int = 8004
    ):
        """
        初始化實時監控服務

        Args:
            adaptive_manager: 自適應策略管理器
            host: 服務主機
            port: 服務端口
        """
        self.adaptive_manager = adaptive_manager
        self.monitor = AdaptiveStrategyMonitor(adaptive_manager)
        self.host = host
        self.port = port

        # 設置日誌
        self.logger = self._setup_logger()

        # WebSocket連接管理
        self.active_connections: list[WebSocket] = []

        # 創建FastAPI應用
        self.app = None
        if FASTAPI_AVAILABLE:
            self.app = self._create_app()

        # 後台任務
        self.monitoring_task = None
        self.is_running = False

        self.logger.info(f"實時監控服務初始化完成，將運行在 {host}:{port}")

    def _setup_logger(self) -> logging.Logger:
        """設置日誌"""
        logger = logging.getLogger("RealTimeMonitoringService")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _create_app(self) -> FastAPI:
        """創建FastAPI應用"""
        app = FastAPI(
            title="增強型自適應策略實時監控",
            description="提供實時性能監控、指標追蹤和系統健康狀態",
            version="1.0.0",
        )

        # 靜態文件服務（如果有前端資源）
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # 註冊路由
        self._register_routes(app)

        return app

    def _register_routes(self, app: FastAPI):
        """註冊API路由"""

        @app.get("/", response_class=HTMLResponse)
        async def get_dashboard():
            """監控儀表板主頁"""
            return self._generate_dashboard_html()

        @app.get("/health")
        async def health_check():
            """健康檢查端點"""
            return self.monitor.get_system_health_report()

        @app.get("/api/metrics")
        async def get_metrics():
            """獲取Prometheus格式指標"""
            from fastapi.responses import Response

            return Response(content=self.monitor.get_prometheus_metrics(), media_type="text/plain")

        @app.get("/api/stats")
        async def get_statistics():
            """獲取統計信息"""
            return {
                "system_health": self.monitor.get_system_health_report(),
                "strategy_stats": {
                    strategy: self.monitor.get_strategy_statistics(strategy, hours=1)
                    for strategy in [
                        "text_semantic",
                        "visual_multimodal",
                        "knowledge_graph",
                        "temporal_aware",
                        "hybrid_fusion",
                        "contextual_adaptive",
                    ]
                },
            }

        @app.get("/api/stats/{strategy_name}")
        async def get_strategy_stats(strategy_name: str, hours: int = 1):
            """獲取特定策略統計"""
            return self.monitor.get_strategy_statistics(strategy_name, hours)

        @app.get("/api/recommendations")
        async def get_recommendations():
            """獲取優化建議"""
            return await self.monitor.generate_optimization_recommendations()

        @app.post("/api/test-query")
        async def test_query(request: dict):
            """測試查詢端點"""
            query_text = request.get("query", "測試查詢")

            context = QueryContext(
                query_text=query_text, user_id="test_user", session_id="test_session"
            )

            start_time = time.time()
            strategy = await self.adaptive_manager.select_optimal_strategy(context)
            response_time = time.time() - start_time

            # 模擬性能數據
            performance_data = {
                "response_time": response_time,
                "confidence": 0.85,
                "success": True,
                "user_satisfaction": 4.2,
            }

            # 記錄性能
            await self.monitor.record_strategy_performance(strategy, context, performance_data)

            return {
                "query": query_text,
                "selected_strategy": strategy.value,
                "response_time": response_time,
                "performance_data": performance_data,
            }

        @app.websocket("/ws/realtime")
        async def websocket_endpoint(websocket: WebSocket):
            """實時數據WebSocket端點"""
            await self.connect(websocket)
            try:
                while True:
                    # 保持連接活躍
                    data = await websocket.receive_text()
                    # Echo back for keep-alive
                    await websocket.send_text(f"ping: {data}")
            except WebSocketDisconnect:
                self.disconnect(websocket)

        @app.on_event("startup")
        async def startup_event():
            """應用啟動事件"""
            await self.start_monitoring()

        @app.on_event("shutdown")
        async def shutdown_event():
            """應用關閉事件"""
            await self.stop_monitoring()

    def _generate_dashboard_html(self) -> str:
        """生成監控儀表板HTML"""
        return """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>增強型自適應策略監控儀表板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-healthy { background-color: #4CAF50; }
        .status-warning { background-color: #FF9800; }
        .status-error { background-color: #F44336; }
        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
        }
        .btn:hover {
            background: #5a6fd8;
        }
        #realTimeChart {
            width: 100%;
            height: 300px;
        }
        .log-container {
            max-height: 200px;
            overflow-y: auto;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 增強型自適應策略監控儀表板</h1>
        <p>實時監控RAG系統性能與策略選擇</p>
    </div>

    <div class="dashboard-grid">
        <!-- 系統健康 -->
        <div class="card">
            <h3>🏥 系統健康狀態</h3>
            <div id="healthStatus">
                <div class="metric-value" id="healthScore">載入中...</div>
                <p>健康分數</p>
                <div id="systemStatus">
                    <span class="status-indicator status-healthy"></span>
                    <span id="statusText">系統運行正常</span>
                </div>
            </div>
        </div>

        <!-- 性能指標 -->
        <div class="card">
            <h3>⚡ 性能指標</h3>
            <div>
                <p>平均響應時間: <span id="avgResponseTime">-</span> ms</p>
                <p>成功率: <span id="successRate">-</span>%</p>
                <p>查詢總數: <span id="totalQueries">-</span></p>
            </div>
        </div>

        <!-- 策略分布 -->
        <div class="card">
            <h3>🎭 策略選擇分布</h3>
            <canvas id="strategyChart" width="400" height="200"></canvas>
        </div>

        <!-- 實時性能圖表 -->
        <div class="card">
            <h3>📈 實時性能監控</h3>
            <canvas id="realTimeChart"></canvas>
        </div>

        <!-- 控制面板 -->
        <div class="card">
            <h3>🎮 控制面板</h3>
            <div>
                <button class="btn" onclick="testQuery()">執行測試查詢</button>
                <button class="btn" onclick="refreshData()">刷新數據</button>
                <button class="btn" onclick="downloadReport()">下載報告</button>
            </div>
            <div style="margin-top: 15px;">
                <input type="text" id="testQueryInput" placeholder="輸入測試查詢..."
                       style="width: 100%; padding: 8px; margin-bottom: 10px;">
                <div id="testResult" class="log-container" style="display: none;"></div>
            </div>
        </div>

        <!-- 系統日誌 -->
        <div class="card">
            <h3>📝 實時日誌</h3>
            <div id="systemLogs" class="log-container">
                系統啟動中...
            </div>
        </div>
    </div>

    <script>
        // WebSocket連接
        let ws = null;
        let charts = {};

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
            initCharts();
            loadInitialData();

            // 定期刷新數據
            setInterval(refreshData, 5000);
        });

        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/realtime`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function(event) {
                addLog('WebSocket連接已建立');
            };

            ws.onmessage = function(event) {
                handleRealtimeData(JSON.parse(event.data));
            };

            ws.onerror = function(error) {
                addLog('WebSocket錯誤: ' + error);
            };

            ws.onclose = function(event) {
                addLog('WebSocket連接已關閉');
                // 嘗試重連
                setTimeout(initWebSocket, 5000);
            };
        }

        function initCharts() {
            // 策略分布圖表
            const strategyCtx = document.getElementById('strategyChart').getContext('2d');
            charts.strategy = new Chart(strategyCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Text Semantic', 'Visual Multimodal', 'Knowledge Graph',
                        'Temporal Aware', 'Hybrid Fusion', 'Contextual Adaptive'],
                    datasets: [{
                        data: [0, 0, 0, 0, 0, 0],
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56',
                            '#4BC0C0', '#9966FF', '#FF9F40']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });

            // 實時性能圖表
            const realtimeCtx = document.getElementById('realTimeChart').getContext('2d');
            charts.realtime = new Chart(realtimeCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '響應時間 (ms)',
                        data: [],
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            display: true,
                            title: { display: true, text: '時間' }
                        },
                        y: {
                            display: true,
                            title: { display: true, text: '響應時間 (ms)' }
                        }
                    }
                }
            });
        }

        async function loadInitialData() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                addLog('載入初始數據失敗: ' + error);
            }
        }

        async function refreshData() {
            await loadInitialData();
            addLog('數據已刷新');
        }

        function updateDashboard(data) {
            // 更新系統健康
            const health = data.system_health;
            document.getElementById('healthScore').textContent =
                (health.health_score * 100).toFixed(1) + '%';

            // 更新狀態指示器
            const statusIndicator = document.querySelector('.status-indicator');
            const statusText = document.getElementById('statusText');

            if (health.health_score > 0.8) {
                statusIndicator.className = 'status-indicator status-healthy';
                statusText.textContent = '系統運行正常';
            } else if (health.health_score > 0.6) {
                statusIndicator.className = 'status-indicator status-warning';
                statusText.textContent = '系統性能警告';
            } else {
                statusIndicator.className = 'status-indicator status-error';
                statusText.textContent = '系統需要檢查';
            }

            // 更新性能指標
            document.getElementById('totalQueries').textContent = health.total_queries_monitored;
        }

        async function testQuery() {
            const queryInput = document.getElementById('testQueryInput');
            const query = queryInput.value || '測試印象派畫作特色';
            const resultDiv = document.getElementById('testResult');

            try {
                addLog(`執行測試查詢: ${query}`);

                const response = await fetch('/api/test-query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query: query })
                });

                const result = await response.json();

                resultDiv.innerHTML = `
                    <strong>測試結果:</strong><br>
                    查詢: ${result.query}<br>
                    選擇策略: ${result.selected_strategy}<br>
                    響應時間: ${(result.response_time * 1000).toFixed(2)} ms<br>
                    信心度: ${(result.performance_data.confidence * 100).toFixed(1)}%
                `;
                resultDiv.style.display = 'block';

                addLog(`測試完成 - 策略: ${result.selected_strategy}, ` +
                    `時間: ${(result.response_time * 1000).toFixed(2)}ms`);

                // 刷新數據
                await refreshData();

            } catch (error) {
                addLog('測試查詢失敗: ' + error);
                resultDiv.innerHTML = '<span style="color: red;">測試失敗: ' + error + '</span>';
                resultDiv.style.display = 'block';
            }
        }

        async function downloadReport() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                const reportData = {
                    timestamp: new Date().toISOString(),
                    system_health: data.system_health,
                    strategy_statistics: data.strategy_stats
                };

                const blob = new Blob([JSON.stringify(reportData, null, 2)],
                    { type: 'application/json' });
                const url = URL.createObjectURL(blob);

                const a = document.createElement('a');
                a.href = url;
                a.download = `monitoring_report_${new Date().getTime()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                addLog('報告已下載');
            } catch (error) {
                addLog('下載報告失敗: ' + error);
            }
        }

        function handleRealtimeData(data) {
            // 處理實時數據更新
            addLog('收到實時數據更新');
        }

        function addLog(message) {
            const logContainer = document.getElementById('systemLogs');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = `[${timestamp}] ${message}\\n`;

            logContainer.textContent += logEntry;
            logContainer.scrollTop = logContainer.scrollHeight;

            // 限制日誌長度
            const lines = logContainer.textContent.split('\\n');
            if (lines.length > 50) {
                logContainer.textContent = lines.slice(-50).join('\\n');
            }
        }

        // 鍵盤快捷鍵
        document.addEventListener('keydown', function(event) {
            if (event.ctrlKey || event.metaKey) {
                switch(event.key) {
                    case 'r':
                        event.preventDefault();
                        refreshData();
                        break;
                    case 't':
                        event.preventDefault();
                        document.getElementById('testQueryInput').focus();
                        break;
                }
            }
        });
    </script>
</body>
</html>
        """

    async def connect(self, websocket: WebSocket):
        """WebSocket連接管理"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info("新的WebSocket連接已建立")

    def disconnect(self, websocket: WebSocket):
        """WebSocket斷開連接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info("WebSocket連接已斷開")

    async def broadcast_data(self, data: dict):
        """廣播數據到所有連接的WebSocket客戶端"""
        if not self.active_connections:
            return

        message = json.dumps(data, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                self.logger.error(f"發送WebSocket數據失敗: {e}")
                disconnected.append(connection)

        # 清理斷開的連接
        for connection in disconnected:
            self.disconnect(connection)

    async def start_monitoring(self):
        """啟動監控"""
        self.is_running = True
        await self.monitor.start_monitoring()

        # 啟動後台監控任務
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("實時監控服務已啟動")

    async def stop_monitoring(self):
        """停止監控"""
        self.is_running = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        await self.monitor.stop_monitoring()
        self.logger.info("實時監控服務已停止")

    async def _monitoring_loop(self):
        """監控主循環"""
        while self.is_running:
            try:
                # 收集當前系統狀態
                health_report = self.monitor.get_system_health_report()

                # 廣播實時數據
                await self.broadcast_data(
                    {"type": "health_update", "data": health_report, "timestamp": time.time()}
                )

                # 每5秒更新一次
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"監控循環出錯: {e}")
                await asyncio.sleep(10)

    async def run_server(self):
        """運行監控服務器"""
        if not FASTAPI_AVAILABLE:
            self.logger.error("FastAPI不可用，無法啟動Web服務")
            return

        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level="info", access_log=True
        )

        server = uvicorn.Server(config)

        try:
            self.logger.info(f"啟動監控服務器 http://{self.host}:{self.port}")
            await server.serve()
        except Exception as e:
            self.logger.error(f"服務器運行出錯: {e}")
        finally:
            await self.stop_monitoring()


# 獨立運行
async def main():
    """主函數"""
    from enhanced_adaptive_strategies import EnhancedAdaptiveManager

    # 創建自適應管理器
    adaptive_manager = EnhancedAdaptiveManager(learning_rate=0.15, exploration_rate=0.3)

    # 創建監控服務
    monitoring_service = RealTimeMonitoringService(adaptive_manager)

    # 運行服務器
    await monitoring_service.run_server()


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        asyncio.run(main())
    else:
        print("需要安装 FastAPI 和 uvicorn 才能運行監控服務")
        print("pip install fastapi uvicorn websockets")
