/**
 * 智能任務調度器 - Intelligent Task Scheduler
 * 負責Agent任務的智能調度、優先級管理和資源分配
 */

const EventEmitter = require('events');

class TaskScheduler extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            maxConcurrentTasks: options.maxConcurrentTasks || 10,
            priorityLevels: options.priorityLevels || ['low', 'normal', 'high', 'critical'],
            resourceMonitoringInterval: options.resourceMonitoringInterval || 5000,
            adaptiveScheduling: options.adaptiveScheduling !== false,
            loadBalancing: options.loadBalancing !== false,
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 1000,
            ...options
        };

        // 任務隊列 - 按優先級分組
        this.taskQueues = {
            critical: [],
            high: [],
            normal: [],
            low: []
        };

        // 當前運行的任務
        this.runningTasks = new Map();

        // 完成的任務歷史
        this.completedTasks = [];

        // 失敗的任務
        this.failedTasks = [];

        // 資源監控數據
        this.resourceStats = {
            memoryUsage: 0,
            cpuUsage: 0,
            taskThroughput: 0,
            averageExecutionTime: 0,
            errorRate: 0
        };

        // Agent性能統計
        this.agentStats = new Map();

        // 調度器狀態
        this.isRunning = false;
        this.isPaused = false;

        // 開始資源監控
        this.startResourceMonitoring();

        console.log('🎯 智能任務調度器初始化完成');
    }

    /**
     * 添加任務到調度隊列
     */
    async scheduleTask(task, priority = 'normal') {
        const taskId = task.id || this.generateTaskId();

        const scheduledTask = {
            id: taskId,
            ...task,
            priority: priority,
            scheduledAt: new Date(),
            retryCount: 0,
            estimatedDuration: task.estimatedDuration || 30000,
            dependencies: task.dependencies || [],
            agentType: task.agentType || 'default',
            metadata: task.metadata || {}
        };

        // 驗證任務
        if (!this.validateTask(scheduledTask)) {
            throw new Error(`任務驗證失敗: ${taskId}`);
        }

        // 添加到相應優先級隊列
        this.taskQueues[priority].push(scheduledTask);

        console.log(`📋 任務已加入調度隊列: ${taskId} (優先級: ${priority})`);

        this.emit('taskScheduled', scheduledTask);

        // 如果調度器正在運行，嘗試立即執行
        if (this.isRunning && !this.isPaused) {
            this.processNextTask();
        }

        return taskId;
    }

    /**
     * 開始任務調度
     */
    async start() {
        if (this.isRunning) {
            console.warn('⚠️ 任務調度器已在運行中');
            return;
        }

        this.isRunning = true;
        console.log('🚀 任務調度器開始運行');

        this.emit('schedulerStarted');

        // 開始處理任務
        this.processTaskQueue();
    }

    /**
     * 停止任務調度
     */
    async stop() {
        console.log('⏹️ 停止任務調度器...');

        this.isRunning = false;

        // 等待所有運行中的任務完成
        if (this.runningTasks.size > 0) {
            console.log(`⏳ 等待 ${this.runningTasks.size} 個任務完成...`);

            const runningTaskPromises = Array.from(this.runningTasks.values())
                .map(task => task.promise);

            try {
                await Promise.allSettled(runningTaskPromises);
            } catch (error) {
                console.error('❌ 等待任務完成時發生錯誤:', error.message);
            }
        }

        this.emit('schedulerStopped');
        console.log('✅ 任務調度器已停止');
    }

    /**
     * 暫停任務調度
     */
    pause() {
        this.isPaused = true;
        console.log('⏸️ 任務調度器已暫停');
        this.emit('schedulerPaused');
    }

    /**
     * 恢復任務調度
     */
    resume() {
        this.isPaused = false;
        console.log('▶️ 任務調度器已恢復');
        this.emit('schedulerResumed');

        if (this.isRunning) {
            this.processTaskQueue();
        }
    }

    /**
     * 處理任務隊列
     */
    async processTaskQueue() {
        while (this.isRunning && !this.isPaused) {
            // 檢查是否可以執行更多任務
            if (this.runningTasks.size >= this.options.maxConcurrentTasks) {
                await this.waitForTaskSlot();
                continue;
            }

            // 獲取下一個任務
            const nextTask = this.getNextTask();
            if (!nextTask) {
                // 沒有待執行任務，短暫等待
                await this.sleep(1000);
                continue;
            }

            // 檢查任務依賴
            if (!this.checkTaskDependencies(nextTask)) {
                // 依賴未滿足，將任務重新加入隊列
                this.rescheduleTask(nextTask);
                continue;
            }

            // 執行任務
            await this.executeTask(nextTask);
        }
    }

    /**
     * 獲取下一個要執行的任務
     */
    getNextTask() {
        // 按優先級順序檢查隊列
        for (const priority of this.options.priorityLevels.reverse()) {
            const queue = this.taskQueues[priority];
            if (queue.length > 0) {
                return queue.shift();
            }
        }
        return null;
    }

    /**
     * 執行任務
     */
    async executeTask(task) {
        const startTime = Date.now();

        console.log(`🔄 開始執行任務: ${task.id} (${task.agentType})`);

        // 記錄運行中的任務
        const taskExecution = {
            task: task,
            startTime: startTime,
            promise: null
        };

        this.runningTasks.set(task.id, taskExecution);
        this.emit('taskStarted', task);

        try {
            // 根據任務類型選擇執行方式
            let result;
            if (task.executor && typeof task.executor === 'function') {
                // 直接執行器函數
                taskExecution.promise = task.executor(task);
                result = await taskExecution.promise;
            } else if (task.agentType && task.method) {
                // Agent方法調用
                result = await this.executeAgentTask(task);
            } else {
                throw new Error(`不支援的任務類型: ${task.id}`);
            }

            // 任務執行成功
            const executionTime = Date.now() - startTime;

            const completedTask = {
                ...task,
                result: result,
                executionTime: executionTime,
                completedAt: new Date(),
                status: 'completed'
            };

            this.completedTasks.push(completedTask);
            this.runningTasks.delete(task.id);

            // 更新Agent統計
            this.updateAgentStats(task.agentType, executionTime, true);

            console.log(`✅ 任務完成: ${task.id} (耗時: ${executionTime}ms)`);
            this.emit('taskCompleted', completedTask);

        } catch (error) {
            // 任務執行失敗
            const executionTime = Date.now() - startTime;

            console.error(`❌ 任務執行失敗: ${task.id}`, error.message);

            // 更新重試計數
            task.retryCount++;

            if (task.retryCount < this.options.maxRetries) {
                // 重新調度任務
                console.log(`🔁 重新調度任務: ${task.id} (重試 ${task.retryCount}/${this.options.maxRetries})`);

                // 添加延遲後重新加入隊列
                setTimeout(() => {
                    this.taskQueues[task.priority].unshift(task);
                }, this.options.retryDelay * task.retryCount);

            } else {
                // 達到最大重試次數，標記為失敗
                const failedTask = {
                    ...task,
                    error: error.message,
                    executionTime: executionTime,
                    failedAt: new Date(),
                    status: 'failed'
                };

                this.failedTasks.push(failedTask);
                console.error(`💥 任務最終失敗: ${task.id} (重試 ${task.retryCount} 次)`);
                this.emit('taskFailed', failedTask);
            }

            // 更新Agent統計
            this.updateAgentStats(task.agentType, executionTime, false);
            this.runningTasks.delete(task.id);
        }
    }

    /**
     * 執行Agent任務
     */
    async executeAgentTask(task) {
        // 這裡可以實現與Agent系統的整合
        // 目前作為示例返回模擬結果

        const { agentType, method, params = {} } = task;

        // 模擬Agent執行時間
        const executionTime = Math.random() * task.estimatedDuration;
        await this.sleep(executionTime);

        return {
            agentType: agentType,
            method: method,
            params: params,
            success: true,
            timestamp: new Date()
        };
    }

    /**
     * 檢查任務依賴
     */
    checkTaskDependencies(task) {
        if (!task.dependencies || task.dependencies.length === 0) {
            return true;
        }

        for (const dependencyId of task.dependencies) {
            const dependency = this.completedTasks.find(t => t.id === dependencyId);
            if (!dependency || dependency.status !== 'completed') {
                return false;
            }
        }

        return true;
    }

    /**
     * 重新調度任務
     */
    rescheduleTask(task) {
        // 將任務加入隊列尾部，稍後重試
        this.taskQueues[task.priority].push(task);
    }

    /**
     * 等待任務槽位
     */
    async waitForTaskSlot() {
        return new Promise(resolve => {
            const checkSlot = () => {
                if (this.runningTasks.size < this.options.maxConcurrentTasks) {
                    resolve();
                } else {
                    setTimeout(checkSlot, 100);
                }
            };
            checkSlot();
        });
    }

    /**
     * 驗證任務
     */
    validateTask(task) {
        if (!task.id) {
            console.error('❌ 任務缺少ID');
            return false;
        }

        if (!this.options.priorityLevels.includes(task.priority)) {
            console.error(`❌ 無效的任務優先級: ${task.priority}`);
            return false;
        }

        return true;
    }

    /**
     * 生成任務ID
     */
    generateTaskId() {
        return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 更新Agent統計
     */
    updateAgentStats(agentType, executionTime, success) {
        if (!this.agentStats.has(agentType)) {
            this.agentStats.set(agentType, {
                totalTasks: 0,
                completedTasks: 0,
                failedTasks: 0,
                totalExecutionTime: 0,
                averageExecutionTime: 0,
                successRate: 0
            });
        }

        const stats = this.agentStats.get(agentType);
        stats.totalTasks++;
        stats.totalExecutionTime += executionTime;

        if (success) {
            stats.completedTasks++;
        } else {
            stats.failedTasks++;
        }

        stats.averageExecutionTime = stats.totalExecutionTime / stats.totalTasks;
        stats.successRate = stats.completedTasks / stats.totalTasks;

        this.agentStats.set(agentType, stats);
    }

    /**
     * 開始資源監控
     */
    startResourceMonitoring() {
        setInterval(() => {
            this.updateResourceStats();
        }, this.options.resourceMonitoringInterval);
    }

    /**
     * 更新資源統計
     */
    updateResourceStats() {
        const memoryUsage = process.memoryUsage();
        this.resourceStats.memoryUsage = memoryUsage.heapUsed / memoryUsage.heapTotal;

        // 計算任務吞吐量
        const recentTasks = this.completedTasks.filter(task =>
            Date.now() - task.completedAt.getTime() < 60000
        );
        this.resourceStats.taskThroughput = recentTasks.length;

        // 計算平均執行時間
        if (recentTasks.length > 0) {
            const totalTime = recentTasks.reduce((sum, task) => sum + task.executionTime, 0);
            this.resourceStats.averageExecutionTime = totalTime / recentTasks.length;
        }

        // 計算錯誤率
        const recentFailures = this.failedTasks.filter(task =>
            Date.now() - task.failedAt.getTime() < 60000
        );
        const totalRecentTasks = recentTasks.length + recentFailures.length;
        this.resourceStats.errorRate = totalRecentTasks > 0 ?
            recentFailures.length / totalRecentTasks : 0;

        this.emit('resourceStatsUpdated', this.resourceStats);
    }

    /**
     * 獲取調度器狀態
     */
    getStatus() {
        const queueSizes = {};
        for (const [priority, queue] of Object.entries(this.taskQueues)) {
            queueSizes[priority] = queue.length;
        }

        return {
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            runningTasks: this.runningTasks.size,
            queueSizes: queueSizes,
            completedTasks: this.completedTasks.length,
            failedTasks: this.failedTasks.length,
            resourceStats: this.resourceStats,
            agentStats: Object.fromEntries(this.agentStats)
        };
    }

    /**
     * 獲取詳細統計報告
     */
    getDetailedReport() {
        const status = this.getStatus();

        return {
            ...status,
            taskHistory: {
                completed: this.completedTasks.slice(-10), // 最近10個完成的任務
                failed: this.failedTasks.slice(-10) // 最近10個失敗的任務
            },
            performance: {
                averageWaitTime: this.calculateAverageWaitTime(),
                throughputTrend: this.calculateThroughputTrend(),
                errorRateTrend: this.calculateErrorRateTrend()
            }
        };
    }

    /**
     * 計算平均等待時間
     */
    calculateAverageWaitTime() {
        const recentTasks = this.completedTasks.slice(-100);
        if (recentTasks.length === 0) return 0;

        const totalWaitTime = recentTasks.reduce((sum, task) => {
            const waitTime = task.startTime ?
                task.startTime.getTime() - task.scheduledAt.getTime() : 0;
            return sum + waitTime;
        }, 0);

        return totalWaitTime / recentTasks.length;
    }

    /**
     * 計算吞吐量趨勢
     */
    calculateThroughputTrend() {
        // 簡化版本，實際應該計算更詳細的趨勢
        return this.resourceStats.taskThroughput;
    }

    /**
     * 計算錯誤率趨勢
     */
    calculateErrorRateTrend() {
        // 簡化版本，實際應該計算更詳細的趨勢
        return this.resourceStats.errorRate;
    }

    /**
     * 清理已完成的任務歷史
     */
    cleanupTaskHistory(maxAge = 24 * 60 * 60 * 1000) { // 默認24小時
        const cutoffTime = Date.now() - maxAge;

        this.completedTasks = this.completedTasks.filter(task =>
            task.completedAt.getTime() > cutoffTime
        );

        this.failedTasks = this.failedTasks.filter(task =>
            task.failedAt.getTime() > cutoffTime
        );

        console.log('🧹 任務歷史清理完成');
    }

    /**
     * 輔助函數：sleep
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

module.exports = TaskScheduler;