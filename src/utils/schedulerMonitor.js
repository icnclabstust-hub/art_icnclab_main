/**
 * 排程狀態監控系統
 * 提供全面的排程任務監控、告警、性能分析功能
 */

const EventEmitter = require('events');
const { logger } = require('./logger');

class SchedulerMonitor extends EventEmitter {
    constructor(cronScheduler, options = {}) {
        super();

        this.cronScheduler = cronScheduler;
        this.options = {
            monitoringInterval: options.monitoringInterval || 30000, // 30 seconds
            alertThresholds: {
                consecutiveFailures: options.consecutiveFailures || 3,
                successRate: options.successRate || 0.8,
                avgExecutionTime: options.avgExecutionTime || 300000, // 5 minutes
                memoryUsage: options.memoryUsage || 500 * 1024 * 1024, // 500MB
                ...options.alertThresholds
            },
            retentionPeriod: options.retentionPeriod || 7 * 24 * 60 * 60 * 1000, // 7 days
            enableRealTimeAlerts: options.enableRealTimeAlerts !== false,
            ...options
        };

        // 監控資料儲存
        this.metrics = {
            systemMetrics: {
                uptime: Date.now(),
                totalJobs: 0,
                activeJobs: 0,
                completedJobs: 0,
                failedJobs: 0,
                averageExecutionTime: 0,
                systemLoad: 0,
                memoryUsage: 0,
                cpuUsage: 0
            },
            jobMetrics: new Map(),
            performanceHistory: [],
            alertHistory: [],
            healthChecks: new Map()
        };

        // 告警狀態管理
        this.alertStates = new Map();
        this.suppressedAlerts = new Set();

        // 監控狀態
        this.isMonitoring = false;
        this.monitoringInterval = null;
        this.lastCleanupTime = Date.now();

        logger.info('排程監控系統初始化完成');
    }

    /**
     * 啟動監控
     */
    async startMonitoring() {
        if (this.isMonitoring) {
            logger.warn('排程監控已經在運行中');
            return;
        }

        try {
            // 初始化監控資料
            await this.initializeMetrics();

            // 設定監控循環
            this.monitoringInterval = setInterval(() => {
                this.collectMetrics();
            }, this.options.monitoringInterval);

            // 設定告警檢查
            this.alertInterval = setInterval(() => {
                this.checkAlerts();
            }, this.options.monitoringInterval);

            // 設定清理任務
            this.cleanupInterval = setInterval(() => {
                this.performCleanup();
            }, 60 * 60 * 1000); // 每小時執行一次

            // 監聽排程器事件
            this.setupEventListeners();

            this.isMonitoring = true;
            logger.info('排程監控系統已啟動', {
                monitoringInterval: this.options.monitoringInterval,
                alertsEnabled: this.options.enableRealTimeAlerts
            });

            this.emit('monitoringStarted');

        } catch (error) {
            logger.error('啟動排程監控失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 停止監控
     */
    async stopMonitoring() {
        if (!this.isMonitoring) {
            logger.warn('排程監控未在運行');
            return;
        }

        try {
            // 清除定時器
            if (this.monitoringInterval) {
                clearInterval(this.monitoringInterval);
                this.monitoringInterval = null;
            }

            if (this.alertInterval) {
                clearInterval(this.alertInterval);
                this.alertInterval = null;
            }

            if (this.cleanupInterval) {
                clearInterval(this.cleanupInterval);
                this.cleanupInterval = null;
            }

            // 移除事件監聽器
            this.removeEventListeners();

            this.isMonitoring = false;
            logger.info('排程監控系統已停止');

            this.emit('monitoringStopped');

        } catch (error) {
            logger.error('停止排程監控失敗', { error: error.message });
        }
    }

    /**
     * 初始化監控指標
     */
    async initializeMetrics() {
        // 從排程器獲取初始狀態
        const schedulerStats = this.cronScheduler.getScheduleStats();

        this.metrics.systemMetrics = {
            ...this.metrics.systemMetrics,
            totalJobs: schedulerStats.totalSchedules,
            activeJobs: schedulerStats.activeSchedules,
            uptime: Date.now()
        };

        // 初始化每個任務的監控指標
        for (const [jobId, jobConfig] of this.cronScheduler.jobConfigs) {
            this.initializeJobMetrics(jobId, jobConfig);
        }

        logger.info('監控指標初始化完成', {
            totalJobs: this.metrics.systemMetrics.totalJobs,
            activeJobs: this.metrics.systemMetrics.activeJobs
        });
    }

    /**
     * 初始化單個任務的監控指標
     */
    initializeJobMetrics(jobId, jobConfig) {
        if (!this.metrics.jobMetrics.has(jobId)) {
            this.metrics.jobMetrics.set(jobId, {
                jobId,
                name: jobConfig.name,
                taskType: jobConfig.taskType,
                cronExpression: jobConfig.cronExpression,
                status: jobConfig.status,
                enabled: jobConfig.enabled,
                created: jobConfig.createdAt || new Date(),

                // 執行統計
                totalExecutions: 0,
                successfulExecutions: 0,
                failedExecutions: 0,
                consecutiveFailures: 0,
                lastExecution: null,
                nextExecution: null,

                // 性能指標
                averageExecutionTime: 0,
                minExecutionTime: null,
                maxExecutionTime: null,
                totalExecutionTime: 0,

                // 健康狀態
                healthScore: 1.0,
                successRate: 1.0,
                lastError: null,
                errorPattern: new Map(),

                // 歷史記錄
                executionHistory: [],
                performanceMetrics: []
            });
        }
    }

    /**
     * 收集監控指標
     */
    async collectMetrics() {
        try {
            // 收集系統指標
            await this.collectSystemMetrics();

            // 收集任務指標
            await this.collectJobMetrics();

            // 收集性能指標
            await this.collectPerformanceMetrics();

            // 更新健康檢查
            await this.updateHealthChecks();

            this.emit('metricsCollected', {
                timestamp: new Date(),
                systemMetrics: this.metrics.systemMetrics
            });

        } catch (error) {
            logger.error('收集監控指標失敗', { error: error.message });
        }
    }

    /**
     * 收集系統指標
     */
    async collectSystemMetrics() {
        const stats = this.cronScheduler.getScheduleStats();
        const memUsage = process.memoryUsage();
        const cpuUsage = process.cpuUsage();

        this.metrics.systemMetrics = {
            ...this.metrics.systemMetrics,
            totalJobs: stats.totalSchedules,
            activeJobs: stats.activeSchedules,
            completedJobs: stats.totalExecutions,
            uptime: Date.now() - this.metrics.systemMetrics.uptime,
            memoryUsage: memUsage.heapUsed,
            memoryTotal: memUsage.heapTotal,
            memoryRSS: memUsage.rss,
            cpuUser: cpuUsage.user,
            cpuSystem: cpuUsage.system,
            timestamp: new Date()
        };
    }

    /**
     * 收集任務指標
     */
    async collectJobMetrics() {
        for (const [jobId, jobConfig] of this.cronScheduler.jobConfigs) {
            const jobStats = this.cronScheduler.jobStats.get(jobId);
            let jobMetrics = this.metrics.jobMetrics.get(jobId);

            if (!jobMetrics) {
                this.initializeJobMetrics(jobId, jobConfig);
                jobMetrics = this.metrics.jobMetrics.get(jobId);
            }

            if (jobStats) {
                // 更新執行統計
                jobMetrics.totalExecutions = jobStats.totalExecutions || 0;
                jobMetrics.successfulExecutions = jobStats.successfulExecutions || 0;
                jobMetrics.failedExecutions = jobStats.failedExecutions || 0;
                jobMetrics.consecutiveFailures = jobStats.consecutiveFailures || 0;
                jobMetrics.lastExecution = jobStats.lastExecution;
                jobMetrics.nextExecution = jobStats.nextExecution;

                // 計算成功率
                if (jobMetrics.totalExecutions > 0) {
                    jobMetrics.successRate = jobMetrics.successfulExecutions / jobMetrics.totalExecutions;
                }

                // 更新平均執行時間
                if (jobStats.totalExecutionTime && jobStats.totalExecutions > 0) {
                    jobMetrics.averageExecutionTime = jobStats.totalExecutionTime / jobStats.totalExecutions;
                }

                // 計算健康評分
                jobMetrics.healthScore = this.calculateJobHealthScore(jobMetrics);
            }

            // 更新任務狀態
            jobMetrics.status = jobConfig.status;
            jobMetrics.enabled = jobConfig.enabled;
        }
    }

    /**
     * 收集性能指標
     */
    async collectPerformanceMetrics() {
        const timestamp = new Date();
        const performanceSnapshot = {
            timestamp,
            systemLoad: this.metrics.systemMetrics.memoryUsage / this.metrics.systemMetrics.memoryTotal,
            activeJobs: this.metrics.systemMetrics.activeJobs,
            totalJobs: this.metrics.systemMetrics.totalJobs,
            averageHealthScore: this.calculateAverageHealthScore(),
            memoryUsageMB: Math.round(this.metrics.systemMetrics.memoryUsage / 1024 / 1024),
            uptime: this.metrics.systemMetrics.uptime
        };

        this.metrics.performanceHistory.push(performanceSnapshot);

        // 限制歷史記錄長度
        if (this.metrics.performanceHistory.length > 288) { // 24小時的資料點 (每5分鐘)
            this.metrics.performanceHistory.shift();
        }
    }

    /**
     * 更新健康檢查
     */
    async updateHealthChecks() {
        const healthChecks = new Map();

        // 系統健康檢查
        healthChecks.set('system_memory', {
            name: '系統記憶體使用',
            status: this.metrics.systemMetrics.memoryUsage < this.options.alertThresholds.memoryUsage ? 'healthy' : 'warning',
            value: this.metrics.systemMetrics.memoryUsage,
            threshold: this.options.alertThresholds.memoryUsage,
            lastCheck: new Date()
        });

        // 任務健康檢查
        let healthyJobs = 0;
        let totalActiveJobs = 0;

        for (const [jobId, jobMetrics] of this.metrics.jobMetrics) {
            if (jobMetrics.enabled) {
                totalActiveJobs++;
                if (jobMetrics.healthScore >= 0.8) {
                    healthyJobs++;
                }
            }
        }

        healthChecks.set('jobs_health', {
            name: '任務整體健康',
            status: totalActiveJobs > 0 && (healthyJobs / totalActiveJobs) >= 0.8 ? 'healthy' : 'warning',
            value: totalActiveJobs > 0 ? healthyJobs / totalActiveJobs : 1,
            threshold: 0.8,
            lastCheck: new Date(),
            details: { healthyJobs, totalActiveJobs }
        });

        // 排程器狀態檢查
        healthChecks.set('scheduler_status', {
            name: '排程器狀態',
            status: this.cronScheduler.isRunning && this.cronScheduler.isInitialized ? 'healthy' : 'error',
            value: this.cronScheduler.isRunning ? 1 : 0,
            threshold: 1,
            lastCheck: new Date()
        });

        this.metrics.healthChecks = healthChecks;
    }

    /**
     * 檢查告警條件
     */
    async checkAlerts() {
        if (!this.options.enableRealTimeAlerts) {
            return;
        }

        try {
            // 檢查系統級告警
            await this.checkSystemAlerts();

            // 檢查任務級告警
            await this.checkJobAlerts();

            // 清理過期告警
            this.cleanupExpiredAlerts();

        } catch (error) {
            logger.error('檢查告警失敗', { error: error.message });
        }
    }

    /**
     * 檢查系統級告警
     */
    async checkSystemAlerts() {
        const alerts = [];

        // 記憶體使用告警
        if (this.metrics.systemMetrics.memoryUsage > this.options.alertThresholds.memoryUsage) {
            alerts.push({
                type: 'system_memory_high',
                severity: 'warning',
                message: '系統記憶體使用過高',
                value: this.metrics.systemMetrics.memoryUsage,
                threshold: this.options.alertThresholds.memoryUsage,
                timestamp: new Date()
            });
        }

        // 排程器狀態告警
        if (!this.cronScheduler.isRunning || !this.cronScheduler.isInitialized) {
            alerts.push({
                type: 'scheduler_down',
                severity: 'critical',
                message: '排程器停止運行',
                timestamp: new Date()
            });
        }

        // 處理告警
        for (const alert of alerts) {
            await this.handleAlert(alert);
        }
    }

    /**
     * 檢查任務級告警
     */
    async checkJobAlerts() {
        for (const [jobId, jobMetrics] of this.metrics.jobMetrics) {
            const alerts = [];

            // 連續失敗告警
            if (jobMetrics.consecutiveFailures >= this.options.alertThresholds.consecutiveFailures) {
                alerts.push({
                    type: 'job_consecutive_failures',
                    severity: 'error',
                    jobId,
                    jobName: jobMetrics.name,
                    message: `任務 ${jobMetrics.name} 連續失敗 ${jobMetrics.consecutiveFailures} 次`,
                    value: jobMetrics.consecutiveFailures,
                    threshold: this.options.alertThresholds.consecutiveFailures,
                    timestamp: new Date()
                });
            }

            // 成功率告警
            if (jobMetrics.totalExecutions > 5 && jobMetrics.successRate < this.options.alertThresholds.successRate) {
                alerts.push({
                    type: 'job_low_success_rate',
                    severity: 'warning',
                    jobId,
                    jobName: jobMetrics.name,
                    message: `任務 ${jobMetrics.name} 成功率過低: ${(jobMetrics.successRate * 100).toFixed(2)}%`,
                    value: jobMetrics.successRate,
                    threshold: this.options.alertThresholds.successRate,
                    timestamp: new Date()
                });
            }

            // 執行時間告警
            if (jobMetrics.averageExecutionTime > this.options.alertThresholds.avgExecutionTime) {
                alerts.push({
                    type: 'job_long_execution',
                    severity: 'warning',
                    jobId,
                    jobName: jobMetrics.name,
                    message: `任務 ${jobMetrics.name} 平均執行時間過長: ${Math.round(jobMetrics.averageExecutionTime / 1000)}s`,
                    value: jobMetrics.averageExecutionTime,
                    threshold: this.options.alertThresholds.avgExecutionTime,
                    timestamp: new Date()
                });
            }

            // 處理任務告警
            for (const alert of alerts) {
                await this.handleAlert(alert);
            }
        }
    }

    /**
     * 處理告警
     */
    async handleAlert(alert) {
        const alertKey = `${alert.type}_${alert.jobId || 'system'}`;

        // 檢查告警抑制
        if (this.suppressedAlerts.has(alertKey)) {
            return;
        }

        // 檢查告警狀態變化
        const lastAlertState = this.alertStates.get(alertKey);
        const shouldTrigger = !lastAlertState ||
                            (Date.now() - lastAlertState.timestamp) > 5 * 60 * 1000; // 5分鐘冷卻

        if (shouldTrigger) {
            // 記錄告警
            this.metrics.alertHistory.push(alert);
            this.alertStates.set(alertKey, {
                ...alert,
                count: (lastAlertState?.count || 0) + 1
            });

            // 限制告警歷史長度
            if (this.metrics.alertHistory.length > 1000) {
                this.metrics.alertHistory.splice(0, this.metrics.alertHistory.length - 1000);
            }

            // 發送告警事件
            this.emit('alert', alert);

            // 記錄告警日誌
            const logLevel = alert.severity === 'critical' ? 'error' :
                           alert.severity === 'error' ? 'error' : 'warn';

            logger[logLevel]('排程監控告警', {
                type: alert.type,
                message: alert.message,
                jobId: alert.jobId,
                jobName: alert.jobName,
                value: alert.value,
                threshold: alert.threshold,
                severity: alert.severity
            });
        }
    }

    /**
     * 計算任務健康評分
     */
    calculateJobHealthScore(jobMetrics) {
        let score = 1.0;

        // 基於成功率
        score *= jobMetrics.successRate;

        // 基於連續失敗次數
        if (jobMetrics.consecutiveFailures > 0) {
            score *= Math.max(0.1, 1 - (jobMetrics.consecutiveFailures * 0.2));
        }

        // 基於執行時間
        if (jobMetrics.averageExecutionTime > this.options.alertThresholds.avgExecutionTime) {
            score *= 0.8;
        }

        // 基於最近執行狀態
        if (jobMetrics.lastExecution) {
            const timeSinceLastExecution = Date.now() - new Date(jobMetrics.lastExecution).getTime();
            const expectedInterval = this.getExpectedInterval(jobMetrics.cronExpression);

            if (timeSinceLastExecution > expectedInterval * 2) {
                score *= 0.7; // 可能錯過了執行
            }
        }

        return Math.max(0, Math.min(1, score));
    }

    /**
     * 計算平均健康評分
     */
    calculateAverageHealthScore() {
        if (this.metrics.jobMetrics.size === 0) return 1.0;

        let totalScore = 0;
        let activeJobs = 0;

        for (const [, jobMetrics] of this.metrics.jobMetrics) {
            if (jobMetrics.enabled) {
                totalScore += jobMetrics.healthScore;
                activeJobs++;
            }
        }

        return activeJobs > 0 ? totalScore / activeJobs : 1.0;
    }

    /**
     * 獲取預期執行間隔（毫秒）
     */
    getExpectedInterval(cronExpression) {
        // 簡化的cron間隔計算，實際應該使用專門的cron解析庫
        const parts = cronExpression.split(' ');

        // 基本的估算邏輯
        if (parts[0] !== '*') return 60000; // 每分鐘
        if (parts[1] !== '*') return 3600000; // 每小時
        if (parts[2] !== '*') return 86400000; // 每天

        return 60000; // 預設每分鐘
    }

    /**
     * 設定事件監聽器
     */
    setupEventListeners() {
        if (this.cronScheduler) {
            this.cronScheduler.on('taskStarted', (data) => {
                this.onTaskStarted(data);
            });

            this.cronScheduler.on('taskCompleted', (data) => {
                this.onTaskCompleted(data);
            });

            this.cronScheduler.on('taskFailed', (data) => {
                this.onTaskFailed(data);
            });

            this.cronScheduler.on('scheduleCreated', (data) => {
                this.onScheduleCreated(data);
            });

            this.cronScheduler.on('scheduleDeleted', (data) => {
                this.onScheduleDeleted(data);
            });
        }
    }

    /**
     * 移除事件監聽器
     */
    removeEventListeners() {
        if (this.cronScheduler) {
            this.cronScheduler.removeAllListeners('taskStarted');
            this.cronScheduler.removeAllListeners('taskCompleted');
            this.cronScheduler.removeAllListeners('taskFailed');
            this.cronScheduler.removeAllListeners('scheduleCreated');
            this.cronScheduler.removeAllListeners('scheduleDeleted');
        }
    }

    /**
     * 任務開始事件處理
     */
    onTaskStarted(data) {
        const jobMetrics = this.metrics.jobMetrics.get(data.jobId);
        if (jobMetrics) {
            jobMetrics.lastStartTime = new Date();
        }

        this.emit('taskStarted', data);
    }

    /**
     * 任務完成事件處理
     */
    onTaskCompleted(data) {
        const jobMetrics = this.metrics.jobMetrics.get(data.jobId);
        if (jobMetrics && jobMetrics.lastStartTime) {
            const executionTime = Date.now() - jobMetrics.lastStartTime.getTime();

            // 更新執行時間統計
            jobMetrics.totalExecutionTime = (jobMetrics.totalExecutionTime || 0) + executionTime;

            if (!jobMetrics.minExecutionTime || executionTime < jobMetrics.minExecutionTime) {
                jobMetrics.minExecutionTime = executionTime;
            }

            if (!jobMetrics.maxExecutionTime || executionTime > jobMetrics.maxExecutionTime) {
                jobMetrics.maxExecutionTime = executionTime;
            }

            // 重置連續失敗計數
            jobMetrics.consecutiveFailures = 0;
        }

        this.emit('taskCompleted', data);
    }

    /**
     * 任務失敗事件處理
     */
    onTaskFailed(data) {
        const jobMetrics = this.metrics.jobMetrics.get(data.jobId);
        if (jobMetrics) {
            jobMetrics.consecutiveFailures = (jobMetrics.consecutiveFailures || 0) + 1;
            jobMetrics.lastError = data.error;

            // 錯誤模式分析
            const errorType = data.error?.name || 'UnknownError';
            const errorCount = jobMetrics.errorPattern.get(errorType) || 0;
            jobMetrics.errorPattern.set(errorType, errorCount + 1);
        }

        this.emit('taskFailed', data);
    }

    /**
     * 排程創建事件處理
     */
    onScheduleCreated(data) {
        this.initializeJobMetrics(data.id, data);
        this.emit('scheduleCreated', data);
    }

    /**
     * 排程刪除事件處理
     */
    onScheduleDeleted(data) {
        this.metrics.jobMetrics.delete(data.id);
        this.emit('scheduleDeleted', data);
    }

    /**
     * 執行清理任務
     */
    performCleanup() {
        const now = Date.now();
        const retentionTime = now - this.options.retentionPeriod;

        try {
            // 清理過期的性能歷史
            this.metrics.performanceHistory = this.metrics.performanceHistory.filter(
                record => record.timestamp.getTime() > retentionTime
            );

            // 清理過期的告警歷史
            this.metrics.alertHistory = this.metrics.alertHistory.filter(
                alert => alert.timestamp.getTime() > retentionTime
            );

            // 清理任務執行歷史
            for (const [, jobMetrics] of this.metrics.jobMetrics) {
                if (jobMetrics.executionHistory) {
                    jobMetrics.executionHistory = jobMetrics.executionHistory.filter(
                        record => record.timestamp > retentionTime
                    );
                }
            }

            this.lastCleanupTime = now;
            logger.info('監控資料清理完成', {
                performanceHistorySize: this.metrics.performanceHistory.length,
                alertHistorySize: this.metrics.alertHistory.length
            });

        } catch (error) {
            logger.error('監控資料清理失敗', { error: error.message });
        }
    }

    /**
     * 清理過期告警
     */
    cleanupExpiredAlerts() {
        const now = Date.now();
        const alertTimeout = 30 * 60 * 1000; // 30分鐘

        for (const [alertKey, alertState] of this.alertStates) {
            if (now - alertState.timestamp > alertTimeout) {
                this.alertStates.delete(alertKey);
            }
        }
    }

    /**
     * 抑制告警
     */
    suppressAlert(alertType, jobId = null, duration = 60 * 60 * 1000) {
        const alertKey = `${alertType}_${jobId || 'system'}`;
        this.suppressedAlerts.add(alertKey);

        setTimeout(() => {
            this.suppressedAlerts.delete(alertKey);
        }, duration);

        logger.info('告警已抑制', { alertType, jobId, duration });
    }

    /**
     * 獲取監控狀態
     */
    getMonitoringStatus() {
        return {
            isMonitoring: this.isMonitoring,
            uptime: Date.now() - this.metrics.systemMetrics.uptime,
            systemMetrics: this.metrics.systemMetrics,
            totalJobs: this.metrics.jobMetrics.size,
            healthChecks: Object.fromEntries(this.metrics.healthChecks),
            averageHealthScore: this.calculateAverageHealthScore(),
            recentAlerts: this.metrics.alertHistory.slice(-10),
            monitoringConfig: {
                monitoringInterval: this.options.monitoringInterval,
                alertsEnabled: this.options.enableRealTimeAlerts,
                alertThresholds: this.options.alertThresholds
            }
        };
    }

    /**
     * 獲取任務詳細監控資料
     */
    getJobMonitoringData(jobId) {
        const jobMetrics = this.metrics.jobMetrics.get(jobId);
        if (!jobMetrics) {
            throw new Error(`找不到任務監控資料: ${jobId}`);
        }

        return {
            ...jobMetrics,
            recentAlerts: this.metrics.alertHistory
                .filter(alert => alert.jobId === jobId)
                .slice(-10),
            healthChecks: this.metrics.healthChecks.has(`job_${jobId}`) ?
                         this.metrics.healthChecks.get(`job_${jobId}`) : null
        };
    }

    /**
     * 獲取性能報告
     */
    getPerformanceReport(timeRange = 24 * 60 * 60 * 1000) {
        const cutoffTime = Date.now() - timeRange;
        const recentHistory = this.metrics.performanceHistory.filter(
            record => record.timestamp.getTime() > cutoffTime
        );

        if (recentHistory.length === 0) {
            return {
                timeRange,
                dataPoints: 0,
                summary: {
                    avgSystemLoad: 0,
                    avgMemoryUsage: 0,
                    avgHealthScore: 1.0
                }
            };
        }

        const summary = {
            avgSystemLoad: recentHistory.reduce((sum, r) => sum + r.systemLoad, 0) / recentHistory.length,
            avgMemoryUsage: recentHistory.reduce((sum, r) => sum + r.memoryUsageMB, 0) / recentHistory.length,
            avgHealthScore: recentHistory.reduce((sum, r) => sum + r.averageHealthScore, 0) / recentHistory.length,
            peakMemoryUsage: Math.max(...recentHistory.map(r => r.memoryUsageMB)),
            lowestHealthScore: Math.min(...recentHistory.map(r => r.averageHealthScore))
        };

        return {
            timeRange,
            dataPoints: recentHistory.length,
            summary,
            history: recentHistory
        };
    }

    /**
     * 關機清理
     */
    async shutdown() {
        logger.info('排程監控系統開始關機清理');

        await this.stopMonitoring();

        // 清理所有監控資料
        this.metrics = {
            systemMetrics: {},
            jobMetrics: new Map(),
            performanceHistory: [],
            alertHistory: [],
            healthChecks: new Map()
        };

        this.alertStates.clear();
        this.suppressedAlerts.clear();

        logger.info('排程監控系統關機完成');
    }
}

module.exports = SchedulerMonitor;