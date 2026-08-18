/**
 * API錯誤處理中間件
 * 為REST API提供統一的錯誤處理和重試機制
 */

const AdvancedErrorHandler = require('../../utils/advancedErrorHandler');
const { logger } = require('../../utils/logger');

// 全局錯誤處理器實例
const globalErrorHandler = new AdvancedErrorHandler('api-server', {
    maxRetries: 2,
    baseDelay: 500,
    circuitBreakerThreshold: 10,
    alertThreshold: 15,
    enableAutoRecovery: true
});

/**
 * 錯誤分類和HTTP狀態碼映射
 */
const ERROR_MAPPINGS = {
    // 驗證錯誤
    ValidationError: { status: 400, type: 'client_error', recoverable: false },
    'CastError': { status: 400, type: 'client_error', recoverable: false },

    // 認證和授權錯誤
    UnauthorizedError: { status: 401, type: 'auth_error', recoverable: false },
    ForbiddenError: { status: 403, type: 'auth_error', recoverable: false },

    // 資源錯誤
    NotFoundError: { status: 404, type: 'resource_error', recoverable: false },
    ConflictError: { status: 409, type: 'resource_error', recoverable: false },

    // 速率限制
    TooManyRequestsError: { status: 429, type: 'rate_limit', recoverable: true },

    // 伺服器錯誤
    InternalServerError: { status: 500, type: 'server_error', recoverable: true },
    BadGatewayError: { status: 502, type: 'server_error', recoverable: true },
    ServiceUnavailableError: { status: 503, type: 'server_error', recoverable: true },
    GatewayTimeoutError: { status: 504, type: 'server_error', recoverable: true },

    // 資料庫錯誤
    DatabaseConnectionError: { status: 500, type: 'database_error', recoverable: true },
    QueryTimeoutError: { status: 500, type: 'database_error', recoverable: true },

    // 外部API錯誤
    ExternalAPIError: { status: 502, type: 'external_api_error', recoverable: true },
    TimeoutError: { status: 504, type: 'timeout_error', recoverable: true }
};

/**
 * 創建錯誤處理中間件
 */
function createErrorHandlingMiddleware(options = {}) {
    const {
        enableRetry = true,
        enableCircuitBreaker = true,
        logErrors = true,
        exposeStackTrace = process.env.NODE_ENV === 'development'
    } = options;

    return async (error, req, res, next) => {
        try {
            // 生成請求ID用於追蹤
            const requestId = req.id || generateRequestId();
            const context = `${req.method} ${req.path}`;

            // 分析錯誤類型
            const errorInfo = analyzeError(error);

            // 記錄錯誤詳情
            if (logErrors) {
                logger.error('API請求錯誤', {
                    requestId,
                    method: req.method,
                    path: req.path,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip,
                    error: {
                        name: error.name,
                        message: error.message,
                        type: errorInfo.type,
                        status: errorInfo.status,
                        stack: exposeStackTrace ? error.stack : undefined
                    }
                });
            }

            // 更新全局錯誤處理器統計
            await globalErrorHandler.processError(error, context, requestId, 1);

            // 構建錯誤響應
            const errorResponse = buildErrorResponse(error, errorInfo, requestId, exposeStackTrace);

            // 設置響應狀態碼
            res.status(errorInfo.status);

            // 添加錯誤相關的響應頭
            addErrorHeaders(res, errorInfo, requestId);

            // 發送錯誤響應
            res.json(errorResponse);

        } catch (handlingError) {
            // 錯誤處理過程中出錯，發送基本錯誤響應
            logger.error('錯誤處理中間件失敗', {
                originalError: error.message,
                handlingError: handlingError.message
            });

            res.status(500).json({
                success: false,
                error: 'Internal Server Error',
                message: '伺服器內部錯誤',
                timestamp: new Date().toISOString()
            });
        }
    };
}

/**
 * 創建非同步操作包裝中間件
 */
function createAsyncWrapper(options = {}) {
    const {
        enableRetry = true,
        maxRetries = 2,
        retryDelay = 1000
    } = options;

    return (asyncFn) => {
        return async (req, res, next) => {
            const requestId = req.id || generateRequestId();
            const context = `${req.method} ${req.path}`;

            try {
                if (enableRetry) {
                    // 使用錯誤處理器包裝異步操作
                    const result = await globalErrorHandler.executeWithRetry(
                        () => asyncFn(req, res, next),
                        context,
                        { maxRetries, errorType: 'API_REQUEST' }
                    );
                    return result;
                } else {
                    // 直接執行，不重試
                    return await asyncFn(req, res, next);
                }
            } catch (error) {
                // 將錯誤傳遞給錯誤處理中間件
                next(error);
            }
        };
    };
}

/**
 * 創建資料庫操作包裝中間件
 */
function createDatabaseWrapper(options = {}) {
    const {
        maxRetries = 3,
        retryDelay = 2000,
        enableCircuitBreaker = true
    } = options;

    return (dbFn) => {
        return async (req, res, next) => {
            const requestId = req.id || generateRequestId();
            const context = `database_${req.method}_${req.path}`;

            try {
                const result = await globalErrorHandler.executeWithRetry(
                    () => dbFn(req, res, next),
                    context,
                    {
                        maxRetries,
                        retryDelay,
                        errorType: 'DATABASE_CONNECTION'
                    }
                );
                return result;
            } catch (error) {
                // 將資料庫錯誤轉換為適當的API錯誤
                const dbError = transformDatabaseError(error);
                next(dbError);
            }
        };
    };
}

/**
 * 創建外部API調用包裝中間件
 */
function createExternalAPIWrapper(options = {}) {
    const {
        maxRetries = 3,
        retryDelay = 1500,
        timeout = 10000
    } = options;

    return (apiFn) => {
        return async (req, res, next) => {
            const requestId = req.id || generateRequestId();
            const context = `external_api_${req.method}_${req.path}`;

            try {
                const result = await globalErrorHandler.executeWithRetry(
                    () => Promise.race([
                        apiFn(req, res, next),
                        createTimeoutPromise(timeout)
                    ]),
                    context,
                    {
                        maxRetries,
                        retryDelay,
                        errorType: 'API_REQUEST'
                    }
                );
                return result;
            } catch (error) {
                const apiError = transformExternalAPIError(error);
                next(apiError);
            }
        };
    };
}

/**
 * 錯誤恢復中間件
 */
function createRecoveryMiddleware(recoveryStrategies = {}) {
    return async (error, req, res, next) => {
        const errorType = error.name || error.constructor.name;
        const strategy = recoveryStrategies[errorType];

        if (strategy && strategy.enabled) {
            try {
                const recovered = await strategy.recover(error, req, res);
                if (recovered) {
                    logger.info('錯誤自動恢復成功', {
                        errorType,
                        method: req.method,
                        path: req.path
                    });
                    return; // 恢復成功，不繼續傳播錯誤
                }
            } catch (recoveryError) {
                logger.warn('錯誤恢復失敗', {
                    originalError: error.message,
                    recoveryError: recoveryError.message
                });
            }
        }

        // 恢復失敗或無恢復策略，繼續錯誤傳播
        next(error);
    };
}

/**
 * 健康檢查中間件
 */
function createHealthCheckMiddleware() {
    return (req, res) => {
        const healthReport = globalErrorHandler.generateHealthReport();

        const status = healthReport.status === 'healthy' ? 200 :
                      healthReport.status === 'degraded' ? 200 : 503;

        res.status(status).json({
            success: status === 200,
            health: healthReport,
            timestamp: new Date().toISOString()
        });
    };
}

/**
 * 錯誤統計中間件
 */
function createErrorStatsMiddleware() {
    return (req, res) => {
        const stats = {
            metrics: globalErrorHandler.getMetrics(),
            circuitBreaker: globalErrorHandler.getCircuitBreakerState(),
            patterns: globalErrorHandler.getErrorPatterns(),
            timestamp: new Date().toISOString()
        };

        res.json({
            success: true,
            stats,
            timestamp: new Date().toISOString()
        });
    };
}

// 工具函數

/**
 * 分析錯誤類型
 */
function analyzeError(error) {
    const errorName = error.name || error.constructor.name;
    const mapping = ERROR_MAPPINGS[errorName];

    if (mapping) {
        return mapping;
    }

    // 根據錯誤碼判斷
    if (error.code) {
        if (error.code.startsWith('ECONNREF') || error.code.startsWith('ENOTFOUND')) {
            return ERROR_MAPPINGS.ExternalAPIError;
        }
        if (error.code === 'ETIMEDOUT') {
            return ERROR_MAPPINGS.TimeoutError;
        }
    }

    // 根據HTTP狀態碼判斷
    if (error.status || error.statusCode) {
        const status = error.status || error.statusCode;
        if (status >= 400 && status < 500) {
            return { status, type: 'client_error', recoverable: false };
        }
        if (status >= 500) {
            return { status, type: 'server_error', recoverable: true };
        }
    }

    // 默認為伺服器錯誤
    return ERROR_MAPPINGS.InternalServerError;
}

/**
 * 構建錯誤響應
 */
function buildErrorResponse(error, errorInfo, requestId, exposeStackTrace) {
    const response = {
        success: false,
        error: {
            type: errorInfo.type,
            message: error.message || '未知錯誤',
            code: error.code || null,
            requestId
        },
        timestamp: new Date().toISOString()
    };

    // 開發環境下暴露堆疊追蹤
    if (exposeStackTrace && error.stack) {
        response.error.stack = error.stack;
    }

    // 添加錯誤特定的詳細資訊
    if (errorInfo.type === 'validation_error' && error.details) {
        response.error.validation = error.details;
    }

    // 添加重試建議
    if (errorInfo.recoverable) {
        response.error.retryable = true;
        response.error.retryAfter = calculateRetryAfter(errorInfo);
    }

    return response;
}

/**
 * 添加錯誤相關的HTTP響應頭
 */
function addErrorHeaders(res, errorInfo, requestId) {
    res.set('X-Request-ID', requestId);
    res.set('X-Error-Type', errorInfo.type);

    if (errorInfo.recoverable) {
        res.set('X-Retryable', 'true');
        const retryAfter = calculateRetryAfter(errorInfo);
        if (retryAfter > 0) {
            res.set('Retry-After', Math.ceil(retryAfter / 1000).toString());
        }
    }

    // 避免快取錯誤響應
    res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
}

/**
 * 計算重試延遲時間
 */
function calculateRetryAfter(errorInfo) {
    switch (errorInfo.type) {
        case 'rate_limit':
            return 60000; // 1分鐘
        case 'database_error':
            return 5000;  // 5秒
        case 'external_api_error':
            return 10000; // 10秒
        case 'timeout_error':
            return 15000; // 15秒
        default:
            return 3000;  // 3秒
    }
}

/**
 * 轉換資料庫錯誤
 */
function transformDatabaseError(error) {
    if (error.code === 'ECONNREFUSED') {
        const dbError = new Error('資料庫連接被拒絕');
        dbError.name = 'DatabaseConnectionError';
        dbError.originalError = error;
        return dbError;
    }

    if (error.code === 'ETIMEDOUT') {
        const timeoutError = new Error('資料庫查詢超時');
        timeoutError.name = 'QueryTimeoutError';
        timeoutError.originalError = error;
        return timeoutError;
    }

    if (error.message && error.message.includes('duplicate key')) {
        const conflictError = new Error('資料重複');
        conflictError.name = 'ConflictError';
        conflictError.originalError = error;
        return conflictError;
    }

    // 默認返回原始錯誤
    return error;
}

/**
 * 轉換外部API錯誤
 */
function transformExternalAPIError(error) {
    if (error.isTimeout) {
        const timeoutError = new Error('外部API調用超時');
        timeoutError.name = 'TimeoutError';
        timeoutError.originalError = error;
        return timeoutError;
    }

    if (error.response && error.response.status) {
        const apiError = new Error(`外部API錯誤: ${error.response.status}`);
        apiError.name = 'ExternalAPIError';
        apiError.status = error.response.status;
        apiError.originalError = error;
        return apiError;
    }

    return error;
}

/**
 * 創建超時Promise
 */
function createTimeoutPromise(timeout) {
    return new Promise((_, reject) => {
        setTimeout(() => {
            const error = new Error(`操作超時 (${timeout}ms)`);
            error.name = 'TimeoutError';
            error.isTimeout = true;
            reject(error);
        }, timeout);
    });
}

/**
 * 生成請求ID
 */
function generateRequestId() {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// 預定義恢復策略
const DEFAULT_RECOVERY_STRATEGIES = {
    DatabaseConnectionError: {
        enabled: true,
        recover: async (error, req, res) => {
            // 嘗試重新連接資料庫
            logger.info('嘗試重新連接資料庫');
            // 這裡應該實現具體的資料庫重連邏輯
            return false; // 暫時返回false，表示無法自動恢復
        }
    },

    TooManyRequestsError: {
        enabled: true,
        recover: async (error, req, res) => {
            // 對於速率限制，可以返回適當的響應而不是錯誤
            const retryAfter = error.retryAfter || 60;

            res.status(429).json({
                success: false,
                error: {
                    type: 'rate_limit',
                    message: '請求過於頻繁，請稍後再試',
                    retryAfter
                },
                timestamp: new Date().toISOString()
            });

            return true; // 表示已處理錯誤
        }
    }
};

module.exports = {
    createErrorHandlingMiddleware,
    createAsyncWrapper,
    createDatabaseWrapper,
    createExternalAPIWrapper,
    createRecoveryMiddleware,
    createHealthCheckMiddleware,
    createErrorStatsMiddleware,
    globalErrorHandler,
    DEFAULT_RECOVERY_STRATEGIES
};