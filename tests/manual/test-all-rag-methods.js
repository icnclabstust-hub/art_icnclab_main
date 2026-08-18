#!/usr/bin/env node
/**
 * 測試所有9種RAG方法檢索Renaissance和Baroque資料
 * 驗證每種RAG策略都能成功檢索到新增的藝術史資料
 */

const axios = require('axios');

// 配置
const RAG_MANAGER_URL = 'http://localhost:8007';
const GRAPH_RAG_URL = 'http://localhost:8008';

// 所有RAG策略
const RAG_STRATEGIES = [
    'VECTOR_ONLY',
    'GRAPH_ONLY',
    'HYBRID_BALANCED',
    'ADAPTIVE',
    'SPECIALIZED',
    'ADVANCED_RAG',
    'SELF_RAG',
    'AGENTIC_RAG',
    'NAIVE_RAG'
];

// 測試查詢
const TEST_QUERIES = [
    {
        query: 'Leonardo da Vinci',
        description: '文藝復興大師達芬奇',
        expectedKeywords: ['Leonardo', 'Renaissance', 'artist']
    },
    {
        query: 'Renaissance period artworks',
        description: '文藝復興時期作品',
        expectedKeywords: ['Renaissance', 'artwork', 'period']
    },
    {
        query: 'Baroque paintings',
        description: '巴洛克繪畫',
        expectedKeywords: ['Baroque', 'paint']
    },
    {
        query: 'Rembrandt',
        description: '巴洛克大師林布蘭',
        expectedKeywords: ['Rembrandt', 'Baroque', 'artist']
    }
];

class AllRAGMethodsTester {
    constructor() {
        this.results = {};
        RAG_STRATEGIES.forEach(strategy => {
            this.results[strategy] = {
                passed: 0,
                failed: 0,
                queries: []
            };
        });
    }

    async testRAGStrategy(strategy, query, description, expectedKeywords) {
        console.log(`\n🔍 測試 ${strategy}: ${description}`);
        console.log(`   查詢: "${query}"`);

        try {
            let response;
            let answer = '';
            let sources = [];
            let confidence = 0;

            // 將策略名稱轉換為小寫格式
            const strategyLower = strategy.toLowerCase();

            // Graph RAG可以使用任一端點
            if (strategy === 'GRAPH_ONLY') {
                // 使用專用Graph RAG端點
                response = await axios.post(`${GRAPH_RAG_URL}/query`, {
                    query: query,
                    strategy: 'graph_only',
                    top_k: 5
                }, { timeout: 30000 });

                answer = response.data.answer || '';
                sources = response.data.sources || [];
                confidence = response.data.confidence_score || 0;

            } else {
                // 其他策略使用RAG Manager，需要model_combination_id
                // 使用llama3.1:8b作為默認LLM
                const modelCombinationId = `llama3.1:8b@${strategyLower}`;

                response = await axios.post(`${RAG_MANAGER_URL}/api/v1/query`, {
                    query: query,
                    model_combination_id: modelCombinationId,
                    top_k: 5
                }, { timeout: 60000 });

                answer = response.data.answer || response.data.response || '';
                sources = response.data.sources || response.data.context || [];
                confidence = response.data.confidence || response.data.confidence_score || 0;
            }

            // 檢查結果
            const hasAnswer = answer && answer.length > 0;
            const hasSources = sources && sources.length > 0;

            // 檢查答案中是否包含預期關鍵字
            const keywordsFound = expectedKeywords.filter(keyword =>
                answer.toLowerCase().includes(keyword.toLowerCase())
            );

            const success = hasAnswer && (hasSources || keywordsFound.length > 0);

            if (success) {
                console.log(`   ✅ 成功`);
                console.log(`      答案長度: ${answer.length} 字符`);
                console.log(`      來源數量: ${Array.isArray(sources) ? sources.length : 0}`);
                console.log(`      信心分數: ${confidence.toFixed(3)}`);
                console.log(`      找到關鍵字: ${keywordsFound.join(', ')}`);

                this.results[strategy].passed++;
                this.results[strategy].queries.push({
                    query,
                    success: true,
                    answerLength: answer.length,
                    sourcesCount: Array.isArray(sources) ? sources.length : 0,
                    confidence,
                    keywordsFound
                });

                return true;
            } else {
                console.log(`   ⚠️ 查詢成功但結果不完整`);
                console.log(`      答案: ${hasAnswer ? '有' : '無'}`);
                console.log(`      來源: ${hasSources ? sources.length : 0}`);
                console.log(`      關鍵字: ${keywordsFound.length}/${expectedKeywords.length}`);

                this.results[strategy].failed++;
                this.results[strategy].queries.push({
                    query,
                    success: false,
                    hasAnswer,
                    hasSources,
                    keywordsFound: keywordsFound.length
                });

                return false;
            }

        } catch (error) {
            console.log(`   ❌ 失敗: ${error.message}`);

            if (error.response) {
                console.log(`      狀態碼: ${error.response.status}`);
                console.log(`      錯誤: ${error.response.data?.error || error.response.data?.detail || '未知錯誤'}`);
            }

            this.results[strategy].failed++;
            this.results[strategy].queries.push({
                query,
                success: false,
                error: error.message
            });

            return false;
        }
    }

    async checkServices() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              檢查服務狀態                                  ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 檢查Graph RAG
        try {
            const health = await axios.get(`${GRAPH_RAG_URL}/health`, { timeout: 5000 });
            console.log(`\n✅ Graph RAG (port 8008): ${health.data.status}`);
            console.log(`   Neo4j: ${health.data.neo4j}`);
        } catch (error) {
            console.log(`\n❌ Graph RAG (port 8008): 無法連接`);
            console.log(`   請確保服務運行: node neo4j_graph_rag_server.js`);
        }

        // 檢查RAG Manager
        try {
            const health = await axios.get(`${RAG_MANAGER_URL}/health`, { timeout: 5000 });
            console.log(`\n✅ RAG Manager (port 8010): 運行中`);
        } catch (error) {
            console.log(`\n❌ RAG Manager (port 8010): 無法連接`);
            console.log(`   請確保服務運行: docker exec art-history-rag-manager-v2`);
        }

        // 檢查Neo4j
        try {
            await axios.get('http://localhost:7474', { timeout: 5000 });
            console.log(`\n✅ Neo4j (port 7474): 運行中`);
        } catch (error) {
            console.log(`\n⚠️ Neo4j Browser (port 7474): 無法訪問`);
        }

        // 檢查ChromaDB
        try {
            await axios.get('http://localhost:8000/api/v1/heartbeat', { timeout: 5000 });
            console.log(`\n✅ ChromaDB (port 8000): 運行中`);
        } catch (error) {
            console.log(`\n⚠️ ChromaDB (port 8000): 無法訪問`);
        }
    }

    async runAllTests() {
        console.log('╔═══════════════════════════════════════════════════════════╗');
        console.log('║        測試所有RAG方法檢索Renaissance & Baroque          ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 檢查服務
        await this.checkServices();

        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              開始測試所有RAG策略                          ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 測試每個策略
        for (const strategy of RAG_STRATEGIES) {
            console.log(`\n\n═══════════════════════════════════════════════════════════`);
            console.log(`   策略: ${strategy}`);
            console.log(`═══════════════════════════════════════════════════════════`);

            // 對每個查詢進行測試
            for (const testQuery of TEST_QUERIES) {
                await this.testRAGStrategy(
                    strategy,
                    testQuery.query,
                    testQuery.description,
                    testQuery.expectedKeywords
                );

                // 稍微延遲避免請求過快
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        this.printSummary();
    }

    printSummary() {
        console.log('\n\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║                  測試總結                                  ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        console.log('\n📊 各RAG策略測試結果:\n');

        let totalPassed = 0;
        let totalFailed = 0;

        RAG_STRATEGIES.forEach(strategy => {
            const result = this.results[strategy];
            const total = result.passed + result.failed;
            const successRate = total > 0 ? (result.passed / total * 100).toFixed(1) : 0;

            const icon = successRate >= 90 ? '✅' : successRate >= 70 ? '⚠️' : '❌';

            console.log(`${icon} ${strategy.padEnd(20)} - 成功: ${result.passed}/${total} (${successRate}%)`);

            totalPassed += result.passed;
            totalFailed += result.failed;
        });

        // 總體統計
        const overallTotal = totalPassed + totalFailed;
        const overallRate = overallTotal > 0 ? (totalPassed / overallTotal * 100).toFixed(1) : 0;

        console.log('\n' + '─'.repeat(63));
        console.log('\n🎯 總體統計:');
        console.log(`   總測試數: ${overallTotal} (${RAG_STRATEGIES.length} 個策略 × ${TEST_QUERIES.length} 個查詢)`);
        console.log(`   成功: ${totalPassed}`);
        console.log(`   失敗: ${totalFailed}`);
        console.log(`   成功率: ${overallRate}%`);

        // 評估
        console.log('\n🎯 評估:');
        if (overallRate >= 90) {
            console.log('   ✅ 優秀！所有RAG方法都能成功檢索Renaissance和Baroque資料');
        } else if (overallRate >= 70) {
            console.log('   ⚠️ 良好，大部分RAG方法正常，部分需要改進');
        } else if (overallRate >= 50) {
            console.log('   ⚠️ 一般，多數RAG方法需要檢查');
        } else {
            console.log('   ❌ 需要改進，多數RAG方法無法正常檢索');
        }

        // 列出失敗的策略
        const failedStrategies = RAG_STRATEGIES.filter(strategy => {
            const result = this.results[strategy];
            const total = result.passed + result.failed;
            return total > 0 && (result.passed / total < 0.7);
        });

        if (failedStrategies.length > 0) {
            console.log('\n⚠️ 需要改進的策略:');
            failedStrategies.forEach(strategy => {
                const result = this.results[strategy];
                const total = result.passed + result.failed;
                const rate = (result.passed / total * 100).toFixed(1);
                console.log(`   - ${strategy}: ${result.passed}/${total} (${rate}%)`);
            });
        }

        // 使用指南
        console.log('\n\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              OpenWebUI 使用指南                           ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        console.log('\n🌐 用戶可以在OpenWebUI使用以下RAG策略:');
        RAG_STRATEGIES.forEach((strategy, idx) => {
            const result = this.results[strategy];
            const total = result.passed + result.failed;
            const successRate = total > 0 ? (result.passed / total * 100).toFixed(1) : 0;
            const status = successRate >= 70 ? '✅' : '⚠️';
            console.log(`   ${idx + 1}. ${status} ${strategy}`);
        });

        console.log('\n💡 示例問題:');
        TEST_QUERIES.forEach((test, idx) => {
            console.log(`   ${idx + 1}. "${test.query}"`);
        });

        console.log('\n🔗 訪問方式:');
        console.log('   OpenWebUI: http://localhost:8080');
        console.log('   Graph RAG API: http://localhost:8008');
        console.log('   RAG Manager API: http://localhost:8007');

        console.log('\n' + '═'.repeat(63));
        console.log('測試完成！');
        console.log('═'.repeat(63) + '\n');
    }
}

async function main() {
    const tester = new AllRAGMethodsTester();
    await tester.runAllTests();
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = AllRAGMethodsTester;
