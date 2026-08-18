#!/usr/bin/env node
const axios = require('axios');

async function quickTest() {
    try {
        const response = await axios.post('http://localhost:8007/api/v1/query', {
            query: 'American paintings',
            model_combination_id: 'llama3.1:8b@graph_only',
            max_results: 3,
            include_sources: true
        }, { timeout: 60000 });

        console.log('✅ 查詢成功！');
        console.log(`📚 找到文檔: ${response.data.metadata.num_sources} 個`);
        console.log(`⏱️  總時間: ${response.data.metadata.total_time_ms.toFixed(0)}ms`);

        if (response.data.sources && response.data.sources.length > 0) {
            console.log('\n📖 檢索結果:');
            response.data.sources.forEach((s, i) => {
                console.log(`  [${i+1}] ${s.source} - 分數: ${s.score?.toFixed(2)}`);
                console.log(`      ${s.content.substring(0, 100)}...`);
            });
        }
    } catch (error) {
        console.error('❌ 測試失敗:', error.response?.status || error.message);
        console.error('   詳情:', error.response?.data || error.message);
    }
}

quickTest();
