/**
 * 爬蟲效能監控系統
 * 提供全面的效能監控、統計分析和優化建議
 */

const EventEmitter = require('events');
const os = require('os');
const fs = require('fs').promises;
const path = require('path');
const { logger } = require('./logger');

class CrawlerPerformanceMonitor extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            monitoringInterval: options.monitoringInterval || 30000, // 30秒
            statisticsInterval: options.statisticsInterval || 300000, // 5分鐘統計
            enableResourceMonitoring: options.enableResourceMonitoring !== false,
            enableNetworkMonitoring: options.enableNetworkMonitoring !== false,
            enableDetailedLogging: options.enableDetailedLogging || false,
            retentionDays: options.retentionDays || 7,
            alertThresholds: {
                cpuUsage: options.alertThresholds?.cpuUsage || 0.8,
                memoryUsage: options.alertThresholds?.memoryUsage || 0.8,
                errorRate: options.alertThresholds?.errorRate || 0.1,
                responseTime: options.alertThresholds?.responseTime || 10000,
                ...options.alertThresholds
            },
            ...options
        };

        // 監控資料
        this.metrics = {
            system: {
                cpuUsage: 0,
                memoryUsage: 0,
                diskUsage: 0,
                networkLatency: 0,
                uptime: 0
            },
            crawler: {
                totalRequests: 0,
                successfulRequests: 0,
                failedRequests: 0,
                averageResponseTime: 0,
                requestsPerSecond: 0,
                bytesDownloaded: 0,
                errorRate: 0,
                concurrentConnections: 0
            },
            sources: new Map(), // source -> metrics
            workers: new Map()  // worker -> metrics
        };

        // 歷史資料
        this.history = {
            system: [],
            crawler: [],
            sources: new Map(),
            alerts: []
        };

        // 警告狀態
        this.alertState = new Map();

        // 統計資料
        this.statistics = {
            lastReset: Date.now(),
            peakMetrics: {
                maxCpuUsage: 0,
                maxMemoryUsage: 0,
                maxRequestsPerSecond: 0,
                maxResponseTime: 0
            },
            totalStats: {
                totalUptime: 0,
                totalRequests: 0,
                totalDataProcessed: 0,
                totalErrors: 0
            }
        };

        this.isMonitoring = false;
        this.monitoringTimer = null;
        this.statisticsTimer = null;

        logger.info('爬蟲效能監控系統初始化完成', this.options);
    }

    /**
     * 開始監控
     */
    start() {
        if (this.isMonitoring) {
            logger.warn('監控系統已在運行');
            return;
        }

        this.isMonitoring = true;

        // 啟動定期監控
        this.monitoringTimer = setInterval(() => {
            this.collectMetrics();
        }, this.options.monitoringInterval);

        // 啟動統計分析
        this.statisticsTimer = setInterval(() => {
            this.generateStatistics();
        }, this.options.statisticsInterval);

        // 記錄啟動時間
        this.statistics.startTime = Date.now();

        logger.info('效能監控系統已啟動', {
            monitoringInterval: this.options.monitoringInterval,
            statisticsInterval: this.options.statisticsInterval
        });

        this.emit('monitoringStarted');
    }

    /**
     * 停止監控
     */
    stop() {
        if (!this.isMonitoring) {
            return;
        }

        this.isMonitoring = false;

        if (this.monitoringTimer) {
            clearInterval(this.monitoringTimer);
            this.monitoringTimer = null;
        }

        if (this.statisticsTimer) {
            clearInterval(this.statisticsTimer);
            this.statisticsTimer = null;
        }

        // 最後一次統計收集
        this.generateStatistics();

        logger.info('效能監控系統已停止');
        this.emit('monitoringStopped');
    }

    /**
     * 收集系統指標
     */
    async collectMetrics() {
        try {
            const timestamp = Date.now();

            // 收集系統資源指標
            if (this.options.enableResourceMonitoring) {
                await this.collectSystemMetrics();
            }

            // 收集網路指標
            if (this.options.enableNetworkMonitoring) {
                await this.collectNetworkMetrics();
            }

            // 收集爬蟲指標
            this.collectCrawlerMetrics();

            // 檢查警告條件
            this.checkAlertConditions();

            // 記錄歷史資料
            this.recordHistoryData(timestamp);

            // 清理舊資料
            this.cleanupOldData();

            this.emit('metricsCollected', {
                timestamp,
                metrics: this.getMetricsSnapshot()
            });

        } catch (error) {
            logger.error('收集效能指標失敗', { error: error.message });
        }
    }

    /**
     * 收集系統資源指標
     */
    async collectSystemMetrics() {
        // CPU使用率
        const cpus = os.cpus();
        let totalIdle = 0;
        let totalTick = 0;

        cpus.forEach(cpu => {
            for (const type in cpu.times) {
                totalTick += cpu.times[type];
            }
            totalIdle += cpu.times.idle;
        });

        this.metrics.system.cpuUsage = 1 - (totalIdle / totalTick);

        // 記憶體使用率
        const totalMemory = os.totalmem();
        const freeMemory = os.freemem();
        this.metrics.system.memoryUsage = (totalMemory - freeMemory) / totalMemory;

        // 系統運行時間
        this.metrics.system.uptime = os.uptime();

        // 磁碟使用率 (簡化實現)
        try {
            const stats = await fs.stat(process.cwd());
            this.metrics.system.diskUsage = 0.5; // 佔位符，實際需要更複雜的實現
        } catch (error) {
            this.metrics.system.diskUsage = 0;
        }

        // 更新峰值記錄
        this.statistics.peakMetrics.maxCpuUsage = Math.max(
            this.statistics.peakMetrics.maxCpuUsage,
            this.metrics.system.cpuUsage
        );

        this.statistics.peakMetrics.maxMemoryUsage = Math.max(
            this.statistics.peakMetrics.maxMemoryUsage,
            this.metrics.system.memoryUsage
        );
    }

    /**
     * 收集網路指標
     */
    async collectNetworkMetrics() {
        // 測試網路延遲 (簡化實現)
        const testUrls = [
            'https://www.google.com',
            'https://www.github.com'
        ];

        const latencies = [];

        for (const url of testUrls) {
            try {
                const start = Date.now();
                const response = await fetch(url, {
                    method: 'HEAD',
                    timeout: 5000
                });
                const latency = Date.now() - start;
                latencies.push(latency);
            } catch (error) {
                // 忽略網路錯誤
            }
        }

        if (latencies.length > 0) {
            this.metrics.system.networkLatency = latencies.reduce((a, b) => a + b) / latencies.length;
        }
    }

    /**
     * 收集爬蟲指標
     */
    collectCrawlerMetrics() {
        // 計算請求成功率
        const totalRequests = this.metrics.crawler.totalRequests;
        if (totalRequests > 0) {
            this.metrics.crawler.errorRate = this.metrics.crawler.failedRequests / totalRequests;
        }

        // 計算每秒請求數
        const timeDiff = (Date.now() - this.statistics.lastReset) / 1000;
        if (timeDiff > 0) {
            this.metrics.crawler.requestsPerSecond = this.metrics.crawler.totalRequests / timeDiff;
        }

        // 更新峰值記錄
        this.statistics.peakMetrics.maxRequestsPerSecond = Math.max(
            this.statistics.peakMetrics.maxRequestsPerSecond,
            this.metrics.crawler.requestsPerSecond
        );

        this.statistics.peakMetrics.maxResponseTime = Math.max(
            this.statistics.peakMetrics.maxResponseTime,
            this.metrics.crawler.averageResponseTime
        );
    }

    /**
     * 記錄爬蟲請求
     */
    recordRequest(source, metadata = {}) {
        this.metrics.crawler.totalRequests++;
        this.statistics.totalStats.totalRequests++;

        // 更新來源統計
        if (!this.metrics.sources.has(source)) {
            this.metrics.sources.set(source, {
                totalRequests: 0,
                successfulRequests: 0,
                failedRequests: 0,
                averageResponseTime: 0,
                bytesDownloaded: 0,
                errorRate: 0
            });
        }

        const sourceMetrics = this.metrics.sources.get(source);
        sourceMetrics.totalRequests++;

        this.emit('requestRecorded', { source, metadata });
    }

    /**
     * 記錄請求完成
     */
    recordRequestCompletion(source, success = true, responseTime = 0, bytesDownloaded = 0, statusCode = 200) {
        const sourceMetrics = this.metrics.sources.get(source);
        if (!sourceMetrics) return;

        if (success) {
            this.metrics.crawler.successfulRequests++;
            sourceMetrics.successfulRequests++;
        } else {
            this.metrics.crawler.failedRequests++;
            sourceMetrics.failedRequests++;
            this.statistics.totalStats.totalErrors++;
        }

        // 更新平均響應時間
        const totalSuccessful = this.metrics.crawler.successfulRequests;
        if (totalSuccessful > 0) {
            this.metrics.crawler.averageResponseTime =
                (this.metrics.crawler.averageResponseTime * (totalSuccessful - 1) + responseTime) / totalSuccessful;
        }

        const sourceSuccessful = sourceMetrics.successfulRequests;
        if (sourceSuccessful > 0) {
            sourceMetrics.averageResponseTime =
                (sourceMetrics.averageResponseTime * (sourceSuccessful - 1) + responseTime) / sourceSuccessful;
        }

        // 更新下載量
        this.metrics.crawler.bytesDownloaded += bytesDownloaded;
        sourceMetrics.bytesDownloaded += bytesDownloaded;
        this.statistics.totalStats.totalDataProcessed += bytesDownloaded;

        // 更新錯誤率
        sourceMetrics.errorRate = sourceMetrics.failedRequests / sourceMetrics.totalRequests;

        this.emit('requestCompleted', {
            source,
            success,
            responseTime,
            bytesDownloaded,
            statusCode
        });
    }

    /**
     * 記錄工作執行緒狀態
     */
    recordWorkerStatus(workerId, status) {
        if (!this.metrics.workers.has(workerId)) {
            this.metrics.workers.set(workerId, {
                totalTasks: 0,
                completedTasks: 0,
                failedTasks: 0,
                averageTaskTime: 0,
                isActive: false,
                lastActivity: Date.now()
            });
        }

        const workerMetrics = this.metrics.workers.get(workerId);
        Object.assign(workerMetrics, status);

        this.emit('workerStatusUpdated', { workerId, status });
    }

    /**
     * 檢查警告條件
     */
    checkAlertConditions() {
        const alerts = [];

        // 檢查CPU使用率
        if (this.metrics.system.cpuUsage > this.options.alertThresholds.cpuUsage) {
            alerts.push({
                type: 'cpu_high',
                severity: 'warning',
                value: this.metrics.system.cpuUsage,
                threshold: this.options.alertThresholds.cpuUsage,
                message: `CPU使用率過高: ${Math.round(this.metrics.system.cpuUsage * 100)}%`
            });
        }

        // 檢查記憶體使用率
        if (this.metrics.system.memoryUsage > this.options.alertThresholds.memoryUsage) {
            alerts.push({
                type: 'memory_high',
                severity: 'warning',
                value: this.metrics.system.memoryUsage,
                threshold: this.options.alertThresholds.memoryUsage,
                message: `記憶體使用率過高: ${Math.round(this.metrics.system.memoryUsage * 100)}%`
            });
        }

        // 檢查錯誤率
        if (this.metrics.crawler.errorRate > this.options.alertThresholds.errorRate) {
            alerts.push({
                type: 'error_rate_high',
                severity: 'error',
                value: this.metrics.crawler.errorRate,
                threshold: this.options.alertThresholds.errorRate,
                message: `錯誤率過高: ${Math.round(this.metrics.crawler.errorRate * 100)}%`
            });
        }

        // 檢查響應時間
        if (this.metrics.crawler.averageResponseTime > this.options.alertThresholds.responseTime) {
            alerts.push({
                type: 'response_time_high',
                severity: 'warning',
                value: this.metrics.crawler.averageResponseTime,
                threshold: this.options.alertThresholds.responseTime,
                message: `平均響應時間過長: ${this.metrics.crawler.averageResponseTime}ms`
            });
        }

        // 處理警告
        alerts.forEach(alert => {
            this.handleAlert(alert);
        });
    }

    /**
     * 處理警告
     */
    handleAlert(alert) {
        const alertKey = `${alert.type}_${Math.floor(Date.now() / 60000)}`;

        // 避免重複警告 (1分鐘內)
        if (this.alertState.has(alertKey)) {
            return;
        }

        this.alertState.set(alertKey, alert);

        // 記錄警告歷史
        const alertRecord = {
            ...alert,
            timestamp: Date.now(),
            id: alertKey
        };

        this.history.alerts.push(alertRecord);

        // 限制警告歷史數量
        if (this.history.alerts.length > 1000) {
            this.history.alerts.splice(0, this.history.alerts.length - 1000);
        }

        logger.warn('效能警告', alert);

        this.emit('alert', alertRecord);

        // 清理過期警告狀態
        setTimeout(() => {
            this.alertState.delete(alertKey);
        }, 300000); // 5分鐘後清理
    }

    /**
     * 記錄歷史資料
     */
    recordHistoryData(timestamp) {
        const snapshot = {
            timestamp,
            system: { ...this.metrics.system },
            crawler: { ...this.metrics.crawler }
        };

        this.history.system.push(snapshot);
        this.history.crawler.push(snapshot);

        // 限制歷史資料數量
        const maxHistory = Math.floor(86400000 / this.options.monitoringInterval); // 1天的資料點

        if (this.history.system.length > maxHistory) {
            this.history.system.splice(0, this.history.system.length - maxHistory);
        }

        if (this.history.crawler.length > maxHistory) {
            this.history.crawler.splice(0, this.history.crawler.length - maxHistory);
        }

        // 記錄來源歷史
        for (const [source, metrics] of this.metrics.sources.entries()) {
            if (!this.history.sources.has(source)) {
                this.history.sources.set(source, []);
            }

            const sourceHistory = this.history.sources.get(source);
            sourceHistory.push({
                timestamp,
                metrics: { ...metrics }
            });

            if (sourceHistory.length > maxHistory) {
                sourceHistory.splice(0, sourceHistory.length - maxHistory);
            }
        }
    }

    /**
     * 生成統計報告
     */
    generateStatistics() {
        const now = Date.now();
        const timeSinceStart = now - this.statistics.startTime;

        this.statistics.totalStats.totalUptime = timeSinceStart;

        // 生成來源統計
        const sourceStats = {};
        for (const [source, metrics] of this.metrics.sources.entries()) {
            sourceStats[source] = {
                ...metrics,
                requestsPerHour: metrics.totalRequests / (timeSinceStart / 3600000),
                successRate: metrics.totalRequests > 0 ? metrics.successfulRequests / metrics.totalRequests : 0
            };
        }

        // 生成工作執行緒統計
        const workerStats = {};
        for (const [workerId, metrics] of this.metrics.workers.entries()) {
            workerStats[workerId] = {
                ...metrics,
                successRate: metrics.totalTasks > 0 ? metrics.completedTasks / metrics.totalTasks : 0
            };
        }

        const statisticsReport = {
            timestamp: now,
            period: {
                start: this.statistics.startTime,
                duration: timeSinceStart
            },
            system: {
                ...this.metrics.system,
                peaks: this.statistics.peakMetrics
            },
            crawler: {
                ...this.metrics.crawler,
                totals: this.statistics.totalStats
            },
            sources: sourceStats,
            workers: workerStats,
            alerts: {
                total: this.history.alerts.length,
                recent: this.history.alerts.filter(a => now - a.timestamp < 3600000).length // 1小時內
            }
        };

        logger.info('效能統計報告', {
            uptime: Math.round(timeSinceStart / 1000),
            totalRequests: this.metrics.crawler.totalRequests,
            errorRate: Math.round(this.metrics.crawler.errorRate * 100),
            avgResponseTime: Math.round(this.metrics.crawler.averageResponseTime)
        });

        this.emit('statisticsGenerated', statisticsReport);

        return statisticsReport;
    }

    /**
     * 清理舊資料
     */
    cleanupOldData() {
        const cutoffTime = Date.now() - (this.options.retentionDays * 86400000);

        // 清理警告歷史
        this.history.alerts = this.history.alerts.filter(alert => alert.timestamp > cutoffTime);
    }

    /**
     * 獲取當前指標快照
     */
    getMetricsSnapshot() {
        return {
            timestamp: Date.now(),
            system: { ...this.metrics.system },
            crawler: { ...this.metrics.crawler },
            sources: Object.fromEntries(this.metrics.sources),
            workers: Object.fromEntries(this.metrics.workers)
        };
    }

    /**
     * 獲取歷史資料
     */
    getHistoryData(type = 'all', timeRange = 3600000) { // 預設1小時
        const cutoffTime = Date.now() - timeRange;
        const result = {};

        if (type === 'all' || type === 'system') {
            result.system = this.history.system.filter(data => data.timestamp > cutoffTime);
        }

        if (type === 'all' || type === 'crawler') {
            result.crawler = this.history.crawler.filter(data => data.timestamp > cutoffTime);
        }

        if (type === 'all' || type === 'sources') {
            result.sources = {};
            for (const [source, history] of this.history.sources.entries()) {
                result.sources[source] = history.filter(data => data.timestamp > cutoffTime);
            }
        }

        if (type === 'all' || type === 'alerts') {
            result.alerts = this.history.alerts.filter(alert => alert.timestamp > cutoffTime);
        }

        return result;
    }

    /**
     * 重設統計資料
     */
    resetStatistics() {
        this.statistics.lastReset = Date.now();
        this.statistics.peakMetrics = {
            maxCpuUsage: 0,
            maxMemoryUsage: 0,
            maxRequestsPerSecond: 0,
            maxResponseTime: 0
        };

        this.metrics.crawler = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageResponseTime: 0,
            requestsPerSecond: 0,
            bytesDownloaded: 0,
            errorRate: 0,
            concurrentConnections: 0
        };

        this.metrics.sources.clear();
        this.metrics.workers.clear();

        logger.info('效能統計已重設');
        this.emit('statisticsReset');
    }

    /**
     * 獲取效能建議
     */
    getPerformanceRecommendations() {
        const recommendations = [];

        // CPU使用率建議
        if (this.metrics.system.cpuUsage > 0.8) {
            recommendations.push({
                type: 'cpu',
                priority: 'high',
                message: '建議降低併發數或增加處理間隔',
                action: 'reduce_concurrency'
            });
        }

        // 記憶體使用率建議
        if (this.metrics.system.memoryUsage > 0.8) {
            recommendations.push({
                type: 'memory',
                priority: 'high',
                message: '建議啟用垃圾回收或減少資料快取',
                action: 'optimize_memory'
            });
        }

        // 錯誤率建議
        if (this.metrics.crawler.errorRate > 0.1) {
            recommendations.push({
                type: 'errors',
                priority: 'medium',
                message: '建議啟用退避機制或檢查目標網站狀態',
                action: 'enable_backoff'
            });
        }

        // 響應時間建議
        if (this.metrics.crawler.averageResponseTime > 10000) {
            recommendations.push({
                type: 'response_time',
                priority: 'medium',
                message: '建議檢查網路連接或增加請求超時時間',
                action: 'check_network'
            });
        }

        return recommendations;
    }
}

module.exports = CrawlerPerformanceMonitor;