#!/usr/bin/env node

/**
 * 快取系統效能測試腳本
 */

const axios = require('axios');

const BASE_URL = 'http://localhost:3000';

class CachePerformanceTester {
    constructor() {
        this.testResults = {
            artwork: {},
            search: {},
            statistics: {}
        };
    }

    // 測試API響應時間
    async testApiResponse(endpoint, description) {
        const startTime = Date.now();
        try {
            await axios.get(`${BASE_URL}${endpoint}`);
            const responseTime = Date.now() - startTime;
            console.log(`✅ ${description}: ${responseTime}ms`);
            return responseTime;
        } catch (error) {
            console.log(`❌ ${description}: Failed - ${error.message}`);
            return null;
        }
    }

    // 測試藝術作品快取效能
    async testArtworkCache() {
        console.log('\n📊 測試藝術作品快取效能...');

        // 假設存在 ID 為 1 的藝術作品
        const endpoint = '/api/v1/artworks/1';

        // 第一次請求（冷快取）
        const coldTime = await this.testApiResponse(endpoint, '藝術作品詳情 (冷快取)');

        // 第二次請求（熱快取）
        const hotTime = await this.testApiResponse(endpoint, '藝術作品詳情 (熱快取)');

        if (coldTime && hotTime) {
            const improvement = ((coldTime - hotTime) / coldTime * 100).toFixed(2);
            console.log(`⚡ 快取改善: ${improvement}%`);
            this.testResults.artwork = { coldTime, hotTime, improvement };
        }
    }

    // 測試搜索快取效能
    async testSearchCache() {
        console.log('\n🔍 測試搜索快取效能...');

        const searchQuery = 'art';
        const endpoint = `/api/v1/search/global?q=${searchQuery}`;

        // 第一次搜索（冷快取）
        const coldTime = await this.testApiResponse(endpoint, '全域搜索 (冷快取)');

        // 第二次搜索（熱快取）
        const hotTime = await this.testApiResponse(endpoint, '全域搜索 (熱快取)');

        if (coldTime && hotTime) {
            const improvement = ((coldTime - hotTime) / coldTime * 100).toFixed(2);
            console.log(`⚡ 搜索快取改善: ${improvement}%`);
            this.testResults.search = { coldTime, hotTime, improvement };
        }
    }

    // 測試統計資料快取
    async testStatisticsCache() {
        console.log('\n📈 測試統計資料快取效能...');

        const endpoint = '/api/v1/artworks/stats';

        // 第一次請求統計（冷快取）
        const coldTime = await this.testApiResponse(endpoint, '統計資料 (冷快取)');

        // 第二次請求統計（熱快取）
        const hotTime = await this.testApiResponse(endpoint, '統計資料 (熱快取)');

        if (coldTime && hotTime) {
            const improvement = ((coldTime - hotTime) / coldTime * 100).toFixed(2);
            console.log(`⚡ 統計快取改善: ${improvement}%`);
            this.testResults.statistics = { coldTime, hotTime, improvement };
        }
    }

    // 測試搜索建議快取
    async testSearchSuggestionsCache() {
        console.log('\n💡 測試搜索建議快取效能...');

        const endpoint = '/api/v1/search/suggestions?q=ar&type=all';

        // 第一次請求建議（冷快取）
        const coldTime = await this.testApiResponse(endpoint, '搜索建議 (冷快取)');

        // 第二次請求建議（熱快取）
        const hotTime = await this.testApiResponse(endpoint, '搜索建議 (熱快取)');

        if (coldTime && hotTime) {
            const improvement = ((coldTime - hotTime) / coldTime * 100).toFixed(2);
            console.log(`⚡ 建議快取改善: ${improvement}%`);
        }
    }

    // 獲取快取統計
    async getCacheStats() {
        console.log('\n📊 獲取快取統計資訊...');

        try {
            const response = await axios.get(`${BASE_URL}/api/v1/cache/stats`);
            const { stats, health } = response.data.data;

            console.log('快取統計:');
            console.log(`  - 命中率: ${stats.hitRate}`);
            console.log(`  - 總請求數: ${stats.totalRequests}`);
            console.log(`  - 命中次數: ${stats.hits}`);
            console.log(`  - 未命中次數: ${stats.misses}`);
            console.log(`  - 設置次數: ${stats.sets}`);
            console.log(`  - 刪除次數: ${stats.deletes}`);
            console.log(`  - 錯誤次數: ${stats.errors}`);
            console.log(`  - 記憶體使用: ${stats.memoryUsage} 項目`);
            console.log(`  - Redis 可用: ${stats.isRedisAvailable ? '是' : '否'}`);

            console.log('\n健康檢查:');
            console.log(`  - 系統狀態: ${health.healthy ? '健康' : '不健康'}`);
            console.log(`  - 後端: ${health.backend}`);

            if (health.error) {
                console.log(`  - 錯誤: ${health.error}`);
            }
        } catch (error) {
            console.log(`❌ 無法獲取快取統計: ${error.message}`);
        }
    }

    // 清除快取並重新測試
    async testCacheClear() {
        console.log('\n🧹 測試快取清除功能...');

        try {
            // 清除搜索快取
            await axios.post(`${BASE_URL}/api/v1/cache/clear/search`);
            console.log('✅ 搜索快取已清除');

            // 清除藝術作品快取
            await axios.post(`${BASE_URL}/api/v1/cache/clear/artwork`);
            console.log('✅ 藝術作品快取已清除');

        } catch (error) {
            console.log(`❌ 清除快取失敗: ${error.message}`);
        }
    }

    // 執行壓力測試
    async stressTest() {
        console.log('\n⚡ 執行快取壓力測試...');

        const endpoint = '/api/v1/artworks/stats';
        const requests = 10;
        const times = [];

        console.log(`發送 ${requests} 個並發請求...`);

        const promises = Array(requests).fill().map(async (_, index) => {
            const startTime = Date.now();
            try {
                await axios.get(`${BASE_URL}${endpoint}`);
                const responseTime = Date.now() - startTime;
                times.push(responseTime);
                return responseTime;
            } catch (error) {
                console.log(`請求 ${index + 1} 失敗: ${error.message}`);
                return null;
            }
        });

        await Promise.all(promises);

        if (times.length > 0) {
            const avgTime = times.reduce((sum, time) => sum + time, 0) / times.length;
            const minTime = Math.min(...times);
            const maxTime = Math.max(...times);

            console.log(`結果統計:`);
            console.log(`  - 成功請求: ${times.length}/${requests}`);
            console.log(`  - 平均響應時間: ${avgTime.toFixed(2)}ms`);
            console.log(`  - 最快響應: ${minTime}ms`);
            console.log(`  - 最慢響應: ${maxTime}ms`);
        }
    }

    // 執行完整測試套件
    async runFullTest() {
        console.log('🚀 啟動快取系統效能測試\n');

        // 先清除快取確保乾淨的測試環境
        await this.testCacheClear();

        // 等待一小段時間讓清除生效
        await new Promise(resolve => setTimeout(resolve, 1000));

        // 執行各項測試
        await this.testArtworkCache();
        await this.testSearchCache();
        await this.testStatisticsCache();
        await this.testSearchSuggestionsCache();

        // 執行壓力測試
        await this.stressTest();

        // 獲取最終統計
        await this.getCacheStats();

        console.log('\n🎉 測試完成！');
        this.printSummary();
    }

    // 打印測試總結
    printSummary() {
        console.log('\n📋 測試總結:');

        if (this.testResults.artwork.improvement) {
            console.log(`  - 藝術作品快取改善: ${this.testResults.artwork.improvement}%`);
        }

        if (this.testResults.search.improvement) {
            console.log(`  - 搜索快取改善: ${this.testResults.search.improvement}%`);
        }

        if (this.testResults.statistics.improvement) {
            console.log(`  - 統計快取改善: ${this.testResults.statistics.improvement}%`);
        }

        console.log('\n建議:');
        console.log('  - 監控快取命中率，目標 > 80%');
        console.log('  - 定期清理過期快取');
        console.log('  - 根據使用模式調整快取配置');
    }
}

// 主執行函數
async function main() {
    const tester = new CachePerformanceTester();

    // 檢查伺服器是否運行
    try {
        await axios.get(`${BASE_URL}/health`);
        console.log('✅ 伺服器正在運行');
    } catch (error) {
        console.log('❌ 無法連接到伺服器，請確保應用正在運行');
        console.log('   運行命令: npm start');
        process.exit(1);
    }

    await tester.runFullTest();
}

// 如果直接執行此腳本
if (require.main === module) {
    main().catch(error => {
        console.error('測試執行錯誤:', error.message);
        process.exit(1);
    });
}

module.exports = CachePerformanceTester;