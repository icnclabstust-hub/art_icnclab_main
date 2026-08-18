#!/usr/bin/env node
/**
 * 測試所有 RAG 策略的綜合腳本
 */

const axios = require('axios');

const testQueries = [
    { query: "達文西的作品", name: "達文西作品" },
    { query: "蒙娜麗莎", name: "蒙娜麗莎" },
    { query: "文藝復興時期的繪畫", name: "文藝復興繪畫" },
    { query: "巴洛克風格", name: "巴洛克風格" }
];

const strategies = ['graph_only', 'vector_only', 'hybrid_balanced'];

async function testStrategy(query, strategy) {
    try {
        const response = await axios.post('http://localhost:8008/query', {
            query: query,
            strategy: strategy,
            top_k: 5
        });

        const data = response.data;

        return {
            strategy: data.strategy_used,
            sourceCount: data.sources.length,
            processingTime: data.processing_time,
            confidence: data.confidence_score,
            firstResult: data.sources[0] ? data.sources[0].title : 'N/A',
            sources: data.sources
        };

    } catch (error) {
        return {
            strategy: strategy,
            error: error.message
        };
    }
}

async function runTests() {
    console.log('🎨 RAG 策略綜合測試');
    console.log('═══════════════════════════════════════\n');

    for (const {query, name} of testQueries) {
        console.log(`\n📝 測試查詢: "${name}"`);
        console.log('─────────────────────────────────────');

        for (const strategy of strategies) {
            const result = await testStrategy(query, strategy);

            if (result.error) {
                console.log(`❌ ${strategy}: ${result.error}`);
            } else {
                console.log(`\n✓ ${strategy.toUpperCase()}`);
                console.log(`  結果數: ${result.sourceCount}`);
                console.log(`  處理時間: ${result.processingTime.toFixed(3)}秒`);
                console.log(`  信心分數: ${result.confidence.toFixed(2)}`);
                console.log(`  第一項: ${result.firstResult.substring(0, 60)}${result.firstResult.length > 60 ? '...' : ''}`);

                // 顯示來源統計（僅 hybrid）
                if (strategy === 'hybrid_balanced' && result.sources) {
                    const graphCount = result.sources.filter(s => s.source === 'graph').length;
                    const vectorCount = result.sources.filter(s => s.source === 'vector').length;
                    const hybridCount = result.sources.filter(s => s.source === 'hybrid').length;

                    if (graphCount + vectorCount + hybridCount > 0) {
                        console.log(`  來源分布: 圖譜=${graphCount}, 向量=${vectorCount}, 混合=${hybridCount}`);
                    }
                }
            }

            // 避免過快請求
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        console.log('');
    }

    console.log('\n═══════════════════════════════════════');
    console.log('📊 測試總結');
    console.log('═══════════════════════════════════════');
    console.log('✓ Graph Only: 純知識圖譜檢索，速度最快');
    console.log('✓ Vector Only: 純向量語義檢索，理解語義');
    console.log('✓ Hybrid Balanced: 混合檢索，綜合優勢');
    console.log('═══════════════════════════════════════');
}

runTests().catch(console.error);
