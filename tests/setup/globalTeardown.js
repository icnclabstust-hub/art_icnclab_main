/**
 * Jest全局清理
 * 測試後的一次性清理
 */

const { dbManager } = require('../../src/database/connection');

module.exports = async () => {
    console.log('🧹 開始全局測試清理...');

    try {
        // 清理所有測試資料
        await cleanupAllTestData();

        // 關閉資料庫連接
        await dbManager.closeAll();

        console.log('✅ 全局測試清理完成');

    } catch (error) {
        console.error('❌ 全局測試清理失敗:', error);
    }
};

// 清理所有測試資料
async function cleanupAllTestData() {
    try {
        if (!dbManager.isConnected.postgres) {
            console.log('跳過資料清理：資料庫未連接');
            return;
        }

        const pool = dbManager.getPostgresPool();
        const client = await pool.connect();

        // 獲取所有測試資料的統計
        const statsQuery = `
            SELECT
                'artists' as table_name,
                COUNT(*) as test_count
            FROM artists WHERE metadata->>'test' = 'true'
            UNION ALL
            SELECT
                'artworks' as table_name,
                COUNT(*) as test_count
            FROM artworks WHERE metadata->>'test' = 'true'
            UNION ALL
            SELECT
                'institutions' as table_name,
                COUNT(*) as test_count
            FROM institutions WHERE metadata->>'test' = 'true'
            UNION ALL
            SELECT
                'tags' as table_name,
                COUNT(*) as test_count
            FROM tags WHERE metadata->>'test' = 'true'
            UNION ALL
            SELECT
                'document_vectors' as table_name,
                COUNT(*) as test_count
            FROM document_vectors WHERE metadata->>'test' = 'true'
            UNION ALL
            SELECT
                'crawl_tasks' as table_name,
                COUNT(*) as test_count
            FROM crawl_tasks WHERE metadata->>'test' = 'true'
        `;

        const statsResult = await client.query(statsQuery);
        const testDataCounts = statsResult.rows.reduce((acc, row) => {
            if (row.test_count > 0) {
                acc[row.table_name] = row.test_count;
            }
            return acc;
        }, {});

        if (Object.keys(testDataCounts).length > 0) {
            console.log('📊 發現以下測試資料需要清理:');
            Object.entries(testDataCounts).forEach(([table, count]) => {
                console.log(`   - ${table}: ${count} 條記錄`);
            });
        }

        // 按照正確的順序刪除測試資料（處理外鍵約束）
        const cleanupQueries = [
            // 先刪除關聯表
            {
                query: "DELETE FROM artwork_tags WHERE artwork_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true')",
                description: 'artwork_tags (關聯)'
            },
            {
                query: "DELETE FROM collections WHERE artwork_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true') OR institution_id IN (SELECT id FROM institutions WHERE metadata->>'test' = 'true')",
                description: 'collections (關聯)'
            },
            {
                query: "DELETE FROM artist_movements WHERE artist_id IN (SELECT id FROM artists WHERE metadata->>'test' = 'true')",
                description: 'artist_movements (關聯)'
            },
            {
                query: "DELETE FROM processing_logs WHERE entity_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true') OR entity_id IN (SELECT id FROM artists WHERE metadata->>'test' = 'true')",
                description: 'processing_logs'
            },

            // 再刪除主要表
            {
                query: "DELETE FROM document_vectors WHERE metadata->>'test' = 'true'",
                description: 'document_vectors'
            },
            {
                query: "DELETE FROM crawl_tasks WHERE metadata->>'test' = 'true'",
                description: 'crawl_tasks'
            },
            {
                query: "DELETE FROM search_queries WHERE metadata->>'test' = 'true'",
                description: 'search_queries'
            },
            {
                query: "DELETE FROM artworks WHERE metadata->>'test' = 'true'",
                description: 'artworks'
            },
            {
                query: "DELETE FROM artists WHERE metadata->>'test' = 'true'",
                description: 'artists'
            },
            {
                query: "DELETE FROM institutions WHERE metadata->>'test' = 'true'",
                description: 'institutions'
            },
            {
                query: "DELETE FROM tags WHERE metadata->>'test' = 'true'",
                description: 'tags'
            }
        ];

        let totalCleaned = 0;

        for (const { query, description } of cleanupQueries) {
            try {
                const result = await client.query(query);
                if (result.rowCount > 0) {
                    console.log(`🗑️  清理 ${description}: ${result.rowCount} 條記錄`);
                    totalCleaned += result.rowCount;
                }
            } catch (error) {
                console.warn(`⚠️  清理 ${description} 失敗: ${error.message}`);
            }
        }

        // 重置序列（如果有使用自增ID）
        try {
            await client.query(`
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE 'pg_%') LOOP
                        EXECUTE 'ALTER SEQUENCE IF EXISTS ' || quote_ident(r.tablename) || '_id_seq RESTART WITH 1';
                    END LOOP;
                END $$;
            `);
            console.log('🔄 序列重置完成');
        } catch (error) {
            console.debug('序列重置失敗（正常，如果沒有序列）:', error.message);
        }

        client.release();

        if (totalCleaned > 0) {
            console.log(`✅ 總共清理了 ${totalCleaned} 條測試資料`);
        } else {
            console.log('✅ 沒有發現需要清理的測試資料');
        }

    } catch (error) {
        console.error('❌ 清理測試資料失敗:', error);
    }
}