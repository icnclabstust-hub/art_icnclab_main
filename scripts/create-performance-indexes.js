/**
 * 效能索引創建腳本
 * 執行資料庫索引優化以提升查詢效能
 */

const fs = require('fs');
const path = require('path');
const { dbManager } = require('../src/database/connection');

async function createPerformanceIndexes() {
    const pool = dbManager.getPostgresPool();

    try {
        console.log('🔍 開始創建效能優化索引...');

        // 讀取索引SQL文件
        const sqlPath = path.join(__dirname, '../context/database/03-performance-indexes-clean.sql');
        const sqlContent = fs.readFileSync(sqlPath, 'utf8');

        // 分割SQL語句
        const sqlStatements = sqlContent
            .split(';')
            .map(stmt => stmt.trim())
            .filter(stmt => stmt.length > 0 && !stmt.startsWith('--') && !stmt.startsWith('/*'));

        console.log(`📊 準備執行 ${sqlStatements.length} 個索引創建語句...`);

        let successCount = 0;
        let skipCount = 0;
        let errorCount = 0;

        for (let i = 0; i < sqlStatements.length; i++) {
            const statement = sqlStatements[i];

            // 跳過查詢語句和DO塊
            if (statement.toLowerCase().includes('select') ||
                statement.toLowerCase().includes('do $$')) {
                console.log(`⏭️  跳過非索引語句: ${statement.substring(0, 50)}...`);
                skipCount++;
                continue;
            }

            try {
                console.log(`🔧 [${i + 1}/${sqlStatements.length}] 執行索引語句...`);

                const client = await pool.connect();
                try {
                    await client.query(statement);
                } finally {
                    client.release();
                }
                successCount++;

                // 從語句中提取索引名稱
                const indexNameMatch = statement.match(/INDEX\s+(?:IF NOT EXISTS\s+)?(\w+)/i);
                const indexName = indexNameMatch ? indexNameMatch[1] : 'unknown';

                console.log(`✅ 索引創建成功: ${indexName}`);

            } catch (error) {
                errorCount++;

                // 如果是索引已存在的錯誤，不算作失敗
                if (error.message.includes('already exists')) {
                    console.log(`ℹ️  索引已存在（跳過）: ${error.message.split(' ')[1]}`);
                    successCount++;
                    errorCount--;
                } else {
                    console.error(`❌ 索引創建失敗: ${error.message}`);
                    console.error(`   語句: ${statement.substring(0, 100)}...`);
                }
            }
        }

        // 檢查現有索引
        console.log('\n🔍 檢查現有索引狀況...');
        const indexQuery = `
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname NOT LIKE '%_pkey'
            ORDER BY tablename, indexname
        `;

        const client = await pool.connect();
        let indexResult;
        try {
            indexResult = await client.query(indexQuery);
        } finally {
            client.release();
        }
        console.log(`📋 當前共有 ${indexResult.rows.length} 個自定義索引`);

        // 按表分組顯示索引
        const indexesByTable = {};
        indexResult.rows.forEach(row => {
            if (!indexesByTable[row.tablename]) {
                indexesByTable[row.tablename] = [];
            }
            indexesByTable[row.tablename].push(row.indexname);
        });

        console.log('\n📊 索引分佈統計:');
        Object.entries(indexesByTable).forEach(([tableName, indexes]) => {
            console.log(`   ${tableName}: ${indexes.length} 個索引`);
            indexes.forEach(indexName => {
                console.log(`     - ${indexName}`);
            });
        });

        // 執行結果總結
        console.log('\n==============================================');
        console.log('📈 索引創建完成總結');
        console.log(`✅ 成功: ${successCount} 個`);
        console.log(`⏭️  跳過: ${skipCount} 個`);
        console.log(`❌ 錯誤: ${errorCount} 個`);
        console.log(`📋 現有索引總數: ${indexResult.rows.length} 個`);
        console.log('==============================================');

        // 提供優化建議
        if (indexResult.rows.length > 0) {
            console.log('\n💡 效能優化建議:');
            console.log('1. 監控慢查詢日誌以識別未優化的查詢');
            console.log('2. 使用 EXPLAIN ANALYZE 分析查詢執行計劃');
            console.log('3. 定期檢查索引使用統計 (pg_stat_user_indexes)');
            console.log('4. 考慮清理未使用的索引以減少寫入開銷');
        }

        return {
            success: true,
            successCount,
            skipCount,
            errorCount,
            totalIndexes: indexResult.rows.length
        };

    } catch (error) {
        console.error('❌ 索引創建過程發生錯誤:', error);
        throw error;
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    (async () => {
        try {
            console.log('🚀 啟動效能索引創建腳本...');

            // 初始化資料庫連接
            await dbManager.connectAll();

            // 執行索引創建
            const result = await createPerformanceIndexes();

            if (result.success) {
                console.log('🎉 索引創建腳本執行完成!');
                process.exit(0);
            } else {
                console.log('⚠️  索引創建腳本執行完成，但有部分失敗');
                process.exit(1);
            }

        } catch (error) {
            console.error('💥 腳本執行失敗:', error);
            process.exit(1);
        } finally {
            // 關閉資料庫連接
            await dbManager.closeAll();
        }
    })();
}

module.exports = { createPerformanceIndexes };