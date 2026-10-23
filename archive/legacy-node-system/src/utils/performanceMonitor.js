/**
 * 性能監控器 - Performance Monitor
 * 負責收集、分析和報告系統性能指標
 */

const EventEmitter = require('events');
const fs = require('fs/promises');
const path = require('path');

class PerformanceMonitor extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            metricsInterval: options.metricsInterval || 5000,
            alertThresholds: {
                memoryUsage: options.memoryThreshold || 0.85,
                cpuUsage: options.cpuThreshold || 0.80,
                errorRate: options.errorRateThreshold || 0.10,
                responseTime: options.responseTimeThreshold || 5000,
                ...options.alertThresholds
            },
            historySize: options.historySize || 1000,
            enableFileLogging: options.enableFileLogging !== false,
            logPath: options.logPath || './logs/performance',
            enableRealTimeAlerts: options.enableRealTimeAlerts !== false,
            ...options
        };

        // 性能指標數據
        this.metrics = {
            system: {
                memoryUsage: [],
                cpuUsage: [],
                diskUsage: [],
                networkActivity: []
            },
            application: {
                activeAgents: [],
                taskThroughput: [],
                responseTime: [],
                errorRate: [],
                queueSize: []
            },
            agents: new Map() // Agent特定指標
        };

        // 當前狀態
        this.currentMetrics = {
            timestamp: new Date(),
            system: {},
            application: {},
            agents: {}
        };

        // 警報歷史
        this.alerts = [];

        // 監控狀態
        this.isMonitoring = false;
        this.monitoringInterval = null;

        // 性能基準線
        this.baselines = {
            memoryUsage: 0.5,
            cpuUsage: 0.3,
            responseTime: 1000,
            throughput: 10
        };

        console.log('📊 性能監控器初始化完成');
    }

    /**
     * 開始監控
     */
    async start() {
        if (this.isMonitoring) {
            console.warn('⚠️ 性能監控器已在運行中');
            return;
        }

        console.log('🚀 開始性能監控...');

        this.isMonitoring = true;

        // 確保日誌目錄存在
        if (this.options.enableFileLogging) {
            await this.ensureLogDirectory();
        }

        // 開始收集指標
        this.monitoringInterval = setInterval(() => {
            this.collectMetrics();
        }, this.options.metricsInterval);

        this.emit('monitoringStarted');
        console.log('✅ 性能監控已啟動');
    }

    /**
     * 停止監控
     */
    async stop() {
        if (!this.isMonitoring) {
            console.warn('⚠️ 性能監控器未在運行中');
            return;
        }

        console.log('⏹️ 停止性能監控...');

        this.isMonitoring = false;

        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }

        // 生成最終報告
        if (this.options.enableFileLogging) {
            await this.generateFinalReport();
        }

        this.emit('monitoringStopped');
        console.log('✅ 性能監控已停止');
    }

    /**
     * 收集系統和應用性能指標
     */
    async collectMetrics() {
        try {
            const timestamp = new Date();

            // 收集系統指標
            const systemMetrics = await this.collectSystemMetrics();

            // 收集應用指標
            const applicationMetrics = await this.collectApplicationMetrics();

            // 收集Agent指標
            const agentMetrics = await this.collectAgentMetrics();

            // 更新當前指標
            this.currentMetrics = {
                timestamp: timestamp,
                system: systemMetrics,
                application: applicationMetrics,
                agents: agentMetrics
            };

            // 添加到歷史記錄
            this.addToHistory(this.currentMetrics);

            // 檢查警報條件
            this.checkAlerts(this.currentMetrics);

            // 觸發指標更新事件
            this.emit('metricsUpdated', this.currentMetrics);

            // 記錄到文件
            if (this.options.enableFileLogging) {
                await this.logMetrics(this.currentMetrics);
            }

        } catch (error) {
            console.error('❌ 收集性能指標時發生錯誤:', error.message);
            this.emit('metricsError', error);
        }
    }

    /**
     * 收集系統指標
     */
    async collectSystemMetrics() {
        const memoryUsage = process.memoryUsage();
        const cpuUsage = process.cpuUsage();

        return {
            memory: {
                heapUsed: memoryUsage.heapUsed,
                heapTotal: memoryUsage.heapTotal,
                heapUsedPercentage: memoryUsage.heapUsed / memoryUsage.heapTotal,
                external: memoryUsage.external,
                rss: memoryUsage.rss
            },
            cpu: {
                user: cpuUsage.user,
                system: cpuUsage.system,
                // 計算CPU使用率需要更複雜的邏輯，這裡簡化處理
                usage: this.calculateCpuUsage(cpuUsage)
            },
            process: {
                uptime: process.uptime(),
                pid: process.pid,
                version: process.version,
                platform: process.platform
            }
        };
    }

    /**
     * 收集應用指標
     */
    async collectApplicationMetrics() {
        return {
            activeConnections: this.getActiveConnections(),
            requestRate: this.calculateRequestRate(),
            responseTime: this.calculateAverageResponseTime(),
            errorRate: this.calculateErrorRate(),
            queueSizes: this.getQueueSizes(),
            throughput: this.calculateThroughput()
        };
    }

    /**
     * 收集Agent特定指標
     */
    async collectAgentMetrics() {
        const agentMetrics = {};

        // 這裡應該從Agent管理器獲取實際數據
        // 目前返回模擬數據
        const agentTypes = ['web-crawler', 'metadata-extractor', 'classification', 'summarization'];

        for (const agentType of agentTypes) {
            agentMetrics[agentType] = {
                status: this.getAgentStatus(agentType),
                activeTasks: this.getAgentActiveTasks(agentType),
                completedTasks: this.getAgentCompletedTasks(agentType),
                errorCount: this.getAgentErrorCount(agentType),
                averageExecutionTime: this.getAgentAverageExecutionTime(agentType),
                memoryUsage: this.getAgentMemoryUsage(agentType)
            };
        }

        return agentMetrics;
    }

    /**
     * 計算CPU使用率
     */
    calculateCpuUsage(cpuUsage) {
        // 簡化的CPU使用率計算
        // 實際實現應該基於時間間隔計算差值
        if (!this.lastCpuUsage) {
            this.lastCpuUsage = cpuUsage;
            return 0;
        }

        const userDiff = cpuUsage.user - this.lastCpuUsage.user;
        const systemDiff = cpuUsage.system - this.lastCpuUsage.system;
        const totalDiff = userDiff + systemDiff;

        this.lastCpuUsage = cpuUsage;

        // 轉換微秒到百分比（簡化處理）
        return Math.min(totalDiff / (this.options.metricsInterval * 1000), 1.0);
    }

    /**
     * 獲取活躍連接數
     */
    getActiveConnections() {
        // 實際實現應該從HTTP服務器或數據庫獲取
        return Math.floor(Math.random() * 50) + 10;
    }

    /**
     * 計算請求率
     */
    calculateRequestRate() {
        // 實際實現應該基於請求計數器
        return Math.floor(Math.random() * 100) + 20;
    }

    /**
     * 計算平均回應時間
     */
    calculateAverageResponseTime() {
        // 實際實現應該基於回應時間記錄
        return Math.floor(Math.random() * 1000) + 500;
    }

    /**
     * 計算錯誤率
     */
    calculateErrorRate() {
        // 實際實現應該基於錯誤計數器
        return Math.random() * 0.05; // 0-5%錯誤率
    }

    /**
     * 獲取隊列大小
     */
    getQueueSizes() {
        return {
            high: Math.floor(Math.random() * 10),
            normal: Math.floor(Math.random() * 20),
            low: Math.floor(Math.random() * 15)
        };
    }

    /**
     * 計算吞吐量
     */
    calculateThroughput() {
        return Math.floor(Math.random() * 50) + 25;
    }

    /**
     * 獲取Agent狀態
     */
    getAgentStatus(agentType) {
        const statuses = ['running', 'idle', 'busy', 'error'];
        return statuses[Math.floor(Math.random() * statuses.length)];
    }

    /**
     * 獲取Agent活躍任務數
     */
    getAgentActiveTasks(agentType) {
        return Math.floor(Math.random() * 5);
    }

    /**
     * 獲取Agent已完成任務數
     */
    getAgentCompletedTasks(agentType) {
        return Math.floor(Math.random() * 100) + 50;
    }

    /**
     * 獲取Agent錯誤數
     */
    getAgentErrorCount(agentType) {
        return Math.floor(Math.random() * 5);
    }

    /**
     * 獲取Agent平均執行時間
     */
    getAgentAverageExecutionTime(agentType) {
        return Math.floor(Math.random() * 2000) + 1000;
    }

    /**
     * 獲取Agent內存使用量
     */
    getAgentMemoryUsage(agentType) {
        return Math.random() * 100; // MB
    }

    /**
     * 添加到歷史記錄
     */
    addToHistory(metrics) {
        // 添加到系統指標歷史
        this.metrics.system.memoryUsage.push({
            timestamp: metrics.timestamp,
            value: metrics.system.memory.heapUsedPercentage
        });

        this.metrics.system.cpuUsage.push({
            timestamp: metrics.timestamp,
            value: metrics.system.cpu.usage
        });

        // 添加到應用指標歷史
        this.metrics.application.responseTime.push({
            timestamp: metrics.timestamp,
            value: metrics.application.responseTime
        });

        this.metrics.application.errorRate.push({
            timestamp: metrics.timestamp,
            value: metrics.application.errorRate
        });

        this.metrics.application.taskThroughput.push({
            timestamp: metrics.timestamp,
            value: metrics.application.throughput
        });

        // 限制歷史大小
        this.limitHistorySize();
    }

    /**
     * 限制歷史記錄大小
     */
    limitHistorySize() {
        const limit = this.options.historySize;

        for (const category in this.metrics.system) {
            if (this.metrics.system[category].length > limit) {
                this.metrics.system[category] = this.metrics.system[category].slice(-limit);
            }
        }

        for (const category in this.metrics.application) {
            if (this.metrics.application[category].length > limit) {
                this.metrics.application[category] = this.metrics.application[category].slice(-limit);
            }
        }
    }

    /**
     * 檢查警報條件
     */
    checkAlerts(metrics) {
        const alerts = [];

        // 檢查內存使用率
        if (metrics.system.memory.heapUsedPercentage > this.options.alertThresholds.memoryUsage) {
            alerts.push({
                type: 'memory',
                severity: 'warning',
                message: `內存使用率過高: ${(metrics.system.memory.heapUsedPercentage * 100).toFixed(1)}%`,
                value: metrics.system.memory.heapUsedPercentage,
                threshold: this.options.alertThresholds.memoryUsage,
                timestamp: metrics.timestamp
            });
        }

        // 檢查CPU使用率
        if (metrics.system.cpu.usage > this.options.alertThresholds.cpuUsage) {
            alerts.push({
                type: 'cpu',
                severity: 'warning',
                message: `CPU使用率過高: ${(metrics.system.cpu.usage * 100).toFixed(1)}%`,
                value: metrics.system.cpu.usage,
                threshold: this.options.alertThresholds.cpuUsage,
                timestamp: metrics.timestamp
            });
        }

        // 檢查錯誤率
        if (metrics.application.errorRate > this.options.alertThresholds.errorRate) {
            alerts.push({
                type: 'error_rate',
                severity: 'critical',
                message: `錯誤率過高: ${(metrics.application.errorRate * 100).toFixed(1)}%`,
                value: metrics.application.errorRate,
                threshold: this.options.alertThresholds.errorRate,
                timestamp: metrics.timestamp
            });
        }

        // 檢查回應時間
        if (metrics.application.responseTime > this.options.alertThresholds.responseTime) {
            alerts.push({
                type: 'response_time',
                severity: 'warning',
                message: `回應時間過長: ${metrics.application.responseTime}ms`,
                value: metrics.application.responseTime,
                threshold: this.options.alertThresholds.responseTime,
                timestamp: metrics.timestamp
            });
        }

        // 處理警報
        for (const alert of alerts) {
            this.handleAlert(alert);
        }
    }

    /**
     * 處理警報
     */
    handleAlert(alert) {
        this.alerts.push(alert);

        // 限制警報歷史大小
        if (this.alerts.length > 100) {
            this.alerts = this.alerts.slice(-100);
        }

        if (this.options.enableRealTimeAlerts) {
            console.warn(`🚨 [性能警報] ${alert.message}`);
        }

        this.emit('alert', alert);
    }

    /**
     * 獲取性能報告
     */
    getPerformanceReport() {
        return {
            current: this.currentMetrics,
            summary: this.generateSummary(),
            trends: this.analyzeTrends(),
            alerts: this.alerts.slice(-10), // 最近10個警報
            recommendations: this.generateRecommendations()
        };
    }

    /**
     * 生成性能摘要
     */
    generateSummary() {
        const recentMetrics = this.getRecentMetrics(10);

        if (recentMetrics.length === 0) {
            return {
                averageMemoryUsage: 0,
                averageCpuUsage: 0,
                averageResponseTime: 0,
                averageErrorRate: 0,
                totalThroughput: 0
            };
        }

        return {
            averageMemoryUsage: this.calculateAverage(recentMetrics, 'system.memory.heapUsedPercentage'),
            averageCpuUsage: this.calculateAverage(recentMetrics, 'system.cpu.usage'),
            averageResponseTime: this.calculateAverage(recentMetrics, 'application.responseTime'),
            averageErrorRate: this.calculateAverage(recentMetrics, 'application.errorRate'),
            totalThroughput: this.calculateSum(recentMetrics, 'application.throughput')
        };
    }

    /**
     * 分析趨勢
     */
    analyzeTrends() {
        return {
            memoryTrend: this.calculateTrend(this.metrics.system.memoryUsage),
            cpuTrend: this.calculateTrend(this.metrics.system.cpuUsage),
            responseTimeTrend: this.calculateTrend(this.metrics.application.responseTime),
            errorRateTrend: this.calculateTrend(this.metrics.application.errorRate),
            throughputTrend: this.calculateTrend(this.metrics.application.taskThroughput)
        };
    }

    /**
     * 生成建議
     */
    generateRecommendations() {
        const recommendations = [];
        const summary = this.generateSummary();

        if (summary.averageMemoryUsage > 0.8) {
            recommendations.push({
                type: 'memory',
                priority: 'high',
                message: '建議增加內存或優化內存使用',
                action: 'optimize_memory'
            });
        }

        if (summary.averageCpuUsage > 0.7) {
            recommendations.push({
                type: 'cpu',
                priority: 'medium',
                message: '建議優化CPU密集型操作或增加處理能力',
                action: 'optimize_cpu'
            });
        }

        if (summary.averageResponseTime > 3000) {
            recommendations.push({
                type: 'performance',
                priority: 'high',
                message: '建議優化回應時間，檢查慢查詢或網路延遲',
                action: 'optimize_response_time'
            });
        }

        if (summary.averageErrorRate > 0.05) {
            recommendations.push({
                type: 'reliability',
                priority: 'critical',
                message: '建議檢查錯誤處理和系統穩定性',
                action: 'improve_error_handling'
            });
        }

        return recommendations;
    }

    /**
     * 獲取最近的指標
     */
    getRecentMetrics(count = 10) {
        // 這裡應該返回實際的歷史指標數據
        // 目前返回空數組作為示例
        return [];
    }

    /**
     * 計算平均值
     */
    calculateAverage(metrics, path) {
        if (metrics.length === 0) return 0;

        const values = metrics.map(m => this.getNestedValue(m, path)).filter(v => v !== undefined);
        return values.reduce((sum, val) => sum + val, 0) / values.length;
    }

    /**
     * 計算總和
     */
    calculateSum(metrics, path) {
        const values = metrics.map(m => this.getNestedValue(m, path)).filter(v => v !== undefined);
        return values.reduce((sum, val) => sum + val, 0);
    }

    /**
     * 計算趨勢
     */
    calculateTrend(dataPoints) {
        if (dataPoints.length < 2) return 'stable';

        const recent = dataPoints.slice(-10);
        const firstHalf = recent.slice(0, Math.floor(recent.length / 2));
        const secondHalf = recent.slice(Math.floor(recent.length / 2));

        if (firstHalf.length === 0 || secondHalf.length === 0) return 'stable';

        const firstAvg = firstHalf.reduce((sum, point) => sum + point.value, 0) / firstHalf.length;
        const secondAvg = secondHalf.reduce((sum, point) => sum + point.value, 0) / secondHalf.length;

        const changePercent = ((secondAvg - firstAvg) / firstAvg) * 100;

        if (changePercent > 10) return 'increasing';
        if (changePercent < -10) return 'decreasing';
        return 'stable';
    }

    /**
     * 獲取嵌套屬性值
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current && current[key], obj);
    }

    /**
     * 確保日誌目錄存在
     */
    async ensureLogDirectory() {
        try {
            await fs.mkdir(this.options.logPath, { recursive: true });
        } catch (error) {
            console.error('❌ 創建日誌目錄失敗:', error.message);
        }
    }

    /**
     * 記錄指標到文件
     */
    async logMetrics(metrics) {
        try {
            const logFile = path.join(this.options.logPath, `performance_${this.getDateString()}.json`);
            const logEntry = JSON.stringify(metrics) + '\n';

            await fs.appendFile(logFile, logEntry);
        } catch (error) {
            console.error('❌ 記錄指標到文件失敗:', error.message);
        }
    }

    /**
     * 生成最終報告
     */
    async generateFinalReport() {
        try {
            const report = this.getPerformanceReport();
            const reportFile = path.join(this.options.logPath, `final_report_${Date.now()}.json`);

            await fs.writeFile(reportFile, JSON.stringify(report, null, 2));
            console.log(`📊 性能監控最終報告已生成: ${reportFile}`);
        } catch (error) {
            console.error('❌ 生成最終報告失敗:', error.message);
        }
    }

    /**
     * 獲取日期字符串
     */
    getDateString() {
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    }

    /**
     * 重置監控數據
     */
    reset() {
        this.metrics = {
            system: {
                memoryUsage: [],
                cpuUsage: [],
                diskUsage: [],
                networkActivity: []
            },
            application: {
                activeAgents: [],
                taskThroughput: [],
                responseTime: [],
                errorRate: [],
                queueSize: []
            },
            agents: new Map()
        };

        this.alerts = [];
        console.log('🔄 性能監控數據已重置');
    }
}

module.exports = PerformanceMonitor;