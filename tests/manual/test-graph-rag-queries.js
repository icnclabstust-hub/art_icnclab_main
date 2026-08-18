#!/usr/bin/env node
/**
 * 測試 Graph RAG 策略查詢新增的藝術史資料
 */

const axios = require('axios');

const RAG_MANAGER_URL = 'http://localhost:8007';

async function testGraphRAG(query, description) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`📊 測試: ${description}`);
    console.log(`🔍 查詢: ${query}`);
    console.log(`${'='.repeat(80)}\n`);

    try {
        const response = await axios.post(`${RAG_MANAGER_URL}/api/v1/query`, {
            query: query,
            model_combination_id: 'llama3.1:8b@graph_only',
            max_results: 5,
            include_sources: true
        }, {
            timeout: 60000
        });

        const result = response.data;

        console.log(`✅ 查詢成功`);
        console.log(`⏱️  檢索時間: ${result.retrieval_time_ms.toFixed(2)}ms`);
        console.log(`⏱️  生成時間: ${result.generation_time_ms.toFixed(2)}ms`);
        console.log(`📚 找到文檔: ${result.metadata.num_sources} 個\n`);

        if (result.sources && result.sources.length > 0) {
            console.log(`📖 檢索結果:\n`);
            result.sources.forEach((source, i) => {
                console.log(`  [${i + 1}] 來源: ${source.source}`);
                console.log(`      分數: ${source.score?.toFixed(3) || 'N/A'}`);
                console.log(`      內容預覽: ${source.content.substring(0, 150)}...`);
                if (source.metadata) {
                    console.log(`      元數據:`, JSON.stringify(source.metadata, null, 2).substring(0, 200));
                }
                console.log();
            });

            console.log(`\n💬 生成答案:\n${result.answer}\n`);
        } else {
            console.log(`⚠️  未找到相關文檔`);
            console.log(`💬 生成答案:\n${result.answer}\n`);
        }

        return {
            success: true,
            sources_count: result.sources.length,
            query: query
        };

    } catch (error) {
        console.error(`❌ 查詢失敗: ${error.message}`);
        if (error.response) {
            console.error(`   狀態碼: ${error.response.status}`);
            console.error(`   錯誤詳情:`, JSON.stringify(error.response.data, null, 2));
        }
        return {
            success: false,
            error: error.message,
            query: query
        };
    }
}

async function runTests() {
    console.log('🚀 開始測試 Graph RAG 策略查詢新增的藝術史資料\n');
    console.log(`📡 連接到: ${RAG_MANAGER_URL}\n`);

    // 測試查詢列表
    const testQueries = [
        {
            query: 'Gilbert Stuart',
            description: 'Harvard 資料 - 藝術家 Gilbert Stuart'
        },
        {
            query: 'Thomas Jefferson portrait',
            description: 'Harvard 資料 - Thomas Jefferson 肖像'
        },
        {
            query: 'George Washington',
            description: 'Harvard 資料 - George Washington 相關作品'
        },
        {
            query: 'American paintings 18th century',
            description: 'Harvard 資料 - 18世紀美國繪畫'
        },
        {
            query: '達文西',
            description: '多語言查詢 - 中文查詢達文西'
        },
        {
            query: 'Baroque period sculptures',
            description: '通用查詢 - 巴洛克時期雕塑'
        }
    ];

    const results = [];

    for (const test of testQueries) {
        const result = await testGraphRAG(test.query, test.description);
        results.push(result);

        // 延遲避免過載
        await new Promise(resolve => setTimeout(resolve, 2000));
    }

    // 總結
    console.log('\n' + '='.repeat(80));
    console.log('📊 測試總結');
    console.log('='.repeat(80) + '\n');

    const successful = results.filter(r => r.success).length;
    const withResults = results.filter(r => r.success && r.sources_count > 0).length;
    const noResults = results.filter(r => r.success && r.sources_count === 0).length;
    const failed = results.filter(r => !r.success).length;

    console.log(`總測試數: ${results.length}`);
    console.log(`✅ 成功查詢: ${successful}`);
    console.log(`📚 有結果: ${withResults}`);
    console.log(`⚠️  無結果: ${noResults}`);
    console.log(`❌ 失敗: ${failed}\n`);

    if (noResults > 0) {
        console.log('⚠️  以下查詢沒有返回結果:');
        results.filter(r => r.success && r.sources_count === 0).forEach(r => {
            console.log(`   - ${r.query}`);
        });
        console.log();
    }

    if (failed > 0) {
        console.log('❌ 以下查詢失敗:');
        results.filter(r => !r.success).forEach(r => {
            console.log(`   - ${r.query}: ${r.error}`);
        });
        console.log();
    }

    if (withResults === results.length) {
        console.log('🎉 所有查詢都成功返回結果！Graph RAG 工作正常！');
    } else if (withResults > 0) {
        console.log('⚠️  部分查詢返回結果，Graph RAG 部分正常工作');
    } else {
        console.log('❌ 沒有查詢返回結果，Graph RAG 可能存在問題');
    }
}

// 執行測試
runTests().catch(error => {
    console.error('❌ 測試執行失敗:', error.message);
    process.exit(1);
});
