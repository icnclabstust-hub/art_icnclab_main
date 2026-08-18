#!/usr/bin/env node
/**
 * 測試核心作品的中文查詢效果
 */

const axios = require('axios');

const queries = [
    { query: "蒙娜麗莎", expected: "Mona Lisa" },
    { query: "最後的晚餐", expected: "Last Supper" },
    { query: "大衛像", expected: "David" },
    { query: "創世紀", expected: "Creation of Adam" },
    { query: "雅典學院", expected: "School of Athens" },
    { query: "維納斯的誕生", expected: "Birth of Venus" },
    { query: "夜巡", expected: "Night Watch" },
    { query: "戴珍珠耳環的少女", expected: "Pearl Earring" },
    { query: "達文西的作品", expected: "Leonardo" },
    { query: "米開朗基羅的雕塑", expected: "Michelangelo" },
    { query: "拉斐爾的壁畫", expected: "Raphael" },
    { query: "文藝復興時期的繪畫", expected: "Renaissance" },
    { query: "巴洛克繪畫", expected: "Baroque" }
];

async function testQuery(queryText, expected) {
    try {
        const response = await axios.post('http://localhost:8008/query', {
            query: queryText,
            strategy: 'graph_only'
        });

        const data = response.data;
        const sources = data.sources || [];

        // 檢查是否找到預期的作品
        const found = sources.some(s =>
            (s.title && s.title.includes(expected)) ||
            (s.artist && s.artist.includes(expected)) ||
            (s.period && s.period.includes(expected))
        );

        return {
            query: queryText,
            expected,
            found,
            count: sources.length,
            firstResult: sources[0] ? sources[0].title : 'N/A'
        };

    } catch (error) {
        return {
            query: queryText,
            expected,
            found: false,
            error: error.message
        };
    }
}

async function runTests() {
    console.log('🎨 核心作品中文查詢測試');
    console.log('═══════════════════════════════════════\n');

    let success = 0;
    let total = queries.length;

    for (const { query, expected } of queries) {
        const result = await testQuery(query, expected);

        if (result.found) {
            console.log(`✓ "${result.query}"`);
            console.log(`  找到相關結果: ${result.count} 件`);
            console.log(`  第一項: ${result.firstResult}`);
            success++;
        } else if (result.error) {
            console.log(`✗ "${result.query}" - 錯誤: ${result.error}`);
        } else {
            console.log(`⚠ "${result.query}"`);
            console.log(`  找到: ${result.count} 件，但不包含 "${result.expected}"`);
            console.log(`  第一項: ${result.firstResult}`);
        }
        console.log('');

        // 避免過快請求
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    console.log('═══════════════════════════════════════');
    console.log(`總測試數: ${total}`);
    console.log(`成功: ${success} (${(success/total*100).toFixed(1)}%)`);
    console.log(`失敗: ${total - success}`);
    console.log('═══════════════════════════════════════');
}

runTests().catch(console.error);
