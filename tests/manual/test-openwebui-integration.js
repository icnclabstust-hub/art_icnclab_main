#!/usr/bin/env node
/**
 * 測試OpenWebUI與Graph RAG的完整整合
 * 驗證端到端查詢流程
 */

const axios = require('axios');

const OPENWEBUI_URL = 'http://localhost:8080';
const OPENWEBUI_INTEGRATION_URL = 'http://localhost:8009';
const GRAPH_RAG_URL = 'http://localhost:8008';

class OpenWebUIIntegrationTester {
    constructor() {
        this.results = {
            graphRAG: { passed: 0, failed: 0 },
            integration: { passed: 0, failed: 0 },
            openwebui: { passed: 0, failed: 0 }
        };
    }

    async checkService(name, url, endpoint = '/') {
        console.log(`\n🔍 檢查 ${name}...`);
        try {
            const response = await axios.get(`${url}${endpoint}`, { timeout: 5000 });
            console.log(`   ✅ ${name} 運行正常 (狀態碼: ${response.status})`);
            return true;
        } catch (error) {
            console.log(`   ❌ ${name} 無法訪問: ${error.message}`);
            return false;
        }
    }

    async testGraphRAG() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              測試 Graph RAG 服務                          ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 測試健康狀態
        try {
            const health = await axios.get(`${GRAPH_RAG_URL}/health`);
            console.log(`\n✅ Graph RAG 健康檢查: ${health.data.status}`);
            console.log(`   Neo4j 連接: ${health.data.neo4j}`);
            this.results.graphRAG.passed++;
        } catch (error) {
            console.log(`\n❌ Graph RAG 健康檢查失敗: ${error.message}`);
            this.results.graphRAG.failed++;
            return false;
        }

        // 測試查詢功能
        const testQueries = [
            { query: 'Leonardo da Vinci', description: '達芬奇' },
            { query: 'Renaissance', description: '文藝復興' },
            { query: 'Baroque', description: '巴洛克' }
        ];

        for (const test of testQueries) {
            try {
                const response = await axios.post(`${GRAPH_RAG_URL}/query`, {
                    query: test.query,
                    strategy: 'graph_only',
                    top_k: 3
                });

                const hasResults = response.data.sources && response.data.sources.length > 0;

                if (hasResults) {
                    console.log(`\n✅ 查詢「${test.description}」: 找到 ${response.data.sources.length} 個結果`);
                    console.log(`   信心分數: ${response.data.confidence_score}`);
                    this.results.graphRAG.passed++;
                } else {
                    console.log(`\n⚠️ 查詢「${test.description}」: 無結果`);
                    this.results.graphRAG.failed++;
                }
            } catch (error) {
                console.log(`\n❌ 查詢「${test.description}」失敗: ${error.message}`);
                this.results.graphRAG.failed++;
            }
        }

        return true;
    }

    async testIntegrationService() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║          測試 OpenWebUI Integration 服務                  ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        try {
            const response = await axios.get(`${OPENWEBUI_INTEGRATION_URL}/`);
            console.log(`\n✅ Integration 服務運行中`);
            console.log(`   回應: ${JSON.stringify(response.data).substring(0, 100)}`);
            this.results.integration.passed++;
            return true;
        } catch (error) {
            console.log(`\n❌ Integration 服務無法訪問: ${error.message}`);
            this.results.integration.failed++;
            return false;
        }
    }

    async testOpenWebUI() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              測試 OpenWebUI 服務                          ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        try {
            const response = await axios.get(`${OPENWEBUI_URL}/`, { timeout: 5000 });
            console.log(`\n✅ OpenWebUI 運行中 (狀態碼: ${response.status})`);
            this.results.openwebui.passed++;
            return true;
        } catch (error) {
            console.log(`\n❌ OpenWebUI 無法訪問: ${error.message}`);
            console.log(`   確保已啟動: docker-compose -f docker-compose.openwebui.yml up -d`);
            this.results.openwebui.failed++;
            return false;
        }
    }

    async demonstrateQueryFlow() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║            演示完整查詢流程                               ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        console.log('\n📝 查詢流程說明:');
        console.log('   1. 用戶在 OpenWebUI 提問');
        console.log('   2. OpenWebUI → Integration Service');
        console.log('   3. Integration Service → Graph RAG');
        console.log('   4. Graph RAG → Neo4j 知識圖譜');
        console.log('   5. Neo4j 返回結果');
        console.log('   6. 結果返回用戶');

        // 模擬查詢
        const userQuery = '請告訴我關於Leonardo da Vinci的資訊';
        console.log(`\n🤔 模擬用戶提問: "${userQuery}"`);

        try {
            // 直接查詢 Graph RAG
            console.log('\n🔄 步驟 1: 查詢 Graph RAG...');
            const graphResponse = await axios.post(`${GRAPH_RAG_URL}/query`, {
                query: 'Leonardo da Vinci',
                strategy: 'graph_only',
                top_k: 5
            });

            console.log('✅ Graph RAG 回應成功');
            console.log(`   找到 ${graphResponse.data.sources.length} 個來源`);
            console.log(`   處理時間: ${graphResponse.data.processing_time.toFixed(3)}秒`);

            // 顯示結果摘要
            console.log('\n📊 結果摘要:');
            console.log(graphResponse.data.answer.substring(0, 500));

            if (graphResponse.data.sources.length > 0) {
                console.log('\n🎨 相關作品:');
                graphResponse.data.sources.slice(0, 3).forEach((source, idx) => {
                    console.log(`   ${idx + 1}. ${source.title}`);
                    console.log(`      藝術家: ${source.artist}`);
                    console.log(`      年代: ${source.date}`);
                });
            }

            return true;
        } catch (error) {
            console.log(`\n❌ 查詢失敗: ${error.message}`);
            return false;
        }
    }

    printSummary() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║                  整合測試總結                              ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        const sections = [
            { name: 'Graph RAG', results: this.results.graphRAG },
            { name: 'Integration Service', results: this.results.integration },
            { name: 'OpenWebUI', results: this.results.openwebui }
        ];

        sections.forEach(section => {
            const total = section.results.passed + section.results.failed;
            const successRate = total > 0 ? (section.results.passed / total * 100).toFixed(1) : 0;

            console.log(`\n📊 ${section.name}:`);
            console.log(`   通過: ${section.results.passed}`);
            console.log(`   失敗: ${section.results.failed}`);
            console.log(`   成功率: ${successRate}%`);
        });

        // 總體評估
        const totalPassed = Object.values(this.results).reduce((sum, r) => sum + r.passed, 0);
        const totalFailed = Object.values(this.results).reduce((sum, r) => sum + r.failed, 0);
        const overallRate = totalPassed / (totalPassed + totalFailed) * 100;

        console.log('\n🎯 總體評估:');
        console.log(`   總測試數: ${totalPassed + totalFailed}`);
        console.log(`   成功率: ${overallRate.toFixed(1)}%`);

        if (overallRate >= 90) {
            console.log('\n🎉 結論: 整合測試成功！系統已準備就緒。');
        } else if (overallRate >= 70) {
            console.log('\n⚠️ 結論: 部分功能正常，建議檢查失敗項目。');
        } else {
            console.log('\n❌ 結論: 多項測試失敗，需要排查問題。');
        }
    }

    async printUsageGuide() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║              OpenWebUI 使用指南                           ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        console.log('\n🌐 訪問方式:');
        console.log(`   1. 瀏覽器打開: ${OPENWEBUI_URL}`);
        console.log(`   2. 註冊或登入帳戶`);
        console.log(`   3. 開始提問！`);

        console.log('\n💡 示例問題:');
        console.log('   - "告訴我關於Leonardo da Vinci的資訊"');
        console.log('   - "文藝復興時期有哪些著名藝術家？"');
        console.log('   - "Rembrandt有哪些作品？"');
        console.log('   - "比較Renaissance和Baroque的特點"');
        console.log('   - "巴洛克時期的肖像畫有什麼特色？"');

        console.log('\n📊 資料覆蓋:');
        console.log('   - 1,359件藝術作品');
        console.log('   - 894位藝術家');
        console.log('   - 重點: Renaissance & Baroque 時期');
        console.log('   - 包含Leonardo、Rembrandt、Rubens等大師');

        console.log('\n🔧 後端服務:');
        console.log(`   - OpenWebUI: ${OPENWEBUI_URL}`);
        console.log(`   - Graph RAG: ${GRAPH_RAG_URL}`);
        console.log(`   - Neo4j Browser: http://localhost:7474`);

        console.log('\n✅ 系統狀態檢查:');
        console.log('   - Graph RAG: curl http://localhost:8008/health');
        console.log('   - OpenWebUI: curl http://localhost:8080');
        console.log('   - Neo4j: curl http://localhost:7474');
    }

    async run() {
        console.log('╔═══════════════════════════════════════════════════════════╗');
        console.log('║    OpenWebUI + Graph RAG 完整整合測試                    ║');
        console.log('║    Renaissance & Baroque 藝術史資料庫                    ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 檢查各服務狀態
        console.log('\n🔍 服務狀態檢查');
        console.log('─'.repeat(63));

        await this.checkService('OpenWebUI', OPENWEBUI_URL);
        await this.checkService('OpenWebUI Integration', OPENWEBUI_INTEGRATION_URL);
        await this.checkService('Graph RAG', GRAPH_RAG_URL, '/health');
        await this.checkService('Neo4j', 'http://localhost:7474');

        // 執行測試
        await this.testGraphRAG();
        await this.testIntegrationService();
        await this.testOpenWebUI();
        await this.demonstrateQueryFlow();

        // 打印總結
        this.printSummary();
        await this.printUsageGuide();

        console.log('\n' + '═'.repeat(63));
        console.log('測試完成！');
        console.log('═'.repeat(63) + '\n');
    }
}

async function main() {
    const tester = new OpenWebUIIntegrationTester();
    await tester.run();
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = OpenWebUIIntegrationTester;
