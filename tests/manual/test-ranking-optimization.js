#!/usr/bin/env node
/**
 * 測試排序優化效果
 * 對比優化前後的排序結果
 */

const axios = require('axios');

// 測試查詢集
const testQueries = [
    { query: "達文西的作品", type: "artist", language: "zh" },
    { query: "Leonardo da Vinci artworks", type: "artist", language: "en" },
    { query: "Renaissance paintings", type: "period", language: "en" },
    { query: "文藝復興時期的繪畫", type: "period", language: "zh" },
    { query: "Mona Lisa", type: "artwork", language: "en" },
    { query: "蒙娜麗莎", type: "artwork", language: "zh" },
    { query: "Baroque art in museums", type: "complex", language: "en" },
    { query: "羅浮宮收藏的作品", type: "complex", language: "zh" }
];

// 測試策略
const strategies = ["graph_only", "vector_only", "hybrid_balanced"];

async function testStrategy(strategy, query) {
    try {
        const response = await axios.post('http://localhost:8008/query', {
            query: query.query,
            strategy: strategy,
            top_k: 5
        });

        const data = response.data;
        return {
            query: query.query,
            type: query.type,
            language: query.language,
            strategy: strategy,
            confidence: data.confidence_score,
            processing_time: data.processing_time,
            sources: data.sources.map(s => ({
                title: s.title,
                artist: s.artist,
                score: s.score,
                bm25_score: s.bm25_score,
                graph_score: s.graph_score,
                vector_score: s.vector_score,
                source: s.source
            }))
        };
    } catch (error) {
        console.error(`  ❌ 查詢失敗: ${query.query} (${strategy}) - ${error.message}`);
        return null;
    }
}

async function runTests() {
    console.log('🔬 測試排序優化效果');
    console.log('═'.repeat(80));
    console.log(`測試查詢數: ${testQueries.length}`);
    console.log(`測試策略: ${strategies.join(', ')}`);
    console.log('\n');

    const results = {};

    for (const query of testQueries) {
        console.log(`\n查詢: ${query.query} (${query.type}, ${query.language})`);
        console.log('─'.repeat(80));

        results[query.query] = {};

        for (const strategy of strategies) {
            const result = await testStrategy(strategy, query);
            if (result) {
                results[query.query][strategy] = result;

                console.log(`\n  ${strategy}:`);
                console.log(`    信心分數: ${result.confidence.toFixed(3)}`);
                console.log(`    處理時間: ${(result.processing_time * 1000).toFixed(1)}ms`);
                console.log(`    結果數: ${result.sources.length}`);

                if (result.sources.length > 0) {
                    console.log(`    Top 3 結果:`);
                    result.sources.slice(0, 3).forEach((s, i) => {
                        const scoreInfo = [];
                        scoreInfo.push(`總分: ${s.score.toFixed(3)}`);
                        if (s.bm25_score !== undefined) {
                            scoreInfo.push(`BM25: ${s.bm25_score.toFixed(3)}`);
                        }
                        if (s.graph_score !== undefined && s.graph_score > 0) {
                            scoreInfo.push(`Graph: ${s.graph_score.toFixed(3)}`);
                        }
                        if (s.vector_score !== undefined && s.vector_score > 0) {
                            scoreInfo.push(`Vector: ${s.vector_score.toFixed(3)}`);
                        }
                        if (s.source) {
                            scoreInfo.push(`來源: ${s.source}`);
                        }

                        console.log(`      ${i + 1}. ${s.title} (${s.artist})`);
                        console.log(`         ${scoreInfo.join(', ')}`);
                    });
                }
            }

            // 避免過快請求
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }

    // 生成統計報告
    console.log('\n\n📊 統計報告');
    console.log('═'.repeat(80));

    const stats = {};
    strategies.forEach(strategy => {
        stats[strategy] = {
            avg_confidence: 0,
            avg_processing_time: 0,
            total_results: 0,
            count: 0
        };
    });

    Object.values(results).forEach(queryResults => {
        Object.entries(queryResults).forEach(([strategy, data]) => {
            stats[strategy].avg_confidence += data.confidence;
            stats[strategy].avg_processing_time += data.processing_time;
            stats[strategy].total_results += data.sources.length;
            stats[strategy].count += 1;
        });
    });

    strategies.forEach(strategy => {
        if (stats[strategy].count > 0) {
            console.log(`\n${strategy}:`);
            console.log(`  平均信心分數: ${(stats[strategy].avg_confidence / stats[strategy].count).toFixed(3)}`);
            console.log(`  平均處理時間: ${(stats[strategy].avg_processing_time / stats[strategy].count * 1000).toFixed(1)}ms`);
            console.log(`  平均結果數: ${(stats[strategy].total_results / stats[strategy].count).toFixed(1)}`);
        }
    });

    // 保存詳細結果
    const fs = require('fs');
    fs.writeFileSync('ranking-optimization-test-results.json', JSON.stringify({
        timestamp: new Date().toISOString(),
        test_config: {
            total_queries: testQueries.length,
            strategies: strategies
        },
        results: results,
        stats: stats
    }, null, 2));

    console.log('\n\n✅ 詳細結果已保存到: ranking-optimization-test-results.json');

    // 關鍵改進總結
    console.log('\n\n💡 關鍵改進:');
    console.log('   1. Graph策略: 使用 BM25 + 實體重要性替代固定分數');
    console.log('   2. Hybrid策略: 使用調和平均融合分數，雙重匹配加成 20%');
    console.log('   3. 分數範圍: 更合理的歸一化到 [0, 1] 範圍');
    console.log('   4. 多因素排序: BM25 (70%) + 實體重要性 (30%)');
}

runTests().catch(console.error);
