/**
 * 資料品質監控API路由
 * 提供品質指標查詢、評估觸發、報告生成等功能
 */

const express = require('express');
const { logger } = require('../../utils/logger');

function createDataQualityRoutes(dataQualityMonitor) {
    const router = express.Router();

    /**
     * GET /status - 獲取品質監控狀態
     */
    router.get('/status', async (req, res) => {
        try {
            const status = dataQualityMonitor.getMonitoringStatus();
            res.json({
                success: true,
                data: status,
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質監控狀態失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取監控狀態失敗',
                message: error.message
            });
        }
    });

    /**
     * GET /report - 獲取品質報告
     */
    router.get('/report', async (req, res) => {
        try {
            const timeRange = parseInt(req.query.timeRange) || 24 * 60 * 60 * 1000; // 預設24小時
            const report = dataQualityMonitor.getQualityReport(timeRange);

            res.json({
                success: true,
                data: report,
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質報告失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取品質報告失敗',
                message: error.message
            });
        }
    });

    /**
     * POST /evaluate - 觸發品質評估
     */
    router.post('/evaluate', async (req, res) => {
        try {
            logger.info('手動觸發品質評估', { user: req.ip });

            const evaluation = await dataQualityMonitor.performQualityEvaluation();

            if (!evaluation) {
                return res.status(404).json({
                    success: false,
                    error: '無可評估的資料'
                });
            }

            res.json({
                success: true,
                data: evaluation,
                message: '品質評估完成',
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('執行品質評估失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '執行品質評估失敗',
                message: error.message
            });
        }
    });

    /**
     * GET /metrics - 獲取歷史品質指標
     */
    router.get('/metrics', async (req, res) => {
        try {
            const {
                metric = 'overall',
                limit = 100,
                startDate,
                endDate
            } = req.query;

            const allMetrics = dataQualityMonitor.qualityMetrics;

            if (!allMetrics[metric]) {
                return res.status(400).json({
                    success: false,
                    error: '無效的指標名稱',
                    availableMetrics: Object.keys(allMetrics).filter(key => Array.isArray(allMetrics[key]))
                });
            }

            let metrics = allMetrics[metric];

            // 時間範圍過濾
            if (startDate || endDate) {
                const start = startDate ? new Date(startDate) : new Date(0);
                const end = endDate ? new Date(endDate) : new Date();

                metrics = metrics.filter(m => {
                    const timestamp = new Date(m.timestamp);
                    return timestamp >= start && timestamp <= end;
                });
            }

            // 限制結果數量
            if (limit) {
                metrics = metrics.slice(-parseInt(limit));
            }

            res.json({
                success: true,
                data: {
                    metric,
                    values: metrics,
                    count: metrics.length
                },
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質指標失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取品質指標失敗',
                message: error.message
            });
        }
    });

    /**
     * GET /trends - 獲取品質趨勢分析
     */
    router.get('/trends', async (req, res) => {
        try {
            const timeRange = parseInt(req.query.timeRange) || 7 * 24 * 60 * 60 * 1000; // 預設7天
            const cutoffTime = Date.now() - timeRange;

            const trends = {};
            const allMetrics = dataQualityMonitor.qualityMetrics;

            for (const [key, metrics] of Object.entries(allMetrics)) {
                if (Array.isArray(metrics)) {
                    const recentMetrics = metrics.filter(m =>
                        new Date(m.timestamp).getTime() > cutoffTime
                    );

                    if (recentMetrics.length > 0) {
                        const values = recentMetrics.map(m => m.value);
                        trends[key] = {
                            current: values[values.length - 1],
                            average: values.reduce((sum, v) => sum + v, 0) / values.length,
                            min: Math.min(...values),
                            max: Math.max(...values),
                            trend: dataQualityMonitor.calculateTrend(recentMetrics),
                            dataPoints: values.length
                        };
                    }
                }
            }

            res.json({
                success: true,
                data: {
                    timeRange,
                    trends
                },
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質趨勢失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取品質趨勢失敗',
                message: error.message
            });
        }
    });

    /**
     * PUT /config - 更新監控配置
     */
    router.put('/config', async (req, res) => {
        try {
            const {
                evaluationInterval,
                alertThresholds,
                sampleSize,
                enableAlerts
            } = req.body;

            // 驗證配置參數
            const updates = {};

            if (evaluationInterval && evaluationInterval >= 60000) { // 最少1分鐘
                updates.evaluationInterval = evaluationInterval;
            }

            if (alertThresholds && typeof alertThresholds === 'object') {
                updates.alertThresholds = { ...dataQualityMonitor.options.alertThresholds, ...alertThresholds };
            }

            if (sampleSize && sampleSize > 0 && sampleSize <= 10000) {
                updates.sampleSize = sampleSize;
            }

            if (typeof enableAlerts === 'boolean') {
                updates.enableAlerts = enableAlerts;
            }

            // 應用更新
            Object.assign(dataQualityMonitor.options, updates);

            logger.info('品質監控配置已更新', updates);

            res.json({
                success: true,
                data: {
                    updated: updates,
                    current: dataQualityMonitor.options
                },
                message: '配置更新成功',
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('更新監控配置失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '更新配置失敗',
                message: error.message
            });
        }
    });

    /**
     * GET /alerts - 獲取品質告警記錄
     */
    router.get('/alerts', async (req, res) => {
        try {
            const {
                limit = 50,
                severity,
                type,
                startDate,
                endDate
            } = req.query;

            // 從事件歷史中獲取告警記錄
            let alerts = dataQualityMonitor.alertHistory || [];

            // 過濾條件
            if (severity) {
                alerts = alerts.filter(alert => alert.severity === severity);
            }

            if (type) {
                alerts = alerts.filter(alert => alert.type === type);
            }

            if (startDate || endDate) {
                const start = startDate ? new Date(startDate) : new Date(0);
                const end = endDate ? new Date(endDate) : new Date();

                alerts = alerts.filter(alert => {
                    const timestamp = new Date(alert.timestamp);
                    return timestamp >= start && timestamp <= end;
                });
            }

            // 限制結果數量並按時間排序
            alerts = alerts
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                .slice(0, parseInt(limit));

            res.json({
                success: true,
                data: {
                    alerts,
                    count: alerts.length,
                    filters: { severity, type, startDate, endDate }
                },
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質告警失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取告警記錄失敗',
                message: error.message
            });
        }
    });

    /**
     * GET /dashboard - 獲取品質儀表板資料
     */
    router.get('/dashboard', async (req, res) => {
        try {
            const status = dataQualityMonitor.getMonitoringStatus();
            const report = dataQualityMonitor.getQualityReport(24 * 60 * 60 * 1000);

            const dashboard = {
                status: {
                    isMonitoring: status.isMonitoring,
                    lastEvaluation: status.lastEvaluation,
                    evaluationInterval: status.evaluationInterval
                },
                currentQuality: report.current ? {
                    overallScore: report.current.overallScore,
                    grade: report.summary?.qualityGrade,
                    timestamp: report.current.timestamp
                } : null,
                trends: report.trends,
                topIssues: report.summary?.topIssues || [],
                recommendations: report.summary?.recommendations || [],
                quickStats: {
                    totalMetrics: status.metricsCount,
                    rulesCount: status.qualityRules.length,
                    alertsEnabled: status.alertThresholds
                }
            };

            res.json({
                success: true,
                data: dashboard,
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('獲取品質儀表板失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '獲取儀表板資料失敗',
                message: error.message
            });
        }
    });

    /**
     * POST /start - 啟動品質監控
     */
    router.post('/start', async (req, res) => {
        try {
            if (dataQualityMonitor.isMonitoring) {
                return res.status(400).json({
                    success: false,
                    error: '品質監控已在運行中'
                });
            }

            await dataQualityMonitor.startMonitoring();

            logger.info('品質監控已通過API啟動', { user: req.ip });

            res.json({
                success: true,
                message: '品質監控已啟動',
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('啟動品質監控失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '啟動監控失敗',
                message: error.message
            });
        }
    });

    /**
     * POST /stop - 停止品質監控
     */
    router.post('/stop', async (req, res) => {
        try {
            if (!dataQualityMonitor.isMonitoring) {
                return res.status(400).json({
                    success: false,
                    error: '品質監控未在運行'
                });
            }

            await dataQualityMonitor.stopMonitoring();

            logger.info('品質監控已通過API停止', { user: req.ip });

            res.json({
                success: true,
                message: '品質監控已停止',
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('停止品質監控失敗', { error: error.message });
            res.status(500).json({
                success: false,
                error: '停止監控失敗',
                message: error.message
            });
        }
    });

    // 錯誤處理中間件
    router.use((error, req, res, next) => {
        logger.error('品質監控API錯誤', {
            error: error.message,
            path: req.path,
            method: req.method
        });

        res.status(500).json({
            success: false,
            error: '內部服務錯誤',
            message: error.message
        });
    });

    return router;
}

module.exports = createDataQualityRoutes;