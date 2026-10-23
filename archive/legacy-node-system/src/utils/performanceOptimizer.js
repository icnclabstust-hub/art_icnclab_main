#!/usr/bin/env node
/**
 * 性能優化模塊
 * 提供批處理、並行處理、智能任務調度和性能監控功能
 */

const EventEmitter = require('events');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const os = require('os');

class PerformanceOptimizer extends EventEmitter {
    constructor(options = {}) {
        super();
        this.options = {
            maxConcurrency: options.maxConcurrency || Math.min(os.cpus().length, 8),
            batchSize: options.batchSize || 50,
            queueHighWaterMark: options.queueHighWaterMark || 1000,
            adaptiveBatching: options.adaptiveBatching !== false,
            enableWorkerThreads: options.enableWorkerThreads !== false,
            memoryThreshold: options.memoryThreshold || 0.8, // 80%
            cpuThreshold: options.cpuThreshold || 0.85, // 85%
            enableMetrics: options.enableMetrics !== false
        };

        this.taskQueue = [];
        this.runningTasks = new Set();
        this.workers = new Map();
        this.metrics = this.initializeMetrics();
        this.resourceMonitor = null;

        // 啟動資源監控
        if (this.options.enableMetrics) {
            this.startResourceMonitoring();
        }
    }

    /**
     * 初始化性能指標
     */
    initializeMetrics() {
        return {
            tasksProcessed: 0,
            tasksQueued: 0,
            batchesCompleted: 0,
            averageProcessingTime: 0,
            throughputPerSecond: 0,
            memoryUsage: process.memoryUsage(),
            cpuUsage: 0,
            startTime: Date.now(),
            lastMetricsUpdate: Date.now()
        };
    }

    /**
     * 智能批處理 - 根據性能動態調整批次大小
     */
    async processBatch(items, processor, options = {}) {
        const startTime = Date.now();
        const batchSize = this.calculateOptimalBatchSize(items.length, options.batchSize);

        console.log(`🚀 開始批處理: ${items.length} 個項目，批次大小: ${batchSize}`);

        const results = [];
        const errors = [];

        // 將項目分批
        const batches = this.chunkArray(items, batchSize);

        for (let i = 0; i < batches.length; i++) {
            const batch = batches[i];
            const batchStartTime = Date.now();

            try {
                // 並行處理批次內的項目
                const batchResults = await this.processParallel(batch, processor, {
                    maxConcurrency: Math.min(batchSize, this.options.maxConcurrency)
                });

                results.push(...batchResults.results);
                if (batchResults.errors.length > 0) {
                    errors.push(...batchResults.errors);
                }

                const batchTime = Date.now() - batchStartTime;
                console.log(`✅ 批次 ${i + 1}/${batches.length} 完成: ${batch.length} 項目，耗時 ${batchTime}ms`);

                // 更新指標
                this.updateBatchMetrics(batch.length, batchTime);

                // 自適應延遲
                if (this.isResourceStrained()) {
                    const delay = this.calculateAdaptiveDelay();
                    console.log(`⏸️ 系統負載較高，延遲 ${delay}ms`);
                    await this.delay(delay);
                }

                // 發送進度事件
                this.emit('batchProgress', {
                    completed: i + 1,
                    total: batches.length,
                    processed: results.length,
                    errors: errors.length
                });

            } catch (error) {
                console.error(`❌ 批次 ${i + 1} 處理失敗:`, error.message);
                errors.push({ batch: i + 1, error: error.message, items: batch });
            }
        }

        const totalTime = Date.now() - startTime;
        const throughput = Math.round(items.length / (totalTime / 1000));

        console.log(`🎉 批處理完成: ${results.length}/${items.length} 成功，${errors.length} 錯誤，吞吐量: ${throughput} 項目/秒`);

        return {
            results,
            errors,
            metrics: {
                totalTime,
                throughput,
                successRate: results.length / items.length,
                averageBatchTime: totalTime / batches.length
            }
        };
    }

    /**
     * 並行處理 - 控制並發數量的並行處理
     */
    async processParallel(items, processor, options = {}) {
        const maxConcurrency = options.maxConcurrency || this.options.maxConcurrency;
        const results = [];
        const errors = [];

        // 創建處理承諾
        const processing = async (item, index) => {
            try {
                const result = await processor(item, index);
                return { success: true, result, index };
            } catch (error) {
                return { success: false, error: error.message, item, index };
            }
        };

        // 並發控制
        const semaphore = new Semaphore(maxConcurrency);
        const promises = items.map(async (item, index) => {
            return semaphore.acquire().then(async (release) => {
                try {
                    return await processing(item, index);
                } finally {
                    release();
                }
            });
        });

        // 等待所有任務完成
        const outcomes = await Promise.allSettled(promises);

        outcomes.forEach((outcome, index) => {
            if (outcome.status === 'fulfilled') {
                const result = outcome.value;
                if (result.success) {
                    results[result.index] = result.result;
                } else {
                    errors.push({ index: result.index, error: result.error, item: result.item });
                }
            } else {
                errors.push({ index, error: outcome.reason.message, item: items[index] });
            }
        });

        return { results: results.filter(r => r !== undefined), errors };
    }

    /**
     * Worker線程處理
     */
    async processWithWorkers(items, workerScript, options = {}) {
        const numWorkers = options.numWorkers || Math.min(this.options.maxConcurrency, os.cpus().length);
        const chunkSize = Math.ceil(items.length / numWorkers);
        const chunks = this.chunkArray(items, chunkSize);

        console.log(`🔧 啟動 ${numWorkers} 個Worker處理 ${items.length} 個項目`);

        const workerPromises = chunks.map((chunk, index) => {
            return this.createWorker(workerScript, { chunk, index, options });
        });

        try {
            const results = await Promise.all(workerPromises);
            const flatResults = results.reduce((acc, result) => {
                acc.results.push(...result.results);
                acc.errors.push(...result.errors);
                return acc;
            }, { results: [], errors: [] });

            console.log(`🎉 Worker處理完成: ${flatResults.results.length} 成功，${flatResults.errors.length} 錯誤`);
            return flatResults;

        } catch (error) {
            console.error('❌ Worker處理失敗:', error);
            throw error;
        } finally {
            // 清理Worker
            this.cleanupWorkers();
        }
    }

    /**
     * 創建Worker
     */
    createWorker(script, data) {
        return new Promise((resolve, reject) => {
            const worker = new Worker(script, { workerData: data });

            worker.on('message', (result) => {
                resolve(result);
            });

            worker.on('error', (error) => {
                reject(error);
            });

            worker.on('exit', (code) => {
                if (code !== 0) {
                    reject(new Error(`Worker退出碼: ${code}`));
                }
            });

            this.workers.set(worker.threadId, worker);
        });
    }

    /**
     * 智能任務調度
     */
    async scheduleTask(task, priority = 'normal') {
        const taskWrapper = {
            id: this.generateTaskId(),
            task,
            priority,
            timestamp: Date.now(),
            retries: 0,
            maxRetries: 3
        };

        // 根據優先級插入任務
        this.insertTaskByPriority(taskWrapper);
        this.metrics.tasksQueued++;

        this.emit('taskQueued', taskWrapper);

        // 如果隊列未滿且有可用資源，立即處理
        if (this.canProcessMoreTasks()) {
            this.processNextTask();
        }

        return taskWrapper.id;
    }

    /**
     * 處理下一個任務
     */
    async processNextTask() {
        if (this.taskQueue.length === 0 || !this.canProcessMoreTasks()) {
            return;
        }

        const taskWrapper = this.taskQueue.shift();
        this.runningTasks.add(taskWrapper.id);
        this.metrics.tasksQueued--;

        const startTime = Date.now();

        try {
            const result = await taskWrapper.task();
            const processingTime = Date.now() - startTime;

            this.updateTaskMetrics(processingTime);
            this.emit('taskCompleted', { id: taskWrapper.id, result, processingTime });

        } catch (error) {
            taskWrapper.retries++;

            if (taskWrapper.retries < taskWrapper.maxRetries) {
                // 重新排程
                console.log(`⚠️ 任務 ${taskWrapper.id} 重試 ${taskWrapper.retries}/${taskWrapper.maxRetries}`);
                this.insertTaskByPriority(taskWrapper);
                this.metrics.tasksQueued++;
            } else {
                console.error(`❌ 任務 ${taskWrapper.id} 最終失敗:`, error.message);
                this.emit('taskFailed', { id: taskWrapper.id, error: error.message });
            }

        } finally {
            this.runningTasks.delete(taskWrapper.id);

            // 處理下一個任務
            setImmediate(() => this.processNextTask());
        }
    }

    /**
     * 計算最佳批次大小
     */
    calculateOptimalBatchSize(totalItems, suggestedBatchSize) {
        if (!this.options.adaptiveBatching) {
            return suggestedBatchSize || this.options.batchSize;
        }

        const memoryUsage = process.memoryUsage();
        const memoryPressure = memoryUsage.heapUsed / memoryUsage.heapTotal;

        let batchSize = suggestedBatchSize || this.options.batchSize;

        // 根據記憶體壓力調整
        if (memoryPressure > 0.8) {
            batchSize = Math.floor(batchSize * 0.5);
        } else if (memoryPressure < 0.3) {
            batchSize = Math.floor(batchSize * 1.5);
        }

        // 根據CPU使用率調整
        if (this.metrics.cpuUsage > this.options.cpuThreshold) {
            batchSize = Math.floor(batchSize * 0.7);
        }

        // 確保合理範圍
        return Math.max(1, Math.min(batchSize, Math.floor(totalItems / 2), 200));
    }

    /**
     * 檢查資源是否緊張
     */
    isResourceStrained() {
        const memoryUsage = process.memoryUsage();
        const memoryPressure = memoryUsage.heapUsed / memoryUsage.heapTotal;

        return memoryPressure > this.options.memoryThreshold ||
               this.metrics.cpuUsage > this.options.cpuThreshold;
    }

    /**
     * 計算自適應延遲
     */
    calculateAdaptiveDelay() {
        const baseDelay = 100;
        const memoryUsage = process.memoryUsage();
        const memoryPressure = memoryUsage.heapUsed / memoryUsage.heapTotal;

        return Math.floor(baseDelay * (1 + memoryPressure + this.metrics.cpuUsage));
    }

    /**
     * 啟動資源監控
     */
    startResourceMonitoring() {
        this.resourceMonitor = setInterval(() => {
            this.updateResourceMetrics();
            this.emitMetrics();
        }, 5000); // 每5秒更新
    }

    /**
     * 更新資源指標
     */
    updateResourceMetrics() {
        this.metrics.memoryUsage = process.memoryUsage();

        // 簡單的CPU使用率估算
        const now = Date.now();
        const timeDiff = now - this.metrics.lastMetricsUpdate;
        this.metrics.cpuUsage = Math.min(this.runningTasks.size / this.options.maxConcurrency, 1.0);

        // 計算吞吐量
        if (timeDiff > 0) {
            const throughputWindow = 60000; // 1分鐘窗口
            const recentTasks = this.metrics.tasksProcessed; // 簡化計算
            this.metrics.throughputPerSecond = (recentTasks / throughputWindow) * 1000;
        }

        this.metrics.lastMetricsUpdate = now;
    }

    /**
     * 更新批次指標
     */
    updateBatchMetrics(batchSize, processingTime) {
        this.metrics.batchesCompleted++;
        this.metrics.averageProcessingTime =
            (this.metrics.averageProcessingTime + processingTime) / 2;
    }

    /**
     * 更新任務指標
     */
    updateTaskMetrics(processingTime) {
        this.metrics.tasksProcessed++;
        this.metrics.averageProcessingTime =
            (this.metrics.averageProcessingTime + processingTime) / 2;
    }

    /**
     * 發送指標事件
     */
    emitMetrics() {
        this.emit('metrics', {
            ...this.metrics,
            queueSize: this.taskQueue.length,
            runningTasks: this.runningTasks.size
        });
    }

    /**
     * 工具方法
     */
    chunkArray(array, chunkSize) {
        const chunks = [];
        for (let i = 0; i < array.length; i += chunkSize) {
            chunks.push(array.slice(i, i + chunkSize));
        }
        return chunks;
    }

    insertTaskByPriority(task) {
        const priorities = { high: 0, normal: 1, low: 2 };
        const taskPriority = priorities[task.priority] || 1;

        let insertIndex = 0;
        for (let i = 0; i < this.taskQueue.length; i++) {
            const queuedTaskPriority = priorities[this.taskQueue[i].priority] || 1;
            if (taskPriority <= queuedTaskPriority) {
                insertIndex = i;
                break;
            }
            insertIndex = i + 1;
        }

        this.taskQueue.splice(insertIndex, 0, task);
    }

    canProcessMoreTasks() {
        return this.runningTasks.size < this.options.maxConcurrency &&
               !this.isResourceStrained();
    }

    generateTaskId() {
        return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    cleanupWorkers() {
        for (const [threadId, worker] of this.workers.entries()) {
            worker.terminate();
            this.workers.delete(threadId);
        }
    }

    /**
     * 獲取性能報告
     */
    getPerformanceReport() {
        const runtime = Date.now() - this.metrics.startTime;

        return {
            runtime,
            metrics: { ...this.metrics },
            queueStatus: {
                queued: this.taskQueue.length,
                running: this.runningTasks.size,
                capacity: this.options.maxConcurrency
            },
            resourceStatus: {
                memoryPressure: this.metrics.memoryUsage.heapUsed / this.metrics.memoryUsage.heapTotal,
                cpuUsage: this.metrics.cpuUsage,
                isStrained: this.isResourceStrained()
            },
            recommendations: this.generateRecommendations()
        };
    }

    /**
     * 生成優化建議
     */
    generateRecommendations() {
        const recommendations = [];

        if (this.metrics.cpuUsage > 0.9) {
            recommendations.push('考慮降低並發數量或增加處理延遲');
        }

        const memoryPressure = this.metrics.memoryUsage.heapUsed / this.metrics.memoryUsage.heapTotal;
        if (memoryPressure > 0.85) {
            recommendations.push('記憶體使用率過高，建議減少批次大小');
        }

        if (this.metrics.throughputPerSecond < 10) {
            recommendations.push('吞吐量較低，考慮增加並發數量或優化處理邏輯');
        }

        return recommendations;
    }

    /**
     * 清理和關閉
     */
    shutdown() {
        if (this.resourceMonitor) {
            clearInterval(this.resourceMonitor);
        }

        this.cleanupWorkers();
        this.removeAllListeners();

        console.log('🛑 性能優化器已關閉');
    }
}

/**
 * 信號量實現 - 控制並發數量
 */
class Semaphore {
    constructor(permits) {
        this.permits = permits;
        this.waiting = [];
    }

    async acquire() {
        return new Promise((resolve) => {
            if (this.permits > 0) {
                this.permits--;
                resolve(() => this.release());
            } else {
                this.waiting.push(() => {
                    this.permits--;
                    resolve(() => this.release());
                });
            }
        });
    }

    release() {
        this.permits++;
        if (this.waiting.length > 0) {
            const next = this.waiting.shift();
            next();
        }
    }
}

module.exports = { PerformanceOptimizer, Semaphore };