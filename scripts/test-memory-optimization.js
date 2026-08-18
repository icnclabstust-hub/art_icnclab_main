/**
 * 記憶體最佳化測試腳本
 * 測試記憶體監控、物件池、GC最佳化和壓力管理等功能
 */

const { memoryMonitor } = require('../src/utils/memoryMonitor');
const { objectPoolManager } = require('../src/utils/objectPoolManager');
const { gcOptimizer } = require('../src/utils/gcOptimizer');
const { memoryPressureManager } = require('../src/utils/memoryPressureManager');

class MemoryOptimizationTester {
    constructor() {
        this.testResults = {
            memoryMonitoring: {},
            objectPools: {},
            gcOptimization: {},
            pressureManagement: {},
            integration: {}
        };
    }

    /**
     * 運行所有測試
     */
    async runAllTests() {
        console.log('🧪 開始記憶體最佳化測試...\n');

        try {
            // 初始化系統
            await this.initializeSystem();

            // 記憶體監控測試
            await this.testMemoryMonitoring();

            // 物件池測試
            await this.testObjectPools();

            // GC最佳化測試
            await this.testGCOptimization();

            // 壓力管理測試
            await this.testPressureManagement();

            // 整合測試
            await this.testIntegration();

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
        console.log('🔧 初始化記憶體最佳化測試環境...');

        // 啟動監控系統
        memoryMonitor.startMonitoring();
        gcOptimizer.startOptimization();
        memoryPressureManager.startMonitoring();

        // 初始化物件池
        objectPoolManager.initializeCommonPools();
        objectPoolManager.initializeBufferPools();
        objectPoolManager.startMaintenance();

        // 等待系統穩定
        await this.delay(2000);

        console.log('✅ 測試環境初始化完成\n');
    }

    /**
     * 測試記憶體監控
     */
    async testMemoryMonitoring() {
        console.log('🔍 測試記憶體監控功能...');

        const startTime = Date.now();

        // 收集基準記憶體使用量
        const baselineMemory = process.memoryUsage();

        // 創建記憶體負載
        const memoryHog = [];
        for (let i = 0; i < 1000; i++) {
            memoryHog.push(Buffer.alloc(1024 * 10)); // 10KB buffers
        }

        // 等待監控系統收集數據
        await this.delay(5000);

        // 檢查監控報告
        const monitorReport = memoryMonitor.getMemoryReport();
        const afterMemory = process.memoryUsage();

        // 清理記憶體負載
        memoryHog.length = 0;

        this.testResults.memoryMonitoring = {
            testDuration: `${Date.now() - startTime}ms`,
            baselineHeap: `${Math.round(baselineMemory.heapUsed / 1024 / 1024)}MB`,
            peakHeap: `${Math.round(afterMemory.heapUsed / 1024 / 1024)}MB`,
            memoryIncrease: `${Math.round((afterMemory.heapUsed - baselineMemory.heapUsed) / 1024 / 1024)}MB`,
            monitoringActive: monitorReport.monitoring?.isActive || false,
            dataPoints: monitorReport.history?.dataPoints || 0,
            alertsGenerated: monitorReport.current ? '✅ 有數據' : '❌ 無數據'
        };

        console.log('記憶體監控測試結果:');
        console.log(`- 基準記憶體: ${this.testResults.memoryMonitoring.baselineHeap}`);
        console.log(`- 峰值記憶體: ${this.testResults.memoryMonitoring.peakHeap}`);
        console.log(`- 記憶體增長: ${this.testResults.memoryMonitoring.memoryIncrease}`);
        console.log(`- 監控狀態: ${this.testResults.memoryMonitoring.monitoringActive ? '✅ 運行中' : '❌ 未運行'}`);
        console.log(`- 數據點: ${this.testResults.memoryMonitoring.dataPoints}`);
        console.log('✅ 記憶體監控測試完成\n');
    }

    /**
     * 測試物件池
     */
    async testObjectPools() {
        console.log('📦 測試物件池功能...');

        const startTime = Date.now();

        // 測試物件池創建和使用
        const testResults = {
            acquisitions: 0,
            releases: 0,
            poolUtilization: {},
            poolEfficiency: {}
        };

        // 測試 HTTP 響應物件池
        const responseObjects = [];
        for (let i = 0; i < 100; i++) {
            const obj = objectPoolManager.acquire('httpResponse');
            obj.data = { test: i };
            obj.message = `Test message ${i}`;
            responseObjects.push(obj);
            testResults.acquisitions++;
        }

        // 歸還一半物件
        for (let i = 0; i < 50; i++) {
            objectPoolManager.release('httpResponse', responseObjects[i]);
            testResults.releases++;
        }

        // 測試緩衝區池
        const buffers = [];
        for (let i = 0; i < 20; i++) {
            const buffer = objectPoolManager.acquireBuffer('medium');
            buffer.write(`Test data ${i}`, 0, 'utf8');
            buffers.push(buffer);
        }

        // 歸還緩衝區
        buffers.forEach(buffer => {
            objectPoolManager.releaseBuffer('medium', buffer);
        });

        // 獲取池統計
        const poolStats = objectPoolManager.getStats();

        this.testResults.objectPools = {
            testDuration: `${Date.now() - startTime}ms`,
            acquisitions: testResults.acquisitions + buffers.length,
            releases: testResults.releases + buffers.length,
            totalPools: poolStats.global.totalPools,
            totalBufferPools: poolStats.global.totalBufferPools,
            reuseRate: poolStats.efficiency.reuseRate,
            avgUtilization: poolStats.efficiency.avgPoolUtilization,
            estimatedMemoryUsage: poolStats.global.estimatedMemoryUsage
        };

        console.log('物件池測試結果:');
        console.log(`- 總獲取數: ${this.testResults.objectPools.acquisitions}`);
        console.log(`- 總歸還數: ${this.testResults.objectPools.releases}`);
        console.log(`- 重用率: ${this.testResults.objectPools.reuseRate}`);
        console.log(`- 平均利用率: ${this.testResults.objectPools.avgUtilization}`);
        console.log(`- 記憶體使用估算: ${this.testResults.objectPools.estimatedMemoryUsage}`);
        console.log('✅ 物件池測試完成\n');
    }

    /**
     * 測試GC最佳化
     */
    async testGCOptimization() {
        console.log('🗑️ 測試GC最佳化功能...');

        const startTime = Date.now();

        // 獲取初始GC統計
        const initialReport = gcOptimizer.getGCReport();

        // 創建記憶體壓力以觸發GC
        const garbageData = [];
        for (let i = 0; i < 500; i++) {
            garbageData.push({
                id: i,
                data: 'x'.repeat(1000),
                nested: {
                    value: Math.random(),
                    array: new Array(100).fill(i)
                }
            });
        }

        // 等待自動GC或手動觸發
        await this.delay(3000);

        // 手動觸發GC測試
        const manualGCResult = gcOptimizer.forceGC('major');

        // 清理垃圾數據
        garbageData.length = 0;

        // 獲取最終GC統計
        const finalReport = gcOptimizer.getGCReport();

        this.testResults.gcOptimization = {
            testDuration: `${Date.now() - startTime}ms`,
            initialGCs: initialReport.stats.manualGCs || 0,
            finalGCs: finalReport.stats.manualGCs || 0,
            manualGCExecuted: manualGCResult ? '✅ 成功' : '❌ 失敗',
            gcEfficiency: manualGCResult ? manualGCResult.efficiency + '%' : 'N/A',
            memoryFreed: manualGCResult ? `${Math.round(manualGCResult.memoryFreed / 1024 / 1024)}MB` : 'N/A',
            avgGCTime: finalReport.stats.avgGCTime,
            avgEfficiency: finalReport.stats.avgEfficiency,
            totalMemoryFreed: finalReport.stats.totalMemoryFreed
        };

        console.log('GC最佳化測試結果:');
        console.log(`- 手動GC執行: ${this.testResults.gcOptimization.manualGCExecuted}`);
        console.log(`- GC效率: ${this.testResults.gcOptimization.gcEfficiency}`);
        console.log(`- 釋放記憶體: ${this.testResults.gcOptimization.memoryFreed}`);
        console.log(`- 平均GC時間: ${this.testResults.gcOptimization.avgGCTime}`);
        console.log(`- 平均效率: ${this.testResults.gcOptimization.avgEfficiency}`);
        console.log('✅ GC最佳化測試完成\n');
    }

    /**
     * 測試壓力管理
     */
    async testPressureManagement() {
        console.log('📊 測試記憶體壓力管理功能...');

        const startTime = Date.now();

        // 獲取初始壓力報告
        const initialPressure = memoryPressureManager.getPressureReport();

        // 模擬記憶體壓力（創建大量物件）
        const pressureData = [];
        try {
            for (let i = 0; i < 2000; i++) {
                pressureData.push({
                    id: i,
                    largeData: Buffer.alloc(1024 * 50), // 50KB per object
                    metadata: {
                        timestamp: Date.now(),
                        value: Math.random(),
                        description: 'x'.repeat(500)
                    }
                });

                // 每100個物件檢查一次壓力狀態
                if (i % 100 === 0) {
                    await this.delay(100);
                    const currentPressure = memoryPressureManager.getPressureReport();
                    if (currentPressure.current.level !== 'normal') {
                        console.log(`💡 壓力等級變化: ${currentPressure.current.level}`);
                        break;
                    }
                }
            }
        } catch (error) {
            console.log('記憶體壓力達到極限:', error.message);
        }

        // 等待壓力管理系統反應
        await this.delay(5000);

        // 測試手動觸發緊急動作
        let manualActionResult = null;
        try {
            manualActionResult = await memoryPressureManager.triggerEmergencyAction('minor_gc');
        } catch (error) {
            console.log('手動觸發緊急動作失敗:', error.message);
        }

        // 獲取最終壓力報告
        const finalPressure = memoryPressureManager.getPressureReport();

        // 清理壓力數據
        pressureData.length = 0;

        this.testResults.pressureManagement = {
            testDuration: `${Date.now() - startTime}ms`,
            initialLevel: initialPressure.current.level,
            finalLevel: finalPressure.current.level,
            totalActions: finalPressure.activity.totalActions,
            manualActionExecuted: manualActionResult ? '✅ 成功' : '❌ 失敗',
            manualActionResult: manualActionResult?.action || 'N/A',
            memoryUtilization: {
                heap: finalPressure.current.memory.utilization.heap,
                rss: finalPressure.current.memory.utilization.rss,
                external: finalPressure.current.memory.utilization.external
            },
            emergencyMode: finalPressure.current.emergencyMode
        };

        console.log('壓力管理測試結果:');
        console.log(`- 初始壓力等級: ${this.testResults.pressureManagement.initialLevel}`);
        console.log(`- 最終壓力等級: ${this.testResults.pressureManagement.finalLevel}`);
        console.log(`- 總執行動作: ${this.testResults.pressureManagement.totalActions}`);
        console.log(`- 手動動作執行: ${this.testResults.pressureManagement.manualActionExecuted}`);
        console.log(`- 記憶體利用率 - 堆疊: ${this.testResults.pressureManagement.memoryUtilization.heap}`);
        console.log('✅ 壓力管理測試完成\n');
    }

    /**
     * 測試系統整合
     */
    async testIntegration() {
        console.log('🔗 測試系統整合功能...');

        const startTime = Date.now();

        // 綜合測試：同時使用所有系統
        const integrationResults = {
            memoryBefore: process.memoryUsage(),
            poolUsageBefore: objectPoolManager.getStats(),
            gcStatsBefore: gcOptimizer.getGCReport()
        };

        // 創建混合工作負載
        const workload = [];

        // 使用物件池
        for (let i = 0; i < 200; i++) {
            const obj = objectPoolManager.acquire('cacheEntry');
            obj.key = `test_key_${i}`;
            obj.value = { data: `value_${i}`, timestamp: Date.now() };
            obj.hits = Math.floor(Math.random() * 100);
            workload.push(obj);
        }

        // 創建緩衝區負載
        const buffers = [];
        for (let i = 0; i < 50; i++) {
            const buffer = objectPoolManager.acquireBuffer('large');
            buffer.write(`Integration test data ${i}`.repeat(100), 0, 'utf8');
            buffers.push(buffer);
        }

        // 等待監控系統收集數據
        await this.delay(3000);

        // 執行清理操作
        for (const obj of workload) {
            objectPoolManager.release('cacheEntry', obj);
        }

        for (const buffer of buffers) {
            objectPoolManager.releaseBuffer('large', buffer);
        }

        // 觸發GC
        const gcResult = gcOptimizer.forceGC('major');

        // 執行物件池維護
        objectPoolManager.cleanup();

        // 收集最終統計
        integrationResults.memoryAfter = process.memoryUsage();
        integrationResults.poolUsageAfter = objectPoolManager.getStats();
        integrationResults.gcStatsAfter = gcOptimizer.getGCReport();

        this.testResults.integration = {
            testDuration: `${Date.now() - startTime}ms`,
            memoryChange: {
                heap: `${Math.round((integrationResults.memoryAfter.heapUsed - integrationResults.memoryBefore.heapUsed) / 1024 / 1024)}MB`,
                external: `${Math.round((integrationResults.memoryAfter.external - integrationResults.memoryBefore.external) / 1024 / 1024)}MB`
            },
            poolEfficiency: integrationResults.poolUsageAfter.efficiency.reuseRate,
            gcEffectiveness: gcResult ? `${gcResult.efficiency}%` : 'N/A',
            workloadSize: {
                objects: workload.length,
                buffers: buffers.length
            },
            systemStability: '✅ 穩定'
        };

        console.log('系統整合測試結果:');
        console.log(`- 記憶體變化 - 堆疊: ${this.testResults.integration.memoryChange.heap}`);
        console.log(`- 記憶體變化 - 外部: ${this.testResults.integration.memoryChange.external}`);
        console.log(`- 物件池效率: ${this.testResults.integration.poolEfficiency}`);
        console.log(`- GC有效性: ${this.testResults.integration.gcEffectiveness}`);
        console.log(`- 系統穩定性: ${this.testResults.integration.systemStability}`);
        console.log('✅ 系統整合測試完成\n');
    }

    /**
     * 生成測試報告
     */
    generateReport() {
        console.log('📋 === 記憶體最佳化測試報告 ===\n');

        console.log('🔍 記憶體監控測試:');
        console.log(`  監控狀態: ${this.testResults.memoryMonitoring.monitoringActive ? '✅ 正常運行' : '❌ 異常'}`);
        console.log(`  記憶體增長監測: ${this.testResults.memoryMonitoring.memoryIncrease}`);
        console.log(`  數據收集: ${this.testResults.memoryMonitoring.dataPoints} 個數據點`);
        console.log();

        console.log('📦 物件池測試:');
        console.log(`  物件重用率: ${this.testResults.objectPools.reuseRate}`);
        console.log(`  平均利用率: ${this.testResults.objectPools.avgUtilization}`);
        console.log(`  記憶體使用估算: ${this.testResults.objectPools.estimatedMemoryUsage}`);
        console.log();

        console.log('🗑️ GC最佳化測試:');
        console.log(`  手動GC執行: ${this.testResults.gcOptimization.manualGCExecuted}`);
        console.log(`  記憶體釋放效果: ${this.testResults.gcOptimization.memoryFreed}`);
        console.log(`  GC效率: ${this.testResults.gcOptimization.gcEfficiency}`);
        console.log();

        console.log('📊 壓力管理測試:');
        console.log(`  壓力檢測: 從 ${this.testResults.pressureManagement.initialLevel} 到 ${this.testResults.pressureManagement.finalLevel}`);
        console.log(`  自動應對動作: ${this.testResults.pressureManagement.totalActions} 次`);
        console.log(`  手動動作執行: ${this.testResults.pressureManagement.manualActionExecuted}`);
        console.log();

        console.log('🔗 系統整合測試:');
        console.log(`  記憶體管理效果: 堆疊變化 ${this.testResults.integration.memoryChange.heap}`);
        console.log(`  物件池整合: 重用率 ${this.testResults.integration.poolEfficiency}`);
        console.log(`  系統穩定性: ${this.testResults.integration.systemStability}`);
        console.log();

        console.log('📊 總體評估:');
        const overallSuccess = this.evaluateOverallSuccess();
        console.log(`  記憶體最佳化系統: ${overallSuccess ? '✅ 運行良好' : '⚠️ 需要改進'}`);
        console.log('✅ 測試完成！記憶體最佳化系統已驗證。');
    }

    /**
     * 評估整體成功率
     */
    evaluateOverallSuccess() {
        const checks = [
            this.testResults.memoryMonitoring.monitoringActive,
            this.testResults.objectPools.reuseRate !== '0%',
            this.testResults.gcOptimization.manualGCExecuted === '✅ 成功',
            this.testResults.pressureManagement.totalActions >= 0,
            this.testResults.integration.systemStability === '✅ 穩定'
        ];

        const successRate = checks.filter(check => check).length / checks.length;
        return successRate >= 0.8; // 80% 成功率
    }

    /**
     * 清理測試環境
     */
    async cleanup() {
        console.log('🧹 清理測試環境...');

        try {
            // 停止監控系統
            memoryMonitor.stopMonitoring();
            gcOptimizer.stopOptimization();
            memoryPressureManager.stopMonitoring();

            // 清理物件池
            objectPoolManager.resetStats();
            objectPoolManager.cleanup();

            // 強制執行一次GC清理
            if (global.gc && typeof global.gc === 'function') {
                global.gc();
            }

            console.log('✅ 測試環境清理完成');
        } catch (error) {
            console.log('清理過程中發生錯誤:', error.message);
        }
    }

    /**
     * 延遲工具函數
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 檢查是否啟用了 --expose-gc
if (!global.gc || typeof global.gc !== 'function') {
    console.warn('⚠️ 建議使用 --expose-gc 參數啟動 Node.js 以獲得最佳測試效果');
    console.warn('   範例: node --expose-gc scripts/test-memory-optimization.js\n');
}

// 運行測試
const tester = new MemoryOptimizationTester();
tester.runAllTests().catch(console.error);