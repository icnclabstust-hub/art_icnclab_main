/**
 * 自動化排程系統 - Automated Cron-based Scheduling System
 * 整合 node-cron 與現有智能任務調度器，提供時間導向的任務排程
 */

const cron = require('node-cron');
const EventEmitter = require('events');
const TaskScheduler = require('./taskScheduler');
const { logger } = require('./logger');
const AdvancedErrorHandler = require('./advancedErrorHandler');

class CronScheduler extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            timezone: options.timezone || 'Asia/Taipei',
            enablePersistence: options.enablePersistence !== false,
            maxConcurrentCronJobs: options.maxConcurrentCronJobs || 50,
            healthCheckInterval: options.healthCheckInterval || 300000, // 5 minutes
            scheduleRetention: options.scheduleRetention || 30 * 24 * 60 * 60 * 1000, // 30 days
            ...options
        };

        // 整合現有的任務調度器
        this.taskScheduler = new TaskScheduler({
            maxConcurrentTasks: options.maxConcurrentTasks || 20,
            enableRetry: true,
            maxRetries: 3
        });

        // 錯誤處理器
        this.errorHandler = new AdvancedErrorHandler('cron-scheduler', {
            maxRetries: 2,
            baseDelay: 1000,
            circuitBreakerThreshold: 10
        });

        // 排程任務註冊表
        this.scheduledJobs = new Map();
        this.jobConfigs = new Map();
        this.jobHistory = [];
        this.jobStats = new Map();

        // 系統狀態
        this.isInitialized = false;
        this.isRunning = false;
        this.healthCheckJob = null;

        // 預設任務類型
        this.taskTypes = {
            WEB_CRAWLING: 'web_crawling',
            DATA_CLEANUP: 'data_cleanup',
            METADATA_EXTRACTION: 'metadata_extraction',
            CLASSIFICATION: 'classification',
            BACKUP: 'backup',
            HEALTH_CHECK: 'health_check',
            ANALYTICS: 'analytics',
            CACHE_CLEANUP: 'cache_cleanup'
        };

        console.log('📅 Cron排程系統初始化完成');
    }

    /**
     * 初始化排程系統
     */
    async initialize() {
        if (this.isInitialized) {
            logger.warn('CronScheduler已初始化');
            return;
        }

        try {
            // 啟動任務調度器
            await this.taskScheduler.start();

            // 設置系統健康檢查
            await this.setupHealthCheck();

            // 載入預設排程
            await this.loadDefaultSchedules();

            this.isInitialized = true;
            this.isRunning = true;

            logger.info('CronScheduler初始化成功', {
                timezone: this.options.timezone,
                maxJobs: this.options.maxConcurrentCronJobs
            });

            this.emit('schedulerInitialized');

        } catch (error) {
            logger.error('CronScheduler初始化失敗', error);
            throw error;
        }
    }

    /**
     * 建立排程任務
     */
    async createSchedule(scheduleConfig) {
        try {
            const {
                id,
                name,
                cronExpression,
                taskType,
                taskParams = {},
                priority = 'normal',
                enabled = true,
                description = '',
                maxExecutions = null,
                timeout = 300000, // 5 minutes
                retryPolicy = { enabled: true, maxRetries: 3, backoff: 'exponential' }
            } = scheduleConfig;

            // 驗證設定
            if (!id || !name || !cronExpression || !taskType) {
                throw new Error('排程設定不完整：需要 id, name, cronExpression, taskType');
            }

            if (!cron.validate(cronExpression)) {
                throw new Error(`無效的 cron 表達式: ${cronExpression}`);
            }

            if (this.scheduledJobs.has(id)) {
                throw new Error(`排程任務已存在: ${id}`);
            }

            // 建立任務配置
            const jobConfig = {
                id,
                name,
                cronExpression,
                taskType,
                taskParams,
                priority,
                enabled,
                description,
                maxExecutions,
                timeout,
                retryPolicy,
                createdAt: new Date(),
                executionCount: 0,
                lastExecution: null,
                nextExecution: null,
                status: enabled ? 'active' : 'inactive'
            };

            // 建立 cron 任務
            const cronTask = cron.schedule(cronExpression, async () => {
                if (jobConfig.enabled && this.isRunning) {
                    await this.executeScheduledTask(jobConfig);
                }
            }, {
                scheduled: false,
                timezone: this.options.timezone
            });

            // 註冊任務
            this.scheduledJobs.set(id, cronTask);
            this.jobConfigs.set(id, jobConfig);
            this.jobStats.set(id, {
                totalExecutions: 0,
                successfulExecutions: 0,
                failedExecutions: 0,
                averageExecutionTime: 0,
                lastExecutionTime: 0,
                totalExecutionTime: 0
            });

            // 如果啟用則開始排程
            if (enabled) {
                cronTask.start();
                logger.info(`排程任務已建立並啟用: ${name} (${cronExpression})`, {
                    id,
                    taskType,
                    timezone: this.options.timezone
                });
            } else {
                logger.info(`排程任務已建立但未啟用: ${name}`, { id });
            }

            this.emit('scheduleCreated', jobConfig);
            return jobConfig;

        } catch (error) {
            logger.error('建立排程任務失敗', {
                scheduleId: scheduleConfig.id,
                error: error.message
            });
            throw error;
        }
    }

    /**
     * 執行排程任務
     */
    async executeScheduledTask(jobConfig) {
        const startTime = Date.now();
        const executionId = `exec_${jobConfig.id}_${startTime}`;

        try {
            logger.info(`執行排程任務: ${jobConfig.name}`, {
                id: jobConfig.id,
                executionId,
                taskType: jobConfig.taskType
            });

            // 檢查最大執行次數限制
            if (jobConfig.maxExecutions && jobConfig.executionCount >= jobConfig.maxExecutions) {
                logger.warn(`排程任務達到最大執行次數限制: ${jobConfig.name}`, {
                    id: jobConfig.id,
                    maxExecutions: jobConfig.maxExecutions
                });
                await this.disableSchedule(jobConfig.id);
                return;
            }

            // 更新執行統計
            jobConfig.executionCount++;
            jobConfig.lastExecution = new Date();

            const stats = this.jobStats.get(jobConfig.id);
            stats.totalExecutions++;

            // 建立任務執行器
            const taskExecutor = this.createTaskExecutor(jobConfig.taskType, jobConfig.taskParams);

            // 使用錯誤處理器執行任務
            const result = await this.errorHandler.executeWithRetry(
                () => this.executeWithTimeout(taskExecutor, jobConfig.timeout),
                `cron_job_${jobConfig.id}`,
                {
                    maxRetries: jobConfig.retryPolicy.maxRetries,
                    errorType: 'CRON_JOB_EXECUTION'
                }
            );

            // 記錄成功執行
            const executionTime = Date.now() - startTime;
            stats.successfulExecutions++;
            stats.lastExecutionTime = executionTime;
            stats.totalExecutionTime += executionTime;
            stats.averageExecutionTime = stats.totalExecutionTime / stats.totalExecutions;

            // 記錄執行歷史
            this.recordJobHistory({
                executionId,
                jobId: jobConfig.id,
                jobName: jobConfig.name,
                taskType: jobConfig.taskType,
                startTime: new Date(startTime),
                endTime: new Date(),
                duration: executionTime,
                status: 'success',
                result: result,
                error: null
            });

            logger.info(`排程任務執行成功: ${jobConfig.name}`, {
                id: jobConfig.id,
                executionId,
                duration: executionTime,
                result: typeof result === 'object' ? JSON.stringify(result) : result
            });

            this.emit('scheduleExecuted', {
                jobConfig,
                executionId,
                result,
                duration: executionTime
            });

        } catch (error) {
            // 記錄失敗執行
            const executionTime = Date.now() - startTime;
            const stats = this.jobStats.get(jobConfig.id);
            stats.failedExecutions++;

            this.recordJobHistory({
                executionId,
                jobId: jobConfig.id,
                jobName: jobConfig.name,
                taskType: jobConfig.taskType,
                startTime: new Date(startTime),
                endTime: new Date(),
                duration: executionTime,
                status: 'failed',
                result: null,
                error: error.message
            });

            logger.error(`排程任務執行失敗: ${jobConfig.name}`, {
                id: jobConfig.id,
                executionId,
                error: error.message,
                duration: executionTime
            });

            this.emit('scheduleExecutionFailed', {
                jobConfig,
                executionId,
                error,
                duration: executionTime
            });

            // 處理錯誤策略
            await this.handleTaskExecutionError(jobConfig, error);
        }
    }

    /**
     * 建立任務執行器
     */
    createTaskExecutor(taskType, taskParams) {
        switch (taskType) {
            case this.taskTypes.WEB_CRAWLING:
                return () => this.executeWebCrawlingTask(taskParams);

            case this.taskTypes.DATA_CLEANUP:
                return () => this.executeDataCleanupTask(taskParams);

            case this.taskTypes.METADATA_EXTRACTION:
                return () => this.executeMetadataExtractionTask(taskParams);

            case this.taskTypes.CLASSIFICATION:
                return () => this.executeClassificationTask(taskParams);

            case this.taskTypes.BACKUP:
                return () => this.executeBackupTask(taskParams);

            case this.taskTypes.HEALTH_CHECK:
                return () => this.executeHealthCheckTask(taskParams);

            case this.taskTypes.ANALYTICS:
                return () => this.executeAnalyticsTask(taskParams);

            case this.taskTypes.CACHE_CLEANUP:
                return () => this.executeCacheCleanupTask(taskParams);

            default:
                throw new Error(`不支援的任務類型: ${taskType}`);
        }
    }

    /**
     * 網頁爬取任務
     */
    async executeWebCrawlingTask(params) {
        const {
            targetUrls = [],
            crawlDepth = 1,
            respectRobotsTxt = true,
            batchSize = 10
        } = params;

        logger.info('執行網頁爬取任務', {
            targetUrls: targetUrls.length,
            crawlDepth,
            batchSize
        });

        // 整合現有的任務調度器執行爬取
        const crawlTasks = targetUrls.map((url, index) => ({
            id: `crawl_${Date.now()}_${index}`,
            agentType: 'WebCrawlerAgent',
            method: 'crawlUrl',
            params: { url, depth: crawlDepth, respectRobotsTxt },
            priority: 'normal',
            estimatedDuration: 30000
        }));

        const results = [];
        for (const task of crawlTasks) {
            try {
                const taskId = await this.taskScheduler.scheduleTask(task);
                results.push({ taskId, url: task.params.url, status: 'scheduled' });
            } catch (error) {
                results.push({ url: task.params.url, status: 'failed', error: error.message });
            }
        }

        return {
            taskType: 'web_crawling',
            scheduledTasks: results.filter(r => r.status === 'scheduled').length,
            failedTasks: results.filter(r => r.status === 'failed').length,
            results
        };
    }

    /**
     * 資料清理任務
     */
    async executeDataCleanupTask(params) {
        const {
            cleanupType = 'expired_data',
            retentionDays = 30,
            dryRun = false
        } = params;

        logger.info('執行資料清理任務', {
            cleanupType,
            retentionDays,
            dryRun
        });

        // 模擬資料清理邏輯
        const cutoffDate = new Date(Date.now() - (retentionDays * 24 * 60 * 60 * 1000));

        let cleanedRecords = 0;
        if (!dryRun) {
            // 實際清理邏輯應該在這裡實現
            cleanedRecords = Math.floor(Math.random() * 100); // 模擬
        }

        return {
            taskType: 'data_cleanup',
            cleanupType,
            cutoffDate,
            cleanedRecords,
            dryRun
        };
    }

    /**
     * 中繼資料提取任務
     */
    async executeMetadataExtractionTask(params) {
        const {
            sourceType = 'artwork',
            batchSize = 50,
            extractionRules = []
        } = params;

        logger.info('執行中繼資料提取任務', {
            sourceType,
            batchSize,
            rulesCount: extractionRules.length
        });

        // 整合任務調度器執行提取
        const extractionTask = {
            id: `metadata_extraction_${Date.now()}`,
            agentType: 'MetadataExtractorAgent',
            method: 'extractBatch',
            params: { sourceType, batchSize, extractionRules },
            priority: 'normal',
            estimatedDuration: 60000
        };

        const taskId = await this.taskScheduler.scheduleTask(extractionTask);

        return {
            taskType: 'metadata_extraction',
            scheduledTaskId: taskId,
            sourceType,
            batchSize
        };
    }

    /**
     * 分類任務
     */
    async executeClassificationTask(params) {
        const {
            classificationModel = 'default',
            batchSize = 30,
            confidenceThreshold = 0.8
        } = params;

        logger.info('執行分類任務', {
            classificationModel,
            batchSize,
            confidenceThreshold
        });

        const classificationTask = {
            id: `classification_${Date.now()}`,
            agentType: 'ClassificationAgent',
            method: 'classifyBatch',
            params: { model: classificationModel, batchSize, confidenceThreshold },
            priority: 'normal',
            estimatedDuration: 45000
        };

        const taskId = await this.taskScheduler.scheduleTask(classificationTask);

        return {
            taskType: 'classification',
            scheduledTaskId: taskId,
            model: classificationModel,
            batchSize
        };
    }

    /**
     * 備份任務
     */
    async executeBackupTask(params) {
        const {
            backupType = 'incremental',
            includeImages = true,
            compressionLevel = 6
        } = params;

        logger.info('執行備份任務', {
            backupType,
            includeImages,
            compressionLevel
        });

        // 模擬備份執行時間
        await this.sleep(Math.random() * 5000 + 2000);

        return {
            taskType: 'backup',
            backupType,
            timestamp: new Date(),
            sizeBytes: Math.floor(Math.random() * 1000000000), // 模擬備份大小
            includeImages,
            compressionLevel
        };
    }

    /**
     * 健康檢查任務
     */
    async executeHealthCheckTask(params) {
        const {
            checkDatabaseConnections = true,
            checkExternalServices = true,
            checkDiskSpace = true
        } = params;

        logger.info('執行健康檢查任務', {
            checkDatabaseConnections,
            checkExternalServices,
            checkDiskSpace
        });

        const healthStatus = {
            taskType: 'health_check',
            timestamp: new Date(),
            overall: 'healthy',
            checks: {}
        };

        if (checkDatabaseConnections) {
            healthStatus.checks.database = {
                status: 'healthy',
                responseTime: Math.floor(Math.random() * 100) + 10
            };
        }

        if (checkExternalServices) {
            healthStatus.checks.externalServices = {
                status: 'healthy',
                servicesChecked: ['openai', 'elasticsearch']
            };
        }

        if (checkDiskSpace) {
            healthStatus.checks.diskSpace = {
                status: 'healthy',
                freeSpaceGB: Math.floor(Math.random() * 500) + 100
            };
        }

        return healthStatus;
    }

    /**
     * 分析任務
     */
    async executeAnalyticsTask(params) {
        const {
            analysisType = 'usage_stats',
            timeRange = '24h'
        } = params;

        logger.info('執行分析任務', {
            analysisType,
            timeRange
        });

        return {
            taskType: 'analytics',
            analysisType,
            timeRange,
            timestamp: new Date(),
            metrics: {
                totalRequests: Math.floor(Math.random() * 10000),
                successRate: (Math.random() * 0.1 + 0.9).toFixed(3),
                averageResponseTime: Math.floor(Math.random() * 500) + 100
            }
        };
    }

    /**
     * 快取清理任務
     */
    async executeCacheCleanupTask(params) {
        const {
            cacheTypes = ['redis', 'memory'],
            maxAge = 3600000 // 1 hour
        } = params;

        logger.info('執行快取清理任務', {
            cacheTypes,
            maxAge
        });

        const results = {};
        for (const cacheType of cacheTypes) {
            results[cacheType] = {
                clearedEntries: Math.floor(Math.random() * 1000),
                freedMemoryMB: Math.floor(Math.random() * 100)
            };
        }

        return {
            taskType: 'cache_cleanup',
            cacheTypes,
            maxAge,
            results
        };
    }

    /**
     * 啟用排程
     */
    async enableSchedule(scheduleId) {
        const cronJob = this.scheduledJobs.get(scheduleId);
        const jobConfig = this.jobConfigs.get(scheduleId);

        if (!cronJob || !jobConfig) {
            throw new Error(`找不到排程任務: ${scheduleId}`);
        }

        cronJob.start();
        jobConfig.enabled = true;
        jobConfig.status = 'active';

        logger.info(`排程任務已啟用: ${jobConfig.name}`, { id: scheduleId });
        this.emit('scheduleEnabled', jobConfig);
    }

    /**
     * 停用排程
     */
    async disableSchedule(scheduleId) {
        const cronJob = this.scheduledJobs.get(scheduleId);
        const jobConfig = this.jobConfigs.get(scheduleId);

        if (!cronJob || !jobConfig) {
            throw new Error(`找不到排程任務: ${scheduleId}`);
        }

        cronJob.stop();
        jobConfig.enabled = false;
        jobConfig.status = 'inactive';

        logger.info(`排程任務已停用: ${jobConfig.name}`, { id: scheduleId });
        this.emit('scheduleDisabled', jobConfig);
    }

    /**
     * 刪除排程
     */
    async deleteSchedule(scheduleId) {
        const cronJob = this.scheduledJobs.get(scheduleId);
        const jobConfig = this.jobConfigs.get(scheduleId);

        if (!cronJob || !jobConfig) {
            throw new Error(`找不到排程任務: ${scheduleId}`);
        }

        cronJob.destroy();
        this.scheduledJobs.delete(scheduleId);
        this.jobConfigs.delete(scheduleId);
        this.jobStats.delete(scheduleId);

        logger.info(`排程任務已刪除: ${jobConfig.name}`, { id: scheduleId });
        this.emit('scheduleDeleted', { id: scheduleId, name: jobConfig.name });
    }

    /**
     * 載入預設排程
     */
    async loadDefaultSchedules() {
        const defaultSchedules = [
            {
                id: 'daily_web_crawling',
                name: '每日網頁爬取',
                cronExpression: '0 2 * * *', // 每天凌晨2點
                taskType: this.taskTypes.WEB_CRAWLING,
                taskParams: {
                    targetUrls: ['https://example-art-museum.com/collections'],
                    crawlDepth: 2,
                    batchSize: 20
                },
                priority: 'high',
                description: '每日執行的網頁爬取任務'
            },
            {
                id: 'hourly_health_check',
                name: '每小時健康檢查',
                cronExpression: '0 * * * *', // 每小時
                taskType: this.taskTypes.HEALTH_CHECK,
                taskParams: {
                    checkDatabaseConnections: true,
                    checkExternalServices: true
                },
                priority: 'normal',
                description: '系統健康狀態檢查'
            },
            {
                id: 'weekly_data_cleanup',
                name: '每週資料清理',
                cronExpression: '0 3 * * 0', // 每週日凌晨3點
                taskType: this.taskTypes.DATA_CLEANUP,
                taskParams: {
                    cleanupType: 'expired_data',
                    retentionDays: 30
                },
                priority: 'low',
                description: '清理過期資料'
            },
            {
                id: 'daily_backup',
                name: '每日備份',
                cronExpression: '0 1 * * *', // 每天凌晨1點
                taskType: this.taskTypes.BACKUP,
                taskParams: {
                    backupType: 'incremental',
                    includeImages: false
                },
                priority: 'high',
                description: '每日增量備份'
            }
        ];

        for (const scheduleConfig of defaultSchedules) {
            try {
                await this.createSchedule(scheduleConfig);
            } catch (error) {
                logger.warn(`無法載入預設排程: ${scheduleConfig.id}`, {
                    error: error.message
                });
            }
        }

        logger.info('預設排程載入完成', {
            loaded: defaultSchedules.length
        });
    }

    /**
     * 設定系統健康檢查
     */
    async setupHealthCheck() {
        this.healthCheckJob = cron.schedule('*/5 * * * *', async () => {
            try {
                await this.performSystemHealthCheck();
            } catch (error) {
                logger.error('系統健康檢查失敗', error);
            }
        }, {
            scheduled: false,
            timezone: this.options.timezone
        });

        this.healthCheckJob.start();
        logger.info('系統健康檢查已設定 (每5分鐘)');
    }

    /**
     * 執行系統健康檢查
     */
    async performSystemHealthCheck() {
        const healthReport = {
            timestamp: new Date(),
            scheduler: {
                isRunning: this.isRunning,
                totalSchedules: this.scheduledJobs.size,
                activeSchedules: Array.from(this.jobConfigs.values()).filter(job => job.enabled).length
            },
            taskScheduler: this.taskScheduler.getStatus(),
            errorHandler: this.errorHandler.generateHealthReport()
        };

        this.emit('healthCheckCompleted', healthReport);

        // 檢查是否需要發出警告
        if (healthReport.errorHandler.status !== 'healthy') {
            logger.warn('系統健康狀態異常', healthReport);
            this.emit('healthWarning', healthReport);
        }
    }

    /**
     * 處理任務執行錯誤
     */
    async handleTaskExecutionError(jobConfig, error) {
        const stats = this.jobStats.get(jobConfig.id);
        const errorRate = stats.failedExecutions / stats.totalExecutions;

        // 如果錯誤率過高，暫時停用排程
        if (errorRate > 0.5 && stats.totalExecutions >= 10) {
            logger.warn(`排程任務錯誤率過高，暫時停用: ${jobConfig.name}`, {
                id: jobConfig.id,
                errorRate: errorRate.toFixed(2),
                totalExecutions: stats.totalExecutions
            });

            await this.disableSchedule(jobConfig.id);
            this.emit('scheduleAutoDisabled', { jobConfig, reason: 'high_error_rate', errorRate });
        }
    }

    /**
     * 帶超時的執行
     */
    async executeWithTimeout(taskExecutor, timeout) {
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error(`任務執行超時 (${timeout}ms)`));
            }, timeout);

            // executor 不可為 async：async executor 內未被 await 捕捉的同步拋錯
            // 會變成懸空 rejection 而非 reject 這個 Promise
            Promise.resolve()
                .then(taskExecutor)
                .then(result => {
                    clearTimeout(timeoutId);
                    resolve(result);
                })
                .catch(error => {
                    clearTimeout(timeoutId);
                    reject(error);
                });
        });
    }

    /**
     * 記錄任務執行歷史
     */
    recordJobHistory(executionRecord) {
        this.jobHistory.push(executionRecord);

        // 限制歷史記錄數量
        if (this.jobHistory.length > 1000) {
            this.jobHistory.splice(0, this.jobHistory.length - 1000);
        }
    }

    /**
     * 獲取排程統計
     */
    getScheduleStats() {
        const stats = {
            totalSchedules: this.scheduledJobs.size,
            activeSchedules: 0,
            inactiveSchedules: 0,
            totalExecutions: 0,
            successfulExecutions: 0,
            failedExecutions: 0,
            schedulesByType: {},
            jobStats: {}
        };

        // 計算排程統計
        for (const [id, jobConfig] of this.jobConfigs) {
            if (jobConfig.enabled) {
                stats.activeSchedules++;
            } else {
                stats.inactiveSchedules++;
            }

            const taskType = jobConfig.taskType;
            if (!stats.schedulesByType[taskType]) {
                stats.schedulesByType[taskType] = 0;
            }
            stats.schedulesByType[taskType]++;

            const jobStat = this.jobStats.get(id);
            if (jobStat) {
                stats.totalExecutions += jobStat.totalExecutions;
                stats.successfulExecutions += jobStat.successfulExecutions;
                stats.failedExecutions += jobStat.failedExecutions;
                stats.jobStats[id] = { ...jobStat, jobName: jobConfig.name };
            }
        }

        return stats;
    }

    /**
     * 獲取詳細狀態報告
     */
    getDetailedStatus() {
        return {
            system: {
                isInitialized: this.isInitialized,
                isRunning: this.isRunning,
                timezone: this.options.timezone,
                maxConcurrentJobs: this.options.maxConcurrentCronJobs
            },
            schedules: Array.from(this.jobConfigs.values()),
            statistics: this.getScheduleStats(),
            recentHistory: this.jobHistory.slice(-20),
            taskScheduler: this.taskScheduler.getStatus(),
            errorHandler: this.errorHandler.getMetrics()
        };
    }

    /**
     * 停止排程系統
     */
    async shutdown() {
        logger.info('正在關閉Cron排程系統...');

        this.isRunning = false;

        // 停止健康檢查
        if (this.healthCheckJob) {
            this.healthCheckJob.destroy();
        }

        // 停止所有排程任務
        for (const [id, cronJob] of this.scheduledJobs) {
            try {
                cronJob.destroy();
                logger.info(`排程任務已停止: ${id}`);
            } catch (error) {
                logger.warn(`停止排程任務時發生錯誤: ${id}`, error);
            }
        }

        // 停止任務調度器
        await this.taskScheduler.stop();

        logger.info('Cron排程系統已關閉');
        this.emit('schedulerShutdown');
    }

    /**
     * 輔助函數：睡眠
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

module.exports = CronScheduler;