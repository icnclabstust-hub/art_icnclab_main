/**
 * 快取預載器
 * 在系統啟動時預載常用數據，提升響應速度
 */

const { cacheManager } = require('./cacheManager');
const { logger } = require('./logger');
const { dbManager } = require('../database/connection');

class CachePreloader {
    constructor() {
        this.preloadTasks = [];
        this.isPreloading = false;
        this.preloadStats = {
            total: 0,
            completed: 0,
            failed: 0,
            startTime: null,
            endTime: null
        };
    }

    /**
     * 註冊預載任務
     */
    registerTask(category, identifier, fetchFunction, options = {}) {
        this.preloadTasks.push({
            category,
            identifier,
            fetchFunction,
            priority: options.priority || 1,
            ttl: options.ttl,
            condition: options.condition, // 預載條件函數
            dependencies: options.dependencies || [] // 依賴的其他任務
        });
    }

    /**
     * 註冊常用數據預載任務
     */
    registerCommonTasks() {
        // 預載熱門藝術家
        this.registerTask('artist', 'popular_artists', async () => {
            const pgClient = dbManager.getConnection('postgres');
            const result = await pgClient.query(`
                SELECT a.*, COUNT(aw.id) as artwork_count
                FROM artists a
                LEFT JOIN artworks aw ON a.id = aw.artist_id
                GROUP BY a.id
                ORDER BY artwork_count DESC
                LIMIT 20
            `);
            return result.rows;
        }, { priority: 10, ttl: 14400 }); // 4小時

        // 預載熱門收藏
        this.registerTask('collection', 'featured_collections', async () => {
            const pgClient = dbManager.getConnection('postgres');
            const result = await pgClient.query(`
                SELECT c.*, COUNT(ca.artwork_id) as artwork_count
                FROM collections c
                LEFT JOIN collection_artworks ca ON c.id = ca.collection_id
                WHERE c.featured = true
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT 10
            `);
            return result.rows;
        }, { priority: 8, ttl: 10800 }); // 3小時

        // 預載最新藝術作品
        this.registerTask('artwork', 'recent_artworks', async () => {
            const pgClient = dbManager.getConnection('postgres');
            const result = await pgClient.query(`
                SELECT * FROM artworks
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT 50
            `);
            return result.rows;
        }, { priority: 9, ttl: 3600 }); // 1小時

        // 預載系統統計
        this.registerTask('metadata', 'system_stats', async () => {
            const pgClient = dbManager.getConnection('postgres');
            const [artistCount, artworkCount, collectionCount] = await Promise.all([
                pgClient.query('SELECT COUNT(*) FROM artists'),
                pgClient.query('SELECT COUNT(*) FROM artworks WHERE status = \'active\''),
                pgClient.query('SELECT COUNT(*) FROM collections')
            ]);

            return {
                artists: parseInt(artistCount.rows[0].count),
                artworks: parseInt(artworkCount.rows[0].count),
                collections: parseInt(collectionCount.rows[0].count),
                lastUpdated: new Date().toISOString()
            };
        }, { priority: 5, ttl: 1800 }); // 30分鐘

        // 預載搜索建議
        this.registerTask('search', 'popular_terms', async () => {
            // 從日誌或統計表中獲取熱門搜索詞
            return [
                'Van Gogh', 'Picasso', 'Monet', 'Da Vinci', 'Rembrandt',
                'impressionism', 'abstract art', 'renaissance', 'baroque', 'modern art'
            ];
        }, { priority: 6, ttl: 7200 }); // 2小時
    }

    /**
     * 開始預載
     */
    async startPreloading() {
        if (this.isPreloading) {
            logger.warn('預載器已在運行中');
            return;
        }

        this.isPreloading = true;
        this.preloadStats = {
            total: this.preloadTasks.length,
            completed: 0,
            failed: 0,
            startTime: Date.now(),
            endTime: null
        };

        logger.info(`🔄 開始快取預載，共 ${this.preloadTasks.length} 個任務`);

        try {
            // 按優先級排序
            const sortedTasks = this.preloadTasks.sort((a, b) => b.priority - a.priority);

            // 批量處理，避免過載
            const batchSize = 5;
            for (let i = 0; i < sortedTasks.length; i += batchSize) {
                const batch = sortedTasks.slice(i, i + batchSize);
                await Promise.all(batch.map(task => this.executeTask(task)));

                // 短暫延遲，避免系統負載過高
                if (i + batchSize < sortedTasks.length) {
                    await this.delay(1000); // 1秒延遲
                }
            }

            this.preloadStats.endTime = Date.now();
            const duration = (this.preloadStats.endTime - this.preloadStats.startTime) / 1000;

            logger.info(`✅ 快取預載完成，耗時 ${duration.toFixed(2)}s，成功 ${this.preloadStats.completed}/${this.preloadStats.total}`);

        } catch (error) {
            logger.error('快取預載失敗:', error);
        } finally {
            this.isPreloading = false;
        }
    }

    /**
     * 執行單個預載任務
     */
    async executeTask(task) {
        try {
            // 檢查預載條件
            if (task.condition && !await task.condition()) {
                logger.debug(`跳過預載任務: ${task.category}:${task.identifier} (條件不滿足)`);
                return;
            }

            // 檢查依賴
            if (task.dependencies.length > 0) {
                const dependenciesReady = await this.checkDependencies(task.dependencies);
                if (!dependenciesReady) {
                    logger.debug(`跳過預載任務: ${task.category}:${task.identifier} (依賴未就緒)`);
                    return;
                }
            }

            // 檢查是否已存在於快取
            const existing = await cacheManager.get(task.category, task.identifier);
            if (existing !== null) {
                logger.debug(`跳過預載任務: ${task.category}:${task.identifier} (已存在)`);
                this.preloadStats.completed++;
                return;
            }

            // 執行獲取函數
            const data = await task.fetchFunction();
            if (data !== null && data !== undefined) {
                await cacheManager.set(task.category, task.identifier, data, task.ttl);
                this.preloadStats.completed++;
                logger.debug(`✅ 預載完成: ${task.category}:${task.identifier}`);
            } else {
                this.preloadStats.failed++;
                logger.warn(`⚠️ 預載失敗: ${task.category}:${task.identifier} (無數據)`);
            }

        } catch (error) {
            this.preloadStats.failed++;
            logger.error(`❌ 預載失敗: ${task.category}:${task.identifier}`, error);
        }
    }

    /**
     * 檢查依賴是否就緒
     */
    async checkDependencies(dependencies) {
        for (const dep of dependencies) {
            const exists = await cacheManager.get(dep.category, dep.identifier);
            if (exists === null) {
                return false;
            }
        }
        return true;
    }

    /**
     * 延遲函數
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 獲取預載統計
     */
    getStats() {
        const duration = this.preloadStats.endTime && this.preloadStats.startTime ?
            (this.preloadStats.endTime - this.preloadStats.startTime) / 1000 : null;

        return {
            ...this.preloadStats,
            duration: duration ? `${duration.toFixed(2)}s` : 'N/A',
            successRate: this.preloadStats.total > 0 ?
                `${((this.preloadStats.completed / this.preloadStats.total) * 100).toFixed(2)}%` : '0%',
            isRunning: this.isPreloading,
            totalTasks: this.preloadTasks.length
        };
    }

    /**
     * 定期預載（用於維護熱門快取）
     */
    startPeriodicPreloading() {
        // 每小時執行一次部分預載
        setInterval(async () => {
            if (this.isPreloading) return;

            logger.info('🔄 開始定期預載...');

            // 只預載高優先級的任務
            const highPriorityTasks = this.preloadTasks.filter(task => task.priority >= 8);

            for (const task of highPriorityTasks) {
                try {
                    await this.executeTask(task);
                } catch (error) {
                    logger.error(`定期預載失敗: ${task.category}:${task.identifier}`, error);
                }
            }
        }, 3600000); // 每小時
    }
}

// 單例模式
const cachePreloader = new CachePreloader();

module.exports = {
    CachePreloader,
    cachePreloader
};