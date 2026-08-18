#!/usr/bin/env node
const axios = require('axios');

const GRAPH_RAG_URL = 'http://localhost:8008';

async function testQuery(query, description) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`測試: ${description}`);
    console.log(`查詢: "${query}"`);
    console.log('='.repeat(60));

    try {
        const response = await axios.post(`${GRAPH_RAG_URL}/query`, {
            query: query,
            top_k: 5
        }, { timeout: 30000 });

        const data = response.data;

        console.log(`\n✅ 查詢成功`);
        console.log(`來源數量: ${data.sources.length}`);
        console.log(`信心分數: ${data.confidence_score}`);
        
        if (data.sources.length > 0) {
            console.log(`\n📚 找到的來源:`);
            data.sources.slice(0, 3).forEach((source, idx) => {
                console.log(`${idx + 1}. ${source.title}`);
                console.log(`   藝術家: ${source.artist || 'Unknown'}`);
            });
        }

        return { success: data.sources.length > 0, sourcesCount: data.sources.length };

    } catch (error) {
        console.log(`\n❌ 查詢失敗: ${error.message}`);
        return { success: false, error: error.message };
    }
}

async function main() {
    console.log('╔═══════════════════════════════════════════════════════════╗');
    console.log('║       Graph RAG 中文查詢測試                               ║');
    console.log('╚═══════════════════════════════════════════════════════════╝');

    const tests = [
        { query: "達文西的代表作品有哪些", description: "查詢達文西作品" },
        { query: "文藝復興時期的著名藝術家", description: "查詢文藝復興藝術家" },
        { query: "林布蘭的自畫像", description: "查詢林布蘭作品" },
        { query: "巴洛克時期的繪畫特點", description: "查詢巴洛克特點" },
    ];

    const results = [];
    for (const test of tests) {
        const result = await testQuery(test.query, test.description);
        results.push({ ...test, ...result });
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    console.log(`\n\n╔═══════════════════════════════════════════════════════════╗`);
    console.log(`║                    測試總結                                ║`);
    console.log(`╚═══════════════════════════════════════════════════════════╝`);

    const successCount = results.filter(r => r.success).length;
    console.log(`\n總測試數: ${results.length}`);
    console.log(`成功: ${successCount}`);
    console.log(`失敗: ${results.length - successCount}`);
    console.log(`成功率: ${(successCount / results.length * 100).toFixed(1)}%`);

    console.log(`\n詳細結果:`);
    results.forEach((result, idx) => {
        const icon = result.success ? '✅' : '❌';
        console.log(`${icon} ${idx + 1}. ${result.description}`);
        if (result.success) {
            console.log(`      來源: ${result.sourcesCount}個`);
        }
    });

    if (successCount === results.length) {
        console.log(`\n🎉 所有測試通過！Graph RAG 中文查詢功能正常！`);
        console.log(`\n用戶現在可以在 OpenWebUI 中使用 "Llama 3.1 8B + Graph Only RAG" 進行中文查詢`);
    }
}

main().catch(console.error);
