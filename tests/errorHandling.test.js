/**
 * 錯誤處理機制測試
 * 測試新增的高級錯誤處理系統的各個功能
 */

const AdvancedErrorHandler = require('../src/utils/advancedErrorHandler');
const { ErrorClassifier, RecoveryStrategyManager } = require('../src/utils/errorClassification');
const {
    createErrorHandlingMiddleware,
    createAsyncWrapper,
    createDatabaseWrapper,
    createExternalAPIWrapper
} = require('../src/api/middleware/errorHandlingMiddleware');

describe('高級錯誤處理系統測試', () => {
    let errorHandler;
    let errorClassifier;
    let recoveryManager;

    beforeEach(() => {
        errorHandler = new AdvancedErrorHandler('test-system', {
            maxRetries: 2,
            baseDelay: 100,
            circuitBreakerThreshold: 5,
            alertThreshold: 10
        });
        errorClassifier = new ErrorClassifier();
        recoveryManager = new RecoveryStrategyManager();
    });

    describe('AdvancedErrorHandler 測試', () => {
        test('應該正確初始化錯誤處理器', () => {
            expect(errorHandler).toBeInstanceOf(AdvancedErrorHandler);
            expect(errorHandler.config.maxRetries).toBe(2);
            expect(errorHandler.config.baseDelay).toBe(100);
        });

        test('應該在操作成功時不重試', async () => {
            const successOperation = jest.fn().mockResolvedValue('success');

            const result = await errorHandler.executeWithRetry(successOperation, 'test-context');

            expect(result).toBe('success');
            expect(successOperation).toHaveBeenCalledTimes(1);
        });

        test('應該在可重試錯誤時執行重試', async () => {
            const failingOperation = jest.fn()
                .mockRejectedValueOnce(new Error('Temporary failure'))
                .mockRejectedValueOnce(new Error('Another failure'))
                .mockResolvedValue('success');

            const result = await errorHandler.executeWithRetry(failingOperation, 'test-context');

            expect(result).toBe('success');
            expect(failingOperation).toHaveBeenCalledTimes(3);
        });

        test('應該在達到最大重試次數後拋出錯誤', async () => {
            const alwaysFailingOperation = jest.fn()
                .mockRejectedValue(new Error('Permanent failure'));

            await expect(errorHandler.executeWithRetry(alwaysFailingOperation, 'test-context'))
                .rejects.toThrow('Permanent failure');

            expect(alwaysFailingOperation).toHaveBeenCalledTimes(3); // 初始調用 + 2次重試
        });

        test('應該正確計算指數退避延遲', () => {
            const delay1 = errorHandler.calculateDelay(1);
            const delay2 = errorHandler.calculateDelay(2);

            expect(delay2).toBeGreaterThan(delay1);
            expect(delay1).toBeGreaterThanOrEqual(100); // baseDelay
            expect(delay2).toBeGreaterThanOrEqual(200); // baseDelay * 2
        });

        test('應該追蹤錯誤統計', async () => {
            const error = new Error('Test error');

            await errorHandler.processError(error, 'test-context', 'req-123', 1);

            const metrics = errorHandler.getMetrics();
            expect(metrics.totalErrors).toBe(1);
            expect(metrics.errorsByType['Error']).toBe(1);
        });

        test('應該在達到閾值時觸發熔斷器', async () => {
            const error = new Error('Circuit breaker test');

            // 觸發足夠的錯誤來啟動熔斷器
            for (let i = 0; i < 6; i++) {
                await errorHandler.processError(error, 'test-context', `req-${i}`, 1);
            }

            const state = errorHandler.getCircuitBreakerState();
            expect(state.status).toBe('open');
        });
    });

    describe('ErrorClassifier 測試', () => {
        test('應該正確分類資料庫錯誤', () => {
            const dbError = new Error('Connection refused');
            dbError.code = 'ECONNREFUSED';

            const classification = errorClassifier.classify(dbError);

            expect(classification.category).toBe('database');
            expect(classification.subcategory).toBe('connection');
            expect(classification.severity).toBe('high');
            expect(classification.recoverable).toBe(true);
        });

        test('應該正確分類網路錯誤', () => {
            const networkError = new Error('Request timeout');
            networkError.code = 'ETIMEDOUT';

            const classification = errorClassifier.classify(networkError);

            expect(classification.category).toBe('network');
            expect(classification.subcategory).toBe('timeout');
            expect(classification.recoverable).toBe(true);
        });

        test('應該正確分類驗證錯誤', () => {
            const validationError = new Error('Invalid input format');
            validationError.name = 'ValidationError';

            const classification = errorClassifier.classify(validationError);

            expect(classification.category).toBe('validation');
            expect(classification.recoverable).toBe(false);
        });

        test('應該生成恰當的修復建議', () => {
            const dbError = new Error('Connection refused');
            dbError.code = 'ECONNREFUSED';

            const classification = errorClassifier.classify(dbError);
            const suggestions = errorClassifier.generateSuggestions(classification, dbError);

            expect(suggestions).toContain('檢查資料庫連接配置');
            expect(suggestions).toContain('確認資料庫服務正在運行');
        });
    });

    describe('RecoveryStrategyManager 測試', () => {
        test('應該註冊和執行恢復策略', async () => {
            const mockStrategy = {
                canHandle: jest.fn().mockReturnValue(true),
                recover: jest.fn().mockResolvedValue(true)
            };

            recoveryManager.registerStrategy('database_connection', mockStrategy);

            const error = new Error('Connection failed');
            error.code = 'ECONNREFUSED';

            const recovered = await recoveryManager.attemptRecovery(error, {});

            expect(recovered).toBe(true);
            expect(mockStrategy.canHandle).toHaveBeenCalledWith(error);
            expect(mockStrategy.recover).toHaveBeenCalledWith(error, {});
        });

        test('應該在沒有適用策略時返回 false', async () => {
            const error = new Error('Unknown error');

            const recovered = await recoveryManager.attemptRecovery(error, {});

            expect(recovered).toBe(false);
        });
    });

    describe('API 中間件測試', () => {
        test('createErrorHandlingMiddleware 應該處理錯誤並返回正確響應', async () => {
            const middleware = createErrorHandlingMiddleware({
                logErrors: false,
                exposeStackTrace: true
            });

            const error = new Error('Test API error');
            const req = { method: 'GET', path: '/test', ip: '127.0.0.1' };
            const res = {
                status: jest.fn().mockReturnThis(),
                json: jest.fn(),
                set: jest.fn()
            };
            const next = jest.fn();

            await middleware(error, req, res, next);

            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith(
                expect.objectContaining({
                    success: false,
                    error: expect.objectContaining({
                        message: 'Test API error',
                        type: 'server_error'
                    })
                })
            );
        });

        test('createAsyncWrapper 應該捕獲異步錯誤', async () => {
            const asyncWrapper = createAsyncWrapper({ enableRetry: false });
            const failingAsyncFn = jest.fn().mockRejectedValue(new Error('Async error'));
            const wrappedFn = asyncWrapper(failingAsyncFn);

            const req = { method: 'GET', path: '/test' };
            const res = {};
            const next = jest.fn();

            await wrappedFn(req, res, next);

            expect(next).toHaveBeenCalledWith(expect.any(Error));
        });

        test('createDatabaseWrapper 應該轉換資料庫錯誤', async () => {
            const dbWrapper = createDatabaseWrapper({
                maxRetries: 1,
                enableCircuitBreaker: false
            });

            const dbError = new Error('Connection refused');
            dbError.code = 'ECONNREFUSED';

            const failingDbFn = jest.fn().mockRejectedValue(dbError);
            const wrappedFn = dbWrapper(failingDbFn);

            const req = { method: 'GET', path: '/test' };
            const res = {};
            const next = jest.fn();

            await wrappedFn(req, res, next);

            expect(next).toHaveBeenCalledWith(
                expect.objectContaining({
                    name: 'DatabaseConnectionError'
                })
            );
        });

        test('createExternalAPIWrapper 應該處理超時', async () => {
            const apiWrapper = createExternalAPIWrapper({
                maxRetries: 1,
                timeout: 100
            });

            const slowApiFn = jest.fn().mockImplementation(() =>
                new Promise(resolve => setTimeout(resolve, 200))
            );

            const wrappedFn = apiWrapper(slowApiFn);

            const req = { method: 'GET', path: '/test' };
            const res = {};
            const next = jest.fn();

            await wrappedFn(req, res, next);

            expect(next).toHaveBeenCalledWith(
                expect.objectContaining({
                    name: 'TimeoutError'
                })
            );
        }, 10000);
    });

    describe('錯誤模式檢測測試', () => {
        test('應該檢測重複錯誤模式', async () => {
            const error = new Error('Repeated error');

            // 模擬重複錯誤
            for (let i = 0; i < 5; i++) {
                await errorHandler.processError(error, 'test-context', `req-${i}`, 1);
            }

            const patterns = errorHandler.getErrorPatterns();
            expect(patterns.length).toBeGreaterThan(0);
            expect(patterns[0]).toMatchObject({
                pattern: 'Repeated error',
                frequency: 5
            });
        });

        test('應該生成健康報告', () => {
            const healthReport = errorHandler.generateHealthReport();

            expect(healthReport).toHaveProperty('status');
            expect(healthReport).toHaveProperty('metrics');
            expect(healthReport).toHaveProperty('circuitBreaker');
            expect(healthReport).toHaveProperty('timestamp');
            expect(['healthy', 'degraded', 'unhealthy']).toContain(healthReport.status);
        });
    });

    describe('記憶體管理測試', () => {
        test('應該清理舊的錯誤記錄', async () => {
            // 添加大量錯誤記錄
            for (let i = 0; i < 1000; i++) {
                await errorHandler.processError(
                    new Error(`Error ${i}`),
                    'test-context',
                    `req-${i}`,
                    1
                );
            }

            const initialMemoryUsage = errorHandler.getMemoryUsage();

            // 執行清理
            errorHandler.cleanup();

            const afterCleanupMemoryUsage = errorHandler.getMemoryUsage();
            expect(afterCleanupMemoryUsage.errorHistory).toBeLessThan(initialMemoryUsage.errorHistory);
        });
    });
});