/**
 * 物件池管理器
 * 減少物件創建和銷毀的開銷，提升記憶體效率
 */

const { logger } = require('./logger');

class ObjectPool {
    constructor(factory, reset, initialSize = 10, maxSize = 100) {
        this.factory = factory;        // 物件建立函數
        this.reset = reset;            // 物件重置函數
        this.pool = [];               // 物件池
        this.maxSize = maxSize;       // 最大池大小
        this.created = 0;             // 已創建物件數
        this.acquired = 0;            // 已取得物件數
        this.released = 0;            // 已釋放物件數

        // 預創建物件
        for (let i = 0; i < initialSize; i++) {
            this.pool.push(this.createObject());
        }
    }

    /**
     * 創建新物件
     */
    createObject() {
        const obj = this.factory();
        this.created++;
        return obj;
    }

    /**
     * 從池中取得物件
     */
    acquire() {
        let obj;

        if (this.pool.length > 0) {
            obj = this.pool.pop();
        } else {
            obj = this.createObject();
        }

        this.acquired++;
        return obj;
    }

    /**
     * 歸還物件到池中
     */
    release(obj) {
        if (!obj) return;

        try {
            // 重置物件狀態
            if (this.reset) {
                this.reset(obj);
            }

            // 如果池未滿，歸還物件
            if (this.pool.length < this.maxSize) {
                this.pool.push(obj);
                this.released++;
            }
        } catch (error) {
            logger.error('物件池歸還失敗:', error);
        }
    }

    /**
     * 清空池
     */
    clear() {
        this.pool = [];
    }

    /**
     * 獲取池統計
     */
    getStats() {
        return {
            poolSize: this.pool.length,
            maxSize: this.maxSize,
            created: this.created,
            acquired: this.acquired,
            released: this.released,
            utilization: this.acquired > 0 ?
                ((this.acquired - this.pool.length) / this.acquired * 100).toFixed(2) + '%' : '0%'
        };
    }
}

class ObjectPoolManager {
    constructor() {
        this.pools = new Map();
        this.bufferPools = new Map();
        this.stats = {
            totalAcquisitions: 0,
            totalReleases: 0,
            memoryUsage: 0
        };
    }

    /**
     * 創建或取得物件池
     */
    createPool(name, factory, reset, initialSize = 10, maxSize = 100) {
        if (this.pools.has(name)) {
            return this.pools.get(name);
        }

        const pool = new ObjectPool(factory, reset, initialSize, maxSize);
        this.pools.set(name, pool);

        logger.info(`📦 創建物件池 '${name}' (初始: ${initialSize}, 最大: ${maxSize})`);
        return pool;
    }

    /**
     * 創建常用物件池
     */
    initializeCommonPools() {
        // HTTP 響應物件池
        this.createPool('httpResponse',
            () => ({
                success: true,
                data: null,
                message: '',
                error: null,
                pagination: null
            }),
            (obj) => {
                obj.success = true;
                obj.data = null;
                obj.message = '';
                obj.error = null;
                obj.pagination = null;
            },
            20, 100
        );

        // 查詢結果物件池
        this.createPool('queryResult',
            () => ({
                rows: [],
                count: 0,
                metadata: {},
                executionTime: 0
            }),
            (obj) => {
                obj.rows = [];
                obj.count = 0;
                obj.metadata = {};
                obj.executionTime = 0;
            },
            15, 50
        );

        // 日誌物件池
        this.createPool('logEntry',
            () => ({
                level: '',
                message: '',
                timestamp: null,
                metadata: {},
                stack: null
            }),
            (obj) => {
                obj.level = '';
                obj.message = '';
                obj.timestamp = null;
                obj.metadata = {};
                obj.stack = null;
            },
            30, 150
        );

        // 快取項目物件池
        this.createPool('cacheEntry',
            () => ({
                key: '',
                value: null,
                expiry: 0,
                hits: 0,
                created: 0
            }),
            (obj) => {
                obj.key = '';
                obj.value = null;
                obj.expiry = 0;
                obj.hits = 0;
                obj.created = 0;
            },
            25, 200
        );

        logger.info('✅ 常用物件池初始化完成');
    }

    /**
     * 創建緩衝區池
     */
    createBufferPool(name, bufferSize, initialCount = 5, maxCount = 50) {
        if (this.bufferPools.has(name)) {
            return this.bufferPools.get(name);
        }

        const pool = new ObjectPool(
            () => Buffer.alloc(bufferSize),
            (buffer) => buffer.fill(0),
            initialCount,
            maxCount
        );

        this.bufferPools.set(name, pool);
        logger.info(`💾 創建緩衝區池 '${name}' (大小: ${bufferSize}bytes, 數量: ${initialCount}-${maxCount})`);
        return pool;
    }

    /**
     * 初始化常用緩衝區池
     */
    initializeBufferPools() {
        // 小型緩衝區 (1KB)
        this.createBufferPool('small', 1024, 10, 100);

        // 中型緩衝區 (16KB)
        this.createBufferPool('medium', 16384, 5, 50);

        // 大型緩衝區 (64KB)
        this.createBufferPool('large', 65536, 2, 20);

        logger.info('✅ 緩衝區池初始化完成');
    }

    /**
     * 從池中取得物件
     */
    acquire(poolName) {
        const pool = this.pools.get(poolName);
        if (!pool) {
            throw new Error(`物件池 '${poolName}' 不存在`);
        }

        const obj = pool.acquire();
        this.stats.totalAcquisitions++;
        return obj;
    }

    /**
     * 歸還物件到池
     */
    release(poolName, obj) {
        const pool = this.pools.get(poolName);
        if (!pool) {
            logger.warn(`嘗試歸還物件到不存在的池: ${poolName}`);
            return;
        }

        pool.release(obj);
        this.stats.totalReleases++;
    }

    /**
     * 取得緩衝區
     */
    acquireBuffer(poolName) {
        const pool = this.bufferPools.get(poolName);
        if (!pool) {
            throw new Error(`緩衝區池 '${poolName}' 不存在`);
        }

        return pool.acquire();
    }

    /**
     * 歸還緩衝區
     */
    releaseBuffer(poolName, buffer) {
        const pool = this.bufferPools.get(poolName);
        if (!pool) {
            logger.warn(`嘗試歸還緩衝區到不存在的池: ${poolName}`);
            return;
        }

        pool.release(buffer);
    }

    /**
     * 清理未使用的池
     */
    cleanup() {
        let cleaned = 0;

        // 清理物件池
        for (const [name, pool] of this.pools) {
            const stats = pool.getStats();
            if (stats.poolSize > stats.maxSize * 0.8) {
                // 如果池中物件過多，清理一半
                const toRemove = Math.floor(stats.poolSize * 0.5);
                for (let i = 0; i < toRemove; i++) {
                    pool.pool.pop();
                    cleaned++;
                }
                logger.debug(`清理物件池 '${name}': 移除 ${toRemove} 個物件`);
            }
        }

        // 清理緩衝區池
        for (const [name, pool] of this.bufferPools) {
            const stats = pool.getStats();
            if (stats.poolSize > stats.maxSize * 0.8) {
                const toRemove = Math.floor(stats.poolSize * 0.5);
                for (let i = 0; i < toRemove; i++) {
                    pool.pool.pop();
                    cleaned++;
                }
                logger.debug(`清理緩衝區池 '${name}': 移除 ${toRemove} 個緩衝區`);
            }
        }

        if (cleaned > 0) {
            logger.info(`🧹 物件池清理完成，移除 ${cleaned} 個未使用物件`);
        }
    }

    /**
     * 獲取所有池的統計資訊
     */
    getStats() {
        const poolStats = {};
        const bufferStats = {};

        // 物件池統計
        for (const [name, pool] of this.pools) {
            poolStats[name] = pool.getStats();
        }

        // 緩衝區池統計
        for (const [name, pool] of this.bufferPools) {
            bufferStats[name] = pool.getStats();
        }

        // 計算總記憶體使用量估算
        let estimatedMemory = 0;
        for (const pool of this.pools.values()) {
            estimatedMemory += pool.pool.length * 1024; // 假設每個物件平均1KB
        }
        for (const [name, pool] of this.bufferPools) {
            const bufferSize = name === 'small' ? 1024 :
                             name === 'medium' ? 16384 : 65536;
            estimatedMemory += pool.pool.length * bufferSize;
        }

        return {
            global: {
                ...this.stats,
                estimatedMemoryUsage: `${Math.round(estimatedMemory / 1024 / 1024)}MB`,
                totalPools: this.pools.size,
                totalBufferPools: this.bufferPools.size
            },
            objectPools: poolStats,
            bufferPools: bufferStats,
            efficiency: {
                reuseRate: this.stats.totalAcquisitions > 0 ?
                    `${((this.stats.totalReleases / this.stats.totalAcquisitions) * 100).toFixed(2)}%` : '0%',
                avgPoolUtilization: this.calculateAvgUtilization()
            }
        };
    }

    /**
     * 計算平均池利用率
     */
    calculateAvgUtilization() {
        let totalUtilization = 0;
        let poolCount = 0;

        for (const pool of this.pools.values()) {
            const stats = pool.getStats();
            if (stats.acquired > 0) {
                totalUtilization += parseFloat(stats.utilization);
                poolCount++;
            }
        }

        for (const pool of this.bufferPools.values()) {
            const stats = pool.getStats();
            if (stats.acquired > 0) {
                totalUtilization += parseFloat(stats.utilization);
                poolCount++;
            }
        }

        return poolCount > 0 ? `${(totalUtilization / poolCount).toFixed(2)}%` : '0%';
    }

    /**
     * 定期維護
     */
    startMaintenance() {
        // 每5分鐘進行一次清理
        setInterval(() => {
            this.cleanup();
        }, 300000);

        logger.info('🔧 物件池維護已啟動');
    }

    /**
     * 重置所有統計
     */
    resetStats() {
        this.stats = {
            totalAcquisitions: 0,
            totalReleases: 0,
            memoryUsage: 0
        };

        // 重置各個池的統計
        for (const pool of this.pools.values()) {
            pool.created = 0;
            pool.acquired = 0;
            pool.released = 0;
        }

        for (const pool of this.bufferPools.values()) {
            pool.created = 0;
            pool.acquired = 0;
            pool.released = 0;
        }

        logger.info('物件池統計已重置');
    }

    /**
     * 關閉管理器
     */
    shutdown() {
        // 清空所有池
        for (const pool of this.pools.values()) {
            pool.clear();
        }

        for (const pool of this.bufferPools.values()) {
            pool.clear();
        }

        this.pools.clear();
        this.bufferPools.clear();

        logger.info('📦 物件池管理器已關閉');
    }
}

// 單例模式
const objectPoolManager = new ObjectPoolManager();

module.exports = {
    ObjectPool,
    ObjectPoolManager,
    objectPoolManager
};