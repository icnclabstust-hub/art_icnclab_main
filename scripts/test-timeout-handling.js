/**
 * 超時處理機制測試腳本
 * 測試各種超時場景和處理邏輯
 */

const { globalTimeoutHandler, TimeoutError } = require('../src/utils/timeoutHandler');
const { dbManager } = require('../src/database/connection');

// 測試場景配置
const testScenarios = [
    {
        name: '快速完成操作',
        timeout: 5000,
        actualDelay: 1000,
        expectedResult: 'success'
    },
    {
        name: '剛好超時操作',
        timeout: 2000,
        actualDelay: 2100,
        expectedResult: 'timeout'
    },
    {
        name: '嚴重超時操作',
        timeout: 3000,
        actualDelay: 8000,
        expectedResult: 'timeout'
    },
    {
        name: '資料庫查詢超時測試',
        timeout: 1000,
        actualDelay: 1500,
        expectedResult: 'timeout'
    },
    {
        name: '批量操作超時測試',
        timeout: 4000,
        actualDelay: 5000,
        expectedResult: 'timeout'
    }
];

/**
 * 模擬異步操作
 * @param {number} delay - 延遲時間
 * @param {boolean} shouldFail - 是否應該失敗
 * @returns {Promise}
 */
function simulateAsyncOperation(delay, shouldFail = false) {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            if (shouldFail) {
                reject(new Error('模擬操作失敗'));
            } else {
                resolve(`操作完成，耗時 ${delay}ms`);
            }
        }, delay);
    });
}

/**
 * 模擬資料庫查詢
 * @param {number} delay - 查詢延遲時間
 * @returns {Promise}
 */
function simulateDatabaseQuery(delay) {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve({
                rows: [{ id: 1, name: '測試數據', created_at: new Date() }],
                rowCount: 1
            });
        }, delay);
    });
}

/**
 * 執行單個測試場景
 * @param {Object} scenario - 測試場景
 * @returns {Promise<Object>} 測試結果
 */
async function runTestScenario(scenario) {
    const { name, timeout, actualDelay, expectedResult } = scenario;
    const startTime = Date.now();

    console.log(`\n🧪 測試: ${name}`);
    console.log(`   設定超時: ${timeout}ms, 實際延遲: ${actualDelay}ms`);
    console.log(`   預期結果: ${expectedResult}`);

    try {
        let result;

        if (name.includes('資料庫')) {
            // 測試資料庫超時
            const queryPromise = simulateDatabaseQuery(actualDelay);
            result = await globalTimeoutHandler.withDatabaseTimeout(
                queryPromise,
                '測試查詢',
                timeout
            );
        } else if (name.includes('批量')) {
            // 測試批量操作超時
            const promises = [
                simulateAsyncOperation(actualDelay),
                simulateAsyncOperation(actualDelay * 0.8),
                simulateAsyncOperation(actualDelay * 1.2)
            ];
            result = await globalTimeoutHandler.withBatchTimeout(
                promises,
                timeout,
                '批量測試操作'
            );
        } else {
            // 測試一般超時
            const operation = simulateAsyncOperation(actualDelay);
            result = await globalTimeoutHandler.withTimeout(
                operation,
                timeout,
                name
            );
        }

        const executionTime = Date.now() - startTime;
        const actualResult = 'success';

        console.log(`   ✅ 實際結果: ${actualResult}`);
        console.log(`   ⏱️  實際執行時間: ${executionTime}ms`);
        console.log(`   📊 返回數據: ${JSON.stringify(result).substring(0, 100)}...`);

        return {
            scenario: name,
            expected: expectedResult,
            actual: actualResult,
            executionTime,
            success: expectedResult === actualResult,
            result
        };

    } catch (error) {
        const executionTime = Date.now() - startTime;
        const actualResult = error instanceof TimeoutError ? 'timeout' : 'error';

        if (error instanceof TimeoutError) {
            console.log(`   ⏰ 實際結果: ${actualResult} (${error.message})`);
        } else {
            console.log(`   ❌ 實際結果: ${actualResult} (${error.message})`);
        }
        console.log(`   ⏱️  實際執行時間: ${executionTime}ms`);

        return {
            scenario: name,
            expected: expectedResult,
            actual: actualResult,
            executionTime,
            success: expectedResult === actualResult,
            error: error.message
        };
    }
}

/**
 * 測試並發超時處理
 */
async function testConcurrentTimeouts() {
    console.log('\n🔄 測試並發超時處理...');

    const concurrentPromises = [
        globalTimeoutHandler.withTimeout(
            simulateAsyncOperation(1000),
            2000,
            '並發操作1'
        ),
        globalTimeoutHandler.withTimeout(
            simulateAsyncOperation(3000),
            2500,
            '並發操作2'
        ),
        globalTimeoutHandler.withTimeout(
            simulateAsyncOperation(500),
            1500,
            '並發操作3'
        )
    ];

    try {
        const results = await Promise.allSettled(concurrentPromises);

        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                console.log(`   ✅ 並發操作${index + 1}: 成功`);
            } else {
                const error = result.reason;
                if (error instanceof TimeoutError) {
                    console.log(`   ⏰ 並發操作${index + 1}: 超時`);
                } else {
                    console.log(`   ❌ 並發操作${index + 1}: 錯誤 - ${error.message}`);
                }
            }
        });

        return {
            total: results.length,
            successful: results.filter(r => r.status === 'fulfilled').length,
            timeouts: results.filter(r =>
                r.status === 'rejected' && r.reason instanceof TimeoutError
            ).length,
            errors: results.filter(r =>
                r.status === 'rejected' && !(r.reason instanceof TimeoutError)
            ).length
        };

    } catch (error) {
        console.error('   ❌ 並發測試失敗:', error.message);
        return { error: error.message };
    }
}

/**
 * 測試超時處理統計
 */
async function testTimeoutStats() {
    console.log('\n📊 測試超時統計功能...');

    // 執行一些操作來生成統計數據
    const statsTestPromises = [
        globalTimeoutHandler.withTimeout(
            simulateAsyncOperation(100),
            1000,
            '統計測試1'
        ),
        globalTimeoutHandler.withTimeout(
            simulateAsyncOperation(2000),
            1500,
            '統計測試2'
        )
    ];

    await Promise.allSettled(statsTestPromises);

    // 獲取統計信息
    const stats = globalTimeoutHandler.getStats();
    const activeTimeouts = globalTimeoutHandler.getActiveTimeouts();

    console.log('   📈 統計數據:', stats);
    console.log('   🔄 活躍超時:', activeTimeouts.length);

    return { stats, activeTimeouts };
}

/**
 * 主測試函數
 */
async function runTimeoutTests() {
    console.log('🚀 開始超時處理機制測試...\n');
    console.log('='.repeat(60));

    const testResults = [];
    const startTime = Date.now();

    try {
        // 重置統計
        globalTimeoutHandler.resetStats();

        // 執行基本測試場景
        console.log('\n📋 執行基本超時測試場景...');
        for (const scenario of testScenarios) {
            const result = await runTestScenario(scenario);
            testResults.push(result);

            // 在測試之間稍作停頓
            await new Promise(resolve => setTimeout(resolve, 200));
        }

        // 測試並發處理
        const concurrentResult = await testConcurrentTimeouts();

        // 測試統計功能
        const statsResult = await testTimeoutStats();

        // 生成測試報告
        console.log('\n' + '='.repeat(60));
        console.log('📊 測試結果總結');
        console.log('='.repeat(60));

        const totalTests = testResults.length;
        const passedTests = testResults.filter(r => r.success).length;
        const failedTests = totalTests - passedTests;

        console.log(`\n📈 基本測試統計:`);
        console.log(`   總測試數: ${totalTests}`);
        console.log(`   通過測試: ${passedTests} (${(passedTests/totalTests*100).toFixed(1)}%)`);
        console.log(`   失敗測試: ${failedTests} (${(failedTests/totalTests*100).toFixed(1)}%)`);

        console.log(`\n🔄 並發測試統計:`);
        if (concurrentResult.error) {
            console.log(`   錯誤: ${concurrentResult.error}`);
        } else {
            console.log(`   總操作數: ${concurrentResult.total}`);
            console.log(`   成功操作: ${concurrentResult.successful}`);
            console.log(`   超時操作: ${concurrentResult.timeouts}`);
            console.log(`   錯誤操作: ${concurrentResult.errors}`);
        }

        console.log(`\n📊 系統統計:`);
        console.log(`   ${JSON.stringify(statsResult.stats, null, 2)}`);

        // 測試詳細結果
        console.log('\n📋 詳細測試結果:');
        testResults.forEach(result => {
            const status = result.success ? '✅ 通過' : '❌ 失敗';
            console.log(`   ${result.scenario}: ${status} (${result.executionTime}ms)`);
            if (!result.success) {
                console.log(`     預期: ${result.expected}, 實際: ${result.actual}`);
            }
        });

        const totalTime = Date.now() - startTime;
        console.log(`\n⏱️  總測試時間: ${totalTime}ms`);

        // 評估測試結果
        const overallSuccess = passedTests >= totalTests * 0.8; // 80%通過率為成功
        console.log(`\n🏆 整體評估: ${overallSuccess ? '✅ 成功' : '❌ 需要改進'}`);

        if (!overallSuccess) {
            console.log('\n💡 改進建議:');
            console.log('   - 檢查失敗的測試場景');
            console.log('   - 調整超時時間設定');
            console.log('   - 確保超時處理邏輯正確');
        }

        return {
            success: overallSuccess,
            totalTests,
            passedTests,
            failedTests,
            concurrentResult,
            statsResult,
            testResults
        };

    } catch (error) {
        console.error('💥 測試執行失敗:', error);
        return { success: false, error: error.message };
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    (async () => {
        try {
            console.log('🔧 初始化測試環境...');

            // 如果需要資料庫連接，可以在這裡初始化
            // await dbManager.connectAll();

            const results = await runTimeoutTests();

            if (results.success) {
                console.log('\n🎉 所有測試完成！');
                process.exit(0);
            } else {
                console.log('\n⚠️  測試完成，但存在問題');
                process.exit(1);
            }

        } catch (error) {
            console.error('💥 測試腳本執行失敗:', error);
            process.exit(1);
        } finally {
            // 清理資源
            globalTimeoutHandler.cleanup();
            // 如果初始化了資料庫連接，在這裡關閉
            // await dbManager.closeAll();
        }
    })();
}

module.exports = { runTimeoutTests };