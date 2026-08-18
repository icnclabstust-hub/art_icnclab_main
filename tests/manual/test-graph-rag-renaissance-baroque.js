#!/usr/bin/env node
/**
 * 測試Graph RAG能否檢索Renaissance和Baroque資料
 */

const axios = require('axios');

const GRAPH_RAG_URL = 'http://localhost:8008';

class GraphRAGTester {
    constructor() {
        this.testResults = [];
    }

    async testQuery(query, description) {
        console.log(`\n🔍 測試: ${description}`);
        console.log(`   查詢: "${query}"`);

        try {
            const response = await axios.post(`${GRAPH_RAG_URL}/query`, {
                query: query,
                strategy: 'graph_only',
                top_k: 5
            });

            const data = response.data;

            console.log(`   ✅ 成功!`);
            console.log(`   信心分數: ${data.confidence_score}`);
            console.log(`   處理時間: ${data.processing_time.toFixed(3)}秒`);
            console.log(`   來源數量: ${data.sources.length}`);

            // 顯示答案（截短）
            const answerPreview = data.answer.substring(0, 200);
            console.log(`   答案預覽: ${answerPreview}...`);

            this.testResults.push({
                query,
                description,
                success: true,
                confidence: data.confidence_score,
                sourcesCount: data.sources.length,
                processingTime: data.processing_time
            });

            return data;

        } catch (error) {
            console.log(`   ❌ 失敗: ${error.message}`);
            this.testResults.push({
                query,
                description,
                success: false,
                error: error.message
            });
            return null;
        }
    }

    async runAllTests() {
        console.log('╔═══════════════════════════════════════════════════════════╗');
        console.log('║     Graph RAG Renaissance & Baroque 資料檢索測試          ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        // 測試1: 查詢Leonardo da Vinci
        await this.testQuery(
            'Leonardo da Vinci',
            '查詢文藝復興大師達芬奇'
        );

        // 測試2: 查詢Renaissance時期
        await this.testQuery(
            'Renaissance period artworks',
            '查詢文藝復興時期作品'
        );

        // 測試3: 查詢Baroque時期
        await this.testQuery(
            'Baroque paintings',
            '查詢巴洛克時期繪畫'
        );

        // 測試4: 查詢Rembrandt
        await this.testQuery(
            'Rembrandt',
            '查詢巴洛克大師林布蘭'
        );

        // 測試5: 查詢Michelangelo
        await this.testQuery(
            'Michelangelo sculptures',
            '查詢米開朗基羅的雕塑'
        );

        // 測試6: 比較性查詢
        await this.testQuery(
            'Renaissance artists in Italy',
            '查詢意大利的文藝復興藝術家'
        );

        // 測試7: 查詢特定作品
        await this.testQuery(
            'portrait paintings Renaissance',
            '查詢文藝復興時期的肖像畫'
        );

        // 測試8: 查詢Baroque藝術家
        await this.testQuery(
            'Peter Paul Rubens',
            '查詢魯本斯'
        );

        // 測試9: 時期比較
        await this.testQuery(
            'difference between Renaissance and Baroque',
            '文藝復興與巴洛克的差異'
        );

        // 測試10: 特定媒材
        await this.testQuery(
            'oil paintings Baroque',
            '查詢巴洛克時期的油畫'
        );

        this.printSummary();
    }

    printSummary() {
        console.log('\n╔═══════════════════════════════════════════════════════════╗');
        console.log('║                      測試總結                              ║');
        console.log('╚═══════════════════════════════════════════════════════════╝');

        const successful = this.testResults.filter(r => r.success).length;
        const total = this.testResults.length;
        const successRate = (successful / total * 100).toFixed(1);

        console.log(`\n📊 總測試數: ${total}`);
        console.log(`✅ 成功: ${successful}`);
        console.log(`❌ 失敗: ${total - successful}`);
        console.log(`📈 成功率: ${successRate}%`);

        if (successful > 0) {
            const avgConfidence = this.testResults
                .filter(r => r.success)
                .reduce((sum, r) => sum + r.confidence, 0) / successful;

            const avgTime = this.testResults
                .filter(r => r.success)
                .reduce((sum, r) => sum + r.processingTime, 0) / successful;

            const totalSources = this.testResults
                .filter(r => r.success)
                .reduce((sum, r) => sum + r.sourcesCount, 0);

            console.log(`\n🎯 平均信心分數: ${avgConfidence.toFixed(3)}`);
            console.log(`⚡ 平均處理時間: ${avgTime.toFixed(3)}秒`);
            console.log(`📚 總來源數量: ${totalSources}`);
        }

        console.log('\n' + '─'.repeat(63));

        // 列出失敗的測試
        const failed = this.testResults.filter(r => !r.success);
        if (failed.length > 0) {
            console.log('\n❌ 失敗的測試:');
            failed.forEach(r => {
                console.log(`   - ${r.description}: ${r.error}`);
            });
        }

        console.log('\n✅ Renaissance & Baroque 資料檢索測試完成！');

        // 結論
        if (successRate >= 90) {
            console.log('\n🎉 結論: Graph RAG系統運行正常，可以成功檢索Renaissance和Baroque資料！');
        } else if (successRate >= 70) {
            console.log('\n⚠️ 結論: Graph RAG系統基本正常，但部分查詢需要優化。');
        } else {
            console.log('\n❌ 結論: Graph RAG系統需要檢查，多個查詢失敗。');
        }
    }

    async checkSystemStatus() {
        console.log('\n🔧 檢查系統狀態...\n');

        // 檢查健康狀態
        try {
            const healthResponse = await axios.get(`${GRAPH_RAG_URL}/health`);
            console.log(`✅ Graph RAG健康狀態: ${healthResponse.data.status}`);
            console.log(`   Neo4j連接: ${healthResponse.data.neo4j}`);
        } catch (error) {
            console.log(`❌ Graph RAG健康檢查失敗: ${error.message}`);
            return false;
        }

        // 獲取統計
        try {
            const statsResponse = await axios.get(`${GRAPH_RAG_URL}/stats`);
            const stats = statsResponse.data;

            console.log(`\n📊 知識圖譜統計:`);
            console.log(`   節點統計:`);
            stats.nodes.slice(0, 5).forEach(node => {
                console.log(`     - ${node.type}: ${node.count}`);
            });

            console.log(`   關係統計:`);
            stats.relationships.slice(0, 5).forEach(rel => {
                console.log(`     - ${rel.type}: ${rel.count}`);
            });
        } catch (error) {
            console.log(`⚠️ 無法獲取統計: ${error.message}`);
        }

        return true;
    }
}

async function main() {
    const tester = new GraphRAGTester();

    // 先檢查系統狀態
    const systemOk = await tester.checkSystemStatus();

    if (!systemOk) {
        console.log('\n❌ 系統檢查失敗，無法繼續測試');
        process.exit(1);
    }

    // 運行所有測試
    await tester.runAllTests();
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = GraphRAGTester;
