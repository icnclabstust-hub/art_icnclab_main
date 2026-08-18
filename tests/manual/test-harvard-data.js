#!/usr/bin/env node
const axios = require('axios');

async function testHarvardQuery(query) {
    console.log(`\n${'='.repeat(70)}`);
    console.log(`🔍 查詢: ${query}`);
    console.log('='.repeat(70));

    try {
        const response = await axios.post('http://localhost:8007/api/v1/query', {
            query: query,
            model_combination_id: 'llama3.1:8b@graph_only',
            max_results: 5,
            include_sources: true
        }, { timeout: 60000 });

        console.log(`\n✅ 查詢成功！`);
        console.log(`📚 找到文檔: ${response.data.metadata.num_sources} 個`);
        console.log(`⏱️  檢索時間: ${response.data.retrieval_time_ms.toFixed(2)}ms`);
        console.log(`⏱️  生成時間: ${response.data.generation_time_ms.toFixed(2)}ms`);

        if (response.data.sources && response.data.sources.length > 0) {
            console.log('\n📖 檢索結果:\n');
            response.data.sources.forEach((s, i) => {
                console.log(`[${i+1}] ${s.source} (分數: ${s.score.toFixed(2)})`);
                console.log(`    ${s.content.substring(0, 150).replace(/\n/g, ' ')}...`);
                if (s.metadata && s.metadata.source) {
                    console.log(`    來源: ${s.metadata.source}`);
                }
                console.log();
            });

            console.log('💬 生成答案:');
            console.log(response.data.answer);
            console.log();
        } else {
            console.log('\n⚠️  未找到相關文檔');
        }

        return response.data.sources.length > 0;
    } catch (error) {
        console.error(`\n❌ 查詢失敗: ${error.message}`);
        if (error.response) {
            console.error(`狀態碼: ${error.response.status}`);
        }
        return false;
    }
}

async function main() {
    console.log('🎨 測試 Harvard Art Museums 數據查詢\n');

    const testQueries = [
        'Gilbert Stuart',
        'Thomas Jefferson portrait',
        'George Washington',
        'American paintings 19th century'
    ];

    let successCount = 0;
    let withResultsCount = 0;

    for (const query of testQueries) {
        const hasResults = await testHarvardQuery(query);
        successCount++;
        if (hasResults) withResultsCount++;

        await new Promise(resolve => setTimeout(resolve, 2000));
    }

    console.log('\n' + '='.repeat(70));
    console.log('📊 測試總結');
    console.log('='.repeat(70));
    console.log(`總測試數: ${testQueries.length}`);
    console.log(`✅ 成功查詢: ${successCount}`);
    console.log(`📚 有結果: ${withResultsCount}`);
    console.log(`⚠️  無結果: ${successCount - withResultsCount}`);

    if (withResultsCount === testQueries.length) {
        console.log('\n🎉 所有 Harvard 查詢都成功返回結果！');
    } else if (withResultsCount > 0) {
        console.log('\n✅ 部分 Harvard 查詢返回結果');
    } else {
        console.log('\n❌ 沒有查詢返回結果');
    }
}

main().catch(error => {
    console.error('❌ 測試失敗:', error.message);
    process.exit(1);
});
