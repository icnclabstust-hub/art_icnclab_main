#!/usr/bin/env node
/**
 * 測試所有 RAG 策略查詢新增的藝術史資料
 */

const axios = require('axios');

const RAG_MANAGER_URL = 'http://localhost:8007';

async function testRAGStrategy(strategy, query, description) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`📊 策略: ${strategy}`);
    console.log(`🔍 查詢: ${query}`);
    console.log(`📝 說明: ${description}`);
    console.log(`${'='.repeat(80)}\n`);

    try {
        const response = await axios.post(`${RAG_MANAGER_URL}/api/v1/query`, {
            query: query,
            model_combination_id: `llama3.1:8b@${strategy}`,
            max_results: 3,
            include_sources: true
        }, {
            timeout: 60000
        });

        const result = response.data;

        console.log(`✅ 查詢成功`);
        console.log(`⏱️  檢索時間: ${result.retrieval_time_ms.toFixed(2)}ms`);
        console.log(`⏱️  生成時間: ${result.generation_time_ms.toFixed(2)}ms`);
        console.log(`📚 找到文檔: ${result.metadata.num_sources} 個`);

        if (result.sources && result.sources.length > 0) {
            console.log(`\n📖 檢索結果:\n`);
            result.sources.forEach((source, i) => {
                console.log(`  [${i + 1}] ${source.source} (分數: ${source.score?.toFixed(3) || 'N/A'})`);
                console.log(`      ${source.content.substring(0, 80)}...`);
            });

            console.log(`\n💬 答案預覽:\n${result.answer.substring(0, 200)}...\n`);
        } else {
            console.log(`⚠️  未找到相關文檔\n`);
        }

        return {
            success: true,
            strategy: strategy,
            sources_count: result.sources.length,
            retrieval_time: result.retrieval_time_ms,
            query: query
        };

    } catch (error) {
        console.error(`❌ 查詢失敗: ${error.message}`);
        if (error.response) {
            console.error(`   狀態碼: ${error.response.status}`);
        }
        return {
            success: false,
            strategy: strategy,
            error: error.message,
            query: query
        };
    }
}

async function runTests() {
    console.log('🚀 開始測試所有 RAG 策略查詢新增的藝術史資料\n');
    console.log(`📡 連接到: ${RAG_MANAGER_URL}\n`);

    const testCases = [
        {
            strategy: 'vector_only',
            query: '達文西的作品',
            description: 'Vector RAG - 多語言查詢'
        },
        {
            strategy: 'graph_only',
            query: 'Leonardo da Vinci',
            description: 'Graph RAG - 藝術家查詢'
        },
        {
            strategy: 'hybrid_balanced',
            query: 'Renaissance paintings',
            description: 'Hybrid RAG - 混合檢索'
        },
        {
            strategy: 'advanced_rag',
            query: 'Baroque sculptures',
            description: 'Advanced RAG - 高級檢索'
        }
    ];

    const results = [];

    for (const test of testCases) {
        const result = await testRAGStrategy(test.strategy, test.query, test.description);
        results.push(result);

        // 延遲避免過載
        await new Promise(resolve => setTimeout(resolve, 2000));
    }

    // 總結
    console.log('\n' + '='.repeat(80));
    console.log('📊 測試總結');
    console.log('='.repeat(80) + '\n');

    const byStrategy = {};
    results.forEach(r => {
        if (!byStrategy[r.strategy]) {
            byStrategy[r.strategy] = { success: 0, failed: 0, withResults: 0, noResults: 0 };
        }
        if (r.success) {
            byStrategy[r.strategy].success++;
            if (r.sources_count > 0) {
                byStrategy[r.strategy].withResults++;
            } else {
                byStrategy[r.strategy].noResults++;
            }
        } else {
            byStrategy[r.strategy].failed++;
        }
    });

    console.log('各策略測試結果:\n');
    Object.keys(byStrategy).forEach(strategy => {
        const stats = byStrategy[strategy];
        const status = stats.success > 0 && stats.withResults > 0 ? '✅' : (stats.failed > 0 ? '❌' : '⚠️ ');
        console.log(`${status} ${strategy}:`);
        console.log(`   成功: ${stats.success}, 有結果: ${stats.withResults}, 無結果: ${stats.noResults}, 失敗: ${stats.failed}`);
    });

    const allSuccess = results.every(r => r.success);
    const allWithResults = results.every(r => r.success && r.sources_count > 0);

    console.log('\n總結:');
    if (allWithResults) {
        console.log('🎉 所有 RAG 策略都正常工作且返回結果！');
    } else if (allSuccess) {
        console.log('✅ 所有 RAG 策略都正常工作（部分查詢無結果）');
    } else {
        console.log('⚠️  部分 RAG 策略存在問題');
    }
}

// 執行測試
runTests().catch(error => {
    console.error('❌ 測試執行失敗:', error.message);
    process.exit(1);
});
