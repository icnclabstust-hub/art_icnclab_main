/**
 * 爬取間隔管理 API 路由
 * 提供可配置爬取間隔的 REST API 接口
 */

const express = require('express');
const router = express.Router();
const { logger } = require('../../utils/logger');
const { createAsyncWrapper } = require('../middleware/errorHandlingMiddleware');

class CrawlIntervalController {
    constructor(intervalManager) {
        this.intervalManager = intervalManager;
        this.setupRoutes();
    }

    setupRoutes() {
        const asyncWrapper = createAsyncWrapper({
            enableRetry: true,
            maxRetries: 2
        });

        // 獲取所有來源的間隔配置
        router.get('/', asyncWrapper(async (req, res) => {
            const configs = this.intervalManager.getAllSourceConfigs();

            res.json({
                success: true,
                data: {
                    sources: configs,
                    systemStats: this.intervalManager.getSystemStatistics()
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取系統統計資訊
        router.get('/statistics', asyncWrapper(async (req, res) => {
            const systemStats = this.intervalManager.getSystemStatistics();

            res.json({
                success: true,
                data: systemStats,
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取特定來源的配置
        router.get('/:category/:source', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;

            const config = this.intervalManager.getSourceConfig(category, source);

            if (!config) {
                return res.status(404).json({
                    success: false,
                    error: {
                        message: `找不到來源配置: ${category}.${source}`,
                        code: 'SOURCE_NOT_FOUND'
                    },
                    timestamp: new Date().toISOString()
                });
            }

            res.json({
                success: true,
                data: config,
                timestamp: new Date().toISOString()
            });
        }));

        // 更新特定來源的間隔
        router.put('/:category/:source/interval', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;
            const { interval, reason = 'api_update' } = req.body;

            // 驗證輸入
            if (!interval || !Number.isInteger(interval) || interval <= 0) {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: '間隔必須是正整數（毫秒）',
                        code: 'INVALID_INTERVAL',
                        provided: interval
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                const newInterval = await this.intervalManager.setInterval(
                    category,
                    source,
                    interval,
                    reason
                );

                const updatedConfig = this.intervalManager.getSourceConfig(category, source);

                logger.info('間隔已通過 API 更新', {
                    category,
                    source,
                    newInterval,
                    reason,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        category,
                        source,
                        oldInterval: interval,
                        newInterval,
                        config: updatedConfig
                    },
                    message: '間隔設定已更新',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('更新間隔失敗', {
                    category,
                    source,
                    interval,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'INTERVAL_UPDATE_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 批量更新間隔
        router.put('/batch', asyncWrapper(async (req, res) => {
            const { updates, reason = 'batch_api_update' } = req.body;

            if (!Array.isArray(updates)) {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: '更新必須是陣列格式',
                        code: 'INVALID_UPDATES_FORMAT'
                    },
                    timestamp: new Date().toISOString()
                });
            }

            const results = [];
            const errors = [];

            for (const update of updates) {
                const { category, source, interval } = update;

                if (!category || !source || !interval) {
                    errors.push({
                        update,
                        error: '缺少必要欄位 (category, source, interval)'
                    });
                    continue;
                }

                try {
                    const newInterval = await this.intervalManager.setInterval(
                        category,
                        source,
                        interval,
                        reason
                    );

                    results.push({
                        category,
                        source,
                        newInterval,
                        success: true
                    });

                } catch (error) {
                    errors.push({
                        category,
                        source,
                        interval,
                        error: error.message
                    });
                }
            }

            logger.info('批量間隔更新完成', {
                successful: results.length,
                failed: errors.length,
                reason,
                userAgent: req.get('User-Agent'),
                ip: req.ip
            });

            res.json({
                success: errors.length === 0,
                data: {
                    successful: results,
                    failed: errors,
                    summary: {
                        total: updates.length,
                        successful: results.length,
                        failed: errors.length
                    }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 啟用/停用來源
        router.post('/:category/:source/toggle', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;
            const { enabled } = req.body;

            if (typeof enabled !== 'boolean') {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: 'enabled 必須是布林值',
                        code: 'INVALID_ENABLED_VALUE',
                        provided: enabled
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                await this.intervalManager.toggleSource(category, source, enabled);

                const updatedConfig = this.intervalManager.getSourceConfig(category, source);

                logger.info('來源狀態已切換', {
                    category,
                    source,
                    enabled,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        category,
                        source,
                        enabled,
                        config: updatedConfig
                    },
                    message: `來源已${enabled ? '啟用' : '停用'}`,
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('切換來源狀態失敗', {
                    category,
                    source,
                    enabled,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'TOGGLE_SOURCE_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 獲取來源的速率限制
        router.get('/:category/:source/rate-limit', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;

            const rateLimit = this.intervalManager.getRateLimit(category, source);

            res.json({
                success: true,
                data: {
                    category,
                    source,
                    ...rateLimit
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 重置來源統計
        router.post('/:category/:source/reset-statistics', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;

            try {
                this.intervalManager.resetSourceStatistics(category, source);

                logger.info('來源統計已重置', {
                    category,
                    source,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        category,
                        source,
                        resetAt: new Date()
                    },
                    message: '統計已重置',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('重置統計失敗', {
                    category,
                    source,
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: '重置統計失敗',
                        code: 'RESET_STATISTICS_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 匯出配置
        router.get('/export', asyncWrapper(async (req, res) => {
            const { format = 'json' } = req.query;

            const exportData = this.intervalManager.exportConfiguration();

            if (format === 'json') {
                res.json({
                    success: true,
                    data: exportData,
                    timestamp: new Date().toISOString()
                });
            } else if (format === 'csv') {
                // CSV 格式匯出
                const csvData = this.convertToCSV(exportData.intervalConfigs);

                res.setHeader('Content-Type', 'text/csv');
                res.setHeader('Content-Disposition', 'attachment; filename=crawl-intervals.csv');
                res.send(csvData);
            } else {
                res.status(400).json({
                    success: false,
                    error: {
                        message: '不支援的匯出格式',
                        code: 'UNSUPPORTED_FORMAT',
                        supportedFormats: ['json', 'csv']
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 獲取預設配置範本
        router.get('/templates/default', asyncWrapper(async (req, res) => {
            const templates = {
                highFrequency: {
                    description: '高頻率爬取 - 適用於重要來源',
                    baseInterval: 1800000,    // 30 minutes
                    minInterval: 900000,      // 15 minutes
                    maxInterval: 7200000,     // 2 hours
                    rateLimit: 500,           // 0.5 seconds
                    burstLimit: 20,
                    priority: 'high'
                },
                mediumFrequency: {
                    description: '中頻率爬取 - 一般來源',
                    baseInterval: 7200000,    // 2 hours
                    minInterval: 3600000,     // 1 hour
                    maxInterval: 43200000,    // 12 hours
                    rateLimit: 1000,          // 1 second
                    burstLimit: 10,
                    priority: 'medium'
                },
                lowFrequency: {
                    description: '低頻率爬取 - 不重要或敏感來源',
                    baseInterval: 43200000,   // 12 hours
                    minInterval: 21600000,    // 6 hours
                    maxInterval: 604800000,   // 1 week
                    rateLimit: 3000,          // 3 seconds
                    burstLimit: 5,
                    priority: 'low'
                },
                respectful: {
                    description: '友善爬取 - 適用於學術或敏感網站',
                    baseInterval: 86400000,   // 24 hours
                    minInterval: 43200000,    // 12 hours
                    maxInterval: 2592000000,  // 30 days
                    rateLimit: 5000,          // 5 seconds
                    burstLimit: 3,
                    priority: 'low'
                }
            };

            res.json({
                success: true,
                data: {
                    templates,
                    usage: '使用這些範本快速設定不同類型的爬取頻率'
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 應用範本到來源
        router.post('/:category/:source/apply-template', asyncWrapper(async (req, res) => {
            const { category, source } = req.params;
            const { template } = req.body;

            const templates = {
                highFrequency: { baseInterval: 1800000, rateLimit: 500, burstLimit: 20 },
                mediumFrequency: { baseInterval: 7200000, rateLimit: 1000, burstLimit: 10 },
                lowFrequency: { baseInterval: 43200000, rateLimit: 3000, burstLimit: 5 },
                respectful: { baseInterval: 86400000, rateLimit: 5000, burstLimit: 3 }
            };

            if (!templates[template]) {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: '無效的範本名稱',
                        code: 'INVALID_TEMPLATE',
                        availableTemplates: Object.keys(templates)
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                const templateConfig = templates[template];

                await this.intervalManager.setInterval(
                    category,
                    source,
                    templateConfig.baseInterval,
                    `template_${template}`
                );

                const updatedConfig = this.intervalManager.getSourceConfig(category, source);

                logger.info('範本已應用到來源', {
                    category,
                    source,
                    template,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                res.json({
                    success: true,
                    data: {
                        category,
                        source,
                        appliedTemplate: template,
                        config: updatedConfig
                    },
                    message: `已應用 ${template} 範本`,
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('應用範本失敗', {
                    category,
                    source,
                    template,
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: '應用範本失敗',
                        code: 'APPLY_TEMPLATE_FAILED'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 健康檢查端點
        router.get('/health', asyncWrapper(async (req, res) => {
            const systemStats = this.intervalManager.getSystemStatistics();
            const isHealthy = systemStats.averagePerformanceScore > 0.5;

            res.status(isHealthy ? 200 : 503).json({
                success: true,
                data: {
                    status: isHealthy ? 'healthy' : 'degraded',
                    systemStats,
                    checks: {
                        activeSources: systemStats.activeSources > 0,
                        performanceScore: systemStats.averagePerformanceScore > 0.5,
                        errorRate: systemStats.errorRate < 0.2
                    }
                },
                timestamp: new Date().toISOString()
            });
        }));
    }

    /**
     * 轉換為 CSV 格式
     */
    convertToCSV(configs) {
        const headers = [
            'Source',
            'Category',
            'Current Interval (ms)',
            'Min Interval (ms)',
            'Max Interval (ms)',
            'Rate Limit (ms)',
            'Burst Limit',
            'Priority',
            'Enabled',
            'Adaptive Enabled',
            'Last Adjustment'
        ];

        const rows = [];

        for (const [sourceKey, config] of Object.entries(configs)) {
            const [category, source] = sourceKey.split('.');
            rows.push([
                source,
                category,
                config.currentInterval,
                config.minInterval,
                config.maxInterval,
                config.rateLimit,
                config.burstLimit,
                config.priority,
                config.enabled,
                config.adaptiveEnabled,
                config.lastAdjustment
            ]);
        }

        const csvContent = [headers, ...rows]
            .map(row => row.map(field => `"${field}"`).join(','))
            .join('\n');

        return csvContent;
    }
}

module.exports = (intervalManager) => {
    const controller = new CrawlIntervalController(intervalManager);
    return router;
};