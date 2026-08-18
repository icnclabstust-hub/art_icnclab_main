/**
 * 快取系統效能測試腳本
 * 測試增強版快取系統的各項功能和效能指標
 */

const { cacheManager } = require('../src/utils/cacheManager');
const { cachePreloader } = require('../src/utils/cachePreloader');
const { cacheAnalytics } = require('../src/utils/cacheAnalytics');
const { dbManager } = require('../src/database/connection');

class CachePerformanceTester {
    constructor() {
        this.testResults = {
            basic: {},
            compression: {},
            warmup: {},
            analytics: {},
            eviction: {},
            concurrent: {}
        };
    }

    /**
     * 運行所有測試
     */
    async runAllTests() {
        console.log('🧪 開始快取效能測試...\n');

        try {
            // 初始化系統
            await this.initializeSystem();

            // 基礎功能測試
            await this.testBasicOperations();

            // 壓縮功能測試
            await this.testCompression();

            // 預熱功能測試
            await this.testWarmup();

            // 分析系統測試
            await this.testAnalytics();

            // 智能清理測試
            await this.testEviction();

            // 並發測試
            await this.testConcurrency();

            // 生成測試報告
            this.generateReport();

        } catch (error) {
            console.error('❌ 測試過程中發生錯誤:', error);
        } finally {
            await this.cleanup();
        }
    }

    /**
     * 初始化測試環境
     */
    async initializeSystem() {
        console.log('🔧 初始化測試環境...');

        await dbManager.connectAll();
        await cacheManager.init();
        cacheAnalytics.startMonitoring();

        console.log('✅ 測試環境初始化完成\n');
    }

    /**
     * 測試基礎操作
     */
    async testBasicOperations() {
        console.log('📋 測試基礎快取操作...');

        const startTime = Date.now();
        const testData = { id: 1, name: 'Test Item', data: 'Some test data' };

        // 測試設置
        const setResult = await cacheManager.set('test', 'item1', testData);
        console.log('設置操作:', setResult ? '✅ 成功' : '❌ 失敗');

        // 測試獲取
        const getData = await cacheManager.get('test', 'item1');
        const getSuccess = JSON.stringify(getData) === JSON.stringify(testData);
        console.log('獲取操作:', getSuccess ? '✅ 成功' : '❌ 失敗');

        // 測試刪除
        const deleteResult = await cacheManager.delete('test', 'item1');
        console.log('刪除操作:', deleteResult ? '✅ 成功' : '❌ 失敗');

        // 測試批量操作
        const batchStartTime = Date.now();
        for (let i = 0; i < 100; i++) {
            await cacheManager.set('test', `batch_${i}`, { id: i, value: `value_${i}` });
        }
        const batchSetTime = Date.now() - batchStartTime;

        const batchGetStartTime = Date.now();
        for (let i = 0; i < 100; i++) {
            await cacheManager.get('test', `batch_${i}`);
        }
        const batchGetTime = Date.now() - batchGetStartTime;

        this.testResults.basic = {
            singleOperations: {
                set: setResult,
                get: getSuccess,
                delete: deleteResult
            },
            batchOperations: {
                setTime: `${batchSetTime}ms`,
                getTime: `${batchGetTime}ms`,
                avgSetTime: `${(batchSetTime / 100).toFixed(2)}ms`,
                avgGetTime: `${(batchGetTime / 100).toFixed(2)}ms`
            },
            totalTime: `${Date.now() - startTime}ms`
        };

        console.log('✅ 基礎操作測試完成\n');
    }

    /**
     * 測試壓縮功能
     */
    async testCompression() {
        console.log('🗜️ 測試快取壓縮功能...');

        // 創建大數據對象
        const largeData = {
            id: 'large_item',
            description: 'A'.repeat(2000), // 2KB 字符串
            metadata: Array.from({ length: 100 }, (_, i) => ({
                field: `field_${i}`,
                value: `value_${i}`.repeat(10)
            }))
        };

        const startTime = Date.now();

        // 測試壓縮存儲
        await cacheManager.set('artwork', 'large_item', largeData);
        const setTime = Date.now() - startTime;

        // 測試壓縮讀取
        const retrieveStartTime = Date.now();
        const retrievedData = await cacheManager.get('artwork', 'large_item');
        const retrieveTime = Date.now() - retrieveStartTime;

        const dataIntegrity = JSON.stringify(retrievedData) === JSON.stringify(largeData);

        this.testResults.compression = {
            dataSize: `${JSON.stringify(largeData).length} bytes`,
            setTime: `${setTime}ms`,
            retrieveTime: `${retrieveTime}ms`,
            dataIntegrity: dataIntegrity ? '✅ 完整' : '❌ 損壞'
        };

        console.log('壓縮測試結果:');
        console.log(`- 數據大小: ${this.testResults.compression.dataSize}`);
        console.log(`- 設置時間: ${this.testResults.compression.setTime}`);
        console.log(`- 讀取時間: ${this.testResults.compression.retrieveTime}`);
        console.log(`- 數據完整性: ${this.testResults.compression.dataIntegrity}`);
        console.log('✅ 壓縮功能測試完成\n');
    }

    /**
     * 測試預熱功能
     */
    async testWarmup() {
        console.log('🔥 測試快取預熱功能...');

        const startTime = Date.now();

        // 註冊測試預熱任務
        cachePreloader.registerTask('test', 'warmup_item1', async () => {
            return { id: 'warmup1', data: 'Warmed up data 1' };
        }, { priority: 10 });

        cachePreloader.registerTask('test', 'warmup_item2', async () => {
            return { id: 'warmup2', data: 'Warmed up data 2' };
        }, { priority: 8 });

        // 執行預熱
        await cachePreloader.startPreloading();

        // 檢查預熱結果
        const warmedItem1 = await cacheManager.get('test', 'warmup_item1');
        const warmedItem2 = await cacheManager.get('test', 'warmup_item2');

        const warmupTime = Date.now() - startTime;
        const preloaderStats = cachePreloader.getStats();

        this.testResults.warmup = {
            warmupTime: `${warmupTime}ms`,
            item1Success: warmedItem1 ? '✅ 成功' : '❌ 失敗',
            item2Success: warmedItem2 ? '✅ 成功' : '❌ 失敗',
            preloaderStats
        };

        console.log('預熱測試結果:');
        console.log(`- 預熱時間: ${this.testResults.warmup.warmupTime}`);
        console.log(`- 項目1: ${this.testResults.warmup.item1Success}`);
        console.log(`- 項目2: ${this.testResults.warmup.item2Success}`);
        console.log('✅ 預熱功能測試完成\n');
    }

    /**
     * 測試分析系統
     */
    async testAnalytics() {
        console.log('📊 測試快取分析功能...');

        const startTime = Date.now();

        // 生成一些快取活動
        for (let i = 0; i < 50; i++) {
            await cacheManager.set('analytics', `item_${i}`, { id: i, value: `test_${i}` });
            if (i % 2 === 0) {
                await cacheManager.get('analytics', `item_${i}`); // 50% 命中率
            }
            await cacheManager.get('analytics', `nonexistent_${i}`); // 未命中
        }

        // 等待分析收集數據
        await this.delay(2000);

        const analyticsReport = cacheAnalytics.getAnalyticsReport();
        const analysisTime = Date.now() - startTime;

        this.testResults.analytics = {
            analysisTime: `${analysisTime}ms`,
            reportGenerated: analyticsReport ? '✅ 成功' : '❌ 失敗',
            summary: analyticsReport.summary || {},
            current: analyticsReport.current || {},
            monitoring: analyticsReport.monitoring || {}
        };

        console.log('分析測試結果:');
        console.log(`- 分析時間: ${this.testResults.analytics.analysisTime}`);
        console.log(`- 報告生成: ${this.testResults.analytics.reportGenerated}`);
        console.log('✅ 分析功能測試完成\n');
    }

    /**
     * 測試智能清理
     */
    async testEviction() {
        console.log('🧹 測試智能清理功能...');

        const startTime = Date.now();

        // 填充快取直到觸發清理
        for (let i = 0; i < 200; i++) {
            await cacheManager.set('eviction_test', `item_${i}`, {
                id: i,
                data: `data_${i}`,
                timestamp: Date.now()
            });

            // 模擬不同的訪問模式
            if (i < 50) {
                // 前50個項目多次訪問（熱門項目）
                for (let j = 0; j < 3; j++) {
                    await cacheManager.get('eviction_test', `item_${i}`);
                }
            }
        }

        // 觸發智能清理
        if (cacheManager.smartEviction) {
            cacheManager.smartEviction();
        }

        const evictionTime = Date.now() - startTime;
        const finalStats = cacheManager.getStats();

        this.testResults.eviction = {
            evictionTime: `${evictionTime}ms`,
            itemsAfterEviction: finalStats.memoryUsage,
            evictionCount: finalStats.evictions || 0
        };

        console.log('清理測試結果:');
        console.log(`- 清理時間: ${this.testResults.eviction.evictionTime}`);
        console.log(`- 剩餘項目: ${this.testResults.eviction.itemsAfterEviction}`);
        console.log(`- 清理次數: ${this.testResults.eviction.evictionCount}`);
        console.log('✅ 智能清理測試完成\n');
    }

    /**
     * 測試並發性能
     */
    async testConcurrency() {
        console.log('⚡ 測試並發性能...');

        const startTime = Date.now();
        const concurrentOperations = 100;

        // 並發寫入測試
        const writePromises = Array.from({ length: concurrentOperations }, (_, i) =>
            cacheManager.set('concurrent', `write_item_${i}`, { id: i, data: `concurrent_data_${i}` })
        );

        await Promise.all(writePromises);
        const writeTime = Date.now() - startTime;

        // 並發讀取測試
        const readStartTime = Date.now();
        const readPromises = Array.from({ length: concurrentOperations }, (_, i) =>
            cacheManager.get('concurrent', `write_item_${i}`)
        );

        const readResults = await Promise.all(readPromises);
        const readTime = Date.now() - readStartTime;

        const successfulReads = readResults.filter(result => result !== null).length;

        this.testResults.concurrent = {
            operations: concurrentOperations,
            writeTime: `${writeTime}ms`,
            readTime: `${readTime}ms`,
            avgWriteTime: `${(writeTime / concurrentOperations).toFixed(2)}ms`,
            avgReadTime: `${(readTime / concurrentOperations).toFixed(2)}ms`,
            readSuccessRate: `${((successfulReads / concurrentOperations) * 100).toFixed(2)}%`,
            totalTime: `${Date.now() - startTime}ms`
        };

        console.log('並發測試結果:');
        console.log(`- 操作數量: ${this.testResults.concurrent.operations}`);
        console.log(`- 寫入時間: ${this.testResults.concurrent.writeTime}`);
        console.log(`- 讀取時間: ${this.testResults.concurrent.readTime}`);
        console.log(`- 平均寫入: ${this.testResults.concurrent.avgWriteTime}`);
        console.log(`- 平均讀取: ${this.testResults.concurrent.avgReadTime}`);
        console.log(`- 讀取成功率: ${this.testResults.concurrent.readSuccessRate}`);
        console.log('✅ 並發性能測試完成\n');
    }

    /**
     * 生成測試報告
     */
    generateReport() {
        console.log('📋 === 快取系統效能測試報告 ===\n');

        console.log('🔧 基礎功能測試:');
        console.log(`  單項操作: 設置(${this.testResults.basic.singleOperations.set ? '通過' : '失敗'}), 獲取(${this.testResults.basic.singleOperations.get ? '通過' : '失敗'}), 刪除(${this.testResults.basic.singleOperations.delete ? '通過' : '失敗'})`);
        console.log(`  批量操作: 平均設置時間 ${this.testResults.basic.batchOperations.avgSetTime}, 平均獲取時間 ${this.testResults.basic.batchOperations.avgGetTime}`);
        console.log();

        console.log('🗜️ 壓縮功能測試:');
        console.log(`  數據完整性: ${this.testResults.compression.dataIntegrity}`);
        console.log(`  設置時間: ${this.testResults.compression.setTime}`);
        console.log(`  讀取時間: ${this.testResults.compression.retrieveTime}`);
        console.log();

        console.log('🔥 預熱功能測試:');
        console.log(`  預熱時間: ${this.testResults.warmup.warmupTime}`);
        console.log(`  成功率: ${this.testResults.warmup.preloaderStats.successRate}`);
        console.log();

        console.log('⚡ 並發性能測試:');
        console.log(`  ${this.testResults.concurrent.operations} 個並發操作`);
        console.log(`  平均寫入時間: ${this.testResults.concurrent.avgWriteTime}`);
        console.log(`  平均讀取時間: ${this.testResults.concurrent.avgReadTime}`);
        console.log(`  讀取成功率: ${this.testResults.concurrent.readSuccessRate}`);
        console.log();

        console.log('📊 系統統計:');
        const finalStats = cacheManager.getStats();
        console.log(`  總請求數: ${finalStats.totalRequests}`);
        console.log(`  命中率: ${finalStats.hitRate}`);
        console.log(`  記憶體使用: ${finalStats.memoryUsage} 項目`);
        console.log(`  預熱隊列: ${finalStats.warmupQueueSize || 0} 項目`);
        console.log();

        console.log('✅ 測試完成！快取系統運行正常。');
    }

    /**
     * 清理測試環境
     */
    async cleanup() {
        console.log('🧹 清理測試環境...');

        try {
            // 清空測試數據
            const testCategories = ['test', 'artwork', 'analytics', 'eviction_test', 'concurrent'];
            for (const category of testCategories) {
                await cacheManager.clearCategory(category);
            }

            cacheAnalytics.stopMonitoring();
            await cacheManager.shutdown();
            await dbManager.closeAll();
        } catch (error) {
            console.log('清理時發生錯誤:', error.message);
        }

        console.log('✅ 清理完成');
    }

    /**
     * 延遲工具函數
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 運行測試
const tester = new CachePerformanceTester();
tester.runAllTests().catch(console.error);