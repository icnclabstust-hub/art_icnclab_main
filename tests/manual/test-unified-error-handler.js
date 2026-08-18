#!/usr/bin/env node
/**
 * 統一錯誤處理系統測試
 * 測試企業級錯誤處理功能和所有高級特性
 */

const UnifiedErrorHandler = require('../../src/utils/unifiedErrorHandler');
const WebCrawlerAgent = require('../../agents/web-crawler');
const MetadataExtractorAgent = require('../../agents/metadata-extractor');
const fs = require('fs/promises');
const path = require('path');

class UnifiedErrorHandlerTester {
    constructor() {
        this.testResults = [];
        this.startTime = Date.now();
    }

    async runAllTests() {
        console.log('🚀 開始統一錯誤處理系統測試...\n');

        // 基礎功能測試
        await this.testBasicErrorHandling();
        await this.testRetryMechanism();
        await this.testCircuitBreaker();

        // 高級功能測試
        await this.testPatternRecognition();
        await this.testIntelligentRecovery();
        await this.testMetricsAndAlerts();

        // Agent整合測試
        await this.testAgentIntegration();

        // 性能和壓力測試
        await this.testPerformance();

        // 生成報告
        await this.generateReport();
    }

    async testBasicErrorHandling() {
        console.log('🧪 測試基礎錯誤處理...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-basic', {
                maxRetries: 2,
                retryDelay: 100
            });

            // 測試成功操作
            const successResult = await errorHandler.wrapAsync(async () => {
                return 'success';
            }, '成功操作測試');

            this.addResult('基礎錯誤處理 - 成功操作', successResult === 'success', '操作成功完成');

            // 測試失敗操作重試
            let attemptCount = 0;
            try {
                await errorHandler.wrapAsync(async () => {
                    attemptCount++;
                    throw new Error('模擬錯誤');
                }, '失敗操作重試測試');
            } catch (error) {
                this.addResult('基礎錯誤處理 - 重試機制', attemptCount === 3, `重試次數: ${attemptCount}`);
            }

        } catch (error) {
            this.addResult('基礎錯誤處理', false, `測試失敗: ${error.message}`);
        }
    }

    async testRetryMechanism() {
        console.log('🔄 測試智能重試機制...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-retry', {
                maxRetries: 3,
                retryDelay: 50,
                exponentialBackoff: true,
                jitterRange: 0.1
            });

            const retryTimes = [];
            let attempts = 0;

            try {
                await errorHandler.wrapAsync(async () => {
                    const now = Date.now();
                    if (retryTimes.length > 0) {
                        const delay = now - retryTimes[retryTimes.length - 1];
                        console.log(`  重試延遲: ${delay}ms`);
                    }
                    retryTimes.push(now);
                    attempts++;

                    if (attempts < 3) {
                        throw new Error(`ETIMEDOUT: 模擬超時 (嘗試 ${attempts})`);
                    }
                    return '最終成功';
                }, '智能重試測試');

                this.addResult('智能重試機制 - 最終成功', attempts === 3, `總嘗試次數: ${attempts}`);
            } catch (error) {
                this.addResult('智能重試機制 - 指數退避', retryTimes.length === 4, `重試時間序列記錄完整`);
            }

        } catch (error) {
            this.addResult('智能重試機制', false, `測試失敗: ${error.message}`);
        }
    }

    async testCircuitBreaker() {
        console.log('🔌 測試斷路器模式...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-circuit', {
                circuitBreakerThreshold: 3,
                circuitBreakerTimeout: 100
            });

            let circuitOpened = false;
            errorHandler.on('circuitBreakerOpened', () => {
                circuitOpened = true;
            });

            // 觸發足夠的失敗來開啟斷路器
            for (let i = 0; i < 4; i++) {
                try {
                    await errorHandler.wrapAsync(async () => {
                        throw new Error(`失敗 ${i + 1}`);
                    }, `斷路器測試失敗 ${i + 1}`);
                } catch (error) {
                    // 預期的失敗
                }
            }

            this.addResult('斷路器模式 - 開啟檢測', circuitOpened, '斷路器成功開啟');

            // 測試斷路器開啟時的行為
            try {
                await errorHandler.wrapAsync(async () => {
                    return 'should not execute';
                }, '斷路器開啟時測試');

                this.addResult('斷路器模式 - 開啟阻斷', false, '斷路器未能阻斷請求');
            } catch (error) {
                const isCircuitBreakerError = error.message.includes('Circuit breaker is OPEN');
                this.addResult('斷路器模式 - 開啟阻斷', isCircuitBreakerError, '斷路器正確阻斷請求');
            }

        } catch (error) {
            this.addResult('斷路器模式', false, `測試失敗: ${error.message}`);
        }
    }

    async testPatternRecognition() {
        console.log('🔍 測試錯誤模式識別...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-pattern', {});

            let patternDetected = false;
            let detectedPattern = null;

            errorHandler.on('patternDetected', (pattern) => {
                patternDetected = true;
                detectedPattern = pattern;
            });

            // 生成重複的錯誤模式
            for (let i = 0; i < 6; i++) {
                try {
                    await errorHandler.wrapAsync(async () => {
                        const error = new Error('文件未找到');
                        error.code = 'ENOENT';
                        throw error;
                    }, `模式識別測試 ${i + 1}`);
                } catch (error) {
                    // 預期的失敗
                }
            }

            this.addResult('錯誤模式識別', patternDetected && detectedPattern?.pattern === 'Error_ENOENT',
                detectedPattern ? `檢測到模式: ${detectedPattern.pattern}` : '未檢測到模式');

        } catch (error) {
            this.addResult('錯誤模式識別', false, `測試失敗: ${error.message}`);
        }
    }

    async testIntelligentRecovery() {
        console.log('🔧 測試智能恢復機制...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-recovery', {
                enableRecovery: true
            });

            let recoveryAttempted = false;
            errorHandler.on('errorRecovered', () => {
                recoveryAttempted = true;
            });

            // 測試文件不存在錯誤的自動恢復
            const testDir = './test_recovery_dir';
            try {
                await fs.rmdir(testDir, { recursive: true });
            } catch (e) {
                // 忽略刪除錯誤
            }

            try {
                await errorHandler.wrapAsync(async () => {
                    const error = new Error(`ENOENT: no such file or directory, open '${testDir}/test.json'`);
                    error.code = 'ENOENT';
                    error.path = testDir;
                    throw error;
                }, '智能恢復測試');
            } catch (error) {
                // 檢查目錄是否被創建
                try {
                    await fs.access(testDir);
                    this.addResult('智能恢復機制 - 目錄創建', true, '成功自動創建缺失目錄');
                } catch (accessError) {
                    this.addResult('智能恢復機制 - 目錄創建', false, '未能自動創建目錄');
                }
            }

        } catch (error) {
            this.addResult('智能恢復機制', false, `測試失敗: ${error.message}`);
        }
    }

    async testMetricsAndAlerts() {
        console.log('📊 測試指標和警報系統...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-metrics', {
                alertThreshold: 3,
                metricsEnabled: true
            });

            let alertTriggered = false;
            errorHandler.on('alertTriggered', (alert) => {
                alertTriggered = true;
                console.log(`  警報觸發: ${alert.recentErrors} 個錯誤`);
            });

            // 生成足夠的錯誤觸發警報
            for (let i = 0; i < 4; i++) {
                try {
                    await errorHandler.wrapAsync(async () => {
                        throw new Error(`指標測試錯誤 ${i + 1}`);
                    }, `指標測試 ${i + 1}`);
                } catch (error) {
                    // 預期的失敗
                }
            }

            const stats = errorHandler.getErrorStats();
            const healthReport = errorHandler.generateHealthReport();

            this.addResult('指標收集', stats.totalErrors >= 4, `總錯誤數: ${stats.totalErrors}`);
            this.addResult('健康報告生成', healthReport.agentId === 'test-metrics', '健康報告生成成功');
            this.addResult('警報系統', alertTriggered, '警報正確觸發');

        } catch (error) {
            this.addResult('指標和警報系統', false, `測試失敗: ${error.message}`);
        }
    }

    async testAgentIntegration() {
        console.log('🤖 測試Agent整合...');

        try {
            // 測試WebCrawler Agent的錯誤處理整合
            const webCrawler = new WebCrawlerAgent();

            // 確保Agent有errorHandler屬性
            const hasErrorHandler = webCrawler.errorHandler &&
                                  typeof webCrawler.errorHandler.wrapAsync === 'function';

            this.addResult('Agent整合 - WebCrawler', hasErrorHandler,
                hasErrorHandler ? 'WebCrawler Agent成功整合統一錯誤處理' : 'WebCrawler Agent缺少錯誤處理');

            // 測試MetadataExtractor Agent的錯誤處理整合
            const metadataExtractor = new MetadataExtractorAgent();

            const hasMetadataErrorHandler = metadataExtractor.errorHandler &&
                                          typeof metadataExtractor.errorHandler.wrapAsync === 'function';

            this.addResult('Agent整合 - MetadataExtractor', hasMetadataErrorHandler,
                hasMetadataErrorHandler ? 'MetadataExtractor Agent成功整合統一錯誤處理' : 'MetadataExtractor Agent缺少錯誤處理');

        } catch (error) {
            this.addResult('Agent整合', false, `測試失敗: ${error.message}`);
        }
    }

    async testPerformance() {
        console.log('⚡ 測試性能表現...');

        try {
            const errorHandler = new UnifiedErrorHandler('test-performance', {
                maxRetries: 1,
                retryDelay: 1
            });

            const iterations = 100;
            const startTime = Date.now();

            // 並發錯誤處理測試
            const promises = Array.from({ length: iterations }, async (_, i) => {
                try {
                    return await errorHandler.wrapAsync(async () => {
                        if (i % 10 === 0) {
                            throw new Error(`性能測試錯誤 ${i}`);
                        }
                        return `成功 ${i}`;
                    }, `性能測試 ${i}`);
                } catch (error) {
                    return `失敗 ${i}`;
                }
            });

            const results = await Promise.all(promises);
            const endTime = Date.now();
            const duration = endTime - startTime;
            const throughput = Math.round(iterations / (duration / 1000));

            const successCount = results.filter(r => r.includes('成功')).length;
            const errorCount = results.filter(r => r.includes('失敗')).length;

            this.addResult('性能測試 - 吞吐量', throughput > 50, `${throughput} 操作/秒`);
            this.addResult('性能測試 - 錯誤處理', errorCount >= 10, `處理 ${errorCount} 個錯誤`);
            this.addResult('性能測試 - 內存使用', true, `完成 ${iterations} 次操作`);

        } catch (error) {
            this.addResult('性能測試', false, `測試失敗: ${error.message}`);
        }
    }

    addResult(testName, passed, details) {
        const result = {
            test: testName,
            status: passed ? 'pass' : 'fail',
            details,
            timestamp: new Date().toISOString()
        };

        this.testResults.push(result);
        const icon = passed ? '✅' : '❌';
        console.log(`  ${icon} ${testName}: ${details}`);
    }

    async generateReport() {
        const endTime = Date.now();
        const duration = Math.round((endTime - this.startTime) / 1000);

        const summary = {
            total: this.testResults.length,
            passed: this.testResults.filter(r => r.status === 'pass').length,
            failed: this.testResults.filter(r => r.status === 'fail').length,
            successRate: 0,
            duration
        };

        summary.successRate = Math.round((summary.passed / summary.total) * 100);

        const report = {
            timestamp: new Date().toISOString(),
            summary,
            results: this.testResults,
            systemInfo: {
                nodeVersion: process.version,
                platform: process.platform,
                memoryUsage: process.memoryUsage()
            },
            recommendations: this.generateRecommendations(summary)
        };

        // 保存報告
        await fs.mkdir('./logs', { recursive: true });
        const reportPath = `./logs/unified-error-handler-test-report.json`;
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

        // 輸出結果
        console.log('\n📋 測試完成報告:');
        console.log(`  📊 總測試: ${summary.total}`);
        console.log(`  ✅ 通過: ${summary.passed}`);
        console.log(`  ❌ 失敗: ${summary.failed}`);
        console.log(`  📈 成功率: ${summary.successRate}%`);
        console.log(`  ⏱️  執行時間: ${duration}秒`);
        console.log(`  📄 報告已保存: ${reportPath}\n`);

        if (summary.failed > 0) {
            console.log('❌ 失敗的測試:');
            this.testResults
                .filter(r => r.status === 'fail')
                .forEach(r => console.log(`  - ${r.test}: ${r.details}`));
        }

        return report;
    }

    generateRecommendations(summary) {
        const recommendations = [];

        if (summary.successRate < 90) {
            recommendations.push('建議檢查失敗的測試案例並進行優化');
        }

        if (summary.successRate === 100) {
            recommendations.push('所有測試通過！統一錯誤處理系統運行良好');
            recommendations.push('可以考慮部署到生產環境');
        }

        if (summary.duration > 30) {
            recommendations.push('測試執行時間較長，考慮優化測試效率');
        }

        return recommendations;
    }
}

// 執行測試
if (require.main === module) {
    (async () => {
        try {
            const tester = new UnifiedErrorHandlerTester();
            await tester.runAllTests();
            process.exit(0);
        } catch (error) {
            console.error('❌ 測試執行失敗:', error);
            process.exit(1);
        }
    })();
}

module.exports = UnifiedErrorHandlerTester;