#!/usr/bin/env python3
"""
統一監控優化服務
集成所有監控組件，提供完整的監控解決方案
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

# 添加當前目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse, HTMLResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not available, web interface will be disabled")

from adaptive_strategy_monitor import AdaptiveStrategyMonitor
from alert_and_optimization_system import AlertAndOptimizationSystem
from enhanced_adaptive_strategies import EnhancedAdaptiveManager, QueryContext


class UnifiedMonitoringService:
    """統一監控優化服務"""

    def __init__(
        self,
        adaptive_manager: EnhancedAdaptiveManager | None = None,
        host: str = "127.0.0.1",
        port: int = 8005,
    ):
        """
        初始化統一監控服務

        Args:
            adaptive_manager: 自適應策略管理器，如果為None則自動創建
            host: 服務主機
            port: 服務端口
        """
        # 核心組件
        self.adaptive_manager = adaptive_manager or EnhancedAdaptiveManager(
            learning_rate=0.15, exploration_rate=0.3
        )

        self.monitor = AdaptiveStrategyMonitor(self.adaptive_manager)
        self.alert_system = AlertAndOptimizationSystem(
            self.adaptive_manager, self.monitor, enable_auto_optimization=True
        )

        # 服務配置
        self.host = host
        self.port = port

        # 日誌配置
        self.logger = self._setup_logger()

        # 系統狀態
        self.service_started = False
        self.start_time = time.time()

        # WebSocket連接管理
        self.active_connections: list[WebSocket] = []

        # 創建FastAPI應用
        self.app = None
        if FASTAPI_AVAILABLE:
            self.app = self._create_app()

        self.logger.info(f"統一監控服務初始化完成，將運行在 {host}:{port}")

    def _setup_logger(self) -> logging.Logger:
        """設置日誌"""
        logger = logging.getLogger("UnifiedMonitoringService")
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
            title="增強型自適應策略統一監控平台",
            description="集成監控、告警、優化的完整解決方案",
            version="1.0.0",
        )

        # 註冊所有路由
        self._register_routes(app)
        self._register_websocket_routes(app)
        self._register_lifecycle_events(app)

        return app

    def _register_routes(self, app: FastAPI):
        """註冊HTTP路由"""

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """主監控儀表板"""
            return self._generate_unified_dashboard()

        @app.get("/health")
        async def health_check():
            """健康檢查"""
            return {
                "status": "healthy" if self.service_started else "starting",
                "uptime_seconds": time.time() - self.start_time,
                "components": {
                    "adaptive_manager": "running",
                    "monitor": "running" if self.monitor.monitoring_active else "stopped",
                    "alert_system": "running" if self.alert_system.system_running else "stopped",
                },
            }

        @app.get("/api/overview")
        async def get_overview():
            """獲取系統總覽"""
            health_report = self.monitor.get_system_health_report()
            alert_summary = self.alert_system.get_alert_summary()

            return {
                "timestamp": time.time(),
                "system_health": health_report,
                "alerts": alert_summary,
                "uptime": time.time() - self.start_time,
            }

        @app.get("/api/metrics/prometheus")
        async def prometheus_metrics():
            """Prometheus格式的指標"""
            from fastapi.responses import Response

            return Response(content=self.monitor.get_prometheus_metrics(), media_type="text/plain")

        @app.get("/api/stats/strategies")
        async def get_strategy_statistics():
            """獲取策略統計"""
            strategies = [
                "text_semantic",
                "visual_multimodal",
                "knowledge_graph",
                "temporal_aware",
                "hybrid_fusion",
                "contextual_adaptive",
            ]

            return {
                strategy: self.monitor.get_strategy_statistics(strategy, hours=1)
                for strategy in strategies
            }

        @app.get("/api/stats/strategies/{strategy_name}")
        async def get_single_strategy_stats(strategy_name: str, hours: int = 1):
            """獲取單個策略統計"""
            return self.monitor.get_strategy_statistics(strategy_name, hours)

        @app.get("/api/alerts")
        async def get_alerts():
            """獲取告警信息"""
            return self.alert_system.get_alert_summary()

        @app.get("/api/recommendations")
        async def get_recommendations():
            """獲取優化建議"""
            return await self.monitor.generate_optimization_recommendations()

        @app.post("/api/test/query")
        async def test_query(request: dict):
            """測試查詢"""
            query_text = request.get("query", "測試增強型自適應策略")

            context = QueryContext(
                query_text=query_text, user_id="test_user", session_id=f"test_{int(time.time())}"
            )

            # 執行策略選擇
            start_time = time.time()
            try:
                strategy = await self.adaptive_manager.select_optimal_strategy(context)
                response_time = time.time() - start_time

                # 獲取推薦詳情
                recommendation = self.adaptive_manager.get_strategy_recommendation(context)

                # 模擬性能數據
                performance_data = {
                    "response_time": response_time,
                    "confidence": 0.85 + (hash(query_text) % 15) / 100.0,
                    "success": True,
                    "user_satisfaction": 4.2,
                }

                # 記錄性能
                await self.monitor.record_strategy_performance(strategy, context, performance_data)

                return {
                    "success": True,
                    "query": query_text,
                    "selected_strategy": strategy.value,
                    "response_time": response_time,
                    "performance_data": performance_data,
                    "recommendation_details": recommendation,
                }

            except Exception as e:
                self.logger.error(f"測試查詢失敗: {e}")
                return {"success": False, "error": str(e), "query": query_text}

        @app.post("/api/optimization/manual")
        async def manual_optimization():
            """手動觸發優化"""
            try:
                # 執行系統優化
                result = await self.adaptive_manager.optimize_system_performance()
                return {"success": True, "message": "手動優化已執行", "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @app.get("/api/export/metrics")
        async def export_metrics():
            """導出指標數據"""
            export_path = f"monitoring_export_{int(time.time())}.json"
            self.monitor.export_metrics_to_json(export_path)

            return FileResponse(
                path=export_path, filename=export_path, media_type="application/json"
            )

        @app.get("/api/export/alerts")
        async def export_alerts():
            """導出告警數據"""
            export_path = f"alerts_export_{int(time.time())}.json"
            self.alert_system.export_alert_history(export_path, hours=24)

            return FileResponse(
                path=export_path, filename=export_path, media_type="application/json"
            )

        @app.post("/api/config/thresholds")
        async def update_thresholds(config: dict):
            """更新告警閾值"""
            try:
                self.alert_system.alert_thresholds.update(config)
                return {"success": True, "message": "閾值已更新"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @app.get("/api/config/thresholds")
        async def get_thresholds():
            """獲取當前閾值配置"""
            return self.alert_system.alert_thresholds

    def _register_websocket_routes(self, app: FastAPI):
        """註冊WebSocket路由"""

        @app.websocket("/ws/realtime")
        async def websocket_endpoint(websocket: WebSocket):
            """實時數據WebSocket"""
            await self.connect(websocket)
            try:
                while True:
                    # 等待客戶端消息
                    data = await websocket.receive_text()

                    # 處理客戶端請求
                    if data == "get_overview":
                        overview = await self._get_realtime_overview()
                        await websocket.send_text(json.dumps(overview, ensure_ascii=False))
                    else:
                        # Echo back for keep-alive
                        await websocket.send_text(f"pong: {data}")

            except WebSocketDisconnect:
                self.disconnect(websocket)

    def _register_lifecycle_events(self, app: FastAPI):
        """註冊應用生命周期事件"""

        @app.on_event("startup")
        async def startup_event():
            """應用啟動"""
            await self.start_monitoring()

        @app.on_event("shutdown")
        async def shutdown_event():
            """應用關閉"""
            await self.stop_monitoring()

    def _generate_unified_dashboard(self) -> str:
        """生成統一監控儀表板"""
        return """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎯 增強型自適應策略統一監控平台</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .header {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            color: #667eea;
            font-size: 2.2em;
            margin-bottom: 8px;
        }

        .header .subtitle {
            color: #666;
            font-size: 1.1em;
        }

        .main-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .status-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }

        .status-card {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            border: 1px solid rgba(255,255,255,0.2);
        }

        .status-value {
            font-size: 2.5em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }

        .status-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            border: 1px solid rgba(255,255,255,0.2);
        }

        .card h3 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.3em;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .chart-container {
            position: relative;
            height: 300px;
            margin-bottom: 20px;
        }

        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }

        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }

        .btn:active {
            transform: translateY(0);
        }

        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }

        .input-group input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }

        .input-group input:focus {
            outline: none;
            border-color: #667eea;
        }

        .alert-item {
            background: rgba(255, 59, 48, 0.1);
            border: 1px solid rgba(255, 59, 48, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }

        .alert-warning {
            background: rgba(255, 149, 0, 0.1);
            border-color: rgba(255, 149, 0, 0.3);
        }

        .alert-info {
            background: rgba(0, 122, 255, 0.1);
            border-color: rgba(0, 122, 255, 0.3);
        }

        .log-container {
            background: #1a1a1a;
            color: #00ff00;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 15px;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .metric-item {
            text-align: center;
            padding: 15px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 8px;
        }

        .metric-item .value {
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }

        .metric-item .label {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-healthy { background: #4CAF50; }
        .status-warning { background: #FF9800; }
        .status-error { background: #F44336; }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .updating {
            animation: pulse 1s infinite;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 增強型自適應策略統一監控平台</h1>
        <div class="subtitle">集成監控 • 智能告警 • 自動優化</div>
    </div>

    <div class="main-container">
        <!-- 狀態總覽 -->
        <div class="status-bar">
            <div class="status-card">
                <div class="status-value" id="healthScore">--</div>
                <div class="status-label">系統健康分數</div>
            </div>
            <div class="status-card">
                <div class="status-value" id="totalQueries">--</div>
                <div class="status-label">總查詢數</div>
            </div>
            <div class="status-card">
                <div class="status-value" id="avgResponseTime">--</div>
                <div class="status-label">平均響應時間 (ms)</div>
            </div>
            <div class="status-card">
                <div class="status-value" id="activeAlerts">--</div>
                <div class="status-label">活躍告警</div>
            </div>
        </div>

        <!-- 主要監控區域 -->
        <div class="dashboard-grid">
            <div class="card">
                <h3>📈 實時性能監控</h3>
                <div class="chart-container">
                    <canvas id="performanceChart"></canvas>
                </div>
            </div>

            <div class="card">
                <h3>🚨 系統告警</h3>
                <div id="alertsList">載入中...</div>
            </div>
        </div>

        <!-- 測試和控制區域 -->
        <div class="footer-grid">
            <div class="card">
                <h3>🎮 測試控制台</h3>
                <div class="input-group">
                    <input type="text" id="testQuery" placeholder="輸入測試查詢..."
                        value="分析莫內印象派作品的色彩特色">
                    <button class="btn" onclick="executeTestQuery()">執行測試</button>
                </div>
                <div class="controls">
                    <button class="btn" onclick="refreshData()">刷新數據</button>
                    <button class="btn" onclick="triggerOptimization()">手動優化</button>
                    <button class="btn" onclick="exportData()">導出數據</button>
                </div>
                <div id="testResults" class="log-container" style="display: none;"></div>
            </div>

            <div class="card">
                <h3>📊 策略統計</h3>
                <div class="metric-grid" id="strategyMetrics">
                    載入中...
                </div>
            </div>

            <div class="card">
                <h3>💡 優化建議</h3>
                <div id="recommendationsList">載入中...</div>
            </div>
        </div>

        <!-- 系統日誌 -->
        <div class="card" style="margin-top: 20px;">
            <h3>📝 系統日誌</h3>
            <div id="systemLogs" class="log-container">
                [${new Date().toLocaleTimeString()}] 監控系統啟動中...
            </div>
        </div>
    </div>

    <script>
        // 全局變量
        let charts = {};
        let ws = null;
        let updateInterval = null;

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
            initCharts();
            startPeriodicUpdates();
            loadInitialData();
            addLog('監控系統已啟動');
        });

        // WebSocket連接
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/realtime`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function(event) {
                addLog('WebSocket連接已建立');
                // 請求初始數據
                ws.send('get_overview');
            };

            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                } catch (e) {
                    addLog('WebSocket數據: ' + event.data);
                }
            };

            ws.onerror = function(error) {
                addLog('WebSocket錯誤: ' + error);
            };

            ws.onclose = function(event) {
                addLog('WebSocket連接已關閉，嘗試重連...');
                setTimeout(initWebSocket, 5000);
            };
        }

        // 初始化圖表
        function initCharts() {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            charts.performance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '響應時間 (ms)',
                        data: [],
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.4
                    }, {
                        label: '準確度 (%)',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: { display: true, text: '響應時間 (ms)' }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: { display: true, text: '準確度 (%)' },
                            grid: { drawOnChartArea: false }
                        }
                    }
                }
            });
        }

        // 定期更新
        function startPeriodicUpdates() {
            updateInterval = setInterval(async function() {
                await loadInitialData();
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send('get_overview');
                }
            }, 5000); // 每5秒更新
        }

        // 載入初始數據
        async function loadInitialData() {
            try {
                const [overview, strategies, recommendations] = await Promise.all([
                    fetch('/api/overview').then(r => r.json()),
                    fetch('/api/stats/strategies').then(r => r.json()),
                    fetch('/api/recommendations').then(r => r.json())
                ]);

                updateStatusCards(overview);
                updateStrategyMetrics(strategies);
                updateRecommendations(recommendations);
                updateAlerts(overview.alerts);

            } catch (error) {
                addLog('載入數據失敗: ' + error.message);
            }
        }

        // 更新狀態卡片
        function updateStatusCards(overview) {
            const health = overview.system_health;
            const alerts = overview.alerts;

            document.getElementById('healthScore').textContent =
                (health.health_score * 100).toFixed(1) + '%';
            document.getElementById('totalQueries').textContent =
                health.total_queries_monitored.toLocaleString();
            document.getElementById('avgResponseTime').textContent = '--';
            document.getElementById('activeAlerts').textContent =
                alerts.active_alerts_count;

            // 更新健康分數顏色
            const healthElement = document.getElementById('healthScore');
            if (health.health_score > 0.8) {
                healthElement.style.color = '#4CAF50';
            } else if (health.health_score > 0.6) {
                healthElement.style.color = '#FF9800';
            } else {
                healthElement.style.color = '#F44336';
            }
        }

        // 更新策略指標
        function updateStrategyMetrics(strategies) {
            const container = document.getElementById('strategyMetrics');
            let html = '';

            for (const [strategy, stats] of Object.entries(strategies)) {
                if (stats.data_count > 0) {
                    html += `
                        <div class="metric-item">
                            <div class="value">${(stats.avg_response_time * 1000).toFixed(0)}</div>
                            <div class="label">${strategy}<br>響應時間(ms)</div>
                        </div>
                    `;
                }
            }

            container.innerHTML = html || '<div>無數據</div>';
        }

        // 更新優化建議
        function updateRecommendations(recommendations) {
            const container = document.getElementById('recommendationsList');
            let html = '';

            recommendations.forEach(rec => {
                html += `
                    <div class="alert-item alert-${rec.priority}">
                        <strong>${rec.type}</strong>: ${rec.message}
                    </div>
                `;
            });

            container.innerHTML = html || '<div>暫無建議</div>';
        }

        // 更新告警列表
        function updateAlerts(alerts) {
            const container = document.getElementById('alertsList');
            let html = '';

            alerts.active_alerts.forEach(alert => {
                const ageMinutes = Math.floor(alert.age_seconds / 60);
                html += `
                    <div class="alert-item alert-${alert.severity}">
                        <div><strong>${alert.title}</strong></div>
                        <div style="font-size: 0.9em; margin-top: 5px;">
                            ${ageMinutes}分鐘前
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html || '<div>✅ 無活躍告警</div>';
        }

        // 執行測試查詢
        async function executeTestQuery() {
            const queryInput = document.getElementById('testQuery');
            const resultsDiv = document.getElementById('testResults');
            const query = queryInput.value.trim();

            if (!query) {
                addLog('請輸入查詢內容');
                return;
            }

            try {
                addLog(`執行測試查詢: ${query}`);
                resultsDiv.style.display = 'block';
                resultsDiv.innerHTML = '執行中...';

                const response = await fetch('/api/test/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });

                const result = await response.json();

                if (result.success) {
                    resultsDiv.innerHTML = `
測試結果:
查詢: ${result.query}
選擇策略: ${result.selected_strategy}
響應時間: ${(result.response_time * 1000).toFixed(2)} ms
信心度: ${(result.performance_data.confidence * 100).toFixed(1)}%
狀態: 成功
                    `;
                    addLog(`測試完成 - ${result.selected_strategy} - ` +
                        `${(result.response_time * 1000).toFixed(2)}ms`);
                } else {
                    resultsDiv.innerHTML = `錯誤: ${result.error}`;
                    addLog(`測試失敗: ${result.error}`);
                }

                // 刷新數據
                setTimeout(loadInitialData, 1000);

            } catch (error) {
                resultsDiv.innerHTML = `錯誤: ${error.message}`;
                addLog(`測試查詢出錯: ${error.message}`);
            }
        }

        // 刷新數據
        async function refreshData() {
            addLog('手動刷新數據...');
            await loadInitialData();
            addLog('數據已刷新');
        }

        // 觸發手動優化
        async function triggerOptimization() {
            try {
                addLog('觸發手動優化...');
                const response = await fetch('/api/optimization/manual', {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.success) {
                    addLog('手動優化執行成功');
                } else {
                    addLog('手動優化失敗: ' + result.error);
                }

                setTimeout(loadInitialData, 2000);
            } catch (error) {
                addLog('手動優化出錯: ' + error.message);
            }
        }

        // 導出數據
        async function exportData() {
            try {
                addLog('導出監控數據...');
                const response = await fetch('/api/export/metrics');
                const blob = await response.blob();

                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `monitoring_data_${new Date().getTime()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);

                addLog('數據導出完成');
            } catch (error) {
                addLog('導出數據失敗: ' + error.message);
            }
        }

        // 添加日誌
        function addLog(message) {
            const logContainer = document.getElementById('systemLogs');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = `[${timestamp}] ${message}\\n`;

            logContainer.textContent += logEntry;
            logContainer.scrollTop = logContainer.scrollHeight;

            // 限制日誌行數
            const lines = logContainer.textContent.split('\\n');
            if (lines.length > 100) {
                logContainer.textContent = lines.slice(-100).join('\\n');
            }
        }

        // 更新儀表板（WebSocket數據）
        function updateDashboard(data) {
            // 實現實時數據更新邏輯
            addLog('收到實時數據更新');
        }

        // 清理
        window.addEventListener('beforeunload', function() {
            if (updateInterval) {
                clearInterval(updateInterval);
            }
            if (ws) {
                ws.close();
            }
        });
    </script>
</body>
</html>
        """

    async def _get_realtime_overview(self) -> dict[str, Any]:
        """獲取實時概覽數據"""
        health_report = self.monitor.get_system_health_report()
        alert_summary = self.alert_system.get_alert_summary()

        return {
            "type": "overview_update",
            "timestamp": time.time(),
            "system_health": health_report,
            "alerts": alert_summary,
            "uptime": time.time() - self.start_time,
        }

    async def connect(self, websocket: WebSocket):
        """WebSocket連接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info("WebSocket連接已建立")

    def disconnect(self, websocket: WebSocket):
        """WebSocket斷開"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info("WebSocket連接已斷開")

    async def broadcast_update(self, data: dict[str, Any]):
        """廣播更新到所有連接"""
        if not self.active_connections:
            return

        message = json.dumps(data, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    async def start_monitoring(self):
        """啟動所有監控服務"""
        self.service_started = True

        # 啟動核心監控組件
        await self.monitor.start_monitoring()

        # 啟動告警系統（這會自動啟動監控和優化循環）
        # 存到 self：asyncio 對 task 只保存弱引用，區域變數在本方法返回後即失效，
        # 告警迴圈可能被 GC 中途回收——這是實際缺陷而非風格問題
        self._alert_task = asyncio.create_task(self.alert_system.start_monitoring())

        self.logger.info("統一監控服務已全面啟動")

    async def stop_monitoring(self):
        """停止所有監控服務"""
        self.service_started = False

        # 停止監控組件
        await self.monitor.stop_monitoring()
        await self.alert_system.stop_monitoring()

        self.logger.info("統一監控服務已停止")

    async def run_server(self):
        """運行服務器"""
        if not FASTAPI_AVAILABLE:
            self.logger.error("FastAPI不可用，無法啟動Web服務")
            return

        config = uvicorn.Config(app=self.app, host=self.host, port=self.port, log_level="info")

        server = uvicorn.Server(config)

        try:
            self.logger.info(f"啟動統一監控服務 http://{self.host}:{self.port}")
            await server.serve()
        except Exception as e:
            self.logger.error(f"服務器運行出錯: {e}")
        finally:
            await self.stop_monitoring()


# 主函數
async def main():
    """主函數"""
    # 創建統一監控服務
    service = UnifiedMonitoringService()

    # 運行服務器
    await service.run_server()


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        print("🎯 啟動增強型自適應策略統一監控平台...")
        print("📊 訪問 http://localhost:8005 查看監控儀表板")
        asyncio.run(main())
    else:
        print("❌ 需要安裝 FastAPI 和相關依賴才能運行監控服務")
        print("💡 運行命令: pip install fastapi uvicorn websockets")
