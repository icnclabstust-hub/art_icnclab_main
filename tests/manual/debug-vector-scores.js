#!/usr/bin/env node
/**
 * 調試向量檢索分數計算
 */

const axios = require('axios');

async function testVectorQuery() {
    console.log('🔍 調試向量檢索分數計算\n');

    try {
        const response = await axios.post('http://localhost:8008/query', {
            query: "達文西的作品",
            strategy: "vector_only",
            top_k: 5
        });

        const data = response.data;

        console.log('📊 查詢結果:');
        console.log(`策略: ${data.strategy_used}`);
        console.log(`信心分數: ${data.confidence_score}`);
        console.log(`處理時間: ${data.processing_time.toFixed(3)}秒`);
        console.log(`\n找到 ${data.sources.length} 個結果:\n`);

        data.sources.forEach((source, i) => {
            console.log(`${i + 1}. ${source.title.substring(0, 60)}${source.title.length > 60 ? '...' : ''}`);
            console.log(`   藝術家: ${source.artist}`);
            console.log(`   分數: ${source.score}`);
            console.log('');
        });

    } catch (error) {
        console.error('❌ 錯誤:', error.message);
        if (error.response) {
            console.error('響應:', error.response.data);
        }
    }
}

testVectorQuery();
