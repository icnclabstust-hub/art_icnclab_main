/**
 * 記憶體壓力管理系統
 * 動態監控記憶體壓力，實施緊急措施，防止系統崩潰
 */

const { logger } = require('./logger');
const { cacheManager } = require('./cacheManager');
const { objectPoolManager } = require('./objectPoolManager');
const { gcOptimizer } = require('./gcOptimizer');

class MemoryPressureManager {
    constructor(options = {}) {
        this.enabled = options.enabled !== false;
        this.pressureLevels = {
            low: {
                threshold: options.lowPressure || 60,      // 60% 記憶體使用
                actions: ['cleanup_expired_cache', 'pool_maintenance']
            },
            moderate: {
                threshold: options.moderatePressure || 75, // 75% 記憶體使用
                actions: ['aggressive_cache_cleanup', 'minor_gc', 'buffer_reduction']
            },
            high: {
                threshold: options.highPressure || 85,     // 85% 記憶體使用
                actions: ['emergency_cache_clear', 'major_gc', 'pool_shrinking']
            },
            critical: {
                threshold: options.criticalPressure || 95, // 95% 記憶體使用
                actions: ['emergency_shutdown_prep', 'full_gc', 'memory_dump']
            }
        };

        this.currentPressureLevel = 'normal';
        this.lastPressureCheck = 0;
        this.checkInterval = options.checkInterval || 15000; // 15秒檢查一次
        this.actionHistory = [];
        this.emergencyMode = false;

        // 記憶體限制設定
        this.memoryLimits = {
            heap: options.heapLimit || this.getDefaultHeapLimit(),
            rss: options.rssLimit || (2 * 1024 * 1024 * 1024), // 2GB RSS 限制
            external: options.externalLimit || (500 * 1024 * 1024) // 500MB 外部記憶體限制
        };

        // 緊急回應策略
        this.emergencyStrategies = new Map();
        this.initializeEmergencyStrategies();

        this.isMonitoring = false;
        this.intervalId = null;
    }

    /**
     * 取得預設堆疊限制
     */
    getDefaultHeapLimit() {
        try {
            const v8 = require('v8');
            if (v8.getHeapStatistics) {
                const stats = v8.getHeapStatistics();
                return stats.heap_size_limit || (1024 * 1024 * 1024); // 預設 1GB
            }
        } catch (error) {
            // 預設值
        }
        return 1024 * 1024 * 1024; // 1GB
    }

    /**
     * 初始化緊急應對策略
     */
    initializeEmergencyStrategies() {
        // 過期快取清理
        this.emergencyStrategies.set('cleanup_expired_cache', async () => {
            logger.info('🧹 執行過期快取清理...');
            if (cacheManager.cleanupMemoryCache) {
                cacheManager.cleanupMemoryCache();
                return { success: true, action: '清理過期快取' };
            }
            return { success: false, reason: '快取管理器不支援清理功能' };
        });

        // 物件池維護
        this.emergencyStrategies.set('pool_maintenance', async () => {
            logger.info('🔧 執行物件池維護...');
            objectPoolManager.cleanup();
            return { success: true, action: '物件池維護' };
        });

        // 積極快取清理
        this.emergencyStrategies.set('aggressive_cache_cleanup', async () => {
            logger.warn('⚠️ 執行積極快取清理...');
            const categories = ['search', 'user_data'];
            for (const category of categories) {
                await cacheManager.clearCategory(category);
            }
            return { success: true, action: '積極快取清理' };
        });

        // 輕量垃圾回收
        this.emergencyStrategies.set('minor_gc', async () => {
            logger.info('🗑️ 執行輕量垃圾回收...');
            const result = gcOptimizer.forceGC('minor');
            return result ?
                { success: true, action: '輕量GC', freed: result.memoryFreed } :
                { success: false, reason: 'GC 不可用' };
        });

        // 緩衝區減少
        this.emergencyStrategies.set('buffer_reduction', async () => {
            logger.warn('📉 減少緩衝區大小...');
            // 清理大型緩衝區池
            const largePool = objectPoolManager.bufferPools.get('large');
            if (largePool) {
                const originalSize = largePool.pool.length;
                largePool.pool = largePool.pool.slice(0, Math.max(2, originalSize * 0.3));
                return {
                    success: true,
                    action: '緩衝區減少',
                    reduced: originalSize - largePool.pool.length
                };
            }
            return { success: false, reason: '無可減少的緩衝區' };
        });

        // 緊急快取清空
        this.emergencyStrategies.set('emergency_cache_clear', async () => {
            logger.error('🚨 緊急快取清空...');
            const categories = ['artwork', 'artist', 'collection'];
            for (const category of categories) {
                await cacheManager.clearCategory(category);
            }
            return { success: true, action: '緊急快取清空' };
        });

        // 主要垃圾回收
        this.emergencyStrategies.set('major_gc', async () => {
            logger.warn('🗑️ 執行主要垃圾回收...');
            const result = gcOptimizer.forceGC('major');
            return result ?
                { success: true, action: '主要GC', freed: result.memoryFreed } :
                { success: false, reason: 'GC 不可用' };
        });

        // 物件池縮減
        this.emergencyStrategies.set('pool_shrinking', async () => {
            logger.error('📉 緊急物件池縮減...');
            let totalReduced = 0;

            for (const [name, pool] of objectPoolManager.pools) {
                const originalSize = pool.pool.length;
                pool.pool = pool.pool.slice(0, Math.max(1, originalSize * 0.2));
                totalReduced += originalSize - pool.pool.length;
            }

            return {
                success: true,
                action: '物件池縮減',
                reduced: totalReduced
            };
        });

        // 記憶體轉儲
        this.emergencyStrategies.set('memory_dump', async () => {
            logger.error('💾 生成記憶體轉儲...');
            try {
                const memReport = this.generateMemoryDump();
                return {
                    success: true,
                    action: '記憶體轉儲',
                    dump: memReport
                };
            } catch (error) {
                return {
                    success: false,
                    reason: '轉儲失敗',
                    error: error.message
                };
            }
        });

        // 緊急關機準備
        this.emergencyStrategies.set('emergency_shutdown_prep', async () => {
            logger.error('🚨 準備緊急關機...');
            this.emergencyMode = true;

            // 通知其他系統準備關機
            process.emit('memory-emergency', {
                level: 'critical',
                timestamp: Date.now(),
                memory: process.memoryUsage()
            });

            return {
                success: true,
                action: '緊急關機準備',
                emergencyMode: true
            };
        });

        // 完整垃圾回收
        this.emergencyStrategies.set('full_gc', async () => {
            logger.error('🗑️ 執行完整垃圾回收...');

            // 連續執行多次 GC
            let totalFreed = 0;
            for (let i = 0; i < 3; i++) {
                const result = gcOptimizer.forceGC('major');
                if (result) {
                    totalFreed += result.memoryFreed;
                }
                await this.delay(100); // 短暫延遲
            }

            return {
                success: true,
                action: '完整GC',
                iterations: 3,
                totalFreed
            };
        });
    }

    /**
     * 開始記憶體壓力監控
     */
    startMonitoring() {
        if (!this.enabled || this.isMonitoring) return;

        this.isMonitoring = true;
        logger.info('📊 記憶體壓力監控啟動');

        // 定期檢查記憶體壓力
        this.intervalId = setInterval(() => {
            this.checkMemoryPressure();
        }, this.checkInterval);

        // 立即執行一次檢查
        this.checkMemoryPressure();
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

        logger.info('📊 記憶體壓力監控已停止');
    }

    /**
     * 檢查記憶體壓力
     */
    async checkMemoryPressure() {
        try {
            const memUsage = process.memoryUsage();
            const timestamp = Date.now();

            // 計算各項記憶體使用率
            const heapUtilization = (memUsage.heapUsed / this.memoryLimits.heap) * 100;
            const rssUtilization = (memUsage.rss / this.memoryLimits.rss) * 100;
            const externalUtilization = (memUsage.external / this.memoryLimits.external) * 100;

            // 取最高的使用率作為壓力指標
            const maxUtilization = Math.max(heapUtilization, rssUtilization, externalUtilization);

            // 判定壓力等級
            const pressureLevel = this.determinePressureLevel(maxUtilization);

            // 如果壓力等級改變，執行相應動作
            if (pressureLevel !== this.currentPressureLevel) {
                await this.handlePressureLevelChange(pressureLevel, memUsage, maxUtilization);
            }

            this.currentPressureLevel = pressureLevel;
            this.lastPressureCheck = timestamp;

            // 記錄極高壓力情況
            if (pressureLevel === 'critical') {
                logger.error('🚨 記憶體壓力達到臨界狀態！', {
                    heap: `${heapUtilization.toFixed(2)}%`,
                    rss: `${rssUtilization.toFixed(2)}%`,
                    external: `${externalUtilization.toFixed(2)}%`
                });
            }

        } catch (error) {
            logger.error('記憶體壓力檢查失敗:', error);
        }
    }

    /**
     * 判定壓力等級
     */
    determinePressureLevel(utilization) {
        if (utilization >= this.pressureLevels.critical.threshold) {
            return 'critical';
        } else if (utilization >= this.pressureLevels.high.threshold) {
            return 'high';
        } else if (utilization >= this.pressureLevels.moderate.threshold) {
            return 'moderate';
        } else if (utilization >= this.pressureLevels.low.threshold) {
            return 'low';
        }
        return 'normal';
    }

    /**
     * 處理壓力等級變化
     */
    async handlePressureLevelChange(newLevel, memUsage, utilization) {
        logger.warn(`📈 記憶體壓力等級變化: ${this.currentPressureLevel} → ${newLevel} (${utilization.toFixed(2)}%)`);

        if (newLevel === 'normal') {
            // 壓力緩解，記錄恢復
            logger.info('✅ 記憶體壓力已緩解');
            return;
        }

        const levelConfig = this.pressureLevels[newLevel];
        if (!levelConfig) return;

        // 執行對應的應對動作
        const actionResults = [];
        for (const actionName of levelConfig.actions) {
            const strategy = this.emergencyStrategies.get(actionName);
            if (strategy) {
                try {
                    const result = await strategy();
                    actionResults.push({
                        action: actionName,
                        timestamp: Date.now(),
                        level: newLevel,
                        ...result
                    });
                } catch (error) {
                    actionResults.push({
                        action: actionName,
                        timestamp: Date.now(),
                        level: newLevel,
                        success: false,
                        error: error.message
                    });
                }
            }
        }

        // 記錄動作歷史
        this.actionHistory.push({
            timestamp: Date.now(),
            level: newLevel,
            utilization: utilization.toFixed(2),
            memUsage,
            actions: actionResults
        });

        // 限制歷史記錄大小
        if (this.actionHistory.length > 100) {
            this.actionHistory = this.actionHistory.slice(-50);
        }

        // 記錄成功的動作
        const successfulActions = actionResults.filter(r => r.success);
        const failedActions = actionResults.filter(r => !r.success);

        if (successfulActions.length > 0) {
            logger.info(`✅ 成功執行 ${successfulActions.length} 個應對動作:`,
                successfulActions.map(a => a.action));
        }

        if (failedActions.length > 0) {
            logger.error(`❌ ${failedActions.length} 個動作執行失敗:`,
                failedActions.map(a => `${a.action}: ${a.reason || a.error}`));
        }
    }

    /**
     * 生成記憶體轉儲報告
     */
    generateMemoryDump() {
        const memUsage = process.memoryUsage();

        let v8Stats = null;
        try {
            const v8 = require('v8');
            if (v8.getHeapStatistics && v8.getHeapSpaceStatistics) {
                v8Stats = {
                    heap: v8.getHeapStatistics(),
                    spaces: v8.getHeapSpaceStatistics()
                };
            }
        } catch (error) {
            // V8 統計不可用
        }

        return {
            timestamp: new Date().toISOString(),
            process: {
                pid: process.pid,
                uptime: process.uptime(),
                version: process.version,
                platform: process.platform
            },
            memory: {
                usage: memUsage,
                limits: this.memoryLimits,
                utilization: {
                    heap: `${(memUsage.heapUsed / this.memoryLimits.heap * 100).toFixed(2)}%`,
                    rss: `${(memUsage.rss / this.memoryLimits.rss * 100).toFixed(2)}%`,
                    external: `${(memUsage.external / this.memoryLimits.external * 100).toFixed(2)}%`
                }
            },
            v8: v8Stats,
            pressure: {
                currentLevel: this.currentPressureLevel,
                emergencyMode: this.emergencyMode,
                recentActions: this.actionHistory.slice(-10)
            }
        };
    }

    /**
     * 手動觸發壓力應對
     */
    async triggerEmergencyAction(actionName) {
        const strategy = this.emergencyStrategies.get(actionName);
        if (!strategy) {
            throw new Error(`未知的緊急動作: ${actionName}`);
        }

        logger.warn(`🚨 手動觸發緊急動作: ${actionName}`);
        const result = await strategy();

        // 記錄手動觸發的動作
        this.actionHistory.push({
            timestamp: Date.now(),
            level: 'manual',
            utilization: 'N/A',
            memUsage: process.memoryUsage(),
            actions: [{
                action: actionName,
                timestamp: Date.now(),
                level: 'manual',
                ...result
            }]
        });

        return result;
    }

    /**
     * 獲取壓力管理報告
     */
    getPressureReport() {
        const memUsage = process.memoryUsage();
        const recentActions = this.actionHistory.slice(-10);

        return {
            current: {
                level: this.currentPressureLevel,
                emergencyMode: this.emergencyMode,
                lastCheck: new Date(this.lastPressureCheck).toISOString(),
                memory: {
                    heap: `${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
                    rss: `${Math.round(memUsage.rss / 1024 / 1024)}MB`,
                    external: `${Math.round(memUsage.external / 1024 / 1024)}MB`,
                    utilization: {
                        heap: `${(memUsage.heapUsed / this.memoryLimits.heap * 100).toFixed(2)}%`,
                        rss: `${(memUsage.rss / this.memoryLimits.rss * 100).toFixed(2)}%`,
                        external: `${(memUsage.external / this.memoryLimits.external * 100).toFixed(2)}%`
                    }
                }
            },
            configuration: {
                enabled: this.enabled,
                checkInterval: `${this.checkInterval / 1000}s`,
                limits: {
                    heap: `${Math.round(this.memoryLimits.heap / 1024 / 1024)}MB`,
                    rss: `${Math.round(this.memoryLimits.rss / 1024 / 1024)}MB`,
                    external: `${Math.round(this.memoryLimits.external / 1024 / 1024)}MB`
                },
                pressureLevels: Object.keys(this.pressureLevels).map(level => ({
                    level,
                    threshold: `${this.pressureLevels[level].threshold}%`,
                    actions: this.pressureLevels[level].actions
                }))
            },
            activity: {
                totalActions: this.actionHistory.length,
                recentActions: recentActions.map(entry => ({
                    timestamp: new Date(entry.timestamp).toISOString(),
                    level: entry.level,
                    utilization: entry.utilization,
                    actions: entry.actions.map(a => ({
                        name: a.action,
                        success: a.success,
                        result: a.success ? (a.freed ? `freed ${Math.round(a.freed / 1024 / 1024)}MB` : 'completed') : a.reason
                    }))
                }))
            },
            monitoring: {
                isActive: this.isMonitoring,
                interval: `${this.checkInterval / 1000}s`
            }
        };
    }

    /**
     * 延遲工具函數
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 重置統計和歷史
     */
    reset() {
        this.actionHistory = [];
        this.currentPressureLevel = 'normal';
        this.emergencyMode = false;
        this.lastPressureCheck = 0;

        logger.info('記憶體壓力管理器已重置');
    }
}

// 單例模式
const memoryPressureManager = new MemoryPressureManager();

module.exports = {
    MemoryPressureManager,
    memoryPressureManager
};