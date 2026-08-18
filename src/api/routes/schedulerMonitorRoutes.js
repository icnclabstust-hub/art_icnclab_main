/**
 * 排程狀態監控 API 路由
 * 提供排程監控儀表板的 REST API 接口
 */

const express = require('express');
const router = express.Router();
const { logger } = require('../../utils/logger');
const { createAsyncWrapper } = require('../middleware/errorHandlingMiddleware');

class SchedulerMonitorController {
    constructor(schedulerMonitor) {
        this.schedulerMonitor = schedulerMonitor;
        this.setupRoutes();
    }

    setupRoutes() {
        const asyncWrapper = createAsyncWrapper({
            enableRetry: true,
            maxRetries: 2
        });

        // 獲取監控總覽狀態
        router.get('/overview', asyncWrapper(async (req, res) => {
            const monitoringStatus = this.schedulerMonitor.getMonitoringStatus();

            res.json({
                success: true,
                data: {
                    monitoring: {
                        isActive: monitoringStatus.isMonitoring,
                        uptime: monitoringStatus.uptime,
                        averageHealthScore: monitoringStatus.averageHealthScore
                    },
                    system: {
                        totalJobs: monitoringStatus.totalJobs,
                        memoryUsage: Math.round(monitoringStatus.systemMetrics.memoryUsage / 1024 / 1024),
                        memoryTotal: Math.round(monitoringStatus.systemMetrics.memoryTotal / 1024 / 1024),
                        cpuUsage: monitoringStatus.systemMetrics.cpuUser || 0
                    },
                    health: {
                        checks: monitoringStatus.healthChecks,
                        recentAlerts: monitoringStatus.recentAlerts.length,
                        criticalAlerts: monitoringStatus.recentAlerts.filter(a => a.severity === 'critical').length
                    }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取詳細系統狀態
        router.get('/status', asyncWrapper(async (req, res) => {
            const status = this.schedulerMonitor.getMonitoringStatus();

            res.json({
                success: true,
                data: status,
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取所有任務的監控狀態
        router.get('/jobs', asyncWrapper(async (req, res) => {
            const { status, type, healthThreshold } = req.query;

            const allJobsData = [];

            for (const [jobId, jobMetrics] of this.schedulerMonitor.metrics.jobMetrics) {
                // 應用過濾器
                if (status && jobMetrics.status !== status) continue;
                if (type && jobMetrics.taskType !== type) continue;
                if (healthThreshold && jobMetrics.healthScore < parseFloat(healthThreshold)) continue;

                allJobsData.push({
                    jobId: jobMetrics.jobId,
                    name: jobMetrics.name,
                    taskType: jobMetrics.taskType,
                    status: jobMetrics.status,
                    enabled: jobMetrics.enabled,
                    healthScore: jobMetrics.healthScore,
                    successRate: jobMetrics.successRate,
                    totalExecutions: jobMetrics.totalExecutions,
                    consecutiveFailures: jobMetrics.consecutiveFailures,
                    lastExecution: jobMetrics.lastExecution,
                    nextExecution: jobMetrics.nextExecution,
                    averageExecutionTime: jobMetrics.averageExecutionTime,
                    lastError: jobMetrics.lastError
                });
            }

            // 排序（依健康評分降序）
            allJobsData.sort((a, b) => b.healthScore - a.healthScore);

            res.json({
                success: true,
                data: {
                    jobs: allJobsData,
                    total: allJobsData.length,
                    filters: { status, type, healthThreshold }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取特定任務的詳細監控資料
        router.get('/jobs/:jobId', asyncWrapper(async (req, res) => {
            const { jobId } = req.params;

            try {
                const jobData = this.schedulerMonitor.getJobMonitoringData(jobId);

                res.json({
                    success: true,
                    data: jobData,
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                return res.status(404).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'JOB_NOT_FOUND',
                        jobId
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 獲取性能歷史資料
        router.get('/performance', asyncWrapper(async (req, res) => {
            const { timeRange = 86400000, granularity = '5m' } = req.query; // 預設24小時，5分鐘顆粒度

            const performanceReport = this.schedulerMonitor.getPerformanceReport(parseInt(timeRange));

            // 根據顆粒度調整資料點
            let processedHistory = performanceReport.history || [];

            if (granularity === '1h' && processedHistory.length > 24) {
                // 每小時取樣
                processedHistory = this.sampleData(processedHistory, 60 * 60 * 1000);
            } else if (granularity === '15m' && processedHistory.length > 96) {
                // 每15分鐘取樣
                processedHistory = this.sampleData(processedHistory, 15 * 60 * 1000);
            }

            res.json({
                success: true,
                data: {
                    ...performanceReport,
                    history: processedHistory,
                    granularity,
                    charts: {
                        memoryUsage: processedHistory.map(h => ({
                            timestamp: h.timestamp,
                            value: h.memoryUsageMB
                        })),
                        healthScore: processedHistory.map(h => ({
                            timestamp: h.timestamp,
                            value: h.averageHealthScore
                        })),
                        systemLoad: processedHistory.map(h => ({
                            timestamp: h.timestamp,
                            value: h.systemLoad
                        }))
                    }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取告警歷史
        router.get('/alerts', asyncWrapper(async (req, res) => {
            const { severity, jobId, limit = 50, offset = 0 } = req.query;

            let alerts = [...this.schedulerMonitor.metrics.alertHistory];

            // 應用過濾器
            if (severity) {
                alerts = alerts.filter(alert => alert.severity === severity);
            }

            if (jobId) {
                alerts = alerts.filter(alert => alert.jobId === jobId);
            }

            // 排序（最新的在前）
            alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            // 分頁
            const total = alerts.length;
            const paginatedAlerts = alerts.slice(parseInt(offset), parseInt(offset) + parseInt(limit));

            // 統計告警類型
            const alertStats = {
                total,
                bySeverity: {
                    critical: alerts.filter(a => a.severity === 'critical').length,
                    error: alerts.filter(a => a.severity === 'error').length,
                    warning: alerts.filter(a => a.severity === 'warning').length
                },
                byType: {}
            };

            alerts.forEach(alert => {
                alertStats.byType[alert.type] = (alertStats.byType[alert.type] || 0) + 1;
            });

            res.json({
                success: true,
                data: {
                    alerts: paginatedAlerts,
                    statistics: alertStats,
                    pagination: {
                        total,
                        limit: parseInt(limit),
                        offset: parseInt(offset),
                        hasMore: parseInt(offset) + parseInt(limit) < total
                    },
                    filters: { severity, jobId }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取健康檢查狀態
        router.get('/health', asyncWrapper(async (req, res) => {
            const monitoringStatus = this.schedulerMonitor.getMonitoringStatus();
            const healthChecks = monitoringStatus.healthChecks;

            // 計算整體健康狀態
            const healthStatuses = Object.values(healthChecks).map(check => check.status);
            const criticalCount = healthStatuses.filter(s => s === 'error').length;
            const warningCount = healthStatuses.filter(s => s === 'warning').length;

            let overallStatus = 'healthy';
            if (criticalCount > 0) {
                overallStatus = 'critical';
            } else if (warningCount > 0) {
                overallStatus = 'warning';
            }

            // HTTP狀態碼
            const httpStatus = overallStatus === 'critical' ? 503 :
                             overallStatus === 'warning' ? 200 : 200;

            res.status(httpStatus).json({
                success: true,
                data: {
                    overall: overallStatus,
                    score: monitoringStatus.averageHealthScore,
                    checks: healthChecks,
                    summary: {
                        total: Object.keys(healthChecks).length,
                        healthy: healthStatuses.filter(s => s === 'healthy').length,
                        warning: warningCount,
                        critical: criticalCount
                    },
                    monitoring: {
                        isActive: monitoringStatus.isMonitoring,
                        uptime: monitoringStatus.uptime
                    }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取任務類型統計
        router.get('/statistics/task-types', asyncWrapper(async (req, res) => {
            const taskTypeStats = new Map();

            for (const [, jobMetrics] of this.schedulerMonitor.metrics.jobMetrics) {
                const taskType = jobMetrics.taskType;

                if (!taskTypeStats.has(taskType)) {
                    taskTypeStats.set(taskType, {
                        taskType,
                        totalJobs: 0,
                        activeJobs: 0,
                        totalExecutions: 0,
                        successfulExecutions: 0,
                        averageHealthScore: 0,
                        averageExecutionTime: 0
                    });
                }

                const stats = taskTypeStats.get(taskType);
                stats.totalJobs++;

                if (jobMetrics.enabled) {
                    stats.activeJobs++;
                }

                stats.totalExecutions += jobMetrics.totalExecutions;
                stats.successfulExecutions += jobMetrics.successfulExecutions;
                stats.averageHealthScore += jobMetrics.healthScore;
                stats.averageExecutionTime += jobMetrics.averageExecutionTime;
            }

            // 計算平均值
            const results = Array.from(taskTypeStats.values()).map(stats => ({
                ...stats,
                successRate: stats.totalExecutions > 0 ?
                           (stats.successfulExecutions / stats.totalExecutions) : 1,
                averageHealthScore: stats.totalJobs > 0 ?
                                  (stats.averageHealthScore / stats.totalJobs) : 0,
                averageExecutionTime: stats.totalJobs > 0 ?
                                    (stats.averageExecutionTime / stats.totalJobs) : 0
            }));

            res.json({
                success: true,
                data: {
                    taskTypes: results,
                    total: results.length
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取執行歷史趨勢
        router.get('/statistics/execution-trends', asyncWrapper(async (req, res) => {
            const { period = '24h' } = req.query;

            const periodMs = this.parsePeriod(period);
            const cutoffTime = Date.now() - periodMs;

            const trends = {
                totalExecutions: 0,
                successfulExecutions: 0,
                failedExecutions: 0,
                averageExecutionTime: 0,
                trendsData: []
            };

            // 從性能歷史資料計算趨勢
            const relevantHistory = this.schedulerMonitor.metrics.performanceHistory.filter(
                record => record.timestamp.getTime() > cutoffTime
            );

            if (relevantHistory.length > 0) {
                // 計算時間段內的執行統計
                for (const [, jobMetrics] of this.schedulerMonitor.metrics.jobMetrics) {
                    trends.totalExecutions += jobMetrics.totalExecutions;
                    trends.successfulExecutions += jobMetrics.successfulExecutions;
                    trends.failedExecutions += jobMetrics.failedExecutions;
                }

                // 生成趨勢資料點
                trends.trendsData = relevantHistory.map(record => ({
                    timestamp: record.timestamp,
                    activeJobs: record.activeJobs,
                    healthScore: record.averageHealthScore,
                    memoryUsage: record.memoryUsageMB
                }));
            }

            // 計算成功率
            trends.successRate = trends.totalExecutions > 0 ?
                               (trends.successfulExecutions / trends.totalExecutions) : 1;

            res.json({
                success: true,
                data: {
                    period,
                    periodMs,
                    trends,
                    dataPoints: trends.trendsData.length
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 抑制告警
        router.post('/alerts/:alertType/suppress', asyncWrapper(async (req, res) => {
            const { alertType } = req.params;
            const { jobId, duration = 3600000, reason } = req.body; // 預設抑制1小時

            try {
                this.schedulerMonitor.suppressAlert(alertType, jobId, duration);

                logger.info('告警已抑制', {
                    alertType,
                    jobId,
                    duration,
                    reason,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        alertType,
                        jobId,
                        suppressedUntil: new Date(Date.now() + duration),
                        duration,
                        reason
                    },
                    message: '告警抑制已設定',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('抑制告警失敗', {
                    alertType,
                    jobId,
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: '抑制告警失敗',
                        code: 'SUPPRESS_ALERT_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 獲取監控配置
        router.get('/config', asyncWrapper(async (req, res) => {
            const status = this.schedulerMonitor.getMonitoringStatus();

            res.json({
                success: true,
                data: {
                    config: status.monitoringConfig,
                    alertThresholds: this.schedulerMonitor.options.alertThresholds,
                    retentionPeriod: this.schedulerMonitor.options.retentionPeriod,
                    monitoringInterval: this.schedulerMonitor.options.monitoringInterval
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 更新監控配置
        router.put('/config', asyncWrapper(async (req, res) => {
            const { alertThresholds, enableRealTimeAlerts } = req.body;

            try {
                // 更新告警閾值
                if (alertThresholds) {
                    Object.assign(this.schedulerMonitor.options.alertThresholds, alertThresholds);
                }

                // 更新告警開關
                if (typeof enableRealTimeAlerts === 'boolean') {
                    this.schedulerMonitor.options.enableRealTimeAlerts = enableRealTimeAlerts;
                }

                logger.info('監控配置已更新', {
                    alertThresholds,
                    enableRealTimeAlerts,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        alertThresholds: this.schedulerMonitor.options.alertThresholds,
                        enableRealTimeAlerts: this.schedulerMonitor.options.enableRealTimeAlerts
                    },
                    message: '監控配置已更新',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('更新監控配置失敗', {
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: '更新監控配置失敗',
                        code: 'CONFIG_UPDATE_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 導出監控資料
        router.get('/export', asyncWrapper(async (req, res) => {
            const { format = 'json', period = '24h', includeHistory = 'false' } = req.query;

            try {
                const exportData = {
                    exportTime: new Date().toISOString(),
                    period,
                    monitoring: this.schedulerMonitor.getMonitoringStatus(),
                    performance: this.schedulerMonitor.getPerformanceReport(this.parsePeriod(period))
                };

                if (includeHistory === 'true') {
                    exportData.fullHistory = {
                        alerts: this.schedulerMonitor.metrics.alertHistory,
                        performance: this.schedulerMonitor.metrics.performanceHistory
                    };
                }

                if (format === 'json') {
                    res.json({
                        success: true,
                        data: exportData,
                        timestamp: new Date().toISOString()
                    });
                } else if (format === 'csv') {
                    const csvData = this.convertMonitoringDataToCSV(exportData);

                    res.setHeader('Content-Type', 'text/csv');
                    res.setHeader('Content-Disposition',
                                 `attachment; filename=scheduler-monitoring-${Date.now()}.csv`);
                    res.send(csvData);
                } else {
                    res.status(400).json({
                        success: false,
                        error: {
                            message: '不支援的導出格式',
                            code: 'UNSUPPORTED_FORMAT',
                            supportedFormats: ['json', 'csv']
                        },
                        timestamp: new Date().toISOString()
                    });
                }

            } catch (error) {
                logger.error('導出監控資料失敗', {
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: '導出監控資料失敗',
                        code: 'EXPORT_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));
    }

    /**
     * 資料取樣以減少資料點數量
     */
    sampleData(data, intervalMs) {
        if (data.length <= 100) return data; // 如果資料點少於100個就不取樣

        const sampled = [];
        let lastTime = 0;

        for (const point of data) {
            const pointTime = new Date(point.timestamp).getTime();
            if (pointTime - lastTime >= intervalMs) {
                sampled.push(point);
                lastTime = pointTime;
            }
        }

        return sampled;
    }

    /**
     * 解析時間週期
     */
    parsePeriod(period) {
        const matches = period.match(/^(\d+)([hmwd])$/);
        if (!matches) return 24 * 60 * 60 * 1000; // 預設24小時

        const value = parseInt(matches[1]);
        const unit = matches[2];

        switch (unit) {
            case 'h': return value * 60 * 60 * 1000;
            case 'm': return value * 60 * 1000;
            case 'd': return value * 24 * 60 * 60 * 1000;
            case 'w': return value * 7 * 24 * 60 * 60 * 1000;
            default: return 24 * 60 * 60 * 1000;
        }
    }

    /**
     * 將監控資料轉換為CSV格式
     */
    convertMonitoringDataToCSV(data) {
        const headers = [
            'Timestamp',
            'Job ID',
            'Job Name',
            'Task Type',
            'Status',
            'Health Score',
            'Success Rate',
            'Total Executions',
            'Failed Executions',
            'Avg Execution Time (ms)',
            'Memory Usage (MB)'
        ];

        const rows = [];

        // 添加任務資料行
        for (const [, jobMetrics] of this.schedulerMonitor.metrics.jobMetrics) {
            rows.push([
                new Date().toISOString(),
                jobMetrics.jobId,
                jobMetrics.name,
                jobMetrics.taskType,
                jobMetrics.status,
                jobMetrics.healthScore.toFixed(3),
                jobMetrics.successRate.toFixed(3),
                jobMetrics.totalExecutions,
                jobMetrics.failedExecutions,
                Math.round(jobMetrics.averageExecutionTime),
                Math.round(this.schedulerMonitor.metrics.systemMetrics.memoryUsage / 1024 / 1024)
            ]);
        }

        const csvContent = [headers, ...rows]
            .map(row => row.map(field => `"${field}"`).join(','))
            .join('\n');

        return csvContent;
    }
}

module.exports = (schedulerMonitor) => {
    const controller = new SchedulerMonitorController(schedulerMonitor);
    return router;
};