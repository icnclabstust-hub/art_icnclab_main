/**
 * 並行爬取系統
 * 提供高效能並行爬取機制，包括智能負載平衡、動態調度和資源管理
 */

const EventEmitter = require('events');
const cluster = require('cluster');
const os = require('os');
const { Worker } = require('worker_threads');
const { logger } = require('./logger');
const PerformanceOptimizer = require('./performanceOptimizer');
const UnifiedErrorHandler = require('./unifiedErrorHandler');

class ParallelCrawler extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            maxConcurrency: options.maxConcurrency || Math.min(os.cpus().length, 8),
            maxWorkerThreads: options.maxWorkerThreads || 4,
            useCluster: options.useCluster || false,
            queueSize: options.queueSize || 1000,
            retryAttempts: options.retryAttempts || 3,
            retryDelay: options.retryDelay || 1000,
            timeoutMs: options.timeoutMs || 30000,
            enablePriority: options.enablePriority !== false,
            enableLoadBalancing: options.enableLoadBalancing !== false,
            enableAdaptiveScheduling: options.enableAdaptiveScheduling !== false,
            resourceMonitoring: options.resourceMonitoring !== false,
            ...options
        };

        // 任務隊列和管理
        this.taskQueue = [];
        this.priorityQueues = {
            high: [],
            medium: [],
            low: []
        };

        this.runningTasks = new Map();
        this.completedTasks = [];
        this.failedTasks = [];
        this.workerPool = [];
        this.activeWorkers = new Set();

        // 統計和監控
        this.statistics = {
            totalTasks: 0,
            completedTasks: 0,
            failedTasks: 0,
            averageExecutionTime: 0,
            throughputPerSecond: 0,
            memoryUsage: 0,
            cpuUsage: 0,
            networkUsage: 0,
            lastResetTime: Date.now()
        };

        // 負載平衡和調度
        this.loadBalancer = new LoadBalancer();
        this.scheduler = new AdaptiveScheduler();
        this.resourceMonitor = new ResourceMonitor();

        // 效能優化器
        this.performanceOptimizer = new PerformanceOptimizer({
            memoryThreshold: 0.8,
            cpuThreshold: 0.7,
            enableAutomaticOptimization: true
        });

        // 錯誤處理
        this.errorHandler = new UnifiedErrorHandler('ParallelCrawler', {
            maxRetries: this.options.retryAttempts,
            retryDelay: this.options.retryDelay,
            enableCircuitBreaker: true
        });

        this.isRunning = false;
        this.isPaused = false;

        logger.info('並行爬取系統初始化完成', {
            maxConcurrency: this.options.maxConcurrency,
            maxWorkerThreads: this.options.maxWorkerThreads,
            useCluster: this.options.useCluster
        });
    }

    /**
     * 初始化並行爬取系統
     */
    async initialize() {
        try {
            logger.info('初始化並行爬取系統...');

            // 初始化工作池
            if (this.options.useCluster) {
                await this.initializeClusterPool();
            } else {
                await this.initializeWorkerPool();
            }

            // 啟動資源監控
            if (this.options.resourceMonitoring) {
                this.resourceMonitor.start();
            }

            // 啟動自適應調度器
            if (this.options.enableAdaptiveScheduling) {
                this.scheduler.start(this);
            }

            this.isRunning = true;

            this.emit('initialized', {
                workers: this.workerPool.length,
                maxConcurrency: this.options.maxConcurrency
            });

            logger.info('並行爬取系統初始化完成');

        } catch (error) {
            logger.error('並行爬取系統初始化失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 初始化工作執行緒池
     */
    async initializeWorkerPool() {
        const workerCount = Math.min(
            this.options.maxWorkerThreads,
            this.options.maxConcurrency
        );

        for (let i = 0; i < workerCount; i++) {
            const worker = await this.createWorker(`worker-${i}`);
            this.workerPool.push(worker);
        }

        logger.info('工作執行緒池創建完成', { workers: workerCount });
    }

    /**
     * 初始化叢集池
     */
    async initializeClusterPool() {
        if (cluster.isMaster) {
            const workerCount = Math.min(
                os.cpus().length,
                this.options.maxConcurrency
            );

            for (let i = 0; i < workerCount; i++) {
                const worker = cluster.fork();
                worker.workerId = `cluster-${i}`;
                this.workerPool.push(worker);
            }

            logger.info('叢集池創建完成', { workers: workerCount });
        }
    }

    /**
     * 創建工作執行緒
     */
    async createWorker(workerId) {
        const workerPath = require.path.resolve(__dirname, './crawlerWorker.js');

        const worker = new Worker(workerPath, {
            workerData: {
                workerId,
                options: this.options
            }
        });

        worker.workerId = workerId;
        worker.isActive = false;
        worker.currentTask = null;
        worker.tasksCompleted = 0;
        worker.averageExecutionTime = 0;

        // 監聽工作執行緒事件
        worker.on('message', (message) => {
            this.handleWorkerMessage(worker, message);
        });

        worker.on('error', (error) => {
            logger.error('工作執行緒錯誤', { workerId, error: error.message });
            this.handleWorkerError(worker, error);
        });

        worker.on('exit', (code) => {
            if (code !== 0) {
                logger.warn('工作執行緒異常退出', { workerId, code });
                this.replaceWorker(worker);
            }
        });

        return worker;
    }

    /**
     * 添加爬取任務
     */
    addTask(taskConfig) {
        const task = {
            id: this.generateTaskId(),
            config: taskConfig,
            priority: taskConfig.priority || 'medium',
            createdAt: Date.now(),
            attempts: 0,
            status: 'queued',
            metadata: taskConfig.metadata || {}
        };

        if (this.options.enablePriority) {
            this.priorityQueues[task.priority].push(task);
        } else {
            this.taskQueue.push(task);
        }

        this.statistics.totalTasks++;

        this.emit('taskAdded', task);

        // 立即嘗試處理任務
        if (this.isRunning && !this.isPaused) {
            this.processNextTask();
        }

        return task.id;
    }

    /**
     * 批量添加任務
     */
    addTasks(taskConfigs) {
        const taskIds = [];

        for (const config of taskConfigs) {
            const taskId = this.addTask(config);
            taskIds.push(taskId);
        }

        logger.info('批量添加任務', {
            count: taskConfigs.length,
            totalQueueSize: this.getQueueSize()
        });

        return taskIds;
    }

    /**
     * 處理下一個任務
     */
    async processNextTask() {
        if (this.isPaused || !this.isRunning) {
            return;
        }

        const availableWorker = this.findAvailableWorker();
        if (!availableWorker) {
            return; // 沒有可用工作執行緒
        }

        const task = this.getNextTask();
        if (!task) {
            return; // 沒有待處理任務
        }

        await this.executeTask(task, availableWorker);
    }

    /**
     * 獲取下一個任務
     */
    getNextTask() {
        if (this.options.enablePriority) {
            // 優先處理高優先級任務
            for (const priority of ['high', 'medium', 'low']) {
                if (this.priorityQueues[priority].length > 0) {
                    return this.priorityQueues[priority].shift();
                }
            }
        } else {
            if (this.taskQueue.length > 0) {
                return this.taskQueue.shift();
            }
        }

        return null;
    }

    /**
     * 找到可用的工作執行緒
     */
    findAvailableWorker() {
        if (this.options.enableLoadBalancing) {
            return this.loadBalancer.selectOptimalWorker(this.workerPool);
        }

        return this.workerPool.find(worker => !worker.isActive);
    }

    /**
     * 執行任務
     */
    async executeTask(task, worker) {
        try {
            task.status = 'running';
            task.startedAt = Date.now();
            task.workerId = worker.workerId;

            worker.isActive = true;
            worker.currentTask = task;
            this.runningTasks.set(task.id, task);
            this.activeWorkers.add(worker);

            logger.info('開始執行任務', {
                taskId: task.id,
                workerId: worker.workerId,
                priority: task.priority
            });

            // 發送任務到工作執行緒
            const message = {
                type: 'executeTask',
                task: task
            };

            if (this.options.useCluster) {
                worker.send(message);
            } else {
                worker.postMessage(message);
            }

            // 設置任務超時
            this.setTaskTimeout(task);

            this.emit('taskStarted', task);

        } catch (error) {
            await this.handleTaskError(task, worker, error);
        }
    }

    /**
     * 設置任務超時
     */
    setTaskTimeout(task) {
        task.timeoutHandle = setTimeout(async () => {
            if (task.status === 'running') {
                logger.warn('任務執行超時', {
                    taskId: task.id,
                    timeout: this.options.timeoutMs
                });

                await this.handleTaskTimeout(task);
            }
        }, this.options.timeoutMs);
    }

    /**
     * 處理工作執行緒消息
     */
    async handleWorkerMessage(worker, message) {
        try {
            const { type, taskId, result, error } = message;

            switch (type) {
                case 'taskCompleted':
                    await this.handleTaskCompleted(worker, taskId, result);
                    break;

                case 'taskFailed':
                    await this.handleTaskFailed(worker, taskId, error);
                    break;

                case 'progress':
                    this.handleTaskProgress(worker, taskId, message.progress);
                    break;

                case 'workerReady':
                    worker.isActive = false;
                    this.processNextTask(); // 處理下一個任務
                    break;

                default:
                    logger.warn('未知工作執行緒消息類型', { type, workerId: worker.workerId });
            }

        } catch (error) {
            logger.error('處理工作執行緒消息失敗', {
                workerId: worker.workerId,
                error: error.message
            });
        }
    }

    /**
     * 處理任務完成
     */
    async handleTaskCompleted(worker, taskId, result) {
        const task = this.runningTasks.get(taskId);
        if (!task) {
            logger.warn('找不到已完成的任務', { taskId });
            return;
        }

        // 清理任務狀態
        this.clearTaskState(task, worker);

        // 更新任務資訊
        task.status = 'completed';
        task.completedAt = Date.now();
        task.executionTime = task.completedAt - task.startedAt;
        task.result = result;

        // 更新統計
        this.updateStatistics(task, true);
        this.completedTasks.push(task);

        // 更新工作執行緒統計
        worker.tasksCompleted++;
        worker.averageExecutionTime = this.calculateWorkerAverageTime(worker, task.executionTime);

        logger.info('任務完成', {
            taskId: task.id,
            workerId: worker.workerId,
            executionTime: task.executionTime,
            priority: task.priority
        });

        this.emit('taskCompleted', task, result);

        // 處理下一個任務
        this.processNextTask();
    }

    /**
     * 處理任務失敗
     */
    async handleTaskFailed(worker, taskId, error) {
        const task = this.runningTasks.get(taskId);
        if (!task) {
            logger.warn('找不到失敗的任務', { taskId });
            return;
        }

        task.attempts++;
        task.lastError = error;

        // 清理任務狀態
        this.clearTaskState(task, worker);

        if (task.attempts < this.options.retryAttempts) {
            // 重試任務
            logger.info('重試任務', {
                taskId: task.id,
                attempts: task.attempts,
                maxAttempts: this.options.retryAttempts
            });

            task.status = 'queued';

            // 延遲後重新加入隊列
            setTimeout(() => {
                if (this.options.enablePriority) {
                    this.priorityQueues[task.priority].unshift(task);
                } else {
                    this.taskQueue.unshift(task);
                }
                this.processNextTask();
            }, this.options.retryDelay * task.attempts);

        } else {
            // 任務最終失敗
            task.status = 'failed';
            task.failedAt = Date.now();

            this.updateStatistics(task, false);
            this.failedTasks.push(task);

            logger.error('任務最終失敗', {
                taskId: task.id,
                workerId: worker.workerId,
                attempts: task.attempts,
                error: error
            });

            this.emit('taskFailed', task, error);
        }

        // 處理下一個任務
        this.processNextTask();
    }

    /**
     * 處理任務超時
     */
    async handleTaskTimeout(task) {
        const worker = this.workerPool.find(w => w.workerId === task.workerId);

        if (worker) {
            // 嘗試取消任務
            try {
                if (this.options.useCluster) {
                    worker.send({ type: 'cancelTask', taskId: task.id });
                } else {
                    worker.postMessage({ type: 'cancelTask', taskId: task.id });
                }
            } catch (error) {
                logger.error('取消超時任務失敗', { error: error.message });
            }

            this.clearTaskState(task, worker);
        }

        // 處理為失敗任務
        await this.handleTaskFailed(worker, task.id, 'Task timeout');
    }

    /**
     * 清理任務狀態
     */
    clearTaskState(task, worker) {
        // 清除超時定時器
        if (task.timeoutHandle) {
            clearTimeout(task.timeoutHandle);
            task.timeoutHandle = null;
        }

        // 更新工作執行緒狀態
        if (worker) {
            worker.isActive = false;
            worker.currentTask = null;
            this.activeWorkers.delete(worker);
        }

        // 從運行任務中移除
        this.runningTasks.delete(task.id);
    }

    /**
     * 更新統計資訊
     */
    updateStatistics(task, success) {
        if (success) {
            this.statistics.completedTasks++;

            // 更新平均執行時間
            const totalTime = this.statistics.averageExecutionTime * (this.statistics.completedTasks - 1) + task.executionTime;
            this.statistics.averageExecutionTime = totalTime / this.statistics.completedTasks;

        } else {
            this.statistics.failedTasks++;
        }

        // 計算吞吐量
        const timeElapsed = (Date.now() - this.statistics.lastResetTime) / 1000;
        if (timeElapsed > 0) {
            this.statistics.throughputPerSecond = this.statistics.completedTasks / timeElapsed;
        }

        // 更新資源使用狀況
        if (this.options.resourceMonitoring) {
            const resourceStats = this.resourceMonitor.getStats();
            this.statistics.memoryUsage = resourceStats.memoryUsage;
            this.statistics.cpuUsage = resourceStats.cpuUsage;
        }
    }

    /**
     * 計算工作執行緒平均執行時間
     */
    calculateWorkerAverageTime(worker, newTime) {
        if (worker.tasksCompleted === 1) {
            return newTime;
        }

        const totalTime = worker.averageExecutionTime * (worker.tasksCompleted - 1) + newTime;
        return totalTime / worker.tasksCompleted;
    }

    /**
     * 暫停處理
     */
    pause() {
        this.isPaused = true;
        logger.info('並行爬取系統已暫停');
        this.emit('paused');
    }

    /**
     * 恢復處理
     */
    resume() {
        this.isPaused = false;
        logger.info('並行爬取系統已恢復');

        // 重新開始處理任務
        for (let i = 0; i < this.options.maxConcurrency; i++) {
            this.processNextTask();
        }

        this.emit('resumed');
    }

    /**
     * 停止並行爬取系統
     */
    async stop() {
        try {
            this.isRunning = false;
            logger.info('正在停止並行爬取系統...');

            // 等待運行中的任務完成
            await this.waitForRunningTasks();

            // 關閉所有工作執行緒
            await this.closeAllWorkers();

            // 停止資源監控
            if (this.resourceMonitor) {
                this.resourceMonitor.stop();
            }

            // 停止調度器
            if (this.scheduler) {
                this.scheduler.stop();
            }

            logger.info('並行爬取系統已停止');
            this.emit('stopped');

        } catch (error) {
            logger.error('停止並行爬取系統失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 等待運行中的任務完成
     */
    async waitForRunningTasks(timeoutMs = 30000) {
        const startTime = Date.now();

        while (this.runningTasks.size > 0 && Date.now() - startTime < timeoutMs) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        if (this.runningTasks.size > 0) {
            logger.warn('部分任務未能在超時時間內完成', {
                remainingTasks: this.runningTasks.size
            });
        }
    }

    /**
     * 關閉所有工作執行緒
     */
    async closeAllWorkers() {
        const closePromises = this.workerPool.map(async (worker) => {
            try {
                if (this.options.useCluster) {
                    worker.kill();
                } else {
                    await worker.terminate();
                }
            } catch (error) {
                logger.warn('關閉工作執行緒失敗', {
                    workerId: worker.workerId,
                    error: error.message
                });
            }
        });

        await Promise.all(closePromises);
        this.workerPool = [];
    }

    /**
     * 獲取隊列大小
     */
    getQueueSize() {
        if (this.options.enablePriority) {
            return Object.values(this.priorityQueues).reduce((sum, queue) => sum + queue.length, 0);
        }
        return this.taskQueue.length;
    }

    /**
     * 獲取系統狀態
     */
    getStatus() {
        return {
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            queueSize: this.getQueueSize(),
            runningTasks: this.runningTasks.size,
            availableWorkers: this.workerPool.filter(w => !w.isActive).length,
            totalWorkers: this.workerPool.length,
            statistics: { ...this.statistics },
            resourceUsage: this.options.resourceMonitoring ? this.resourceMonitor.getStats() : null
        };
    }

    /**
     * 重設統計資料
     */
    resetStatistics() {
        this.statistics = {
            totalTasks: 0,
            completedTasks: 0,
            failedTasks: 0,
            averageExecutionTime: 0,
            throughputPerSecond: 0,
            memoryUsage: 0,
            cpuUsage: 0,
            networkUsage: 0,
            lastResetTime: Date.now()
        };

        logger.info('統計資料已重設');
        this.emit('statisticsReset');
    }

    /**
     * 生成任務ID
     */
    generateTaskId() {
        return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

/**
 * 負載平衡器
 */
class LoadBalancer {
    constructor() {
        this.strategies = {
            roundRobin: this.roundRobinStrategy.bind(this),
            leastConnections: this.leastConnectionsStrategy.bind(this),
            fastestResponse: this.fastestResponseStrategy.bind(this)
        };

        this.currentStrategy = 'leastConnections';
        this.roundRobinIndex = 0;
    }

    selectOptimalWorker(workers, strategy = this.currentStrategy) {
        const availableWorkers = workers.filter(worker => !worker.isActive);

        if (availableWorkers.length === 0) {
            return null;
        }

        return this.strategies[strategy](availableWorkers);
    }

    roundRobinStrategy(workers) {
        const worker = workers[this.roundRobinIndex % workers.length];
        this.roundRobinIndex++;
        return worker;
    }

    leastConnectionsStrategy(workers) {
        return workers.reduce((best, current) =>
            current.tasksCompleted < best.tasksCompleted ? current : best
        );
    }

    fastestResponseStrategy(workers) {
        return workers.reduce((fastest, current) =>
            current.averageExecutionTime < fastest.averageExecutionTime ? current : fastest
        );
    }
}

/**
 * 自適應調度器
 */
class AdaptiveScheduler {
    constructor() {
        this.isRunning = false;
        this.adjustmentInterval = 30000; // 30秒調整一次
        this.performanceThreshold = 0.8;
    }

    start(crawler) {
        this.crawler = crawler;
        this.isRunning = true;

        this.intervalHandle = setInterval(() => {
            this.adjustConcurrency();
        }, this.adjustmentInterval);

        logger.info('自適應調度器已啟動');
    }

    stop() {
        this.isRunning = false;

        if (this.intervalHandle) {
            clearInterval(this.intervalHandle);
        }

        logger.info('自適應調度器已停止');
    }

    adjustConcurrency() {
        if (!this.crawler || !this.isRunning) {
            return;
        }

        const stats = this.crawler.getStatus();
        const resourceStats = stats.resourceUsage;

        if (!resourceStats) {
            return;
        }

        // 基於資源使用情況調整並發數
        if (resourceStats.cpuUsage > 0.8 || resourceStats.memoryUsage > 0.8) {
            // 降低並發數
            this.decreaseConcurrency();
        } else if (resourceStats.cpuUsage < 0.5 && resourceStats.memoryUsage < 0.6) {
            // 增加並發數
            this.increaseConcurrency();
        }
    }

    increaseConcurrency() {
        const currentConcurrency = this.crawler.options.maxConcurrency;
        const maxAllowed = Math.min(os.cpus().length * 2, 16);

        if (currentConcurrency < maxAllowed) {
            this.crawler.options.maxConcurrency++;
            logger.info('增加並發數', {
                newConcurrency: this.crawler.options.maxConcurrency
            });
        }
    }

    decreaseConcurrency() {
        const currentConcurrency = this.crawler.options.maxConcurrency;

        if (currentConcurrency > 2) {
            this.crawler.options.maxConcurrency--;
            logger.info('降低並發數', {
                newConcurrency: this.crawler.options.maxConcurrency
            });
        }
    }
}

/**
 * 資源監控器
 */
class ResourceMonitor {
    constructor() {
        this.isRunning = false;
        this.monitorInterval = 5000; // 5秒
        this.stats = {
            memoryUsage: 0,
            cpuUsage: 0,
            networkUsage: 0
        };
    }

    start() {
        this.isRunning = true;

        this.intervalHandle = setInterval(() => {
            this.collectStats();
        }, this.monitorInterval);

        logger.info('資源監控器已啟動');
    }

    stop() {
        this.isRunning = false;

        if (this.intervalHandle) {
            clearInterval(this.intervalHandle);
        }

        logger.info('資源監控器已停止');
    }

    collectStats() {
        const memUsage = process.memoryUsage();
        const totalMemory = os.totalmem();

        this.stats = {
            memoryUsage: memUsage.heapUsed / totalMemory,
            cpuUsage: this.getCpuUsage(),
            networkUsage: 0 // TODO: 實現網路使用監控
        };
    }

    getCpuUsage() {
        const cpus = os.cpus();
        let totalIdle = 0;
        let totalTick = 0;

        cpus.forEach(cpu => {
            for (const type in cpu.times) {
                totalTick += cpu.times[type];
            }
            totalIdle += cpu.times.idle;
        });

        return 1 - (totalIdle / totalTick);
    }

    getStats() {
        return { ...this.stats };
    }
}

module.exports = ParallelCrawler;