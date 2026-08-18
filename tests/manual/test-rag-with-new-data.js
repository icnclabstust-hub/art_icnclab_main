#!/usr/bin/env node
/**
 * RAG系統新資料整合測試
 * 測試新收集的資料是否成功整合到各種RAG策略中
 */

const axios = require('axios');

class RAGIntegrationTester {
    constructor() {
        this.ragManagerUrl = process.env.RAG_MANAGER_URL || 'http://localhost:8007';
        this.testQueries = [
            {
                query: '文藝復興時期的藝術特點',
                expectedKeywords: ['文藝復興', 'Renaissance', '藝術'],
                strategies: ['vector_only', 'graph_only', 'hybrid_balanced']
            },
            {
                query: 'Leonardo da Vinci的作品',
                expectedKeywords: ['Leonardo', 'Vinci', 'artist'],
                strategies: ['vector_only', 'graph_only']
            },
            {
                query: '巴洛克時期和文藝復興時期的差異',
                expectedKeywords: ['巴洛克', 'Baroque', '文藝復興', 'Renaissance'],
                strategies: ['graph_only', 'agentic_rag']
            },
            {
                query: '亞洲藝術的特色',
                expectedKeywords: ['亞洲', 'Asian', 'art'],
                strategies: ['vector_only', 'advanced_rag']
            }
        ];

        this.results = {
            timestamp: new Date().toISOString(),
            total_tests: 0,
            passed_tests: 0,
            failed_tests: 0,
            tests: []
        };
    }

    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const prefix = {
            'info': '📋',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️'
        }[type] || '📋';

        console.log(`[${timestamp}] ${prefix} ${message}`);
    }

    async checkHealth() {
        this.log('檢查 RAG 管理器健康狀態...', 'info');

        try {
            const response = await axios.get(`${this.ragManagerUrl}/health`, {
                timeout: 5000
            });

            const health = response.data;
            this.log(`狀態: ${health.status}`, health.status === 'healthy' ? 'success' : 'warning');
            this.log(`服務狀態:`, 'info');
            this.log(`  - Neo4j: ${health.services.neo4j ? '✅' : '❌'}`, 'info');
            this.log(`  - ChromaDB: ${health.services.chromadb ? '✅' : '❌'}`, 'info');
            this.log(`  - Ollama: ${health.services.ollama ? '✅' : '❌'}`, 'info');

            return health.status === 'healthy';
        } catch (error) {
            this.log(`健康檢查失敗: ${error.message}`, 'error');
            return false;
        }
    }

    async testQuery(query, modelId, strategy, expectedKeywords) {
        const testId = `${query.substring(0, 30)}_${strategy}`;
        this.log(`\n測試查詢: "${query}"`, 'info');
        this.log(`  策略: ${strategy}`, 'info');

        const testResult = {
            query,
            strategy,
            modelId,
            timestamp: new Date().toISOString(),
            success: false,
            response_time: 0,
            has_answer: false,
            has_sources: false,
            keyword_match: false,
            error: null
        };

        const startTime = Date.now();
        try {

            const response = await axios.post(
                `${this.ragManagerUrl}/api/v1/query`,
                {
                    query,
                    model_combination_id: modelId,
                    max_results: 5,
                    include_sources: true
                },
                { timeout: 60000 }
            );

            testResult.response_time = Date.now() - startTime;
            const data = response.data;

            // 檢查回答
            testResult.has_answer = !!(data.answer && data.answer.length > 50);

            // 檢查來源
            testResult.has_sources = !!(data.sources && data.sources.length > 0);
            testResult.num_sources = data.sources ? data.sources.length : 0;

            // 檢查關鍵詞匹配
            const answerLower = data.answer.toLowerCase();
            const sourcesText = data.sources
                ? data.sources.map(s => s.content).join(' ').toLowerCase()
                : '';

            testResult.keyword_match = expectedKeywords.some(keyword =>
                answerLower.includes(keyword.toLowerCase()) ||
                sourcesText.includes(keyword.toLowerCase())
            );

            // 判斷成功
            testResult.success = testResult.has_answer &&
                                 testResult.has_sources &&
                                 testResult.keyword_match;

            // 日誌輸出
            this.log(`  回答長度: ${data.answer.length} 字符`, 'info');
            this.log(`  來源數量: ${testResult.num_sources}`, 'info');
            this.log(`  響應時間: ${testResult.response_time}ms`, 'info');
            this.log(`  關鍵詞匹配: ${testResult.keyword_match ? '✅' : '❌'}`, 'info');

            if (testResult.success) {
                this.log(`測試通過`, 'success');
                this.results.passed_tests++;
            } else {
                this.log(`測試失敗：回答不完整或缺少關鍵資訊`, 'warning');
                this.results.failed_tests++;
            }

            // 顯示部分回答
            if (data.answer) {
                const preview = data.answer.substring(0, 150);
                this.log(`  回答預覽: ${preview}...`, 'info');
            }

        } catch (error) {
            testResult.error = error.message;
            testResult.response_time = Date.now() - startTime;

            this.log(`測試失敗: ${error.message}`, 'error');
            this.results.failed_tests++;
        }

        this.results.tests.push(testResult);
        this.results.total_tests++;
    }

    async runAllTests() {
        this.log('\n' + '═'.repeat(60), 'info');
        this.log('🧪 RAG 系統新資料整合測試', 'info');
        this.log('═'.repeat(60), 'info');

        // 檢查健康狀態
        const isHealthy = await this.checkHealth();
        if (!isHealthy) {
            this.log('\n⚠️ RAG 管理器未完全就緒，測試可能失敗', 'warning');
        }

        this.log('\n開始測試查詢...', 'info');

        // 使用主要模型
        const primaryModel = 'llama3.1:8b';

        // 執行所有測試
        for (const testCase of this.testQueries) {
            for (const strategy of testCase.strategies) {
                const modelId = `${primaryModel}@${strategy}`;
                await this.testQuery(
                    testCase.query,
                    modelId,
                    strategy,
                    testCase.expectedKeywords
                );

                // 測試之間延遲
                await this.delay(2000);
            }
        }
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    printSummary() {
        this.log('\n' + '═'.repeat(60), 'info');
        this.log('📊 測試摘要', 'info');
        this.log('═'.repeat(60), 'info');

        this.log(`總測試數: ${this.results.total_tests}`, 'info');
        this.log(`通過: ${this.results.passed_tests}`, 'success');
        this.log(`失敗: ${this.results.failed_tests}`, this.results.failed_tests > 0 ? 'error' : 'info');

        const successRate = this.results.total_tests > 0
            ? (this.results.passed_tests / this.results.total_tests * 100).toFixed(1)
            : 0;

        this.log(`成功率: ${successRate}%`, successRate >= 70 ? 'success' : 'warning');

        // 按策略統計
        const strategyStats = {};
        this.results.tests.forEach(test => {
            if (!strategyStats[test.strategy]) {
                strategyStats[test.strategy] = { total: 0, passed: 0 };
            }
            strategyStats[test.strategy].total++;
            if (test.success) {
                strategyStats[test.strategy].passed++;
            }
        });

        this.log('\n策略表現:', 'info');
        Object.entries(strategyStats).forEach(([strategy, stats]) => {
            const rate = (stats.passed / stats.total * 100).toFixed(0);
            this.log(`  ${strategy}: ${stats.passed}/${stats.total} (${rate}%)`,
                     stats.passed === stats.total ? 'success' : 'warning');
        });

        // 平均響應時間
        const avgResponseTime = this.results.tests
            .filter(t => t.response_time > 0)
            .reduce((sum, t) => sum + t.response_time, 0) / this.results.tests.length;

        this.log(`\n平均響應時間: ${avgResponseTime.toFixed(0)}ms`, 'info');

        this.log('═'.repeat(60) + '\n', 'info');
    }

    async saveSummary() {
        const fs = require('fs').promises;
        const path = require('path');

        const summaryPath = path.join(__dirname, 'rag-integration-test-results.json');

        try {
            await fs.writeFile(
                summaryPath,
                JSON.stringify(this.results, null, 2),
                'utf-8'
            );
            this.log(`測試結果已保存到: ${summaryPath}`, 'success');
        } catch (error) {
            this.log(`保存測試結果失敗: ${error.message}`, 'error');
        }
    }

    async run() {
        try {
            await this.runAllTests();
            this.printSummary();
            await this.saveSummary();

            // 根據測試結果決定退出碼
            process.exit(this.results.failed_tests > 0 ? 1 : 0);

        } catch (error) {
            this.log(`測試執行失敗: ${error.message}`, 'error');
            this.log(error.stack, 'error');
            process.exit(1);
        }
    }
}

// 執行測試
if (require.main === module) {
    const tester = new RAGIntegrationTester();
    tester.run().catch(error => {
        console.error('致命錯誤:', error);
        process.exit(1);
    });
}

module.exports = RAGIntegrationTester;
