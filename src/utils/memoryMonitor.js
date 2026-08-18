/**
 * 記憶體監控系統
 * 監控系統記憶體使用情況，偵測洩漏，並提供最佳化建議
 */

const { logger } = require('./logger');

class MemoryMonitor {
    constructor(options = {}) {
        this.monitoringInterval = options.interval || 60000; // 1分鐘
        this.alertThresholds = {
            heapUsed: options.heapUsedThreshold || 500 * 1024 * 1024, // 500MB
            heapTotal: options.heapTotalThreshold || 1024 * 1024 * 1024, // 1GB
            external: options.externalThreshold || 100 * 1024 * 1024, // 100MB
            arrayBuffers: options.arrayBuffersThreshold || 50 * 1024 * 1024, // 50MB
            gcPressure: options.gcPressureThreshold || 50 // 50% GC時間
        };

        this.memoryHistory = [];
        this.maxHistoryLength = options.maxHistoryLength || 60; // 保留60個記錄點
        this.isMonitoring = false;
        this.gcStats = {
            major: 0,
            minor: 0,
            incremental: 0,
            totalTime: 0
        };

        // 記憶體洩漏偵測
        this.suspiciousGrowth = {
            heapUsed: [],
            external: [],
            arrayBuffers: []
        };

        // 物件追蹤
        this.objectCounters = new Map();
        this.intervalId = null;
    }

    /**
     * 開始記憶體監控
     */
    startMonitoring() {
        if (this.isMonitoring) return;

        this.isMonitoring = true;
        logger.info('🔍 記憶體監控系統啟動');

        // 啟用 GC 統計（如果支援）
        if (global.gc && typeof global.gc === 'function') {
            this.enableGCStats();
        }

        // 定期收集記憶體統計
        this.intervalId = setInterval(() => {
            this.collectMemoryStats();
        }, this.monitoringInterval);

        // 初始統計
        this.collectMemoryStats();
    }

    /**
     * 停止監控
     */
    stopMonitoring() {
        if (!this.isMonitoring) return;

        this.isMonitoring = false;
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        logger.info('🔍 記憶體監控系統已停止');
    }

    /**
     * 收集記憶體統計資訊
     */
    collectMemoryStats() {
        const memUsage = process.memoryUsage();
        const cpuUsage = process.cpuUsage();
        const timestamp = Date.now();

        const stats = {
            timestamp,
            heap: {
                used: memUsage.heapUsed,
                total: memUsage.heapTotal,
                utilization: (memUsage.heapUsed / memUsage.heapTotal * 100).toFixed(2)
            },
            external: memUsage.external,
            arrayBuffers: memUsage.arrayBuffers,
            resident: memUsage.rss,
            cpu: {
                user: cpuUsage.user,
                system: cpuUsage.system
            },
            gc: { ...this.gcStats },
            objectCounts: this.getObjectCounts()
        };

        // 加入歷史記錄
        this.memoryHistory.push(stats);
        if (this.memoryHistory.length > this.maxHistoryLength) {
            this.memoryHistory.shift();
        }

        // 檢查異常情況
        this.checkMemoryAlerts(stats);
        this.detectMemoryLeaks(stats);

        logger.debug('記憶體統計收集完成', {
            heapUsed: `${Math.round(stats.heap.used / 1024 / 1024)}MB`,
            heapUtilization: `${stats.heap.utilization}%`,
            external: `${Math.round(stats.external / 1024 / 1024)}MB`
        });
    }

    /**
     * 檢查記憶體警告
     */
    checkMemoryAlerts(stats) {
        const alerts = [];

        if (stats.heap.used > this.alertThresholds.heapUsed) {
            alerts.push({
                type: 'HIGH_HEAP_USAGE',
                severity: 'WARNING',
                current: stats.heap.used,
                threshold: this.alertThresholds.heapUsed,
                message: `堆疊記憶體使用過高: ${Math.round(stats.heap.used / 1024 / 1024)}MB`
            });
        }

        if (stats.heap.total > this.alertThresholds.heapTotal) {
            alerts.push({
                type: 'HIGH_HEAP_TOTAL',
                severity: 'ERROR',
                current: stats.heap.total,
                threshold: this.alertThresholds.heapTotal,
                message: `總堆疊記憶體過高: ${Math.round(stats.heap.total / 1024 / 1024)}MB`
            });
        }

        if (stats.external > this.alertThresholds.external) {
            alerts.push({
                type: 'HIGH_EXTERNAL_MEMORY',
                severity: 'WARNING',
                current: stats.external,
                threshold: this.alertThresholds.external,
                message: `外部記憶體使用過高: ${Math.round(stats.external / 1024 / 1024)}MB`
            });
        }

        if (parseFloat(stats.heap.utilization) > 90) {
            alerts.push({
                type: 'HIGH_HEAP_UTILIZATION',
                severity: 'WARNING',
                current: stats.heap.utilization,
                threshold: 90,
                message: `堆疊記憶體利用率過高: ${stats.heap.utilization}%`
            });
        }

        // 記錄警告
        alerts.forEach(alert => {
            if (alert.severity === 'ERROR') {
                logger.error(`🚨 記憶體警告 [${alert.type}]: ${alert.message}`);
            } else {
                logger.warn(`⚠️ 記憶體警告 [${alert.type}]: ${alert.message}`);
            }
        });

        return alerts;
    }

    /**
     * 偵測記憶體洩漏
     */
    detectMemoryLeaks(currentStats) {
        if (this.memoryHistory.length < 10) return; // 需要足夠的歷史數據

        const recentHistory = this.memoryHistory.slice(-10);
        const trends = this.analyzeTrends(recentHistory);

        // 檢查持續增長的記憶體使用
        const suspiciousPatterns = [];

        if (trends.heapUsed.trend === 'increasing' && trends.heapUsed.growthRate > 10) {
            suspiciousPatterns.push({
                type: 'HEAP_MEMORY_LEAK',
                growthRate: trends.heapUsed.growthRate,
                message: `堆疊記憶體持續增長，成長率: ${trends.heapUsed.growthRate.toFixed(2)}MB/分鐘`
            });
        }

        if (trends.external.trend === 'increasing' && trends.external.growthRate > 5) {
            suspiciousPatterns.push({
                type: 'EXTERNAL_MEMORY_LEAK',
                growthRate: trends.external.growthRate,
                message: `外部記憶體持續增長，成長率: ${trends.external.growthRate.toFixed(2)}MB/分鐘`
            });
        }

        // 檢查物件計數異常增長
        const objectGrowth = this.detectObjectGrowth(currentStats.objectCounts);
        if (objectGrowth.length > 0) {
            suspiciousPatterns.push(...objectGrowth);
        }

        // 記錄可疑模式
        suspiciousPatterns.forEach(pattern => {
            logger.warn(`🔍 可能的記憶體洩漏 [${pattern.type}]: ${pattern.message}`);
        });

        return suspiciousPatterns;
    }

    /**
     * 分析記憶體趨勢
     */
    analyzeTrends(history) {
        if (history.length < 2) return {};

        const trends = {};
        const fields = ['heapUsed', 'external', 'arrayBuffers'];

        fields.forEach(field => {
            const values = history.map(h => {
                if (field === 'heapUsed') return h.heap.used;
                return h[field];
            });

            const firstValue = values[0];
            const lastValue = values[values.length - 1];
            const change = lastValue - firstValue;
            const timeSpan = history[history.length - 1].timestamp - history[0].timestamp;
            const growthRate = (change / (timeSpan / 60000)) / (1024 * 1024); // MB per minute

            trends[field] = {
                trend: Math.abs(growthRate) < 0.1 ? 'stable' :
                       growthRate > 0 ? 'increasing' : 'decreasing',
                growthRate: Math.abs(growthRate),
                change: change / (1024 * 1024) // MB
            };
        });

        return trends;
    }

    /**
     * 偵測物件計數異常增長
     */
    detectObjectGrowth(currentCounts) {
        const suspiciousGrowth = [];

        for (const [type, count] of currentCounts) {
            const history = this.getObjectCountHistory(type);
            if (history.length >= 5) {
                const recentGrowth = history.slice(-5);
                const avgGrowth = recentGrowth.reduce((sum, h, i) => {
                    if (i === 0) return 0;
                    return sum + (h.count - recentGrowth[i - 1].count);
                }, 0) / (recentGrowth.length - 1);

                if (avgGrowth > 100) { // 每分鐘增長超過100個物件
                    suspiciousGrowth.push({
                        type: 'OBJECT_COUNT_LEAK',
                        objectType: type,
                        growthRate: avgGrowth,
                        message: `物件類型 '${type}' 異常增長，平均增長率: ${avgGrowth.toFixed(2)}/分鐘`
                    });
                }
            }
        }

        return suspiciousGrowth;
    }

    /**
     * 取得物件計數歷史
     */
    getObjectCountHistory(objectType) {
        return this.memoryHistory
            .filter(h => h.objectCounts && h.objectCounts.has(objectType))
            .map(h => ({
                timestamp: h.timestamp,
                count: h.objectCounts.get(objectType)
            }));
    }

    /**
     * 獲取物件計數（模擬）
     */
    getObjectCounts() {
        const counts = new Map();

        // 這裡可以加入實際的物件追蹤邏輯
        // 目前使用模擬數據展示功能
        counts.set('Array', Math.floor(Math.random() * 1000) + 500);
        counts.set('Object', Math.floor(Math.random() * 2000) + 1000);
        counts.set('Function', Math.floor(Math.random() * 500) + 200);
        counts.set('Buffer', Math.floor(Math.random() * 100) + 50);

        return counts;
    }

    /**
     * 啟用 GC 統計（實驗性）
     */
    enableGCStats() {
        if (typeof process.binding === 'function') {
            try {
                // 嘗試使用 V8 API 獲取 GC 統計
                const v8 = require('v8');
                if (v8.getHeapStatistics) {
                    this.v8Available = true;
                }
            } catch (error) {
                logger.debug('V8 統計不可用:', error.message);
            }
        }
    }

    /**
     * 強制垃圾回收（如果可用）
     */
    forceGC() {
        if (global.gc && typeof global.gc === 'function') {
            const before = process.memoryUsage();
            global.gc();
            const after = process.memoryUsage();

            const freed = {
                heapUsed: before.heapUsed - after.heapUsed,
                external: before.external - after.external,
                arrayBuffers: before.arrayBuffers - after.arrayBuffers
            };

            logger.info('🗑️ 強制垃圾回收完成', {
                heapFreed: `${Math.round(freed.heapUsed / 1024 / 1024)}MB`,
                externalFreed: `${Math.round(freed.external / 1024 / 1024)}MB`
            });

            return freed;
        } else {
            logger.warn('垃圾回收不可用，請使用 --expose-gc 參數啟動');
            return null;
        }
    }

    /**
     * 獲取記憶體統計報告
     */
    getMemoryReport() {
        const current = this.getCurrentMemoryStats();
        const trends = this.memoryHistory.length > 1 ?
            this.analyzeTrends(this.memoryHistory.slice(-10)) : {};

        return {
            current,
            trends,
            history: {
                dataPoints: this.memoryHistory.length,
                timeSpan: this.memoryHistory.length > 0 ?
                    this.memoryHistory[this.memoryHistory.length - 1].timestamp - this.memoryHistory[0].timestamp : 0,
                maxHeapUsed: Math.max(...this.memoryHistory.map(h => h.heap.used)),
                minHeapUsed: Math.min(...this.memoryHistory.map(h => h.heap.used)),
                avgHeapUsed: this.memoryHistory.reduce((sum, h) => sum + h.heap.used, 0) / this.memoryHistory.length
            },
            monitoring: {
                isActive: this.isMonitoring,
                interval: `${this.monitoringInterval / 1000}s`,
                alertThresholds: {
                    heapUsed: `${Math.round(this.alertThresholds.heapUsed / 1024 / 1024)}MB`,
                    heapTotal: `${Math.round(this.alertThresholds.heapTotal / 1024 / 1024)}MB`,
                    external: `${Math.round(this.alertThresholds.external / 1024 / 1024)}MB`
                }
            },
            recommendations: this.generateRecommendations()
        };
    }

    /**
     * 取得當前記憶體統計
     */
    getCurrentMemoryStats() {
        const memUsage = process.memoryUsage();
        return {
            timestamp: Date.now(),
            heap: {
                used: `${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
                total: `${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`,
                utilization: `${(memUsage.heapUsed / memUsage.heapTotal * 100).toFixed(2)}%`
            },
            external: `${Math.round(memUsage.external / 1024 / 1024)}MB`,
            arrayBuffers: `${Math.round(memUsage.arrayBuffers / 1024 / 1024)}MB`,
            resident: `${Math.round(memUsage.rss / 1024 / 1024)}MB`
        };
    }

    /**
     * 生成最佳化建議
     */
    generateRecommendations() {
        const recommendations = [];

        if (this.memoryHistory.length === 0) return recommendations;

        const latest = this.memoryHistory[this.memoryHistory.length - 1];
        const trends = this.analyzeTrends(this.memoryHistory.slice(-5));

        // 堆疊記憶體建議
        if (latest.heap.used > this.alertThresholds.heapUsed) {
            recommendations.push({
                type: 'HEAP_OPTIMIZATION',
                priority: 'HIGH',
                message: '考慮減少記憶體中的物件數量，或者增加垃圾回收頻率'
            });
        }

        // 外部記憶體建議
        if (latest.external > this.alertThresholds.external) {
            recommendations.push({
                type: 'EXTERNAL_OPTIMIZATION',
                priority: 'MEDIUM',
                message: '檢查 Buffer、TypedArray 或其他外部記憶體的使用'
            });
        }

        // 趨勢建議
        if (trends.heapUsed && trends.heapUsed.trend === 'increasing' && trends.heapUsed.growthRate > 5) {
            recommendations.push({
                type: 'MEMORY_LEAK_WARNING',
                priority: 'HIGH',
                message: '檢測到記憶體使用持續增長，可能存在記憶體洩漏'
            });
        }

        // 利用率建議
        if (parseFloat(latest.heap.utilization) > 85) {
            recommendations.push({
                type: 'HEAP_PRESSURE',
                priority: 'MEDIUM',
                message: '堆疊記憶體利用率過高，考慮調整 --max-old-space-size 參數'
            });
        }

        return recommendations;
    }

    /**
     * 重置統計
     */
    resetStats() {
        this.memoryHistory = [];
        this.gcStats = {
            major: 0,
            minor: 0,
            incremental: 0,
            totalTime: 0
        };
        this.objectCounters.clear();
        logger.info('記憶體監控統計已重置');
    }
}

// 單例模式
const memoryMonitor = new MemoryMonitor();

module.exports = {
    MemoryMonitor,
    memoryMonitor
};