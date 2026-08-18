/**
 * 快取分析和監控系統
 * 提供詳細的快取效能分析和預測功能
 */

const { logger } = require('./logger');
const { cacheManager } = require('./cacheManager');

class CacheAnalytics {
    constructor() {
        this.metricsHistory = [];
        this.performanceBaselines = {};
        this.alertThresholds = {
            hitRate: 70, // 命中率低於70%時警告
            responseTime: 100, // 響應時間超過100ms時警告
            errorRate: 5, // 錯誤率超過5%時警告
            memoryUsage: 80 // 記憶體使用率超過80%時警告
        };
        this.analysisInterval = 60000; // 1分鐘分析一次
        this.retentionDays = 7; // 保留7天數據
        this.isMonitoring = false;
    }

    /**
     * 開始監控
     */
    startMonitoring() {
        if (this.isMonitoring) return;

        this.isMonitoring = true;
        logger.info('📊 快取分析系統啟動');

        // 定期收集指標
        this.metricsCollectionInterval = setInterval(() => {
            this.collectMetrics();
        }, this.analysisInterval);

        // 定期分析趨勢
        this.trendAnalysisInterval = setInterval(() => {
            this.analyzeTrends();
        }, this.analysisInterval * 5); // 每5分鐘

        // 定期清理舊數據
        this.cleanupInterval = setInterval(() => {
            this.cleanupOldMetrics();
        }, 3600000); // 每小時
    }

    /**
     * 停止監控
     */
    stopMonitoring() {
        if (!this.isMonitoring) return;

        this.isMonitoring = false;
        clearInterval(this.metricsCollectionInterval);
        clearInterval(this.trendAnalysisInterval);
        clearInterval(this.cleanupInterval);
        logger.info('📊 快取分析系統已停止');
    }

    /**
     * 收集快取指標
     */
    async collectMetrics() {
        try {
            const stats = cacheManager.getStats();
            const timestamp = Date.now();

            const metrics = {
                timestamp,
                hitRate: parseFloat(stats.hitRate.replace('%', '')),
                totalRequests: stats.totalRequests,
                hits: stats.hits,
                misses: stats.misses,
                sets: stats.sets,
                deletes: stats.deletes,
                errors: stats.errors,
                warming: stats.warming || 0,
                evictions: stats.evictions || 0,
                memoryUsage: stats.memoryUsage,
                isRedisAvailable: stats.isRedisAvailable,
                warmupQueueSize: stats.warmupQueueSize || 0,
                popularItemsCount: stats.popularItemsCount || 0,
                accessPatternsCount: stats.accessPatternsCount || 0,
                categoryStats: stats.categoryStats || {}
            };

            // 計算派生指標
            metrics.errorRate = metrics.totalRequests > 0 ?
                (metrics.errors / metrics.totalRequests * 100) : 0;

            metrics.missRate = 100 - metrics.hitRate;

            // 計算變化率（相對於上一次指標）
            if (this.metricsHistory.length > 0) {
                const lastMetrics = this.metricsHistory[this.metricsHistory.length - 1];
                const timeDiff = timestamp - lastMetrics.timestamp;

                if (timeDiff > 0) {
                    metrics.requestsPerSecond = ((metrics.totalRequests - lastMetrics.totalRequests) / (timeDiff / 1000)) || 0;
                    metrics.hitsPerSecond = ((metrics.hits - lastMetrics.hits) / (timeDiff / 1000)) || 0;
                    metrics.missesPerSecond = ((metrics.misses - lastMetrics.misses) / (timeDiff / 1000)) || 0;
                }
            }

            this.metricsHistory.push(metrics);

            // 檢查警告條件
            this.checkAlerts(metrics);

        } catch (error) {
            logger.error('收集快取指標時發生錯誤:', error);
        }
    }

    /**
     * 檢查警告條件
     */
    checkAlerts(metrics) {
        const alerts = [];

        if (metrics.hitRate < this.alertThresholds.hitRate) {
            alerts.push({
                type: 'LOW_HIT_RATE',
                severity: 'WARNING',
                message: `快取命中率過低: ${metrics.hitRate.toFixed(2)}%`,
                threshold: this.alertThresholds.hitRate,
                currentValue: metrics.hitRate
            });
        }

        if (metrics.errorRate > this.alertThresholds.errorRate) {
            alerts.push({
                type: 'HIGH_ERROR_RATE',
                severity: 'ERROR',
                message: `快取錯誤率過高: ${metrics.errorRate.toFixed(2)}%`,
                threshold: this.alertThresholds.errorRate,
                currentValue: metrics.errorRate
            });
        }

        // 記憶體使用率檢查（假設最大值為1000）
        const memoryUsagePercent = (metrics.memoryUsage / 1000) * 100;
        if (memoryUsagePercent > this.alertThresholds.memoryUsage) {
            alerts.push({
                type: 'HIGH_MEMORY_USAGE',
                severity: 'WARNING',
                message: `記憶體使用率過高: ${memoryUsagePercent.toFixed(2)}%`,
                threshold: this.alertThresholds.memoryUsage,
                currentValue: memoryUsagePercent
            });
        }

        // Redis 不可用警告
        if (!metrics.isRedisAvailable) {
            alerts.push({
                type: 'REDIS_UNAVAILABLE',
                severity: 'ERROR',
                message: 'Redis 不可用，使用記憶體快取',
                threshold: null,
                currentValue: null
            });
        }

        // 發送警告
        alerts.forEach(alert => {
            if (alert.severity === 'ERROR') {
                logger.error(`🚨 快取警告 [${alert.type}]: ${alert.message}`);
            } else {
                logger.warn(`⚠️ 快取警告 [${alert.type}]: ${alert.message}`);
            }
        });
    }

    /**
     * 分析趨勢
     */
    analyzeTrends() {
        if (this.metricsHistory.length < 2) return;

        const recentMetrics = this.metricsHistory.slice(-10); // 最近10個指標點
        const trends = {};

        // 分析命中率趨勢
        trends.hitRate = this.calculateTrend(recentMetrics, 'hitRate');
        trends.requestRate = this.calculateTrend(recentMetrics, 'requestsPerSecond');
        trends.errorRate = this.calculateTrend(recentMetrics, 'errorRate');
        trends.memoryUsage = this.calculateTrend(recentMetrics, 'memoryUsage');

        // 預測未來趨勢
        const predictions = this.predictFuture(recentMetrics);

        logger.debug('快取趨勢分析完成', { trends, predictions });

        // 根據趨勢給出建議
        this.generateRecommendations(trends, predictions);
    }

    /**
     * 計算趨勢
     */
    calculateTrend(metrics, field) {
        if (metrics.length < 2) return { direction: 'stable', change: 0 };

        const values = metrics.map(m => m[field] || 0);
        const firstValue = values[0];
        const lastValue = values[values.length - 1];
        const change = ((lastValue - firstValue) / firstValue) * 100;

        let direction = 'stable';
        if (Math.abs(change) > 5) {
            direction = change > 0 ? 'increasing' : 'decreasing';
        }

        return { direction, change: change.toFixed(2) };
    }

    /**
     * 預測未來趨勢
     */
    predictFuture(metrics) {
        if (metrics.length < 3) return null;

        // 簡單線性回歸預測
        const predictions = {};

        ['hitRate', 'requestsPerSecond', 'memoryUsage'].forEach(field => {
            const values = metrics.map(m => m[field] || 0);
            const predicted = this.linearRegression(values);
            predictions[field] = predicted;
        });

        return predictions;
    }

    /**
     * 簡單線性回歸
     */
    linearRegression(values) {
        const n = values.length;
        const x = Array.from({ length: n }, (_, i) => i);
        const y = values;

        const sumX = x.reduce((a, b) => a + b, 0);
        const sumY = y.reduce((a, b) => a + b, 0);
        const sumXY = x.reduce((total, xi, i) => total + xi * y[i], 0);
        const sumXX = x.reduce((total, xi) => total + xi * xi, 0);

        const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;

        // 預測下一個值
        const nextValue = slope * n + intercept;

        return {
            slope: slope.toFixed(4),
            nextPredicted: nextValue.toFixed(2),
            trend: slope > 0.1 ? 'increasing' : slope < -0.1 ? 'decreasing' : 'stable'
        };
    }

    /**
     * 生成建議
     */
    generateRecommendations(trends, predictions) {
        const recommendations = [];

        // 命中率建議
        if (trends.hitRate.direction === 'decreasing') {
            recommendations.push({
                type: 'PERFORMANCE',
                priority: 'HIGH',
                message: '快取命中率呈下降趨勢，建議檢查快取策略或增加快取預熱'
            });
        }

        // 記憶體使用建議
        if (trends.memoryUsage.direction === 'increasing') {
            recommendations.push({
                type: 'RESOURCE',
                priority: 'MEDIUM',
                message: '記憶體使用呈上升趨勢，建議檢查快取清理策略或增加記憶體限制'
            });
        }

        // 請求率建議
        if (trends.requestRate.direction === 'increasing') {
            recommendations.push({
                type: 'SCALING',
                priority: 'MEDIUM',
                message: '請求率呈上升趨勢，考慮增加快取容量或啟用更積極的預載策略'
            });
        }

        // 記錄建議
        recommendations.forEach(rec => {
            logger.info(`💡 快取建議 [${rec.priority}]: ${rec.message}`);
        });
    }

    /**
     * 清理舊指標
     */
    cleanupOldMetrics() {
        const cutoffTime = Date.now() - (this.retentionDays * 24 * 60 * 60 * 1000);
        this.metricsHistory = this.metricsHistory.filter(metric => metric.timestamp > cutoffTime);

        logger.debug(`清理了 ${this.metricsHistory.length} 條舊的快取指標記錄`);
    }

    /**
     * 獲取分析報告
     */
    getAnalyticsReport() {
        if (this.metricsHistory.length === 0) {
            return { message: '暫無分析數據' };
        }

        const latest = this.metricsHistory[this.metricsHistory.length - 1];
        const timeRange = this.metricsHistory.length > 1 ?
            this.metricsHistory[this.metricsHistory.length - 1].timestamp - this.metricsHistory[0].timestamp : 0;

        // 計算平均值
        const avgHitRate = this.metricsHistory.reduce((sum, m) => sum + m.hitRate, 0) / this.metricsHistory.length;
        const avgRequestRate = this.metricsHistory
            .filter(m => m.requestsPerSecond !== undefined)
            .reduce((sum, m) => sum + m.requestsPerSecond, 0) /
            this.metricsHistory.filter(m => m.requestsPerSecond !== undefined).length || 0;

        // 找出性能峰值
        const maxHitRate = Math.max(...this.metricsHistory.map(m => m.hitRate));
        const minHitRate = Math.min(...this.metricsHistory.map(m => m.hitRate));

        return {
            summary: {
                timeRange: `${Math.round(timeRange / 60000)} 分鐘`,
                dataPoints: this.metricsHistory.length,
                avgHitRate: `${avgHitRate.toFixed(2)}%`,
                avgRequestRate: `${avgRequestRate.toFixed(2)} req/s`,
                hitRateRange: `${minHitRate.toFixed(2)}% - ${maxHitRate.toFixed(2)}%`
            },
            current: {
                hitRate: `${latest.hitRate.toFixed(2)}%`,
                totalRequests: latest.totalRequests,
                memoryUsage: latest.memoryUsage,
                isRedisAvailable: latest.isRedisAvailable,
                warmupQueueSize: latest.warmupQueueSize,
                categoryStats: latest.categoryStats
            },
            trends: this.metricsHistory.length > 1 ? {
                hitRate: this.calculateTrend(this.metricsHistory.slice(-5), 'hitRate'),
                memoryUsage: this.calculateTrend(this.metricsHistory.slice(-5), 'memoryUsage'),
                requestRate: this.calculateTrend(this.metricsHistory.slice(-5), 'requestsPerSecond')
            } : null,
            monitoring: {
                isActive: this.isMonitoring,
                interval: `${this.analysisInterval / 1000}s`,
                retentionDays: this.retentionDays,
                alertThresholds: this.alertThresholds
            }
        };
    }

    /**
     * 重置統計
     */
    resetAnalytics() {
        this.metricsHistory = [];
        this.performanceBaselines = {};
        logger.info('快取分析數據已重置');
    }

    /**
     * 設置警告閾值
     */
    setAlertThresholds(thresholds) {
        this.alertThresholds = { ...this.alertThresholds, ...thresholds };
        logger.info('警告閾值已更新', this.alertThresholds);
    }
}

// 單例模式
const cacheAnalytics = new CacheAnalytics();

module.exports = {
    CacheAnalytics,
    cacheAnalytics
};