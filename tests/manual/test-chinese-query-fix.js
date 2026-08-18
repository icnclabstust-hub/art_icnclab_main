#!/usr/bin/env node
/**
 * 測試中文查詢修復後的效果
 * 驗證多語言翻譯功能是否正常工作
 */

const axios = require('axios');

const RAG_MANAGER_URL = 'http://localhost:8007';

async function testChineseQuery(query, description) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`測試: ${description}`);
    console.log(`查詢: "${query}"`);
    console.log('='.repeat(60));

    try {
        const response = await axios.post(`${RAG_MANAGER_URL}/api/v1/query`, {
            query: query,
            model_combination_id: "llama3.1:8b@vector_only",
            top_k: 5
        }, { timeout: 60000 });

        const data = response.data;

        console.log(`\n✅ 查詢成功`);
        console.log(`答案長度: ${data.answer.length} 字符`);
        console.log(`來源數量: ${data.sources.length}`);

        console.log(`\n📚 檢索到的來源:`);
        data.sources.forEach((source, idx) => {
            console.log(`${idx + 1}. ${source.metadata.title}`);
            console.log(`   藝術家: ${source.metadata.artist || 'Unknown'}`);
            console.log(`   相關度: ${(source.score * 100).toFixed(1)}%`);
        });

        console.log(`\n💬 答案摘要:`);
        console.log(data.answer.substring(0, 300) + '...');

        // 檢查答案品質
        const hasRelevantInfo = data.answer.length > 100 &&
                                !data.answer.includes('参照资料中出现') &&
                                !data.answer.includes('並沒有在您提供的參照資料');

        console.log(`\n品質評估: ${hasRelevantInfo ? '✅ 找到相關資訊' : '❌ 未找到相關資訊'}`);

        return {
            success: hasRelevantInfo,
            sourcesCount: data.sources.length,
            answerLength: data.answer.length
        };

    } catch (error) {
        console.log(`\n❌ 查詢失敗: ${error.message}`);
        if (error.response) {
            console.log(`狀態碼: ${error.response.status}`);
            console.log(`錯誤: ${error.response.data?.error || error.response.data?.detail || '未知'}`);
        }
        return {
            success: false,
            error: error.message
        };
    }
}

async function main() {
    console.log('╔═══════════════════════════════════════════════════════════╗');
    console.log('║          中文查詢修復驗證測試                              ║');
    console.log('║   測試多語言翻譯功能是否正常工作                            ║');
    console.log('╚═══════════════════════════════════════════════════════════╝');

    const tests = [
        {
            query: "達文西的代表作品有哪些",
            description: "查詢達文西的作品（中文）"
        },
        {
            query: "文藝復興時期的著名藝術家",
            description: "查詢文藝復興藝術家（中文）"
        },
        {
            query: "巴洛克時期的繪畫特點",
            description: "查詢巴洛克繪畫特點（中文）"
        },
        {
            query: "林布蘭的自畫像",
            description: "查詢林布蘭的作品（中文）"
        },
        {
            query: "最後的晚餐是誰創作的",
            description: "查詢名畫作者（中文）"
        }
    ];

    const results = [];

    for (const test of tests) {
        const result = await testChineseQuery(test.query, test.description);
        results.push({
            ...test,
            ...result
        });

        // 間隔一下避免請求過快
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    // 打印總結
    console.log(`\n\n╔═══════════════════════════════════════════════════════════╗`);
    console.log(`║                    測試總結                                ║`);
    console.log(`╚═══════════════════════════════════════════════════════════╝`);

    const successCount = results.filter(r => r.success).length;
    const totalCount = results.length;
    const successRate = (successCount / totalCount * 100).toFixed(1);

    console.log(`\n總測試數: ${totalCount}`);
    console.log(`成功: ${successCount}`);
    console.log(`失敗: ${totalCount - successCount}`);
    console.log(`成功率: ${successRate}%`);

    console.log(`\n詳細結果:`);
    results.forEach((result, idx) => {
        const icon = result.success ? '✅' : '❌';
        console.log(`${icon} ${idx + 1}. ${result.description}`);
        if (result.success) {
            console.log(`      來源: ${result.sourcesCount}個, 答案: ${result.answerLength}字`);
        } else {
            console.log(`      錯誤: ${result.error || '未找到相關資訊'}`);
        }
    });

    if (successRate >= 80) {
        console.log(`\n🎉 測試通過！中文查詢功能已修復！`);
    } else if (successRate >= 60) {
        console.log(`\n⚠️ 部分成功，但仍需改進檢索品質`);
    } else {
        console.log(`\n❌ 測試失敗，需要進一步排查問題`);
    }

    console.log(`\n提示: 用戶現在可以在OpenWebUI中使用中文查詢`);
    console.log(`訪問: http://localhost:8080`);
    console.log(`\n${'='.repeat(63)}\n`);
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = { testChineseQuery };
