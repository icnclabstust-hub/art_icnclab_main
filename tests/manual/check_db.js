const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    user: process.env.DB_USER || 'postgres',
    host: process.env.DB_HOST || 'localhost',
    database: process.env.DB_NAME || 'art_history_db',
    password: process.env.DB_PASSWORD || 'password',
    port: process.env.DB_PORT || 5432,
});

async function checkDatabase() {
    try {
        console.log('🔍 正在檢查資料庫結構...');

        // 檢查所有表
        const tablesQuery = `
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        `;

        const result = await pool.query(tablesQuery);
        const tables = result.rows.map(row => row.table_name);

        console.log('\n📊 現有資料表：');
        console.log(tables.length > 0 ? tables : '(無資料表)');

        // 檢查特定表是否存在
        const requiredTables = ['artists', 'collections', 'institutions', 'artworks'];
        console.log('\n🎯 檢查必要資料表：');

        for (const table of requiredTables) {
            const exists = tables.includes(table);
            console.log(`${exists ? '✅' : '❌'} ${table}: ${exists ? '存在' : '不存在'}`);

            if (exists) {
                // 檢查表結構
                const columnsQuery = `
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position;
                `;
                const colResult = await pool.query(columnsQuery, [table]);
                console.log(`   欄位: ${colResult.rows.map(r => r.column_name).join(', ')}`);
            }
        }

        // 檢查表中的資料數量
        console.log('\n📈 資料表記錄數量：');
        for (const table of tables) {
            try {
                const countQuery = `SELECT COUNT(*) as count FROM ${table}`;
                const countResult = await pool.query(countQuery);
                console.log(`${table}: ${countResult.rows[0].count} 筆記錄`);
            } catch (error) {
                console.log(`${table}: 無法查詢 (${error.message})`);
            }
        }

    } catch (error) {
        console.error('❌ 資料庫檢查失敗:', error.message);
    } finally {
        await pool.end();
    }
}

checkDatabase();