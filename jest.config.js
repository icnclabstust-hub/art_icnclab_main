/**
 * Jest測試配置
 * 配置測試環境和參數
 */

module.exports = {
    // 測試環境
    testEnvironment: 'node',

    // 測試文件匹配模式
    testMatch: [
        '**/tests/**/*.test.js',
        '**/tests/**/*.spec.js',
        '**/__tests__/**/*.js'
    ],

    // 忽略的文件模式
    testPathIgnorePatterns: [
        '/node_modules/',
        '/dist/',
        '/build/'
    ],

    // 覆蓋率收集配置
    collectCoverage: process.env.COLLECT_COVERAGE === 'true',
    collectCoverageFrom: [
        'src/**/*.js',
        '!src/**/*.test.js',
        '!src/**/*.spec.js',
        '!src/app.js', // 排除入口文件
        '!**/node_modules/**',
        '!**/tests/**',
        '!**/__tests__/**'
    ],

    // 覆蓋率輸出目錄
    coverageDirectory: 'coverage',

    // 覆蓋率報告格式
    coverageReporters: [
        'text',
        'lcov',
        'html',
        'json-summary'
    ],

    // 覆蓋率閾值
    coverageThreshold: {
        global: {
            branches: 70,
            functions: 80,
            lines: 80,
            statements: 80
        },
        'src/database/models.js': {
            branches: 80,
            functions: 90,
            lines: 90,
            statements: 90
        },
        'src/api/controllers/*.js': {
            branches: 75,
            functions: 85,
            lines: 85,
            statements: 85
        }
    },

    // 設置文件（暫時禁用）
    // setupFilesAfterEnv: [
    //     '<rootDir>/tests/setup/jest.setup.js'
    // ],

    // 全局設置（暫時禁用以進行單元測試）
    // globalSetup: '<rootDir>/tests/setup/globalSetup.js',
    // globalTeardown: '<rootDir>/tests/setup/globalTeardown.js',

    // 測試超時時間（毫秒）
    testTimeout: 30000,

    // 模組名稱映射
    moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/src/$1',
        '^@tests/(.*)$': '<rootDir>/tests/$1'
    },

    // 清除模擬
    clearMocks: true,
    restoreMocks: true,

    // 詳細輸出
    verbose: process.env.VERBOSE_TESTS === 'true',

    // 檢測打開的句柄
    detectOpenHandles: true,
    forceExit: false,

    // 最大並發數
    maxWorkers: process.env.CI ? 2 : '50%',

    // 報告器配置
    reporters: [
        'default'
    ],

    // 轉換配置
    transform: {
        '^.+\\.js$': 'babel-jest'
    },

    // 模擬配置
    moduleFileExtensions: ['js', 'json'],

    // 環境變數
    globals: {
        NODE_ENV: 'test',
        DB_NAME: 'art_history_db_test',
        LOG_LEVEL: 'error'
    }
};