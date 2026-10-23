/**
 * 垃圾回收最佳化器
 * 智能管理垃圾回收，減少 GC 停頓時間，提升系統效能
 */

const { logger } = require('./logger');

class GCOptimizer {
    constructor(options = {}) {
        this.enabled = options.enabled !== false;
        this.aggressiveMode = options.aggressiveMode || false;
        this.monitoringInterval = options.monitoringInterval || 30000; // 30秒
        this.gcThresholds = {
            heapUtilization: options.heapUtilization || 85, // 85%
            minorGCInterval: options.minorGCInterval || 60000, // 1分鐘
            majorGCInterval: options.majorGCInterval || 300000, // 5分鐘
            memoryPressure: options.memoryPressure || 80 // 80%
        };

        this.gcStats = {
            manualGCs: 0,
            autoGCs: 0,
            totalGCTime: 0,
            lastMinorGC: 0,
            lastMajorGC: 0,
            memoryFreed: 0
        };

        this.memoryHistory = [];
        this.gcHistory = [];
        this.isMonitoring = false;
        this.intervalId = null;

        // V8 引擎統計（如果可用）
        this.v8Stats = null;
        this.initializeV8Stats();
    }

    /**
     * 初始化 V8 統計
     */
    initializeV8Stats() {
        try {
            const v8 = require('v8');
            if (v8.getHeapStatistics && v8.getHeapSpaceStatistics) {
                this.v8Stats = v8;
                logger.info('✅ V8 引擎統計功能可用');
            }
        } catch (error) {
            logger.debug('V8 統計不可用:', error.message);
        }
    }

    /**
     * 開始 GC 最佳化
     */
    startOptimization() {
        if (!this.enabled || this.isMonitoring) return;

        this.isMonitoring = true;
        logger.info('🗑️ GC 最佳化器啟動');

        // 定期監控和最佳化
        this.intervalId = setInterval(() => {
            this.performOptimization();
        }, this.monitoringInterval);

        // 立即執行一次最佳化
        this.performOptimization();
    }

    /**
     * 停止最佳化
     */
    stopOptimization() {
        if (!this.isMonitoring) return;

        this.isMonitoring = false;
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        logger.info('🗑️ GC 最佳化器已停止');
    }

    /**
     * 執行最佳化策略
     */
    performOptimization() {
        try {
            const memUsage = process.memoryUsage();
            const timestamp = Date.now();

            // 記錄記憶體使用歷史
            this.recordMemoryUsage(memUsage, timestamp);

            // 檢查是否需要執行 GC
            const gcDecision = this.analyzeGCNeed(memUsage, timestamp);

            if (gcDecision.needGC) {
                this.executeGC(gcDecision.type, gcDecision.reason);
            }

            // 調整 V8 引擎參數（如果可用）
            this.optimizeV8Settings();

        } catch (error) {
            logger.error('GC 最佳化執行失敗:', error);
        }
    }

    /**
     * 記錄記憶體使用情況
     */
    recordMemoryUsage(memUsage, timestamp) {
        const record = {
            timestamp,
            heapUsed: memUsage.heapUsed,
            heapTotal: memUsage.heapTotal,
            external: memUsage.external,
            utilization: (memUsage.heapUsed / memUsage.heapTotal) * 100
        };

        this.memoryHistory.push(record);

        // 保留最近100個記錄
        if (this.memoryHistory.length > 100) {
            this.memoryHistory.shift();
        }
    }

    /**
     * 分析是否需要執行 GC
     */
    analyzeGCNeed(memUsage, timestamp) {
        const heapUtilization = (memUsage.heapUsed / memUsage.heapTotal) * 100;
        const timeSinceLastMinor = timestamp - this.gcStats.lastMinorGC;
        const timeSinceLastMajor = timestamp - this.gcStats.lastMajorGC;

        // 檢查各種觸發條件
        const conditions = {
            highHeapUtilization: heapUtilization > this.gcThresholds.heapUtilization,
            minorGCDue: timeSinceLastMinor > this.gcThresholds.minorGCInterval,
            majorGCDue: timeSinceLastMajor > this.gcThresholds.majorGCInterval,
            memoryPressure: this.detectMemoryPressure(),
            rapidGrowth: this.detectRapidMemoryGrowth()
        };

        // 決定 GC 類型和原因
        if (conditions.highHeapUtilization || conditions.memoryPressure) {
            return {
                needGC: true,
                type: 'major',
                reason: conditions.highHeapUtilization ? 'high_heap_utilization' : 'memory_pressure'
            };
        }

        if (conditions.rapidGrowth || conditions.majorGCDue) {
            return {
                needGC: true,
                type: 'major',
                reason: conditions.rapidGrowth ? 'rapid_growth' : 'scheduled_major'
            };
        }

        if (conditions.minorGCDue) {
            return {
                needGC: true,
                type: 'minor',
                reason: 'scheduled_minor'
            };
        }

        return { needGC: false };
    }

    /**
     * 偵測記憶體壓力
     */
    detectMemoryPressure() {
        if (this.memoryHistory.length < 5) return false;

        const recent = this.memoryHistory.slice(-5);
        const avgUtilization = recent.reduce((sum, record) =>
            sum + record.utilization, 0) / recent.length;

        return avgUtilization > this.gcThresholds.memoryPressure;
    }

    /**
     * 偵測快速記憶體增長
     */
    detectRapidMemoryGrowth() {
        if (this.memoryHistory.length < 10) return false;

        const recent = this.memoryHistory.slice(-10);
        const first = recent[0];
        const last = recent[recent.length - 1];
        const timeSpan = last.timestamp - first.timestamp;
        const memoryGrowth = last.heapUsed - first.heapUsed;

        // 如果在10個採樣週期內記憶體增長超過50MB
        const growthRate = (memoryGrowth / timeSpan) * 1000; // bytes per second
        return growthRate > (50 * 1024 * 1024 / 60); // 50MB per minute
    }

    /**
     * 執行垃圾回收
     */
    executeGC(type = 'minor', reason = 'manual') {
        if (!global.gc || typeof global.gc !== 'function') {
            logger.warn('垃圾回收不可用，請使用 --expose-gc 參數啟動 Node.js');
            return null;
        }

        const startTime = Date.now();
        const beforeMemory = process.memoryUsage();

        try {
            // 執行垃圾回收
            if (type === 'major') {
                // 執行完整的垃圾回收
                global.gc();
                this.gcStats.lastMajorGC = Date.now();
            } else {
                // 執行輕量級垃圾回收
                global.gc();
                this.gcStats.lastMinorGC = Date.now();
            }

            const afterMemory = process.memoryUsage();
            const gcTime = Date.now() - startTime;
            const memoryFreed = beforeMemory.heapUsed - afterMemory.heapUsed;

            // 更新統計
            this.gcStats.manualGCs++;
            this.gcStats.totalGCTime += gcTime;
            this.gcStats.memoryFreed += memoryFreed;

            // 記錄 GC 歷史
            const gcRecord = {
                timestamp: Date.now(),
                type,
                reason,
                duration: gcTime,
                memoryFreed,
                beforeHeap: beforeMemory.heapUsed,
                afterHeap: afterMemory.heapUsed,
                efficiency: beforeMemory.heapUsed > 0 ?
                    (memoryFreed / beforeMemory.heapUsed * 100).toFixed(2) : 0
            };

            this.gcHistory.push(gcRecord);
            if (this.gcHistory.length > 50) {
                this.gcHistory.shift();
            }

            logger.info(`🗑️ ${type.toUpperCase()} GC 完成 [${reason}]`, {
                duration: `${gcTime}ms`,
                freed: `${Math.round(memoryFreed / 1024 / 1024)}MB`,
                efficiency: `${gcRecord.efficiency}%`
            });

            return gcRecord;

        } catch (error) {
            logger.error('執行垃圾回收時發生錯誤:', error);
            return null;
        }
    }

    /**
     * 最佳化 V8 引擎設定
     */
    optimizeV8Settings() {
        if (!this.v8Stats) return;

        try {
            const heapStats = this.v8Stats.getHeapStatistics();
            const spaceStats = this.v8Stats.getHeapSpaceStatistics();

            // 分析堆疊空間使用情況
            const analysis = this.analyzeHeapSpaces(spaceStats);

            // 根據分析結果給出建議
            if (analysis.shouldOptimize) {
                this.applyV8Optimizations(analysis);
            }

        } catch (error) {
            logger.debug('V8 引擎最佳化失敗:', error.message);
        }
    }

    /**
     * 分析堆疊空間
     */
    analyzeHeapSpaces(spaceStats) {
        const analysis = {
            shouldOptimize: false,
            recommendations: []
        };

        for (const space of spaceStats) {
            const utilization = space.used_size / space.space_size * 100;

            if (space.space_name === 'new_space' && utilization > 90) {
                analysis.shouldOptimize = true;
                analysis.recommendations.push({
                    space: 'new_space',
                    issue: 'high_utilization',
                    suggestion: '考慮增加 --max-semi-space-size 參數'
                });
            }

            if (space.space_name === 'old_space' && utilization > 95) {
                analysis.shouldOptimize = true;
                analysis.recommendations.push({
                    space: 'old_space',
                    issue: 'high_utilization',
                    suggestion: '考慮增加 --max-old-space-size 參數'
                });
            }
        }

        return analysis;
    }

    /**
     * 應用 V8 最佳化建議
     */
    applyV8Optimizations(analysis) {
        for (const rec of analysis.recommendations) {
            logger.info(`💡 V8 最佳化建議 [${rec.space}]: ${rec.suggestion}`);
        }
    }

    /**
     * 強制執行垃圾回收
     */
    forceGC(type = 'major') {
        return this.executeGC(type, 'forced');
    }

    /**
     * 獲取 GC 統計報告
     */
    getGCReport() {
        const recentGCs = this.gcHistory.slice(-10);
        const avgGCTime = recentGCs.length > 0 ?
            recentGCs.reduce((sum, gc) => sum + gc.duration, 0) / recentGCs.length : 0;

        const avgEfficiency = recentGCs.length > 0 ?
            recentGCs.reduce((sum, gc) => sum + parseFloat(gc.efficiency), 0) / recentGCs.length : 0;

        return {
            stats: {
                ...this.gcStats,
                avgGCTime: `${avgGCTime.toFixed(2)}ms`,
                avgEfficiency: `${avgEfficiency.toFixed(2)}%`,
                totalMemoryFreed: `${Math.round(this.gcStats.memoryFreed / 1024 / 1024)}MB`,
                totalGCTime: `${this.gcStats.totalGCTime}ms`
            },
            recentActivity: recentGCs.map(gc => ({
                timestamp: new Date(gc.timestamp).toISOString(),
                type: gc.type,
                reason: gc.reason,
                duration: `${gc.duration}ms`,
                freed: `${Math.round(gc.memoryFreed / 1024 / 1024)}MB`,
                efficiency: `${gc.efficiency}%`
            })),
            configuration: {
                enabled: this.enabled,
                aggressiveMode: this.aggressiveMode,
                monitoringInterval: `${this.monitoringInterval / 1000}s`,
                thresholds: {
                    heapUtilization: `${this.gcThresholds.heapUtilization}%`,
                    minorGCInterval: `${this.gcThresholds.minorGCInterval / 1000}s`,
                    majorGCInterval: `${this.gcThresholds.majorGCInterval / 1000}s`,
                    memoryPressure: `${this.gcThresholds.memoryPressure}%`
                }
            },
            recommendations: this.generateGCRecommendations()
        };
    }

    /**
     * 生成 GC 最佳化建議
     */
    generateGCRecommendations() {
        const recommendations = [];

        if (this.gcHistory.length === 0) {
            return [{
                type: 'INFO',
                message: '暫無 GC 活動記錄'
            }];
        }

        const recentGCs = this.gcHistory.slice(-10);
        const avgEfficiency = recentGCs.reduce((sum, gc) =>
            sum + parseFloat(gc.efficiency), 0) / recentGCs.length;

        // 效率建議
        if (avgEfficiency < 20) {
            recommendations.push({
                type: 'EFFICIENCY',
                priority: 'HIGH',
                message: `GC 效率偏低 (${avgEfficiency.toFixed(2)}%)，建議檢查記憶體洩漏或調整 GC 策略`
            });
        }

        // 頻率建議
        const majorGCs = recentGCs.filter(gc => gc.type === 'major').length;
        if (majorGCs > 5) {
            recommendations.push({
                type: 'FREQUENCY',
                priority: 'MEDIUM',
                message: '主要 GC 執行頻繁，考慮增加堆疊大小或最佳化記憶體使用模式'
            });
        }

        // 時間建議
        const avgDuration = recentGCs.reduce((sum, gc) => sum + gc.duration, 0) / recentGCs.length;
        if (avgDuration > 100) {
            recommendations.push({
                type: 'PERFORMANCE',
                priority: 'MEDIUM',
                message: `GC 執行時間較長 (${avgDuration.toFixed(2)}ms)，考慮啟用增量 GC 或調整引擎參數`
            });
        }

        return recommendations;
    }

    /**
     * 重置 GC 統計
     */
    resetStats() {
        this.gcStats = {
            manualGCs: 0,
            autoGCs: 0,
            totalGCTime: 0,
            lastMinorGC: 0,
            lastMajorGC: 0,
            memoryFreed: 0
        };

        this.gcHistory = [];
        this.memoryHistory = [];

        logger.info('GC 統計已重置');
    }

    /**
     * 設定最佳化參數
     */
    configure(options) {
        if (options.enabled !== undefined) this.enabled = options.enabled;
        if (options.aggressiveMode !== undefined) this.aggressiveMode = options.aggressiveMode;
        if (options.monitoringInterval !== undefined) this.monitoringInterval = options.monitoringInterval;
        if (options.gcThresholds) {
            this.gcThresholds = { ...this.gcThresholds, ...options.gcThresholds };
        }

        logger.info('GC 最佳化器配置已更新', options);
    }
}

// 單例模式
const gcOptimizer = new GCOptimizer();

module.exports = {
    GCOptimizer,
    gcOptimizer
};