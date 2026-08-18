/**
 * 自動化排程系統測試
 * 測試 Cron 排程系統的各項功能和 API 端點
 */

const request = require('supertest');
const CronScheduler = require('../src/utils/cronScheduler');
const cron = require('node-cron');

describe('自動化排程系統測試', () => {
    let cronScheduler;
    let testScheduleId;

    beforeEach(() => {
        // 建立測試用的排程器實例
        cronScheduler = new CronScheduler({
            timezone: 'Asia/Taipei',
            enablePersistence: false,
            maxConcurrentCronJobs: 10,
            healthCheckInterval: 60000 // 1 minute for tests
        });
    });

    afterEach(async () => {
        // 清理測試資源
        if (cronScheduler) {
            await cronScheduler.shutdown();
        }
    });

    describe('CronScheduler 核心功能測試', () => {
        test('應該正確初始化排程器', async () => {
            await cronScheduler.initialize();

            expect(cronScheduler.isInitialized).toBe(true);
            expect(cronScheduler.isRunning).toBe(true);
            expect(cronScheduler.taskScheduler).toBeDefined();
        });

        test('應該建立有效的排程任務', async () => {
            await cronScheduler.initialize();

            const scheduleConfig = {
                id: 'test-schedule-1',
                name: '測試排程',
                cronExpression: '0 */5 * * * *', // 每5分鐘
                taskType: 'health_check',
                taskParams: {
                    checkDatabaseConnections: true,
                    checkExternalServices: false
                },
                priority: 'normal',
                enabled: true,
                description: '測試用健康檢查排程'
            };

            const createdSchedule = await cronScheduler.createSchedule(scheduleConfig);
            testScheduleId = createdSchedule.id;

            expect(createdSchedule).toBeDefined();
            expect(createdSchedule.id).toBe(scheduleConfig.id);
            expect(createdSchedule.name).toBe(scheduleConfig.name);
            expect(createdSchedule.status).toBe('active');
            expect(cronScheduler.scheduledJobs.has(scheduleConfig.id)).toBe(true);
            expect(cronScheduler.jobConfigs.has(scheduleConfig.id)).toBe(true);
        });

        test('應該驗證 cron 表達式', async () => {
            await cronScheduler.initialize();

            const validCron = '0 0 * * *'; // 每天午夜
            const invalidCron = 'invalid cron';

            expect(cron.validate(validCron)).toBe(true);
            expect(cron.validate(invalidCron)).toBe(false);
        });

        test('應該拒絕無效的排程配置', async () => {
            await cronScheduler.initialize();

            const invalidConfig = {
                id: 'test-invalid',
                name: '無效排程',
                // 缺少 cronExpression 和 taskType
                priority: 'normal'
            };

            await expect(cronScheduler.createSchedule(invalidConfig))
                .rejects
                .toThrow();
        });

        test('應該正確啟用和停用排程', async () => {
            await cronScheduler.initialize();

            const scheduleConfig = {
                id: 'test-enable-disable',
                name: '啟用停用測試',
                cronExpression: '0 * * * *',
                taskType: 'health_check',
                enabled: true
            };

            await cronScheduler.createSchedule(scheduleConfig);

            // 停用排程
            await cronScheduler.disableSchedule(scheduleConfig.id);
            const disabledConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);
            expect(disabledConfig.enabled).toBe(false);
            expect(disabledConfig.status).toBe('inactive');

            // 啟用排程
            await cronScheduler.enableSchedule(scheduleConfig.id);
            const enabledConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);
            expect(enabledConfig.enabled).toBe(true);
            expect(enabledConfig.status).toBe('active');
        });

        test('應該正確刪除排程', async () => {
            await cronScheduler.initialize();

            const scheduleConfig = {
                id: 'test-delete',
                name: '刪除測試',
                cronExpression: '0 * * * *',
                taskType: 'health_check'
            };

            await cronScheduler.createSchedule(scheduleConfig);
            expect(cronScheduler.scheduledJobs.has(scheduleConfig.id)).toBe(true);

            await cronScheduler.deleteSchedule(scheduleConfig.id);
            expect(cronScheduler.scheduledJobs.has(scheduleConfig.id)).toBe(false);
            expect(cronScheduler.jobConfigs.has(scheduleConfig.id)).toBe(false);
            expect(cronScheduler.jobStats.has(scheduleConfig.id)).toBe(false);
        });
    });

    describe('任務類型執行測試', () => {
        beforeEach(async () => {
            await cronScheduler.initialize();
        });

        test('應該執行健康檢查任務', async () => {
            const healthCheckParams = {
                checkDatabaseConnections: true,
                checkExternalServices: true,
                checkDiskSpace: true
            };

            const result = await cronScheduler.executeHealthCheckTask(healthCheckParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('health_check');
            expect(result.timestamp).toBeDefined();
            expect(result.overall).toBe('healthy');
            expect(result.checks).toBeDefined();
            expect(result.checks.database).toBeDefined();
            expect(result.checks.externalServices).toBeDefined();
            expect(result.checks.diskSpace).toBeDefined();
        });

        test('應該執行網頁爬取任務', async () => {
            const crawlingParams = {
                targetUrls: ['https://example.com', 'https://test.com'],
                crawlDepth: 1,
                batchSize: 2
            };

            const result = await cronScheduler.executeWebCrawlingTask(crawlingParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('web_crawling');
            expect(result.scheduledTasks).toBe(2);
            expect(result.results).toHaveLength(2);
        });

        test('應該執行資料清理任務', async () => {
            const cleanupParams = {
                cleanupType: 'expired_data',
                retentionDays: 30,
                dryRun: true
            };

            const result = await cronScheduler.executeDataCleanupTask(cleanupParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('data_cleanup');
            expect(result.cleanupType).toBe('expired_data');
            expect(result.dryRun).toBe(true);
            expect(result.cutoffDate).toBeDefined();
        });

        test('應該執行備份任務', async () => {
            const backupParams = {
                backupType: 'incremental',
                includeImages: true,
                compressionLevel: 6
            };

            const result = await cronScheduler.executeBackupTask(backupParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('backup');
            expect(result.backupType).toBe('incremental');
            expect(result.includeImages).toBe(true);
            expect(result.compressionLevel).toBe(6);
            expect(result.timestamp).toBeDefined();
            expect(typeof result.sizeBytes).toBe('number');
        });

        test('應該執行分析任務', async () => {
            const analyticsParams = {
                analysisType: 'usage_stats',
                timeRange: '24h'
            };

            const result = await cronScheduler.executeAnalyticsTask(analyticsParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('analytics');
            expect(result.analysisType).toBe('usage_stats');
            expect(result.timeRange).toBe('24h');
            expect(result.metrics).toBeDefined();
            expect(typeof result.metrics.totalRequests).toBe('number');
        });

        test('應該執行快取清理任務', async () => {
            const cacheParams = {
                cacheTypes: ['redis', 'memory'],
                maxAge: 3600000
            };

            const result = await cronScheduler.executeCacheCleanupTask(cacheParams);

            expect(result).toBeDefined();
            expect(result.taskType).toBe('cache_cleanup');
            expect(result.cacheTypes).toEqual(['redis', 'memory']);
            expect(result.results).toBeDefined();
            expect(result.results.redis).toBeDefined();
            expect(result.results.memory).toBeDefined();
        });
    });

    describe('統計和監控測試', () => {
        beforeEach(async () => {
            await cronScheduler.initialize();
        });

        test('應該生成正確的統計資訊', () => {
            const stats = cronScheduler.getScheduleStats();

            expect(stats).toBeDefined();
            expect(typeof stats.totalSchedules).toBe('number');
            expect(typeof stats.activeSchedules).toBe('number');
            expect(typeof stats.inactiveSchedules).toBe('number');
            expect(typeof stats.totalExecutions).toBe('number');
            expect(stats.schedulesByType).toBeDefined();
            expect(stats.jobStats).toBeDefined();
        });

        test('應該生成詳細的狀態報告', () => {
            const detailedStatus = cronScheduler.getDetailedStatus();

            expect(detailedStatus).toBeDefined();
            expect(detailedStatus.system).toBeDefined();
            expect(detailedStatus.system.isInitialized).toBe(true);
            expect(detailedStatus.system.isRunning).toBe(true);
            expect(detailedStatus.schedules).toBeDefined();
            expect(detailedStatus.statistics).toBeDefined();
            expect(detailedStatus.taskScheduler).toBeDefined();
            expect(detailedStatus.errorHandler).toBeDefined();
        });

        test('應該記錄任務執行歷史', async () => {
            const scheduleConfig = {
                id: 'test-history',
                name: '歷史記錄測試',
                cronExpression: '* * * * * *', // 每秒 (僅測試用)
                taskType: 'health_check',
                enabled: false // 手動執行
            };

            await cronScheduler.createSchedule(scheduleConfig);

            // 手動執行任務
            const jobConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);
            await cronScheduler.executeScheduledTask(jobConfig);

            expect(cronScheduler.jobHistory.length).toBeGreaterThan(0);
            const lastExecution = cronScheduler.jobHistory[cronScheduler.jobHistory.length - 1];
            expect(lastExecution.jobId).toBe(scheduleConfig.id);
            expect(lastExecution.status).toBe('success');
        });
    });

    describe('錯誤處理和恢復測試', () => {
        beforeEach(async () => {
            await cronScheduler.initialize();
        });

        test('應該處理任務執行超時', async () => {
            const mockTask = () => new Promise(resolve => {
                setTimeout(resolve, 2000); // 2秒任務
            });

            const timeout = 1000; // 1秒超時

            await expect(cronScheduler.executeWithTimeout(mockTask, timeout))
                .rejects
                .toThrow('任務執行超時');
        });

        test('應該處理任務執行錯誤', async () => {
            const scheduleConfig = {
                id: 'test-error-handling',
                name: '錯誤處理測試',
                cronExpression: '* * * * * *',
                taskType: 'invalid_task_type', // 無效任務類型
                enabled: false
            };

            await cronScheduler.createSchedule(scheduleConfig);
            const jobConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);

            // 執行應該失敗
            await cronScheduler.executeScheduledTask(jobConfig);

            // 檢查錯誤統計
            const stats = cronScheduler.jobStats.get(scheduleConfig.id);
            expect(stats.failedExecutions).toBe(1);
            expect(stats.successfulExecutions).toBe(0);
        });

        test('應該在高錯誤率時自動停用排程', async () => {
            const scheduleConfig = {
                id: 'test-auto-disable',
                name: '自動停用測試',
                cronExpression: '* * * * * *',
                taskType: 'invalid_task_type',
                enabled: false
            };

            await cronScheduler.createSchedule(scheduleConfig);
            const jobConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);

            // 模擬多次失敗執行
            for (let i = 0; i < 12; i++) {
                await cronScheduler.executeScheduledTask(jobConfig);
            }

            // 檢查是否被自動停用
            const updatedConfig = cronScheduler.jobConfigs.get(scheduleConfig.id);
            expect(updatedConfig.enabled).toBe(false);
        });
    });

    describe('系統關機測試', () => {
        test('應該正確關閉排程系統', async () => {
            await cronScheduler.initialize();

            // 建立一些排程
            await cronScheduler.createSchedule({
                id: 'test-shutdown-1',
                name: '關機測試1',
                cronExpression: '0 * * * *',
                taskType: 'health_check'
            });

            await cronScheduler.createSchedule({
                id: 'test-shutdown-2',
                name: '關機測試2',
                cronExpression: '0 * * * *',
                taskType: 'backup'
            });

            expect(cronScheduler.scheduledJobs.size).toBe(6); // 4個預設 + 2個測試

            await cronScheduler.shutdown();

            expect(cronScheduler.isRunning).toBe(false);
        });
    });
});

describe('排程 API 端點測試', () => {
    // 注意：這些測試需要完整的應用程序運行
    // 如果有完整的應用程序可用，可以使用 supertest 進行測試

    const mockScheduleConfig = {
        id: 'api-test-schedule',
        name: 'API 測試排程',
        cronExpression: '0 * * * *',
        taskType: 'health_check',
        taskParams: {
            checkDatabaseConnections: true
        },
        priority: 'normal',
        enabled: true,
        description: 'API 測試用排程'
    };

    test('驗證 cron 表達式端點', () => {
        const validExpressions = [
            '* * * * *',        // 每分鐘
            '0 * * * *',        // 每小時
            '0 0 * * *',        // 每天
            '0 0 * * 0',        // 每週
            '0 0 1 * *',        // 每月
            '0 0 1 1 *'         // 每年
        ];

        const invalidExpressions = [
            'invalid',
            '60 * * * *',       // 超出分鐘範圍
            '* 24 * * *',       // 超出小時範圍
            '* * 32 * *',       // 超出日期範圍
            '* * * 13 *'        // 超出月份範圍
        ];

        validExpressions.forEach(expr => {
            expect(cron.validate(expr)).toBe(true);
        });

        invalidExpressions.forEach(expr => {
            expect(cron.validate(expr)).toBe(false);
        });
    });

    // 如果應用程序可用，可以加入實際的 HTTP 測試
    /*
    let app;

    beforeAll(() => {
        app = require('../src/app');
    });

    test('GET /api/v1/scheduler/status 應該返回系統狀態', async () => {
        const response = await request(app)
            .get('/api/v1/scheduler/status')
            .expect(200);

        expect(response.body.success).toBe(true);
        expect(response.body.data).toBeDefined();
        expect(response.body.data.system).toBeDefined();
    });

    test('POST /api/v1/scheduler/schedules 應該建立新排程', async () => {
        const response = await request(app)
            .post('/api/v1/scheduler/schedules')
            .send(mockScheduleConfig)
            .expect(201);

        expect(response.body.success).toBe(true);
        expect(response.body.data.id).toBe(mockScheduleConfig.id);
        expect(response.body.data.name).toBe(mockScheduleConfig.name);
    });
    */
});