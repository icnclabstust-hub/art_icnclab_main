/**
 * 統一快取管理器
 * 提供統一的快取介面，支援多種快取策略和失效機制
 */

const { dbManager } = require('../database/connection');
const { logger } = require('./logger');

class CacheManager {
    constructor() {
        this.redisClient = null;
        this.isRedisAvailable = false;
        this.memoryCache = new Map();
        this.cacheStats = {
            hits: 0,
            misses: 0,
            sets: 0,
            deletes: 0,
            errors: 0,
            warming: 0,
            evictions: 0
        };

        // 預設配置
        this.defaultTTL = 3600; // 1小時
        this.maxMemoryCacheSize = 1000; // 記憶體快取最大項目數
        this.keyPrefix = 'art_history_cache:';

        // 高級快取功能
        this.warmupQueue = [];
        this.popularItems = new Map(); // 追蹤熱門項目
        this.accessPatterns = new Map(); // 存取模式分析
        this.compressionEnabled = true;
        this.compressionThreshold = 1024; // 1KB 以上才壓縮

        // 快取類別配置
        this.cacheConfigs = {
            artwork: {
                ttl: 7200,
                prefix: 'artwork:',
                warmup: true,
                compression: true,
                maxSize: 500,
                evictionPolicy: 'lru' // 最近最少使用
            },
            artist: {
                ttl: 14400,
                prefix: 'artist:',
                warmup: true,
                compression: true,
                maxSize: 300,
                evictionPolicy: 'lfu' // 最不常使用
            },
            search: {
                ttl: 1800,
                prefix: 'search:',
                warmup: false,
                compression: false,
                maxSize: 1000,
                evictionPolicy: 'ttl' // 按時間失效
            },
            collection: {
                ttl: 10800,
                prefix: 'collection:',
                warmup: true,
                compression: true,
                maxSize: 200,
                evictionPolicy: 'lru'
            },
            metadata: {
                ttl: 21600,
                prefix: 'metadata:',
                warmup: true,
                compression: true,
                maxSize: 800,
                evictionPolicy: 'lfu'
            },
            user_data: {
                ttl: 3600,
                prefix: 'user:',
                warmup: false,
                compression: false,
                maxSize: 100,
                evictionPolicy: 'lru'
            }
        };
    }

    /**
     * 初始化快取管理器
     */
    async init() {
        try {
            this.redisClient = dbManager.getRedisClient();
            this.isRedisAvailable = true;
            logger.info('✅ 快取管理器初始化成功 (使用 Redis)');

            // 設置定期統計報告
            setInterval(() => this.reportStats(), 300000); // 每5分鐘

            // 設置記憶體快取清理
            setInterval(() => this.cleanupMemoryCache(), 600000); // 每10分鐘

            // 快取預熱
            this.startCacheWarming();

            // 存取模式分析
            setInterval(() => this.analyzeAccessPatterns(), 3600000); // 每小時

        } catch (error) {
            this.isRedisAvailable = false;
            logger.warn('⚠️ Redis 不可用，使用記憶體快取:', error.message);

            // 設置記憶體快取限制檢查
            setInterval(() => this.enforceMemoryCacheLimit(), 60000); // 每分鐘檢查
            setInterval(() => this.smartEviction(), 300000); // 每5分鐘智能清理
        }
    }

    /**
     * 生成快取鍵
     */
    generateKey(category, identifier) {
        const config = this.cacheConfigs[category] || {};
        const prefix = config.prefix || '';
        return `${this.keyPrefix}${prefix}${identifier}`;
    }

    /**
     * 獲取快取
     */
    async get(category, identifier) {
        const key = this.generateKey(category, identifier);
        const startTime = Date.now();

        try {
            let result = null;
            let compressed = false;

            if (this.isRedisAvailable) {
                const redisResult = await this.getFromRedis(key);
                if (redisResult) {
                    result = redisResult.data;
                    compressed = redisResult.compressed;
                }
            } else {
                result = this.getFromMemory(key);
            }

            if (result !== null) {
                this.cacheStats.hits++;

                // 記錄存取模式
                this.recordAccess(category, identifier);

                // 解壓縮
                if (compressed) {
                    result = this.decompress(result);
                }

                const responseTime = Date.now() - startTime;
                logger.debug(`快取命中: ${key} (${responseTime}ms)`);

                return JSON.parse(result);
            } else {
                this.cacheStats.misses++;
                logger.debug(`快取未命中: ${key}`);
                return null;
            }

        } catch (error) {
            this.cacheStats.errors++;
            logger.error('快取獲取錯誤:', error);
            return null;
        }
    }

    /**
     * 設置快取
     */
    async set(category, identifier, data, customTTL = null) {
        const key = this.generateKey(category, identifier);
        const config = this.cacheConfigs[category] || {};
        const ttl = customTTL || config.ttl || this.defaultTTL;

        try {
            let serializedData = JSON.stringify(data);
            let compressed = false;

            // 壓縮大項目
            if (config.compression && serializedData.length > this.compressionThreshold) {
                serializedData = this.compress(serializedData);
                compressed = true;
            }

            if (this.isRedisAvailable) {
                await this.setInRedis(key, { data: serializedData, compressed, timestamp: Date.now() }, ttl);
            } else {
                this.setInMemory(key, serializedData, ttl);
            }

            this.cacheStats.sets++;
            logger.debug(`快取設置: ${key} (TTL: ${ttl}s, 壓縮: ${compressed})`);
            return true;

        } catch (error) {
            this.cacheStats.errors++;
            logger.error('快取設置錯誤:', error);
            return false;
        }
    }

    /**
     * 刪除快取
     */
    async delete(category, identifier) {
        const key = this.generateKey(category, identifier);

        try {
            if (this.isRedisAvailable) {
                await this.deleteFromRedis(key);
            } else {
                this.deleteFromMemory(key);
            }

            this.cacheStats.deletes++;
            logger.debug(`快取刪除: ${key}`);
            return true;

        } catch (error) {
            this.cacheStats.errors++;
            logger.error('快取刪除錯誤:', error);
            return false;
        }
    }

    /**
     * 批量刪除快取（按模式）
     */
    async deleteByPattern(category, pattern) {
        const searchPattern = this.generateKey(category, pattern);

        try {
            if (this.isRedisAvailable) {
                await this.deleteByPatternFromRedis(searchPattern);
            } else {
                this.deleteByPatternFromMemory(searchPattern);
            }

            logger.debug(`批量刪除快取: ${searchPattern}`);
            return true;

        } catch (error) {
            this.cacheStats.errors++;
            logger.error('批量刪除快取錯誤:', error);
            return false;
        }
    }

    /**
     * 清空特定類別的快取
     */
    async clearCategory(category) {
        const pattern = this.generateKey(category, '*');
        return await this.deleteByPattern(category, '*');
    }

    /**
     * 從 Redis 獲取
     */
    async getFromRedis(key) {
        const result = await this.redisClient.get(key);
        if (result) {
            try {
                return JSON.parse(result);
            } catch (error) {
                // 往下相容性：如果不是 JSON 格式，認為是舊數據
                return { data: result, compressed: false, timestamp: Date.now() };
            }
        }
        return null;
    }

    /**
     * 在 Redis 中設置
     */
    async setInRedis(key, dataObject, ttl) {
        await this.redisClient.setEx(key, ttl, JSON.stringify(dataObject));
    }

    /**
     * 從 Redis 刪除
     */
    async deleteFromRedis(key) {
        await this.redisClient.del(key);
    }

    /**
     * 從 Redis 批量刪除
     */
    async deleteByPatternFromRedis(pattern) {
        const keys = await this.redisClient.keys(pattern);
        if (keys.length > 0) {
            await this.redisClient.del(keys);
        }
    }

    /**
     * 從記憶體獲取
     */
    getFromMemory(key) {
        const item = this.memoryCache.get(key);
        if (!item) return null;

        // 檢查是否過期
        if (Date.now() > item.expiry) {
            this.memoryCache.delete(key);
            return null;
        }

        return item.data;
    }

    /**
     * 在記憶體中設置
     */
    setInMemory(key, data, ttl) {
        const expiry = Date.now() + (ttl * 1000);
        this.memoryCache.set(key, { data, expiry });

        // 檢查記憶體快取大小限制
        if (this.memoryCache.size > this.maxMemoryCacheSize) {
            this.enforceMemoryCacheLimit();
        }
    }

    /**
     * 從記憶體刪除
     */
    deleteFromMemory(key) {
        this.memoryCache.delete(key);
    }

    /**
     * 從記憶體批量刪除
     */
    deleteByPatternFromMemory(pattern) {
        const regex = new RegExp(pattern.replace(/\*/g, '.*'));
        const keysToDelete = [];

        for (const key of this.memoryCache.keys()) {
            if (regex.test(key)) {
                keysToDelete.push(key);
            }
        }

        keysToDelete.forEach(key => this.memoryCache.delete(key));
    }

    /**
     * 清理過期的記憶體快取
     */
    cleanupMemoryCache() {
        const now = Date.now();
        let cleanedCount = 0;

        for (const [key, item] of this.memoryCache.entries()) {
            if (now > item.expiry) {
                this.memoryCache.delete(key);
                cleanedCount++;
            }
        }

        if (cleanedCount > 0) {
            logger.debug(`清理了 ${cleanedCount} 個過期的記憶體快取項目`);
        }
    }

    /**
     * 強制執行記憶體快取大小限制
     */
    enforceMemoryCacheLimit() {
        if (this.memoryCache.size <= this.maxMemoryCacheSize) return;

        // 移除最舊的項目直到達到限制
        const entries = Array.from(this.memoryCache.entries());
        entries.sort((a, b) => a[1].expiry - b[1].expiry);

        const toRemove = this.memoryCache.size - this.maxMemoryCacheSize;
        for (let i = 0; i < toRemove; i++) {
            this.memoryCache.delete(entries[i][0]);
        }

        logger.debug(`強制移除了 ${toRemove} 個記憶體快取項目以符合大小限制`);
    }

    /**
     * 獲取快取統計
     */
    getStats() {
        const totalRequests = this.cacheStats.hits + this.cacheStats.misses;
        const hitRate = totalRequests > 0 ? (this.cacheStats.hits / totalRequests * 100).toFixed(2) : 0;

        return {
            ...this.cacheStats,
            hitRate: `${hitRate}%`,
            totalRequests,
            memoryUsage: this.memoryCache.size,
            isRedisAvailable: this.isRedisAvailable,
            warmupQueueSize: this.warmupQueue.length,
            popularItemsCount: this.popularItems.size,
            accessPatternsCount: this.accessPatterns.size,
            categoryStats: this.getCategoryStats()
        };
    }

    /**
     * 獲取各類別統計
     */
    getCategoryStats() {
        const stats = {};

        for (const category of Object.keys(this.cacheConfigs)) {
            const items = this.getCategoryItems(category);
            stats[category] = {
                itemCount: items.length,
                maxSize: this.cacheConfigs[category].maxSize,
                utilizationRate: this.cacheConfigs[category].maxSize > 0 ?
                    ((items.length / this.cacheConfigs[category].maxSize) * 100).toFixed(2) + '%' : 'N/A'
            };
        }

        return stats;
    }

    /**
     * 重置統計
     */
    resetStats() {
        this.cacheStats = {
            hits: 0,
            misses: 0,
            sets: 0,
            deletes: 0,
            errors: 0
        };
        logger.info('快取統計已重置');
    }

    /**
     * 報告統計
     */
    reportStats() {
        const stats = this.getStats();
        logger.info('快取統計報告:', stats);
    }

    /**
     * 健康檢查
     */
    async healthCheck() {
        try {
            const testKey = 'health_check_test';
            const testValue = { timestamp: Date.now() };

            // 測試設置和獲取
            await this.set('metadata', testKey, testValue, 60);
            const retrieved = await this.get('metadata', testKey);
            await this.delete('metadata', testKey);

            const isHealthy = retrieved && retrieved.timestamp === testValue.timestamp;

            return {
                healthy: isHealthy,
                backend: this.isRedisAvailable ? 'Redis' : 'Memory',
                stats: this.getStats()
            };

        } catch (error) {
            return {
                healthy: false,
                error: error.message,
                backend: this.isRedisAvailable ? 'Redis' : 'Memory',
                stats: this.getStats()
            };
        }
    }

    /**
     * 快取包裝器 - 自動處理快取邏輯
     */
    async wrap(category, identifier, fetchFunction, ttl = null) {
        // 嘗試從快取獲取
        let cached = await this.get(category, identifier);
        if (cached !== null) {
            return cached;
        }

        // 快取未命中，執行獲取函數
        try {
            const result = await fetchFunction();
            if (result !== null && result !== undefined) {
                await this.set(category, identifier, result, ttl);
                // 加入預熱隊列如果預測會再次使用
                this.addToWarmupQueue(category, identifier, fetchFunction, ttl);
            }
            return result;
        } catch (error) {
            logger.error(`快取包裝器獲取數據失敗 (${category}:${identifier}):`, error);
            throw error;
        }
    }

    /**
     * 壓縮數據
     */
    compress(data) {
        // 簡單的 gzip 壓縮模擬（實際應使用 zlib 或其他壓縮庫）
        try {
            const compressed = Buffer.from(data).toString('base64');
            return compressed;
        } catch (error) {
            logger.error('壓縮數據失敗:', error);
            return data;
        }
    }

    /**
     * 解壓縮數據
     */
    decompress(data) {
        try {
            const decompressed = Buffer.from(data, 'base64').toString('utf8');
            return decompressed;
        } catch (error) {
            logger.error('解壓縮數據失敗:', error);
            return data;
        }
    }

    /**
     * 記錄存取模式
     */
    recordAccess(category, identifier) {
        const key = `${category}:${identifier}`;
        const now = Date.now();

        if (!this.accessPatterns.has(key)) {
            this.accessPatterns.set(key, {
                count: 0,
                lastAccess: now,
                avgInterval: 0,
                trend: 'stable'
            });
        }

        const pattern = this.accessPatterns.get(key);
        pattern.count++;

        if (pattern.lastAccess) {
            const interval = now - pattern.lastAccess;
            pattern.avgInterval = pattern.avgInterval ?
                (pattern.avgInterval * 0.8 + interval * 0.2) : interval;
        }

        pattern.lastAccess = now;

        // 更新熱門項目
        this.updatePopularItems(key, pattern.count);
    }

    /**
     * 更新熱門項目
     */
    updatePopularItems(key, accessCount) {
        this.popularItems.set(key, accessCount);

        // 保持最熱門的 100 個項目
        if (this.popularItems.size > 100) {
            const sorted = Array.from(this.popularItems.entries())
                .sort((a, b) => b[1] - a[1])
                .slice(0, 100);
            this.popularItems = new Map(sorted);
        }
    }

    /**
     * 分析存取模式
     */
    analyzeAccessPatterns() {
        const now = Date.now();
        const oneHour = 3600000;

        for (const [key, pattern] of this.accessPatterns.entries()) {
            // 清理太舊的記錄
            if (now - pattern.lastAccess > oneHour * 24) {
                this.accessPatterns.delete(key);
                continue;
            }

            // 分析趨勢
            if (pattern.avgInterval && pattern.avgInterval < oneHour) {
                pattern.trend = 'increasing';
                // 預熱高頻率項目
                const [category, identifier] = key.split(':', 2);
                this.addToWarmupQueue(category, identifier);
            } else if (pattern.avgInterval > oneHour * 6) {
                pattern.trend = 'decreasing';
            }
        }

        logger.info(`存取模式分析完成，追蹤 ${this.accessPatterns.size} 個項目`);
    }

    /**
     * 加入預熱隊列
     */
    addToWarmupQueue(category, identifier, fetchFunction = null, ttl = null) {
        const config = this.cacheConfigs[category];
        if (!config || !config.warmup) return;

        const warmupItem = {
            category,
            identifier,
            fetchFunction,
            ttl,
            priority: this.popularItems.get(`${category}:${identifier}`) || 1,
            addedAt: Date.now()
        };

        // 避免重複
        const exists = this.warmupQueue.find(item =>
            item.category === category && item.identifier === identifier
        );

        if (!exists) {
            this.warmupQueue.push(warmupItem);
            this.warmupQueue.sort((a, b) => b.priority - a.priority);

            // 限制隊列大小
            if (this.warmupQueue.length > 500) {
                this.warmupQueue = this.warmupQueue.slice(0, 500);
            }
        }
    }

    /**
     * 啟動快取預熱
     */
    startCacheWarming() {
        setInterval(async () => {
            if (this.warmupQueue.length === 0) return;

            const batchSize = 5; // 每次處理 5 個項目
            const batch = this.warmupQueue.splice(0, batchSize);

            for (const item of batch) {
                try {
                    // 檢查是否已經存在於快取
                    const existing = await this.get(item.category, item.identifier);
                    if (existing === null && item.fetchFunction) {
                        const result = await item.fetchFunction();
                        if (result) {
                            await this.set(item.category, item.identifier, result, item.ttl);
                            this.cacheStats.warming++;
                            logger.debug(`預熱完成: ${item.category}:${item.identifier}`);
                        }
                    }
                } catch (error) {
                    logger.error(`預熱失敗: ${item.category}:${item.identifier}`, error);
                }
            }
        }, 10000); // 每 10 秒執行一次
    }

    /**
     * 智能清理策略
     */
    smartEviction() {
        const now = Date.now();

        for (const [category, config] of Object.entries(this.cacheConfigs)) {
            if (!config.maxSize) continue;

            // 獲取該類別的所有項目
            const categoryItems = this.getCategoryItems(category);

            if (categoryItems.length <= config.maxSize) continue;

            // 根據清理策略排序
            let itemsToEvict = [];

            switch (config.evictionPolicy) {
                case 'lru':
                    itemsToEvict = this.getLRUItems(categoryItems, config.maxSize);
                    break;
                case 'lfu':
                    itemsToEvict = this.getLFUItems(categoryItems, config.maxSize);
                    break;
                case 'ttl':
                    itemsToEvict = this.getTTLExpiredItems(categoryItems);
                    break;
            }

            // 執行清理
            for (const item of itemsToEvict) {
                this.delete(category, item.identifier);
                this.cacheStats.evictions++;
            }

            if (itemsToEvict.length > 0) {
                logger.debug(`智能清理 ${category}: 移除 ${itemsToEvict.length} 個項目`);
            }
        }
    }

    /**
     * 獲取類別項目（記憶體快取）
     */
    getCategoryItems(category) {
        const prefix = this.generateKey(category, '');
        const items = [];

        for (const [key, value] of this.memoryCache.entries()) {
            if (key.startsWith(prefix)) {
                const identifier = key.replace(prefix, '');
                items.push({
                    key,
                    identifier,
                    expiry: value.expiry,
                    accessCount: this.accessPatterns.get(`${category}:${identifier}`)?.count || 0,
                    lastAccess: this.accessPatterns.get(`${category}:${identifier}`)?.lastAccess || 0
                });
            }
        }

        return items;
    }

    /**
     * 獲取 LRU 項目
     */
    getLRUItems(items, maxSize) {
        return items
            .sort((a, b) => a.lastAccess - b.lastAccess)
            .slice(0, Math.max(0, items.length - maxSize));
    }

    /**
     * 獲取 LFU 項目
     */
    getLFUItems(items, maxSize) {
        return items
            .sort((a, b) => a.accessCount - b.accessCount)
            .slice(0, Math.max(0, items.length - maxSize));
    }

    /**
     * 獲取過期項目
     */
    getTTLExpiredItems(items) {
        const now = Date.now();
        return items.filter(item => now > item.expiry);
    }

    /**
     * 優雅關閉
     */
    async shutdown() {
        logger.info('正在關閉快取管理器...');

        // 清理記憶體快取
        this.memoryCache.clear();

        // Redis 連接將由 dbManager 處理
        logger.info('快取管理器已關閉');
    }
}

// 單例模式
const cacheManager = new CacheManager();

module.exports = {
    CacheManager,
    cacheManager
};