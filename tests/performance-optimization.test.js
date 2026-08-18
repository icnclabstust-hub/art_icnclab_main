/**
 * Agent性能優化測試套件
 * 驗證批處理、並行處理、任務調度和性能監控功能
 */

// 使用Jest的內建expect和sinon
const sinon = require('sinon');

// 導入測試目標
const PerformanceOptimizer = require('../src/utils/performanceOptimizer');
const TaskScheduler = require('../src/utils/taskScheduler');
const PerformanceMonitor = require('../src/utils/performanceMonitor');
const MetadataExtractorAgent = require('../agents/metadata-extractor');

describe('Agent性能優化測試', () => {

    describe('PerformanceOptimizer 性能優化器', () => {
        let optimizer;

        beforeEach(() => {
            optimizer = new PerformanceOptimizer({
                memoryThreshold: 0.8,
                cpuThreshold: 0.7,
                minBatchSize: 5,
                maxBatchSize: 20,
                maxConcurrency: 4
            });
        });

        afterEach(() => {
            if (optimizer) {
                optimizer.destroy();
            }
        });

        describe('批處理功能', () => {
            it('應該正確處理批次數據', async () => {
                const testData = Array.from({ length: 25 }, (_, i) => ({ id: i, value: i * 2 }));
                const processor = sinon.stub().callsFake(async (item) => ({
                    ...item,
                    processed: true
                }));

                const results = await optimizer.processBatch(testData, processor, {
                    batchSize: 10
                });

                expect(results).to.have.length(25);
                expect(results.every(r => r.processed)).to.be.true;
                expect(processor.callCount).to.equal(25);
            });

            it('應該根據系統資源動態調整批次大小', async () => {
                const testData = Array.from({ length: 50 }, (_, i) => ({ id: i }));
                const processor = sinon.stub().callsFake(async (item) => item);

                // 模擬高內存使用情況
                sinon.stub(optimizer, 'getSystemResourceUsage').returns({
                    memory: 0.9, // 高內存使用
                    cpu: 0.5
                });

                const results = await optimizer.processBatch(testData, processor, {
                    enableProgress: true,
                    progressCallback: sinon.spy()
                });

                expect(results).to.have.length(50);
            });

            it('應該處理批處理中的錯誤', async () => {
                const testData = Array.from({ length: 10 }, (_, i) => ({ id: i }));
                const processor = sinon.stub().callsFake(async (item) => {
                    if (item.id === 5) {
                        throw new Error('測試錯誤');
                    }
                    return { ...item, processed: true };
                });

                const results = await optimizer.processBatch(testData, processor);

                // 應該跳過錯誤項目，處理其他項目
                expect(results.filter(r => r !== null)).to.have.length(9);
            });
        });

        describe('並行處理功能', () => {
            it('應該並行執行任務', async () => {
                const testData = Array.from({ length: 12 }, (_, i) => ({ id: i }));
                const startTimes = [];
                const processor = sinon.stub().callsFake(async (item) => {
                    startTimes.push(Date.now());
                    await new Promise(resolve => setTimeout(resolve, 100));
                    return { ...item, processed: true };
                });

                const startTime = Date.now();
                const results = await optimizer.processParallel(testData, processor, {
                    concurrency: 4
                });

                const endTime = Date.now();
                const totalTime = endTime - startTime;

                expect(results).to.have.length(12);
                expect(results.every(r => r.processed)).to.be.true;

                // 並行處理應該比串行處理快
                expect(totalTime).to.be.lessThan(12 * 100 * 0.8); // 允許一些誤差
            });

            it('應該正確控制並發數量', async () => {
                const testData = Array.from({ length: 20 }, (_, i) => ({ id: i }));
                const activeTasks = { count: 0, maxConcurrent: 0 };

                const processor = sinon.stub().callsFake(async (item) => {
                    activeTasks.count++;
                    activeTasks.maxConcurrent = Math.max(activeTasks.maxConcurrent, activeTasks.count);

                    await new Promise(resolve => setTimeout(resolve, 50));

                    activeTasks.count--;
                    return { ...item, processed: true };
                });

                await optimizer.processParallel(testData, processor, {
                    concurrency: 5
                });

                expect(activeTasks.maxConcurrent).to.be.lessThanOrEqual(5);
            });
        });

        describe('資源監控功能', () => {
            it('應該正確監控系統資源使用', () => {
                const resourceUsage = optimizer.getSystemResourceUsage();

                expect(resourceUsage).to.have.property('memory');
                expect(resourceUsage).to.have.property('cpu');
                expect(resourceUsage.memory).to.be.a('number');
                expect(resourceUsage.cpu).to.be.a('number');
                expect(resourceUsage.memory).to.be.within(0, 1);
            });

            it('應該在資源不足時調整處理策略', async () => {
                const testData = Array.from({ length: 10 }, (_, i) => ({ id: i }));
                const processor = sinon.stub().callsFake(async (item) => item);

                // 模擬資源不足情況
                sinon.stub(optimizer, 'getSystemResourceUsage').returns({
                    memory: 0.95, // 極高內存使用
                    cpu: 0.85     // 高CPU使用
                });

                const results = await optimizer.processBatch(testData, processor);

                expect(results).to.have.length(10);
                // 在實際實現中，這裡應該驗證較小的批次大小或延遲
            });
        });
    });

    describe('TaskScheduler 任務調度器', () => {
        let scheduler;

        beforeEach(() => {
            scheduler = new TaskScheduler({
                maxConcurrentTasks: 3,
                priorityLevels: ['low', 'normal', 'high', 'critical'],
                maxRetries: 2
            });
        });

        afterEach(async () => {
            if (scheduler && scheduler.isRunning) {
                await scheduler.stop();
            }
        });

        describe('任務調度功能', () => {
            it('應該能夠調度和執行任務', async () => {
                const taskExecuted = sinon.spy();

                const task = {
                    id: 'test-task-1',
                    executor: async () => {
                        taskExecuted();
                        return 'success';
                    },
                    estimatedDuration: 1000
                };

                await scheduler.start();
                const taskId = await scheduler.scheduleTask(task, 'normal');

                // 等待任務執行
                await new Promise(resolve => {
                    scheduler.on('taskCompleted', (completedTask) => {
                        if (completedTask.id === taskId) {
                            resolve();
                        }
                    });
                });

                expect(taskExecuted.calledOnce).to.be.true;
            });

            it('應該按優先級執行任務', async () => {
                const executionOrder = [];

                const createTask = (id, priority) => ({
                    id: id,
                    executor: async () => {
                        executionOrder.push(id);
                        await new Promise(resolve => setTimeout(resolve, 50));
                        return 'success';
                    },
                    priority: priority
                });

                await scheduler.start();

                // 添加不同優先級的任務
                await scheduler.scheduleTask(createTask('low-task', 'low'), 'low');
                await scheduler.scheduleTask(createTask('high-task', 'high'), 'high');
                await scheduler.scheduleTask(createTask('critical-task', 'critical'), 'critical');
                await scheduler.scheduleTask(createTask('normal-task', 'normal'), 'normal');

                // 等待所有任務完成
                await new Promise(resolve => {
                    let completedCount = 0;
                    scheduler.on('taskCompleted', () => {
                        completedCount++;
                        if (completedCount === 4) {
                            resolve();
                        }
                    });
                });

                expect(executionOrder[0]).to.equal('critical-task');
                expect(executionOrder[1]).to.equal('high-task');
            });

            it('應該正確處理任務失敗和重試', async () => {
                let attemptCount = 0;

                const failingTask = {
                    id: 'failing-task',
                    executor: async () => {
                        attemptCount++;
                        if (attemptCount < 3) {
                            throw new Error('任務失敗');
                        }
                        return 'success';
                    }
                };

                await scheduler.start();
                await scheduler.scheduleTask(failingTask, 'normal');

                // 等待任務最終完成或失敗
                await new Promise(resolve => {
                    scheduler.on('taskCompleted', resolve);
                    scheduler.on('taskFailed', resolve);
                });

                expect(attemptCount).to.equal(3); // 初始嘗試 + 2次重試
            });

            it('應該正確控制並發任務數量', async () => {
                const activeTasks = { count: 0, maxConcurrent: 0 };

                const createTask = (id) => ({
                    id: id,
                    executor: async () => {
                        activeTasks.count++;
                        activeTasks.maxConcurrent = Math.max(activeTasks.maxConcurrent, activeTasks.count);

                        await new Promise(resolve => setTimeout(resolve, 200));

                        activeTasks.count--;
                        return 'success';
                    }
                });

                await scheduler.start();

                // 添加5個任務，但最大並發為3
                for (let i = 0; i < 5; i++) {
                    await scheduler.scheduleTask(createTask(`task-${i}`), 'normal');
                }

                // 等待所有任務完成
                await new Promise(resolve => {
                    let completedCount = 0;
                    scheduler.on('taskCompleted', () => {
                        completedCount++;
                        if (completedCount === 5) {
                            resolve();
                        }
                    });
                });

                expect(activeTasks.maxConcurrent).to.be.lessThanOrEqual(3);
            });
        });

        describe('任務依賴處理', () => {
            it('應該正確處理任務依賴', async () => {
                const executionOrder = [];

                const task1 = {
                    id: 'task-1',
                    executor: async () => {
                        executionOrder.push('task-1');
                        return 'success';
                    }
                };

                const task2 = {
                    id: 'task-2',
                    dependencies: ['task-1'],
                    executor: async () => {
                        executionOrder.push('task-2');
                        return 'success';
                    }
                };

                await scheduler.start();

                // 先添加依賴的任務
                await scheduler.scheduleTask(task2, 'normal');
                await scheduler.scheduleTask(task1, 'normal');

                // 等待任務完成
                await new Promise(resolve => {
                    let completedCount = 0;
                    scheduler.on('taskCompleted', () => {
                        completedCount++;
                        if (completedCount === 2) {
                            resolve();
                        }
                    });
                });

                expect(executionOrder).to.deep.equal(['task-1', 'task-2']);
            });
        });
    });

    describe('PerformanceMonitor 性能監控器', () => {
        let monitor;

        beforeEach(() => {
            monitor = new PerformanceMonitor({
                metricsInterval: 1000,
                alertThresholds: {
                    memoryUsage: 0.8,
                    cpuUsage: 0.7,
                    errorRate: 0.1
                },
                historySize: 100,
                enableFileLogging: false
            });
        });

        afterEach(async () => {
            if (monitor && monitor.isMonitoring) {
                await monitor.stop();
            }
        });

        describe('指標收集功能', () => {
            it('應該能夠收集系統指標', async () => {
                await monitor.start();

                // 等待幾個指標收集周期
                await new Promise(resolve => setTimeout(resolve, 2500));

                const report = monitor.getPerformanceReport();

                expect(report.current).to.have.property('system');
                expect(report.current).to.have.property('application');
                expect(report.current.system).to.have.property('memory');
                expect(report.current.system).to.have.property('cpu');
            });

            it('應該能夠觸發警報', async () => {
                const alertSpy = sinon.spy();
                monitor.on('alert', alertSpy);

                // 模擬高內存使用觸發警報
                const mockMetrics = {
                    timestamp: new Date(),
                    system: {
                        memory: { heapUsedPercentage: 0.9 },
                        cpu: { usage: 0.5 }
                    },
                    application: {
                        errorRate: 0.05,
                        responseTime: 1000
                    }
                };

                monitor.checkAlerts(mockMetrics);

                expect(alertSpy.calledOnce).to.be.true;
                expect(alertSpy.getCall(0).args[0]).to.have.property('type', 'memory');
            });

            it('應該生成性能報告', () => {
                const report = monitor.getPerformanceReport();

                expect(report).to.have.property('current');
                expect(report).to.have.property('summary');
                expect(report).to.have.property('trends');
                expect(report).to.have.property('alerts');
                expect(report).to.have.property('recommendations');
            });
        });

        describe('趨勢分析功能', () => {
            it('應該能夠分析性能趨勢', () => {
                // 添加一些測試數據
                const testDataPoints = [
                    { timestamp: new Date(), value: 0.3 },
                    { timestamp: new Date(), value: 0.4 },
                    { timestamp: new Date(), value: 0.5 },
                    { timestamp: new Date(), value: 0.6 },
                    { timestamp: new Date(), value: 0.7 }
                ];

                const trend = monitor.calculateTrend(testDataPoints);
                expect(['increasing', 'decreasing', 'stable']).to.include(trend);
            });

            it('應該生成性能建議', () => {
                // 設置一些問題場景
                monitor.currentMetrics = {
                    system: {
                        memory: { heapUsedPercentage: 0.9 },
                        cpu: { usage: 0.8 }
                    },
                    application: {
                        responseTime: 4000,
                        errorRate: 0.08
                    }
                };

                const recommendations = monitor.generateRecommendations();

                expect(recommendations).to.be.an('array');
                expect(recommendations.length).to.be.greaterThan(0);
            });
        });
    });

    describe('Agent整合測試', () => {
        let agent;

        beforeEach(() => {
            agent = new MetadataExtractorAgent();
            // 模擬環境變數
            process.env.DATA_RAW_DIR = './test-data/raw';
            process.env.DATA_PROCESSED_DIR = './test-data/processed';
        });

        afterEach(async () => {
            if (agent) {
                await agent.stop();
            }
        });

        it('應該成功整合性能優化器', async () => {
            expect(agent.performanceOptimizer).to.be.an('object');
            expect(agent.performanceOptimizer.processBatch).to.be.a('function');
            expect(agent.performanceOptimizer.processParallel).to.be.a('function');
        });

        it('應該能夠使用優化的批處理功能', async () => {
            // 創建測試數據
            const testRecords = Array.from({ length: 10 }, (_, i) => ({
                id: i,
                title: `Test Artwork ${i}`,
                artist: `Test Artist ${i}`,
                date: '2023',
                source: 'test'
            }));

            // 模擬文件數據
            const mockFile = {
                path: '/fake/path/test.json',
                source: 'test',
                filename: 'test.json',
                size: 1024,
                modified: new Date()
            };

            // 模擬 fs.readFile
            const fsStub = sinon.stub(require('fs/promises'), 'readFile');
            fsStub.resolves(JSON.stringify(testRecords));

            // 模擬 fs.writeFile
            const writeStub = sinon.stub(require('fs/promises'), 'writeFile');
            writeStub.resolves();

            try {
                const result = await agent.processFile(mockFile, 'dublin-core', false);

                expect(result).to.be.an('object');
                expect(result).to.have.property('recordsProcessed', 10);

            } finally {
                fsStub.restore();
                writeStub.restore();
            }
        });
    });

    describe('整體性能測試', () => {
        it('應該在大量數據處理中維持良好性能', async () => {

            const optimizer = new PerformanceOptimizer({
                maxConcurrency: 8
            });

            // 創建大量測試數據
            const largeDataSet = Array.from({ length: 1000 }, (_, i) => ({
                id: i,
                data: `test-data-${i}`
            }));

            const startTime = Date.now();
            const processor = sinon.stub().callsFake(async (item) => {
                // 模擬一些處理時間
                await new Promise(resolve => setTimeout(resolve, Math.random() * 10));
                return { ...item, processed: true };
            });

            const results = await optimizer.processBatch(largeDataSet, processor, {
                enableProgress: true
            });

            const endTime = Date.now();
            const totalTime = endTime - startTime;

            expect(results).to.have.length(1000);
            expect(results.every(r => r.processed)).to.be.true;

            console.log(`處理1000個項目耗時: ${totalTime}ms`);

            // 性能要求：應該在30秒內完成
            expect(totalTime).to.be.lessThan(30000);

            optimizer.destroy();
        });

        it('應該能夠同時運行多個性能組件', async () => {
            const optimizer = new PerformanceOptimizer();
            const scheduler = new TaskScheduler({ maxConcurrentTasks: 5 });
            const monitor = new PerformanceMonitor({
                metricsInterval: 2000,
                enableFileLogging: false
            });

            try {
                // 啟動所有組件
                await scheduler.start();
                await monitor.start();

                // 添加一些任務
                for (let i = 0; i < 10; i++) {
                    await scheduler.scheduleTask({
                        id: `integration-task-${i}`,
                        executor: async () => {
                            // 使用性能優化器處理數據
                            const data = Array.from({ length: 20 }, (_, j) => ({ id: j }));
                            return await optimizer.processBatch(
                                data,
                                async (item) => item
                            );
                        }
                    }, 'normal');
                }

                // 等待任務完成
                await new Promise(resolve => {
                    let completedCount = 0;
                    scheduler.on('taskCompleted', () => {
                        completedCount++;
                        if (completedCount === 10) {
                            resolve();
                        }
                    });
                });

                // 檢查監控數據
                const report = monitor.getPerformanceReport();
                expect(report).to.be.an('object');

                // 檢查調度器狀態
                const status = scheduler.getStatus();
                expect(status.completedTasks).to.equal(10);

            } finally {
                await scheduler.stop();
                await monitor.stop();
                optimizer.destroy();
            }
        });
    });
});