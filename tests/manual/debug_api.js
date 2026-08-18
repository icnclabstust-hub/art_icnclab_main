const { Artist } = require('../../src/database/models');
const { successResponse, errorResponse } = require('../../src/utils/responseHelper');
require('dotenv').config();

async function debugArtistController() {
    console.log('🔍 調試Artist控制器...\n');

    try {
        // 模擬控制器中的操作
        console.log('1. 創建Artist模型實例');
        const artistModel = new Artist();

        console.log('2. 測試findAll方法');
        console.time('findAll執行時間');
        const artists = await artistModel.findAll(20, 0);
        console.timeEnd('findAll執行時間');
        console.log(`結果: ${artists.length} 筆記錄`);
        console.log('第一筆記錄:', artists[0] ? Object.keys(artists[0]) : 'null');

        // 模擬成功回應的創建
        console.log('3. 測試回應格式化');
        const mockRes = {
            status: function(code) { console.log(`Status: ${code}`); return this; },
            json: function(data) { console.log('Response:', JSON.stringify(data, null, 2)); return this; }
        };

        // 這應該不會卡住，除非有其他問題
        console.log('4. 測試successResponse功能');
        successResponse(mockRes, artists, {
            page: 1,
            limit: 20,
            total: artists.length
        });

    } catch (error) {
        console.error('❌ 調試過程中發生錯誤:', error.message);
        console.error('Stack:', error.stack);
    }

    console.log('✅ 調試完成');
    process.exit(0);
}

debugArtistController();