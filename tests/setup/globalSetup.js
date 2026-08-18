/**
 * Jest全局設置
 * 測試前的一次性設置
 */

const { dbManager } = require('../../src/database/connection');

module.exports = async () => {
    console.log('🚀 開始全局測試設置...');

    try {
        // 設置測試環境變數
        process.env.NODE_ENV = 'test';
        process.env.LOG_LEVEL = 'error';

        // 設置測試資料庫名稱
        if (!process.env.DB_NAME || !process.env.DB_NAME.includes('test')) {
            process.env.DB_NAME = 'art_history_db_test';
        }

        console.log(`📊 使用測試資料庫: ${process.env.DB_NAME}`);

        // 初始化資料庫連接
        const connected = await dbManager.connectPostgres();
        if (!connected) {
            throw new Error('無法連接到測試資料庫');
        }

        // 初始化資料庫結構（如果需要）
        try {
            await dbManager.initializeDatabaseSchema();
            console.log('✅ 測試資料庫結構初始化完成');
        } catch (error) {
            console.warn('⚠️ 資料庫結構初始化失敗（可能已存在）:', error.message);
        }

        // 清理任何現有的測試資料
        await cleanupTestData();

        console.log('✅ 全局測試設置完成');

    } catch (error) {
        console.error('❌ 全局測試設置失敗:', error);
        process.exit(1);
    }
};

// 清理測試資料函數
async function cleanupTestData() {
    try {
        const pool = dbManager.getPostgresPool();
        const client = await pool.connect();

        // 清理所有包含測試標記的資料
        const cleanupQueries = [
            "DELETE FROM artwork_tags WHERE artwork_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true')",
            "DELETE FROM collections WHERE artwork_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true')",
            "DELETE FROM collections WHERE institution_id IN (SELECT id FROM institutions WHERE metadata->>'test' = 'true')",
            "DELETE FROM artist_movements WHERE artist_id IN (SELECT id FROM artists WHERE metadata->>'test' = 'true')",
            "DELETE FROM document_vectors WHERE metadata->>'test' = 'true'",
            "DELETE FROM processing_logs WHERE entity_id IN (SELECT id FROM artworks WHERE metadata->>'test' = 'true')",
            "DELETE FROM processing_logs WHERE entity_id IN (SELECT id FROM artists WHERE metadata->>'test' = 'true')",
            "DELETE FROM crawl_tasks WHERE metadata->>'test' = 'true'",
            "DELETE FROM search_queries WHERE metadata->>'test' = 'true'",
            "DELETE FROM artworks WHERE metadata->>'test' = 'true'",
            "DELETE FROM artists WHERE metadata->>'test' = 'true'",
            "DELETE FROM institutions WHERE metadata->>'test' = 'true'",
            "DELETE FROM tags WHERE metadata->>'test' = 'true'"
        ];

        for (const query of cleanupQueries) {
            try {
                const result = await client.query(query);
                if (result.rowCount > 0) {
                    console.log(`🧹 清理了 ${result.rowCount} 條測試資料: ${query.split(' ')[2]}`);
                }
            } catch (error) {
                // 忽略清理錯誤（表可能不存在）
                console.debug(`清理查詢失敗（忽略）: ${error.message}`);
            }
        }

        client.release();
        console.log('✅ 測試資料清理完成');

    } catch (error) {
        console.warn('⚠️ 測試資料清理失敗:', error.message);
    }
}