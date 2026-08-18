#!/usr/bin/env node
/**
 * 測試資料庫連接
 */

require('dotenv').config();
const { dbManager } = require('../../src/database/connection');
const { Artist, Artwork } = require('../../src/database/models');

async function testDatabaseConnection() {
    console.log('🔍 測試資料庫連接...');

    try {
        // 測試PostgreSQL連接
        const pgConnected = await dbManager.connectPostgres();
        console.log(`PostgreSQL 連接: ${pgConnected ? '✅ 成功' : '❌ 失敗'}`);

        if (!pgConnected) {
            console.error('無法連接到PostgreSQL，請檢查配置');
            process.exit(1);
        }

        // 測試Redis連接（可選）
        try {
            const redisConnected = await dbManager.connectRedis();
            console.log(`Redis 連接: ${redisConnected ? '✅ 成功' : '❌ 失敗'}`);
        } catch (error) {
            console.log('Redis 連接: ⚠️ 跳過（可選）');
        }

        // 測試基本查詢
        console.log('\n📊 測試基本資料庫操作...');

        const artistModel = new Artist();
        const artworkModel = new Artwork();

        // 查詢藝術家
        const artists = await artistModel.findAll(5);
        console.log(`✅ 查詢藝術家: 找到 ${artists.length} 個`);

        if (artists.length > 0) {
            console.log(`   示例: ${artists[0].name} (${artists[0].nationality})`);
        }

        // 查詢藝術作品
        const artworks = await artworkModel.findAll(5);
        console.log(`✅ 查詢藝術作品: 找到 ${artworks.length} 個`);

        if (artworks.length > 0) {
            console.log(`   示例: ${artworks[0].title} (${artworks[0].creation_year})`);
        }

        // 測試關聯查詢
        if (artworks.length > 0) {
            const artworkDetails = await artworkModel.getArtworkDetails(artworks[0].id);
            if (artworkDetails) {
                console.log(`✅ 關聯查詢: ${artworkDetails.title} by ${artworkDetails.artist_name || '未知藝術家'}`);
            }
        }

        console.log('\n🎉 資料庫連接測試完成！');
        console.log('📝 資料庫已準備就緒，可以啟動API服務');

    } catch (error) {
        console.error('❌ 資料庫連接測試失敗:', error.message);
        process.exit(1);
    } finally {
        await dbManager.closeAll();
    }
}

// 如果直接執行這個文件
if (require.main === module) {
    testDatabaseConnection();
}

module.exports = testDatabaseConnection;