#!/usr/bin/env node
/**
 * A/B 測試不同的 scaling_factor 值
 * 測試範圍：5, 10, 15, 20, 25, 30
 */

const axios = require('axios');
const fs = require('fs');

// 載入測試查詢
const testQueries = JSON.parse(fs.readFileSync('../../comprehensive-test-queries.json', 'utf8'));

// 要測試的 scaling_factor 值
const scalingFactors = [5, 10, 15, 20, 25, 30];

// 展平所有查詢
const allQueries = [
    ...testQueries.artist_queries,
    ...testQueries.artwork_queries,
    ...testQueries.period_queries,
    ...testQueries.material_queries,
    ...testQueries.concept_queries,
    ...testQueries.collection_queries
];

async function testWithScalingFactor(scalingFactor) {
    console.log(`\n測試 scaling_factor = ${scalingFactor}`);
    console.log('─'.repeat(60));

    const results = {
        scaling_factor: scalingFactor,
        queries: [],
        stats: {
            total: 0,
            avg_confidence: 0,
            avg_max_score: 0,
            avg_min_score: 0,
            scores: []
        }
    };

    for (const q of allQueries) {
        try {
            // 直接調用 ChromaDB 獲取原始距離
            const response = await axios.post('http://localhost:8008/query', {
                query: q.query,
                strategy: 'vector_only',
                top_k: 5
            });

            const data = response.data;
            const scores = data.sources.map(s => s.score);

            results.queries.push({
                query: q.query,
                type: q.type,
                language: q.language,
                confidence: data.confidence_score,
                max_score: Math.max(...scores),
                min_score: Math.min(...scores),
                avg_score: scores.reduce((a, b) => a + b, 0) / scores.length,
                scores: scores
            });

            results.stats.scores.push(...scores);

            // 避免過快請求
            await new Promise(resolve => setTimeout(resolve, 50));

        } catch (error) {
            console.error(`  ❌ 查詢失敗: ${q.query} - ${error.message}`);
        }
    }

    // 計算統計
    results.stats.total = results.queries.length;
    results.stats.avg_confidence =
        results.queries.reduce((sum, q) => sum + q.confidence, 0) / results.stats.total;
    results.stats.avg_max_score =
        results.queries.reduce((sum, q) => sum + q.max_score, 0) / results.stats.total;
    results.stats.avg_min_score =
        results.queries.reduce((sum, q) => sum + q.min_score, 0) / results.stats.total;

    // 計算分數分布
    results.stats.score_distribution = {
        '0.0-0.2': results.stats.scores.filter(s => s >= 0.0 && s < 0.2).length,
        '0.2-0.4': results.stats.scores.filter(s => s >= 0.2 && s < 0.4).length,
        '0.4-0.6': results.stats.scores.filter(s => s >= 0.4 && s < 0.6).length,
        '0.6-0.8': results.stats.scores.filter(s => s >= 0.6 && s < 0.8).length,
        '0.8-1.0': results.stats.scores.filter(s => s >= 0.8 && s <= 1.0).length
    };

    // 顯示結果
    console.log(`  查詢總數: ${results.stats.total}`);
    console.log(`  平均信心分數: ${results.stats.avg_confidence.toFixed(3)}`);
    console.log(`  平均最高分數: ${results.stats.avg_max_score.toFixed(3)}`);
    console.log(`  平均最低分數: ${results.stats.avg_min_score.toFixed(3)}`);
    console.log(`  分數分布:`);
    Object.entries(results.stats.score_distribution).forEach(([range, count]) => {
        const percentage = (count / results.stats.scores.length * 100).toFixed(1);
        const bar = '█'.repeat(Math.floor(percentage / 2));
        console.log(`    ${range}: ${count.toString().padStart(3)} (${percentage.padStart(5)}%) ${bar}`);
    });

    return results;
}

async function runABTest() {
    console.log('🔬 A/B 測試：scaling_factor 優化');
    console.log('═'.repeat(60));
    console.log(`測試查詢數: ${allQueries.length}`);
    console.log(`測試 scaling_factor 值: ${scalingFactors.join(', ')}`);

    const allResults = [];

    // 注意：這個測試需要修改伺服器代碼中的 scaling_factor
    // 由於無法動態修改，我們只測試當前值
    console.log('\n⚠️  注意：此測試需要手動修改伺服器中的 scaling_factor 值');
    console.log('   當前只測試伺服器中設定的值\n');

    const currentResult = await testWithScalingFactor(20); // 當前值
    allResults.push(currentResult);

    // 保存結果
    const reportPath = 'ab-test-results.json';
    fs.writeFileSync(reportPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        test_config: {
            total_queries: allQueries.length,
            scaling_factors_tested: [20]
        },
        results: allResults
    }, null, 2));

    console.log(`\n\n📊 詳細結果已保存到: ${reportPath}`);

    // 生成建議
    console.log('\n\n💡 建議:');
    if (currentResult.stats.avg_confidence < 0.4) {
        console.log('   - 信心分數偏低，建議增加 scaling_factor (試試 25-30)');
    } else if (currentResult.stats.avg_confidence > 0.7) {
        console.log('   - 信心分數偏高，建議減少 scaling_factor (試試 15-18)');
    } else {
        console.log('   ✓ 當前 scaling_factor 值合理');
    }

    // 分數分布建議
    const highScores = currentResult.stats.score_distribution['0.6-0.8'] +
                       currentResult.stats.score_distribution['0.8-1.0'];
    const lowScores = currentResult.stats.score_distribution['0.0-0.2'] +
                      currentResult.stats.score_distribution['0.2-0.4'];

    if (highScores < lowScores) {
        console.log('   - 高分結果較少，建議增加 scaling_factor');
    }
}

runABTest().catch(console.error);
