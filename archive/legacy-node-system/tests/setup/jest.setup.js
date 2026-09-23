/**
 * Jest測試環境設置
 * 配置測試環境和全局工具
 */

const { testDataCleaner } = require('./testData');
const { dbManager } = require('../../src/database/connection');

// 設置測試超時時間
jest.setTimeout(30000);

// 全局測試前設置
beforeAll(async () => {
    // 設置測試環境變數
    process.env.NODE_ENV = 'test';
    process.env.LOG_LEVEL = 'error';
    process.env.DB_NAME = process.env.DB_NAME || 'art_history_db_test';

    console.log('🧪 開始設置測試環境...');

    try {
        // 初始化資料庫連接
        await dbManager.connectPostgres();
        console.log('✅ 測試資料庫連接成功');

        // 嘗試連接Redis（如果可用）
        try {
            await dbManager.connectRedis();
            console.log('✅ Redis連接成功（測試環境）');
        } catch (error) {
            console.warn('⚠️ Redis連接失敗，某些功能測試將被跳過');
        }

        // 嘗試連接Elasticsearch（如果可用）
        try {
            await dbManager.connectElasticsearch();
            console.log('✅ Elasticsearch連接成功（測試環境）');
        } catch (error) {
            console.warn('⚠️ Elasticsearch連接失敗，搜索功能測試將被跳過');
        }

    } catch (error) {
        console.error('❌ 測試環境設置失敗:', error);
        process.exit(1);
    }
});

// 全局測試後清理
afterAll(async () => {
    console.log('🧹 開始清理測試環境...');

    try {
        // 清理測試資料
        await testDataCleaner.cleanup();
        console.log('✅ 測試資料清理完成');

        // 關閉資料庫連接
        await dbManager.closeAll();
        console.log('✅ 資料庫連接已關閉');

    } catch (error) {
        console.error('❌ 測試環境清理失敗:', error);
    }
});

// 每個測試套件後清理
afterEach(async () => {
    // 清理可能洩漏的測試資料
    try {
        const { Artist, Artwork, Institution, Tag, DocumentVector, CrawlTask } = require('../../src/database/models');

        const models = [
            new CrawlTask(),
            new DocumentVector(),
            new Artwork(),
            new Artist(),
            new Institution(),
            new Tag()
        ];

        for (const model of models) {
            await testDataCleaner.cleanupModel(model);
        }
    } catch (error) {
        // 靜默處理清理錯誤
    }
});

// 全局錯誤處理
process.on('unhandledRejection', (reason, promise) => {
    console.error('測試中發生未處理的Promise拒絕:', reason);
});

process.on('uncaughtException', (error) => {
    console.error('測試中發生未捕獲的異常:', error);
    process.exit(1);
});

// 全局測試工具
global.testUtils = {
    // 等待指定時間
    wait: (ms) => new Promise(resolve => setTimeout(resolve, ms)),

    // 生成隨機測試ID
    generateTestId: () => `test_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,

    // 檢查資料庫連接狀態
    checkDatabaseConnection: async () => {
        const status = await dbManager.checkConnections();
        return status.postgres;
    },

    // 檢查Redis連接狀態
    checkRedisConnection: async () => {
        const status = await dbManager.checkConnections();
        return status.redis;
    },

    // 檢查Elasticsearch連接狀態
    checkElasticsearchConnection: async () => {
        const status = await dbManager.checkConnections();
        return status.elasticsearch;
    },

    // 跳過需要外部服務的測試
    skipIfServiceUnavailable: (serviceName) => {
        const serviceChecks = {
            redis: () => global.testUtils.checkRedisConnection(),
            elasticsearch: () => global.testUtils.checkElasticsearchConnection()
        };

        return async () => {
            const isAvailable = await serviceChecks[serviceName]?.();
            if (!isAvailable) {
                return test.skip;
            }
            return test;
        };
    }
};

// 自定義匹配器
expect.extend({
    // 檢查UUID格式
    toBeValidUUID(received) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        const pass = uuidRegex.test(received);

        return {
            message: () => `expected ${received} ${pass ? 'not ' : ''}to be a valid UUID`,
            pass: pass
        };
    },

    // 檢查ISO日期格式
    toBeValidISODate(received) {
        const date = new Date(received);
        const pass = date instanceof Date && !isNaN(date) && received === date.toISOString();

        return {
            message: () => `expected ${received} ${pass ? 'not ' : ''}to be a valid ISO date string`,
            pass: pass
        };
    },

    // 檢查數組包含指定屬性的對象
    toContainObjectWithProperty(received, property, value) {
        const pass = Array.isArray(received) &&
                    received.some(item => item && item[property] === value);

        return {
            message: () => `expected array ${pass ? 'not ' : ''}to contain object with ${property}: ${value}`,
            pass: pass
        };
    },

    // 檢查對象是否包含測試元數據
    toBeTestData(received) {
        const pass = received &&
                    received.metadata &&
                    typeof received.metadata === 'object' &&
                    received.metadata.test === true;

        return {
            message: () => `expected object ${pass ? 'not ' : ''}to be test data (metadata.test should be true)`,
            pass: pass
        };
    }
});

console.log('✅ Jest測試環境設置完成');