/**
 * 超時中間件
 * 為Express路由提供統一的超時處理
 */

const { globalTimeoutHandler, TimeoutError } = require('../../utils/timeoutHandler');

/**
 * 創建超時中間件
 * @param {Object} options - 配置選項
 * @returns {Function} Express中間件函數
 */
function createTimeoutMiddleware(options = {}) {
    const {
        timeout = 30000,        // 默認30秒超時
        skipSuccessfulClose = true,
        skipAborted = true,
        onTimeout = null,
        responseMsg = 'Request timeout'
    } = options;

    return (req, res, next) => {
        // 如果響應已經發送，跳過處理
        if (res.headersSent) {
            return next();
        }

        // 創建請求的唯一標識
        const requestId = `${req.method}_${req.path}_${Date.now()}_${Math.random()}`;
        const startTime = Date.now();

        // 設置請求超時
        const timeoutPromise = new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                if (!res.headersSent) {
                    const error = new TimeoutError(
                        `Request ${requestId} timed out after ${timeout}ms`,
                        timeout,
                        `${req.method} ${req.path}`
                    );

                    // 執行自定義超時處理
                    if (onTimeout && typeof onTimeout === 'function') {
                        try {
                            onTimeout(req, res, error);
                        } catch (callbackError) {
                            console.error('超時回調函數執行失敗:', callbackError);
                        }
                    }

                    reject(error);
                } else {
                    resolve();
                }
            }, timeout);

            // 在req對象上存儲定時器，以便清理
            req.timeoutTimer = timer;
            req.timeoutId = requestId;
        });

        // 監聽響應完成事件
        const originalEnd = res.end;
        res.end = function(...args) {
            // 清理超時定時器
            if (req.timeoutTimer) {
                clearTimeout(req.timeoutTimer);
                req.timeoutTimer = null;
            }

            // 記錄請求完成
            const executionTime = Date.now() - startTime;
            globalTimeoutHandler.emit('request-completed', {
                method: req.method,
                path: req.path,
                executionTime,
                requestId,
                statusCode: res.statusCode
            });

            originalEnd.apply(this, args);
        };

        // 監聽連接關閉
        req.on('close', () => {
            if (req.timeoutTimer && (skipAborted || !req.aborted)) {
                clearTimeout(req.timeoutTimer);
                req.timeoutTimer = null;
            }
        });

        // 處理超時
        timeoutPromise.catch((error) => {
            if (!res.headersSent) {
                // 清理定時器
                if (req.timeoutTimer) {
                    clearTimeout(req.timeoutTimer);
                    req.timeoutTimer = null;
                }

                // 記錄超時事件
                globalTimeoutHandler.emit('request-timeout', {
                    method: req.method,
                    path: req.path,
                    timeout,
                    requestId,
                    userAgent: req.get('User-Agent'),
                    ip: req.ip
                });

                // 發送超時響應
                res.status(408).json({
                    success: false,
                    error: 'Request Timeout',
                    message: responseMsg,
                    timeout: timeout,
                    requestId: requestId,
                    timestamp: new Date().toISOString()
                });
            }
        });

        next();
    };
}

/**
 * 快速設置不同類型的超時中間件
 */
const timeoutMiddleware = {
    // 短超時 - 用於簡單查詢
    short: createTimeoutMiddleware({
        timeout: 15000,
        responseMsg: '請求超時，請稍後重試'
    }),

    // 標準超時 - 用於一般API
    standard: createTimeoutMiddleware({
        timeout: 30000,
        responseMsg: '請求處理時間過長，請稍後重試'
    }),

    // 長超時 - 用於複雜操作
    long: createTimeoutMiddleware({
        timeout: 60000,
        responseMsg: '操作正在處理中，請耐心等待或稍後重試'
    }),

    // 超長超時 - 用於數據匯出等重度任務
    extended: createTimeoutMiddleware({
        timeout: 300000,
        responseMsg: '大型任務正在處理，請稍後查看結果'
    }),

    // 自定義超時
    custom: (timeoutMs, message) => createTimeoutMiddleware({
        timeout: timeoutMs,
        responseMsg: message
    })
};

/**
 * 為控制器方法添加超時處理的裝飾器
 * @param {number} timeoutMs - 超時時間
 * @param {string} operationName - 操作名稱
 * @returns {Function} 裝飾器函數
 */
function withControllerTimeout(timeoutMs, operationName) {
    return function(target, propertyName, descriptor) {
        const originalMethod = descriptor.value;

        descriptor.value = async function(...args) {
            const [req, res] = args;

            try {
                const methodPromise = originalMethod.apply(this, args);
                return await globalTimeoutHandler.withTimeout(
                    methodPromise,
                    timeoutMs,
                    `Controller: ${operationName}`,
                    {
                        cleanup: () => {
                            // 控制器清理邏輯
                            if (req.timeoutTimer) {
                                clearTimeout(req.timeoutTimer);
                            }
                        }
                    }
                );
            } catch (error) {
                if (error instanceof TimeoutError) {
                    return res.status(408).json({
                        success: false,
                        error: 'Operation Timeout',
                        message: `${operationName} 操作超時`,
                        timeout: timeoutMs,
                        timestamp: new Date().toISOString()
                    });
                }
                throw error;
            }
        };

        return descriptor;
    };
}

/**
 * 路由級別的超時處理包裝器
 * @param {Function} handler - 路由處理函數
 * @param {number} timeoutMs - 超時時間
 * @param {string} operationName - 操作名稱
 * @returns {Function} 包裝後的處理函數
 */
function wrapRouteWithTimeout(handler, timeoutMs, operationName) {
    return async (req, res, next) => {
        try {
            const handlerPromise = handler(req, res, next);
            await globalTimeoutHandler.withTimeout(
                handlerPromise,
                timeoutMs,
                `Route: ${operationName}`
            );
        } catch (error) {
            if (error instanceof TimeoutError && !res.headersSent) {
                return res.status(408).json({
                    success: false,
                    error: 'Route Timeout',
                    message: `路由 ${operationName} 處理超時`,
                    timeout: timeoutMs,
                    timestamp: new Date().toISOString()
                });
            }
            next(error);
        }
    };
}

/**
 * 獲取超時統計信息的端點處理器
 */
const getTimeoutStats = async (req, res) => {
    try {
        const stats = globalTimeoutHandler.getStats();
        const activeTimeouts = globalTimeoutHandler.getActiveTimeouts();

        res.json({
            success: true,
            data: {
                statistics: stats,
                activeTimeouts: activeTimeouts,
                timestamp: new Date().toISOString()
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: 'Failed to get timeout statistics',
            message: error.message
        });
    }
};

module.exports = {
    createTimeoutMiddleware,
    timeoutMiddleware,
    withControllerTimeout,
    wrapRouteWithTimeout,
    getTimeoutStats
};