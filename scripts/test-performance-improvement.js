/**
 * 效能測試腳本
 * 測試索引優化後的查詢效能改善
 */

const { dbManager } = require('../src/database/connection');

// 測試查詢列表 - 模擬常見的API查詢場景
const testQueries = [
    {
        name: "藝術作品搜索 - 標題關鍵字",
        query: `
            SELECT a.*, ar.name as artist_name
            FROM artworks a
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE a.title ILIKE '%Mona%'
            LIMIT 20
        `,
        description: "基本搜索功能 - 應使用 idx_artworks_title_trgm 索引"
    },
    {
        name: "藝術作品搜索 - 全文檢索",
        query: `
            SELECT * FROM artworks
            WHERE to_tsvector('english', title) @@ to_tsquery('english', 'landscape')
            LIMIT 20
        `,
        description: "全文搜索功能 - 應使用 idx_artworks_title_fulltext 索引"
    },
    {
        name: "藝術家按國籍查詢",
        query: `
            SELECT * FROM artists
            WHERE nationality = 'Italian'
            ORDER BY birth_year
            LIMIT 20
        `,
        description: "藝術家分類查詢 - 應使用 idx_artists_nationality 索引"
    },
    {
        name: "藝術作品按風格和時期查詢",
        query: `
            SELECT * FROM artworks
            WHERE style = 'Renaissance'
                AND creation_year BETWEEN 1400 AND 1600
            ORDER BY creation_year
            LIMIT 20
        `,
        description: "複合條件查詢 - 應使用 idx_artworks_style_year 復合索引"
    },
    {
        name: "藝術家作品統計",
        query: `
            SELECT a.*, ar.name as artist_name
            FROM artworks a
            JOIN artists ar ON a.artist_id = ar.id
            WHERE ar.nationality = 'French'
            ORDER BY a.creation_year DESC
            LIMIT 50
        `,
        description: "JOIN查詢 - 應使用多個索引組合優化"
    },
    {
        name: "館藏按機構查詢",
        query: `
            SELECT c.*, i.name as institution_name, a.title as artwork_title
            FROM collections c
            JOIN institutions i ON c.institution_id = i.id
            JOIN artworks a ON c.artwork_id = a.id
            WHERE i.country = 'France'
                AND c.status = 'active'
            ORDER BY c.acquisition_date DESC
            LIMIT 30
        `,
        description: "多表JOIN查詢 - 測試複合索引效果"
    },
    {
        name: "標籤使用統計",
        query: `
            SELECT t.name, COUNT(at.artwork_id) as usage_count
            FROM tags t
            LEFT JOIN artwork_tags at ON t.id = at.tag_id
            WHERE t.category = 'style'
            GROUP BY t.id, t.name
            ORDER BY usage_count DESC
            LIMIT 20
        `,
        description: "聚合查詢 - 測試標籤索引效果"
    }
];

async function measureQueryPerformance(query, queryName, description) {
    const pool = dbManager.getPostgresPool();
    const client = await pool.connect();

    try {
        console.log(`\n🔍 測試: ${queryName}`);
        console.log(`📝 描述: ${description}`);

        // 預熱查詢 - 避免冷啟動影響
        await client.query(query);

        // 實際測試 - 執行多次取平均值
        const iterations = 5;
        const times = [];

        for (let i = 0; i < iterations; i++) {
            const start = process.hrtime.bigint();
            const result = await client.query(query);
            const end = process.hrtime.bigint();

            const executionTime = Number(end - start) / 1000000; // 轉換為毫秒
            times.push(executionTime);

            if (i === 0) {
                console.log(`📊 返回記錄數: ${result.rows.length}`);
            }
        }

        // 計算統計數據
        const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);

        console.log(`⏱️  平均執行時間: ${avgTime.toFixed(2)}ms`);
        console.log(`⚡ 最快執行時間: ${minTime.toFixed(2)}ms`);
        console.log(`🐌 最慢執行時間: ${maxTime.toFixed(2)}ms`);

        // 獲取查詢執行計劃
        const explainResult = await client.query(`EXPLAIN (ANALYZE, BUFFERS) ${query}`);
        console.log(`📋 執行計劃關鍵信息:`);

        const planLines = explainResult.rows.map(row => row['QUERY PLAN']);
        const importantLines = planLines.filter(line =>
            line.includes('Index') ||
            line.includes('Seq Scan') ||
            line.includes('cost=') ||
            line.includes('actual time=')
        ).slice(0, 3); // 只顯示前3行重要信息

        importantLines.forEach(line => {
            if (line.includes('Index Scan')) {
                console.log(`   ✅ ${line.trim()}`);
            } else if (line.includes('Seq Scan')) {
                console.log(`   ⚠️  ${line.trim()}`);
            } else {
                console.log(`   📊 ${line.trim()}`);
            }
        });

        return {
            queryName,
            avgTime: avgTime.toFixed(2),
            minTime: minTime.toFixed(2),
            maxTime: maxTime.toFixed(2),
            resultCount: explainResult.rows.length > 0 ? 'Has results' : 'No results',
            usesIndex: planLines.some(line => line.includes('Index Scan'))
        };

    } finally {
        client.release();
    }
}

async function runPerformanceTests() {
    try {
        console.log('🚀 開始效能測試...\n');
        console.log('='.repeat(80));

        const results = [];

        for (const testQuery of testQueries) {
            const result = await measureQueryPerformance(
                testQuery.query,
                testQuery.name,
                testQuery.description
            );
            results.push(result);
        }

        // 生成測試總結報告
        console.log('\n' + '='.repeat(80));
        console.log('📈 效能測試總結報告');
        console.log('='.repeat(80));

        console.log('\n📊 查詢效能概覽:');
        console.log('查詢名稱'.padEnd(30) + '平均時間'.padEnd(12) + '索引使用'.padEnd(10) + '狀態');
        console.log('-'.repeat(70));

        results.forEach(result => {
            const status = parseFloat(result.avgTime) < 100 ? '🟢 優秀' :
                          parseFloat(result.avgTime) < 500 ? '🟡 良好' : '🔴 需優化';
            const indexStatus = result.usesIndex ? '✅ 是' : '❌ 否';

            console.log(
                result.queryName.padEnd(30) +
                (result.avgTime + 'ms').padEnd(12) +
                indexStatus.padEnd(10) +
                status
            );
        });

        // 統計分析
        const avgExecutionTime = results.reduce((sum, result) =>
            sum + parseFloat(result.avgTime), 0) / results.length;

        const indexUsageRate = results.filter(result => result.usesIndex).length / results.length * 100;

        console.log('\n📈 總體統計:');
        console.log(`   平均查詢時間: ${avgExecutionTime.toFixed(2)}ms`);
        console.log(`   索引使用率: ${indexUsageRate.toFixed(1)}%`);
        console.log(`   測試查詢數: ${results.length} 個`);

        // 效能評級
        let performanceGrade = 'A';
        if (avgExecutionTime > 100) performanceGrade = 'B';
        if (avgExecutionTime > 500) performanceGrade = 'C';
        if (indexUsageRate < 80) performanceGrade = performanceGrade === 'A' ? 'B' : 'C';

        console.log(`\n🏆 整體效能評級: ${performanceGrade}`);

        // 優化建議
        console.log('\n💡 優化建議:');
        if (indexUsageRate < 100) {
            console.log('   - 部分查詢未使用索引，建議檢查查詢條件和索引匹配');
        }
        if (avgExecutionTime > 50) {
            console.log('   - 平均查詢時間較長，考慮添加更多針對性索引');
        }
        if (performanceGrade === 'A') {
            console.log('   - 查詢效能良好，繼續監控和維護即可');
        }

        console.log('\n🎉 效能測試完成!');
        return results;

    } catch (error) {
        console.error('❌ 效能測試失敗:', error);
        throw error;
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    (async () => {
        try {
            // 初始化資料庫連接
            await dbManager.connectAll();

            // 執行效能測試
            await runPerformanceTests();

        } catch (error) {
            console.error('💥 測試執行失敗:', error);
            process.exit(1);
        } finally {
            // 關閉資料庫連接
            await dbManager.closeAll();
        }
    })();
}

module.exports = { runPerformanceTests };