/**
 * 排程管理 API 路由
 * 提供 Cron 排程系統的 REST API 接口
 */

const express = require('express');
const router = express.Router();
const { logger } = require('../../utils/logger');
const { createAsyncWrapper } = require('../middleware/errorHandlingMiddleware');

class SchedulerController {
    constructor(cronScheduler) {
        this.cronScheduler = cronScheduler;
        this.setupRoutes();
    }

    setupRoutes() {
        const asyncWrapper = createAsyncWrapper({
            enableRetry: true,
            maxRetries: 2
        });

        // 獲取排程系統狀態
        router.get('/status', asyncWrapper(async (req, res) => {
            const status = this.cronScheduler.getDetailedStatus();
            res.json({
                success: true,
                data: status,
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取排程統計
        router.get('/stats', asyncWrapper(async (req, res) => {
            const stats = this.cronScheduler.getScheduleStats();
            res.json({
                success: true,
                data: stats,
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取所有排程列表
        router.get('/schedules', asyncWrapper(async (req, res) => {
            const { type, status, enabled } = req.query;

            const allSchedules = Array.from(this.cronScheduler.jobConfigs.values());
            let filteredSchedules = allSchedules;

            // 應用過濾器
            if (type) {
                filteredSchedules = filteredSchedules.filter(schedule =>
                    schedule.taskType === type
                );
            }

            if (status) {
                filteredSchedules = filteredSchedules.filter(schedule =>
                    schedule.status === status
                );
            }

            if (enabled !== undefined) {
                const isEnabled = enabled === 'true';
                filteredSchedules = filteredSchedules.filter(schedule =>
                    schedule.enabled === isEnabled
                );
            }

            res.json({
                success: true,
                data: {
                    schedules: filteredSchedules,
                    total: filteredSchedules.length,
                    filters: { type, status, enabled }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取特定排程詳情
        router.get('/schedules/:id', asyncWrapper(async (req, res) => {
            const { id } = req.params;

            const jobConfig = this.cronScheduler.jobConfigs.get(id);
            const jobStats = this.cronScheduler.jobStats.get(id);

            if (!jobConfig) {
                return res.status(404).json({
                    success: false,
                    error: {
                        message: '找不到指定的排程任務',
                        code: 'SCHEDULE_NOT_FOUND',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }

            // 獲取最近的執行歷史
            const recentHistory = this.cronScheduler.jobHistory
                .filter(record => record.jobId === id)
                .slice(-10)
                .sort((a, b) => b.startTime - a.startTime);

            res.json({
                success: true,
                data: {
                    config: jobConfig,
                    stats: jobStats,
                    recentHistory
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 建立新排程
        router.post('/schedules', asyncWrapper(async (req, res) => {
            const scheduleConfig = req.body;

            // 基本驗證
            if (!scheduleConfig.id || !scheduleConfig.name || !scheduleConfig.cronExpression || !scheduleConfig.taskType) {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: '排程配置不完整',
                        code: 'INVALID_SCHEDULE_CONFIG',
                        required: ['id', 'name', 'cronExpression', 'taskType'],
                        provided: Object.keys(scheduleConfig)
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                const createdSchedule = await this.cronScheduler.createSchedule(scheduleConfig);

                logger.info('通過API建立排程任務', {
                    scheduleId: createdSchedule.id,
                    name: createdSchedule.name,
                    taskType: createdSchedule.taskType
                });

                res.status(201).json({
                    success: true,
                    data: createdSchedule,
                    message: '排程任務建立成功',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('建立排程任務失敗', {
                    scheduleId: scheduleConfig.id,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_CREATION_FAILED',
                        scheduleId: scheduleConfig.id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 更新排程配置
        router.put('/schedules/:id', asyncWrapper(async (req, res) => {
            const { id } = req.params;
            const updateConfig = req.body;

            const existingConfig = this.cronScheduler.jobConfigs.get(id);
            if (!existingConfig) {
                return res.status(404).json({
                    success: false,
                    error: {
                        message: '找不到指定的排程任務',
                        code: 'SCHEDULE_NOT_FOUND',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                // 刪除現有排程
                await this.cronScheduler.deleteSchedule(id);

                // 建立新的排程配置
                const newConfig = {
                    ...existingConfig,
                    ...updateConfig,
                    id // 確保 ID 不會被更改
                };

                const updatedSchedule = await this.cronScheduler.createSchedule(newConfig);

                logger.info('排程任務更新成功', {
                    scheduleId: id,
                    changes: Object.keys(updateConfig)
                });

                res.json({
                    success: true,
                    data: updatedSchedule,
                    message: '排程任務更新成功',
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('更新排程任務失敗', {
                    scheduleId: id,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_UPDATE_FAILED',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 啟用排程
        router.post('/schedules/:id/enable', asyncWrapper(async (req, res) => {
            const { id } = req.params;

            try {
                await this.cronScheduler.enableSchedule(id);

                logger.info('排程任務已啟用', { scheduleId: id });

                res.json({
                    success: true,
                    message: '排程任務已啟用',
                    data: { scheduleId: id, enabled: true },
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('啟用排程任務失敗', {
                    scheduleId: id,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_ENABLE_FAILED',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 停用排程
        router.post('/schedules/:id/disable', asyncWrapper(async (req, res) => {
            const { id } = req.params;

            try {
                await this.cronScheduler.disableSchedule(id);

                logger.info('排程任務已停用', { scheduleId: id });

                res.json({
                    success: true,
                    message: '排程任務已停用',
                    data: { scheduleId: id, enabled: false },
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('停用排程任務失敗', {
                    scheduleId: id,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_DISABLE_FAILED',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 刪除排程
        router.delete('/schedules/:id', asyncWrapper(async (req, res) => {
            const { id } = req.params;

            try {
                await this.cronScheduler.deleteSchedule(id);

                logger.info('排程任務已刪除', { scheduleId: id });

                res.json({
                    success: true,
                    message: '排程任務已刪除',
                    data: { scheduleId: id },
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('刪除排程任務失敗', {
                    scheduleId: id,
                    error: error.message
                });

                res.status(400).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_DELETE_FAILED',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 手動觸發排程執行
        router.post('/schedules/:id/execute', asyncWrapper(async (req, res) => {
            const { id } = req.params;

            const jobConfig = this.cronScheduler.jobConfigs.get(id);
            if (!jobConfig) {
                return res.status(404).json({
                    success: false,
                    error: {
                        message: '找不到指定的排程任務',
                        code: 'SCHEDULE_NOT_FOUND',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                // 異步執行任務，不等待完成
                this.cronScheduler.executeScheduledTask(jobConfig)
                    .then(result => {
                        logger.info('手動執行排程任務成功', {
                            scheduleId: id,
                            result: typeof result === 'object' ? JSON.stringify(result) : result
                        });
                    })
                    .catch(error => {
                        logger.error('手動執行排程任務失敗', {
                            scheduleId: id,
                            error: error.message
                        });
                    });

                res.json({
                    success: true,
                    message: '排程任務執行已觸發',
                    data: {
                        scheduleId: id,
                        scheduleName: jobConfig.name,
                        taskType: jobConfig.taskType,
                        triggeredAt: new Date().toISOString()
                    },
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                logger.error('觸發排程任務執行失敗', {
                    scheduleId: id,
                    error: error.message
                });

                res.status(500).json({
                    success: false,
                    error: {
                        message: error.message,
                        code: 'SCHEDULE_EXECUTE_FAILED',
                        scheduleId: id
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 獲取任務執行歷史
        router.get('/schedules/:id/history', asyncWrapper(async (req, res) => {
            const { id } = req.params;
            const { limit = 50, offset = 0, status } = req.query;

            let history = this.cronScheduler.jobHistory
                .filter(record => record.jobId === id);

            // 狀態過濾
            if (status) {
                history = history.filter(record => record.status === status);
            }

            // 排序和分頁
            history.sort((a, b) => b.startTime - a.startTime);
            const total = history.length;
            const paginatedHistory = history.slice(parseInt(offset), parseInt(offset) + parseInt(limit));

            res.json({
                success: true,
                data: {
                    history: paginatedHistory,
                    pagination: {
                        total,
                        limit: parseInt(limit),
                        offset: parseInt(offset),
                        hasMore: parseInt(offset) + parseInt(limit) < total
                    },
                    filters: { status }
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 獲取可用的任務類型
        router.get('/task-types', asyncWrapper(async (req, res) => {
            const taskTypes = Object.entries(this.cronScheduler.taskTypes).map(([key, value]) => ({
                key,
                value,
                description: this.getTaskTypeDescription(value)
            }));

            res.json({
                success: true,
                data: {
                    taskTypes,
                    total: taskTypes.length
                },
                timestamp: new Date().toISOString()
            });
        }));

        // 驗證 cron 表達式
        router.post('/validate-cron', asyncWrapper(async (req, res) => {
            const { cronExpression } = req.body;

            if (!cronExpression) {
                return res.status(400).json({
                    success: false,
                    error: {
                        message: '缺少 cron 表達式',
                        code: 'MISSING_CRON_EXPRESSION'
                    },
                    timestamp: new Date().toISOString()
                });
            }

            try {
                const cron = require('node-cron');
                const isValid = cron.validate(cronExpression);

                if (isValid) {
                    res.json({
                        success: true,
                        data: {
                            cronExpression,
                            valid: true,
                            description: this.describeCronExpression(cronExpression)
                        },
                        timestamp: new Date().toISOString()
                    });
                } else {
                    res.status(400).json({
                        success: false,
                        data: {
                            cronExpression,
                            valid: false
                        },
                        error: {
                            message: '無效的 cron 表達式',
                            code: 'INVALID_CRON_EXPRESSION'
                        },
                        timestamp: new Date().toISOString()
                    });
                }

            } catch (error) {
                res.status(400).json({
                    success: false,
                    data: {
                        cronExpression,
                        valid: false
                    },
                    error: {
                        message: error.message,
                        code: 'CRON_VALIDATION_ERROR'
                    },
                    timestamp: new Date().toISOString()
                });
            }
        }));

        // 系統控制端點
        router.post('/system/pause', asyncWrapper(async (req, res) => {
            this.cronScheduler.isRunning = false;

            logger.info('排程系統已暫停');

            res.json({
                success: true,
                message: '排程系統已暫停',
                data: { isRunning: false },
                timestamp: new Date().toISOString()
            });
        }));

        router.post('/system/resume', asyncWrapper(async (req, res) => {
            this.cronScheduler.isRunning = true;

            logger.info('排程系統已恢復');

            res.json({
                success: true,
                message: '排程系統已恢復',
                data: { isRunning: true },
                timestamp: new Date().toISOString()
            });
        }));
    }

    getTaskTypeDescription(taskType) {
        const descriptions = {
            web_crawling: '網頁爬取任務 - 自動爬取指定網站的藝術作品資料',
            data_cleanup: '資料清理任務 - 清理過期或重複的資料',
            metadata_extraction: '中繼資料提取任務 - 從藝術作品中提取詳細資訊',
            classification: '分類任務 - 對藝術作品進行自動分類',
            backup: '備份任務 - 執行資料庫備份操作',
            health_check: '健康檢查任務 - 檢查系統各組件健康狀態',
            analytics: '分析任務 - 生成使用統計和分析報告',
            cache_cleanup: '快取清理任務 - 清理過期的快取資料'
        };

        return descriptions[taskType] || '未知任務類型';
    }

    describeCronExpression(cronExpression) {
        const descriptions = {
            '* * * * *': '每分鐘執行',
            '0 * * * *': '每小時執行',
            '0 0 * * *': '每天執行',
            '0 0 * * 0': '每週執行',
            '0 0 1 * *': '每月執行',
            '0 0 1 1 *': '每年執行'
        };

        return descriptions[cronExpression] || '自定義排程';
    }
}

module.exports = (cronScheduler) => {
    const controller = new SchedulerController(cronScheduler);
    return router;
};