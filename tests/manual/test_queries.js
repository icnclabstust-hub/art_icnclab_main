const { Artist, Collection, Institution } = require('../../src/database/models');
require('dotenv').config();

async function testQueries() {
    console.log('🧪 開始測試各種查詢...\n');

    try {
        // 測試 1: 簡單的Artists查詢
        console.log('1. 測試Artists.findAll()');
        const artistModel = new Artist();
        console.time('Artists查詢時間');
        const artists = await artistModel.findAll(5);
        console.timeEnd('Artists查詢時間');
        console.log(`結果: ${artists.length} 筆藝術家記錄\n`);

        // 測試 2: 簡單的Collections查詢
        console.log('2. 測試Collections.findAll()');
        const collectionModel = new Collection();
        console.time('Collections查詢時間');
        const collections = await collectionModel.findAll(5);
        console.timeEnd('Collections查詢時間');
        console.log(`結果: ${collections.length} 筆館藏記錄\n`);

        // 測試 3: 簡單的Institutions查詢
        console.log('3. 測試Institutions.findAll()');
        const institutionModel = new Institution();
        console.time('Institutions查詢時間');
        const institutions = await institutionModel.findAll(5);
        console.timeEnd('Institutions查詢時間');
        console.log(`結果: ${institutions.length} 筆機構記錄\n`);

        // 測試 4: 測試Artist搜索
        console.log('4. 測試Artist搜索');
        console.time('Artist搜索時間');
        try {
            const searchResults = await artistModel.search('test', 5);
            console.timeEnd('Artist搜索時間');
            console.log(`結果: ${searchResults.length} 筆搜索結果\n`);
        } catch (error) {
            console.timeEnd('Artist搜索時間');
            console.log(`搜索錯誤: ${error.message}\n`);
        }

    } catch (error) {
        console.error('❌ 測試失敗:', error.message);
        console.error('Stack:', error.stack);
    }

    console.log('✅ 測試完成');
    process.exit(0);
}

testQueries();