/**
 * 可配置爬取間隔管理系統
 * 提供動態調整爬取頻率的功能，包括智能間隔調整和性能優化
 */

const EventEmitter = require('events');
const fs = require('fs').promises;
const path = require('path');
const ConfigManager = require('../config/configManager');
const { logger } = require('./logger');

class CrawlIntervalManager extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            configFile: options.configFile || './config/crawl-intervals.json',
            persistConfig: options.persistConfig !== false,
            enableAdaptive: options.enableAdaptive !== false,
            performanceWindow: options.performanceWindow || 300000, // 5 minutes
            adjustmentThreshold: options.adjustmentThreshold || 0.1,
            maxConcurrentSources: options.maxConcurrentSources || 10,
            ...options
        };

        // 配置管理器
        this.configManager = new ConfigManager();

        // 間隔配置存儲
        this.intervalConfigs = new Map();
        this.sourceStatistics = new Map();
        this.performanceHistory = [];

        // 默認間隔配置
        this.defaultIntervals = {
            museums: {
                met: {
                    baseInterval: 3600000,        // 1 hour
                    minInterval: 1800000,         // 30 minutes
                    maxInterval: 86400000,        // 24 hours
                    rateLimit: 1000,              // 1 second between requests
                    burstLimit: 10,               // Max 10 requests in burst
                    adaptiveEnabled: true,
                    priority: 'high'
                },
                louvre: {
                    baseInterval: 7200000,        // 2 hours
                    minInterval: 3600000,         // 1 hour
                    maxInterval: 172800000,       // 48 hours
                    rateLimit: 2000,              // 2 seconds between requests
                    burstLimit: 5,
                    adaptiveEnabled: true,
                    priority: 'medium'
                },
                british: {
                    baseInterval: 10800000,       // 3 hours
                    minInterval: 3600000,         // 1 hour
                    maxInterval: 259200000,       // 72 hours
                    rateLimit: 1500,              // 1.5 seconds
                    burstLimit: 8,
                    adaptiveEnabled: true,
                    priority: 'medium'
                },
                europeana: {
                    baseInterval: 14400000,       // 4 hours
                    minInterval: 7200000,         // 2 hours
                    maxInterval: 86400000,        // 24 hours
                    rateLimit: 1000,              // 1 second (API)
                    burstLimit: 100,              // Higher limit for API
                    adaptiveEnabled: true,
                    priority: 'high'
                }
            },
            academic: {
                jstor: {
                    baseInterval: 43200000,       // 12 hours
                    minInterval: 21600000,        // 6 hours
                    maxInterval: 604800000,       // 1 week
                    rateLimit: 3000,              // 3 seconds (respectful)
                    burstLimit: 3,
                    adaptiveEnabled: true,
                    priority: 'low'
                },
                academia: {
                    baseInterval: 21600000,       // 6 hours
                    minInterval: 10800000,        // 3 hours
                    maxInterval: 172800000,       // 48 hours
                    rateLimit: 2000,              // 2 seconds
                    burstLimit: 5,
                    adaptiveEnabled: true,
                    priority: 'low'
                }
            }
        };

        // 性能指標定義
        this.performanceMetrics = {
            successRate: { weight: 0.3, threshold: 0.8 },
            responseTime: { weight: 0.2, threshold: 5000 },
            errorRate: { weight: 0.25, threshold: 0.1 },
            dataQuality: { weight: 0.15, threshold: 0.7 },
            serverLoad: { weight: 0.1, threshold: 0.8 }
        };

        // 初始化
        this.initialize();

        console.log('🕰️ 可配置爬取間隔管理器初始化完成');
    }

    /**
     * 初始化管理器
     */
    async initialize() {
        try {
            // 載入配置
            await this.loadConfiguration();

            // 初始化統計
            this.initializeStatistics();

            // 啟動性能監控
            if (this.options.enableAdaptive) {
                this.startPerformanceMonitoring();
            }

            logger.info('CrawlIntervalManager 初始化成功');
            this.emit('initialized');

        } catch (error) {
            logger.error('CrawlIntervalManager 初始化失敗', error);
            throw error;
        }
    }

    /**
     * 載入配置
     */
    async loadConfiguration() {
        try {
            // 嘗試從配置文件載入
            if (this.options.persistConfig) {
                try {
                    const configData = await fs.readFile(this.options.configFile, 'utf8');
                    const savedConfig = JSON.parse(configData);

                    // 合併保存的配置和默認配置
                    this.mergeConfiguration(savedConfig);

                    logger.info('爬取間隔配置已從文件載入', {
                        file: this.options.configFile
                    });
                } catch (fileError) {
                    logger.warn('無法載入配置文件，使用默認配置', {
                        error: fileError.message
                    });
                }
            }

            // 如果沒有保存的配置，使用默認配置
            if (this.intervalConfigs.size === 0) {
                this.loadDefaultConfiguration();
            }

            // 從環境變數或配置管理器覆蓋
            await this.loadEnvironmentOverrides();

        } catch (error) {
            logger.error('載入爬取間隔配置失敗', error);
            throw error;
        }
    }

    /**
     * 載入默認配置
     */
    loadDefaultConfiguration() {
        for (const [category, sources] of Object.entries(this.defaultIntervals)) {
            for (const [source, config] of Object.entries(sources)) {
                const sourceKey = `${category}.${source}`;
                this.intervalConfigs.set(sourceKey, {
                    ...config,
                    category,
                    source,
                    currentInterval: config.baseInterval,
                    lastAdjustment: new Date(),
                    adjustmentHistory: [],
                    enabled: true
                });
            }
        }

        logger.info('默認爬取間隔配置已載入', {
            sourcesCount: this.intervalConfigs.size
        });
    }

    /**
     * 合併配置
     */
    mergeConfiguration(savedConfig) {
        for (const [key, config] of Object.entries(savedConfig)) {
            const defaultConfig = this.getDefaultConfigForSource(key);
            const mergedConfig = {
                ...defaultConfig,
                ...config,
                // 確保關鍵屬性存在
                currentInterval: config.currentInterval || config.baseInterval,
                lastAdjustment: new Date(config.lastAdjustment || Date.now()),
                adjustmentHistory: config.adjustmentHistory || []
            };

            this.intervalConfigs.set(key, mergedConfig);
        }
    }

    /**
     * 載入環境變數覆蓋
     */
    async loadEnvironmentOverrides() {
        // 從配置管理器獲取爬取相關設定
        const crawlConfig = this.configManager.get('crawling', {});

        if (crawlConfig.intervals) {
            for (const [sourceKey, override] of Object.entries(crawlConfig.intervals)) {
                if (this.intervalConfigs.has(sourceKey)) {
                    const existing = this.intervalConfigs.get(sourceKey);
                    this.intervalConfigs.set(sourceKey, {
                        ...existing,
                        ...override
                    });
                    logger.info('環境變數覆蓋爬取間隔', { source: sourceKey, override });
                }
            }
        }
    }

    /**
     * 獲取來源的默認配置
     */
    getDefaultConfigForSource(sourceKey) {
        const [category, source] = sourceKey.split('.');
        return this.defaultIntervals[category]?.[source] || {};
    }

    /**
     * 初始化統計
     */
    initializeStatistics() {
        for (const sourceKey of this.intervalConfigs.keys()) {
            this.sourceStatistics.set(sourceKey, {
                totalRequests: 0,
                successfulRequests: 0,
                failedRequests: 0,
                averageResponseTime: 0,
                totalResponseTime: 0,
                lastSuccessTime: null,
                lastFailureTime: null,
                consecutiveFailures: 0,
                dataQualityScore: 1.0,
                performanceScore: 1.0,
                lastUpdated: new Date()
            });
        }
    }

    /**
     * 開始性能監控
     */
    startPerformanceMonitoring() {
        setInterval(() => {
            this.analyzePerformanceAndAdjust();
        }, this.options.performanceWindow);

        logger.info('爬取間隔性能監控已啟動', {
            window: this.options.performanceWindow
        });
    }

    /**
     * 獲取來源的當前間隔
     */
    getInterval(category, source) {
        const sourceKey = `${category}.${source}`;
        const config = this.intervalConfigs.get(sourceKey);

        if (!config) {
            logger.warn('未找到來源間隔配置', { category, source });
            return 3600000; // 默認 1 小時
        }

        return config.enabled ? config.currentInterval : null;
    }

    /**
     * 設置來源間隔
     */
    async setInterval(category, source, interval, reason = 'manual') {
        const sourceKey = `${category}.${source}`;
        const config = this.intervalConfigs.get(sourceKey);

        if (!config) {
            throw new Error(`找不到來源配置: ${sourceKey}`);
        }

        // 驗證間隔範圍
        const clampedInterval = Math.max(
            config.minInterval,
            Math.min(config.maxInterval, interval)
        );

        if (clampedInterval !== interval) {
            logger.warn('間隔已調整到允許範圍', {
                source: sourceKey,
                requested: interval,
                clamped: clampedInterval,
                min: config.minInterval,
                max: config.maxInterval
            });
        }

        // 更新配置
        const oldInterval = config.currentInterval;
        config.currentInterval = clampedInterval;
        config.lastAdjustment = new Date();
        config.adjustmentHistory.push({
            timestamp: new Date(),
            oldInterval,
            newInterval: clampedInterval,
            reason
        });

        // 限制歷史記錄長度
        if (config.adjustmentHistory.length > 50) {
            config.adjustmentHistory = config.adjustmentHistory.slice(-50);
        }

        // 保存配置
        if (this.options.persistConfig) {
            await this.saveConfiguration();
        }

        logger.info('爬取間隔已更新', {
            source: sourceKey,
            oldInterval,
            newInterval: clampedInterval,
            reason
        });

        this.emit('intervalChanged', {
            source: sourceKey,
            category,
            sourceName: source,
            oldInterval,
            newInterval: clampedInterval,
            reason
        });

        return clampedInterval;
    }

    /**
     * 獲取來源的速率限制
     */
    getRateLimit(category, source) {
        const sourceKey = `${category}.${source}`;
        const config = this.intervalConfigs.get(sourceKey);

        return config ? {
            rateLimit: config.rateLimit,
            burstLimit: config.burstLimit
        } : {
            rateLimit: 2000,
            burstLimit: 5
        };
    }

    /**
     * 更新來源統計
     */
    updateStatistics(category, source, stats) {
        const sourceKey = `${category}.${source}`;
        const currentStats = this.sourceStatistics.get(sourceKey);

        if (!currentStats) {
            logger.warn('未找到來源統計', { source: sourceKey });
            return;
        }

        // 更新統計資料
        currentStats.totalRequests++;

        if (stats.success) {
            currentStats.successfulRequests++;
            currentStats.lastSuccessTime = new Date();
            currentStats.consecutiveFailures = 0;
        } else {
            currentStats.failedRequests++;
            currentStats.lastFailureTime = new Date();
            currentStats.consecutiveFailures++;
        }

        // 更新響應時間
        if (stats.responseTime) {
            currentStats.totalResponseTime += stats.responseTime;
            currentStats.averageResponseTime =
                currentStats.totalResponseTime / currentStats.totalRequests;
        }

        // 更新數據品質分數
        if (stats.dataQuality !== undefined) {
            // 使用移動平均更新品質分數
            currentStats.dataQualityScore =
                currentStats.dataQualityScore * 0.8 + stats.dataQuality * 0.2;
        }

        currentStats.lastUpdated = new Date();

        // 計算綜合性能分數
        this.calculatePerformanceScore(sourceKey);

        // 記錄到性能歷史
        this.recordPerformanceHistory(sourceKey, stats);

        logger.debug('來源統計已更新', {
            source: sourceKey,
            stats: {
                total: currentStats.totalRequests,
                successful: currentStats.successfulRequests,
                failed: currentStats.failedRequests,
                avgResponseTime: Math.round(currentStats.averageResponseTime),
                performanceScore: Math.round(currentStats.performanceScore * 100) / 100
            }
        });
    }

    /**
     * 計算性能分數
     */
    calculatePerformanceScore(sourceKey) {
        const stats = this.sourceStatistics.get(sourceKey);
        if (!stats) return;

        let score = 0;
        let totalWeight = 0;

        // 成功率
        const successRate = stats.totalRequests > 0 ?
            stats.successfulRequests / stats.totalRequests : 0;
        const successScore = Math.min(successRate / this.performanceMetrics.successRate.threshold, 1);
        score += successScore * this.performanceMetrics.successRate.weight;
        totalWeight += this.performanceMetrics.successRate.weight;

        // 響應時間
        if (stats.averageResponseTime > 0) {
            const responseScore = Math.max(
                1 - (stats.averageResponseTime / this.performanceMetrics.responseTime.threshold),
                0
            );
            score += responseScore * this.performanceMetrics.responseTime.weight;
            totalWeight += this.performanceMetrics.responseTime.weight;
        }

        // 錯誤率
        const errorRate = stats.totalRequests > 0 ?
            stats.failedRequests / stats.totalRequests : 0;
        const errorScore = Math.max(
            1 - (errorRate / this.performanceMetrics.errorRate.threshold),
            0
        );
        score += errorScore * this.performanceMetrics.errorRate.weight;
        totalWeight += this.performanceMetrics.errorRate.weight;

        // 數據品質
        const qualityScore = stats.dataQualityScore / this.performanceMetrics.dataQuality.threshold;
        score += Math.min(qualityScore, 1) * this.performanceMetrics.dataQuality.weight;
        totalWeight += this.performanceMetrics.dataQuality.weight;

        // 正規化分數
        stats.performanceScore = totalWeight > 0 ? score / totalWeight : 0;
    }

    /**
     * 記錄性能歷史
     */
    recordPerformanceHistory(sourceKey, stats) {
        this.performanceHistory.push({
            timestamp: new Date(),
            source: sourceKey,
            ...stats
        });

        // 限制歷史記錄長度
        if (this.performanceHistory.length > 10000) {
            this.performanceHistory = this.performanceHistory.slice(-5000);
        }
    }

    /**
     * 分析性能並調整間隔
     */
    async analyzePerformanceAndAdjust() {
        for (const [sourceKey, config] of this.intervalConfigs) {
            if (!config.adaptiveEnabled || !config.enabled) {
                continue;
            }

            const stats = this.sourceStatistics.get(sourceKey);
            if (!stats || stats.totalRequests < 10) {
                continue; // 樣本不足
            }

            try {
                await this.adjustIntervalBasedOnPerformance(sourceKey, config, stats);
            } catch (error) {
                logger.error('自動調整間隔失敗', {
                    source: sourceKey,
                    error: error.message
                });
            }
        }
    }

    /**
     * 基於性能調整間隔
     */
    async adjustIntervalBasedOnPerformance(sourceKey, config, stats) {
        const currentInterval = config.currentInterval;
        let newInterval = currentInterval;
        let adjustmentReason = '';

        // 基於性能分數調整
        if (stats.performanceScore > 0.9 && config.priority === 'high') {
            // 性能很好，可以增加頻率
            newInterval = Math.max(
                config.minInterval,
                currentInterval * 0.9
            );
            adjustmentReason = 'high_performance';
        } else if (stats.performanceScore < 0.5) {
            // 性能不佳，減少頻率
            newInterval = Math.min(
                config.maxInterval,
                currentInterval * 1.5
            );
            adjustmentReason = 'low_performance';
        } else if (stats.consecutiveFailures >= 3) {
            // 連續失敗，大幅減少頻率
            newInterval = Math.min(
                config.maxInterval,
                currentInterval * 2
            );
            adjustmentReason = 'consecutive_failures';
        }

        // 檢查是否需要調整
        const changeRatio = Math.abs(newInterval - currentInterval) / currentInterval;
        if (changeRatio > this.options.adjustmentThreshold) {
            await this.setInterval(
                config.category,
                config.source,
                newInterval,
                `adaptive_${adjustmentReason}`
            );
        }
    }

    /**
     * 啟用/停用來源
     */
    async toggleSource(category, source, enabled) {
        const sourceKey = `${category}.${source}`;
        const config = this.intervalConfigs.get(sourceKey);

        if (!config) {
            throw new Error(`找不到來源配置: ${sourceKey}`);
        }

        config.enabled = enabled;

        if (this.options.persistConfig) {
            await this.saveConfiguration();
        }

        logger.info('來源狀態已更新', {
            source: sourceKey,
            enabled
        });

        this.emit('sourceToggled', {
            source: sourceKey,
            category,
            sourceName: source,
            enabled
        });
    }

    /**
     * 獲取來源配置
     */
    getSourceConfig(category, source) {
        const sourceKey = `${category}.${source}`;
        const config = this.intervalConfigs.get(sourceKey);
        const stats = this.sourceStatistics.get(sourceKey);

        if (!config) {
            return null;
        }

        return {
            ...config,
            statistics: stats ? {
                totalRequests: stats.totalRequests,
                successRate: stats.totalRequests > 0 ?
                    (stats.successfulRequests / stats.totalRequests) : 0,
                averageResponseTime: Math.round(stats.averageResponseTime),
                performanceScore: Math.round(stats.performanceScore * 100) / 100,
                lastSuccess: stats.lastSuccessTime,
                lastFailure: stats.lastFailureTime,
                consecutiveFailures: stats.consecutiveFailures
            } : null
        };
    }

    /**
     * 獲取所有來源配置
     */
    getAllSourceConfigs() {
        const configs = {};

        for (const [sourceKey] of this.intervalConfigs) {
            const [category, source] = sourceKey.split('.');
            if (!configs[category]) {
                configs[category] = {};
            }
            configs[category][source] = this.getSourceConfig(category, source);
        }

        return configs;
    }

    /**
     * 獲取系統統計
     */
    getSystemStatistics() {
        let totalRequests = 0;
        let totalSuccessful = 0;
        let totalFailed = 0;
        let totalResponseTime = 0;
        let activeSourcesCount = 0;
        let avgPerformanceScore = 0;

        for (const [sourceKey, stats] of this.sourceStatistics) {
            const config = this.intervalConfigs.get(sourceKey);

            totalRequests += stats.totalRequests;
            totalSuccessful += stats.successfulRequests;
            totalFailed += stats.failedRequests;
            totalResponseTime += stats.averageResponseTime;

            if (config && config.enabled) {
                activeSourcesCount++;
                avgPerformanceScore += stats.performanceScore;
            }
        }

        return {
            totalSources: this.intervalConfigs.size,
            activeSources: activeSourcesCount,
            totalRequests,
            successRate: totalRequests > 0 ? (totalSuccessful / totalRequests) : 0,
            errorRate: totalRequests > 0 ? (totalFailed / totalRequests) : 0,
            averageResponseTime: Math.round(totalResponseTime / Math.max(this.intervalConfigs.size, 1)),
            averagePerformanceScore: activeSourcesCount > 0 ?
                Math.round((avgPerformanceScore / activeSourcesCount) * 100) / 100 : 0,
            performanceHistorySize: this.performanceHistory.length,
            lastUpdate: new Date()
        };
    }

    /**
     * 保存配置到文件
     */
    async saveConfiguration() {
        if (!this.options.persistConfig) {
            return;
        }

        try {
            const configToSave = {};

            for (const [sourceKey, config] of this.intervalConfigs) {
                configToSave[sourceKey] = {
                    ...config,
                    // 不保存統計資料到配置文件
                    adjustmentHistory: config.adjustmentHistory.slice(-10) // 只保存最近10次調整
                };
            }

            // 確保目錄存在
            await fs.mkdir(path.dirname(this.options.configFile), { recursive: true });

            // 寫入文件
            await fs.writeFile(
                this.options.configFile,
                JSON.stringify(configToSave, null, 2),
                'utf8'
            );

            logger.info('爬取間隔配置已保存', {
                file: this.options.configFile,
                sourcesCount: Object.keys(configToSave).length
            });

        } catch (error) {
            logger.error('保存爬取間隔配置失敗', {
                file: this.options.configFile,
                error: error.message
            });
            throw error;
        }
    }

    /**
     * 重置來源統計
     */
    resetSourceStatistics(category, source) {
        const sourceKey = `${category}.${source}`;

        if (this.sourceStatistics.has(sourceKey)) {
            this.sourceStatistics.set(sourceKey, {
                totalRequests: 0,
                successfulRequests: 0,
                failedRequests: 0,
                averageResponseTime: 0,
                totalResponseTime: 0,
                lastSuccessTime: null,
                lastFailureTime: null,
                consecutiveFailures: 0,
                dataQualityScore: 1.0,
                performanceScore: 1.0,
                lastUpdated: new Date()
            });

            logger.info('來源統計已重置', { source: sourceKey });
            this.emit('statisticsReset', { source: sourceKey });
        }
    }

    /**
     * 匯出配置
     */
    exportConfiguration() {
        return {
            intervalConfigs: Object.fromEntries(this.intervalConfigs),
            statistics: Object.fromEntries(this.sourceStatistics),
            systemStats: this.getSystemStatistics(),
            performanceHistory: this.performanceHistory.slice(-100) // 最近100條記錄
        };
    }

    /**
     * 清理資源
     */
    destroy() {
        // 停止性能監控
        if (this.performanceMonitoringInterval) {
            clearInterval(this.performanceMonitoringInterval);
        }

        // 保存最終配置
        if (this.options.persistConfig) {
            this.saveConfiguration().catch(error => {
                logger.error('最終保存配置失敗', error);
            });
        }

        // 清理資源
        this.intervalConfigs.clear();
        this.sourceStatistics.clear();
        this.performanceHistory = [];

        this.removeAllListeners();

        logger.info('CrawlIntervalManager 已清理');
    }
}

module.exports = CrawlIntervalManager;