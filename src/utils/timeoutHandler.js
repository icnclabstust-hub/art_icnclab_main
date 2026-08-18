/**
 * 全域統一超時處理系統
 * 提供統一的超時控制和錯誤處理機制
 */

const { EventEmitter } = require('events');

class TimeoutHandler extends EventEmitter {
    constructor() {
        super();
        this.defaultTimeouts = {
            database: 30000,     // 30秒 - 資料庫查詢
            http: 60000,         // 60秒 - HTTP請求
            upload: 300000,      // 5分鐘 - 文件上傳
            external: 120000,    // 2分鐘 - 外部API調用
            heavy: 600000        // 10分鐘 - 重度計算任務
        };
        this.activeTimeouts = new Map();
        this.stats = {
            totalRequests: 0,
            timeouts: 0,
            completed: 0
        };
    }

    /**
     * 創建帶超時的Promise包裝器
     * @param {Promise} promise - 需要包裝的Promise
     * @param {number} timeoutMs - 超時時間（毫秒）
     * @param {string} operation - 操作名稱，用於錯誤信息
     * @param {Object} options - 額外選項
     * @returns {Promise} 包裝後的Promise
     */
    withTimeout(promise, timeoutMs, operation = 'Operation', options = {}) {
        const timeoutId = `${operation}_${Date.now()}_${Math.random()}`;
        this.stats.totalRequests++;

        return new Promise((resolve, reject) => {
            // 創建超時定時器
            const timeoutTimer = setTimeout(() => {
                this.stats.timeouts++;
                this.activeTimeouts.delete(timeoutId);

                const error = new TimeoutError(
                    `${operation} timed out after ${timeoutMs}ms`,
                    timeoutMs,
                    operation
                );

                // 發出超時事件
                this.emit('timeout', {
                    operation,
                    timeoutMs,
                    timeoutId,
                    timestamp: new Date()
                });

                // 如果提供了清理函數，執行清理
                if (options.cleanup && typeof options.cleanup === 'function') {
                    try {
                        options.cleanup();
                    } catch (cleanupError) {
                        console.error('清理函數執行失敗:', cleanupError);
                    }
                }

                reject(error);
            }, timeoutMs);

            // 記錄活躍的超時
            this.activeTimeouts.set(timeoutId, {
                timer: timeoutTimer,
                operation,
                startTime: Date.now(),
                timeoutMs
            });

            // 處理原Promise
            promise
                .then((result) => {
                    clearTimeout(timeoutTimer);
                    this.activeTimeouts.delete(timeoutId);
                    this.stats.completed++;

                    this.emit('completed', {
                        operation,
                        timeoutId,
                        executionTime: Date.now() - this.activeTimeouts.get(timeoutId)?.startTime,
                        timestamp: new Date()
                    });

                    resolve(result);
                })
                .catch((error) => {
                    clearTimeout(timeoutTimer);
                    this.activeTimeouts.delete(timeoutId);

                    this.emit('error', {
                        operation,
                        error,
                        timeoutId,
                        timestamp: new Date()
                    });

                    reject(error);
                });
        });
    }

    /**
     * 資料庫查詢超時包裝器
     * @param {Promise} queryPromise - 資料庫查詢Promise
     * @param {string} queryName - 查詢名稱
     * @param {number} customTimeout - 自定義超時時間
     * @returns {Promise} 包裝後的Promise
     */
    withDatabaseTimeout(queryPromise, queryName = 'Database Query', customTimeout = null) {
        const timeout = customTimeout || this.defaultTimeouts.database;
        return this.withTimeout(queryPromise, timeout, `DB: ${queryName}`, {
            cleanup: () => {
                // 資料庫連接清理邏輯
                console.log(`清理資料庫操作: ${queryName}`);
            }
        });
    }

    /**
     * HTTP請求超時包裝器
     * @param {Promise} httpPromise - HTTP請求Promise
     * @param {string} url - 請求URL
     * @param {Object} controller - AbortController實例（可選）
     * @param {number} customTimeout - 自定義超時時間
     * @returns {Promise} 包裝後的Promise
     */
    withHttpTimeout(httpPromise, url, controller = null, customTimeout = null) {
        const timeout = customTimeout || this.defaultTimeouts.http;
        return this.withTimeout(httpPromise, timeout, `HTTP: ${url}`, {
            cleanup: () => {
                if (controller && controller.abort) {
                    controller.abort();
                }
            }
        });
    }

    /**
     * 外部API調用超時包裝器
     * @param {Promise} apiPromise - API調用Promise
     * @param {string} apiName - API名稱
     * @param {Object} options - 選項
     * @returns {Promise} 包裝後的Promise
     */
    withExternalApiTimeout(apiPromise, apiName, options = {}) {
        const timeout = options.timeout || this.defaultTimeouts.external;
        return this.withTimeout(apiPromise, timeout, `API: ${apiName}`, {
            cleanup: options.cleanup
        });
    }

    /**
     * 文件處理超時包裝器
     * @param {Promise} filePromise - 文件處理Promise
     * @param {string} operation - 操作類型（upload/download/process）
     * @param {string} filename - 文件名
     * @param {number} customTimeout - 自定義超時時間
     * @returns {Promise} 包裝後的Promise
     */
    withFileTimeout(filePromise, operation, filename, customTimeout = null) {
        const timeout = customTimeout || this.defaultTimeouts.upload;
        return this.withTimeout(filePromise, timeout, `File ${operation}: ${filename}`);
    }

    /**
     * 批量操作超時包裝器
     * @param {Promise[]} promises - Promise數組
     * @param {number} timeoutMs - 整體超時時間
     * @param {string} operation - 操作名稱
     * @returns {Promise} 包裝後的Promise
     */
    withBatchTimeout(promises, timeoutMs, operation = 'Batch Operation') {
        const batchPromise = Promise.allSettled(promises);
        return this.withTimeout(batchPromise, timeoutMs, operation);
    }

    /**
     * 獲取統計信息
     * @returns {Object} 統計數據
     */
    getStats() {
        return {
            ...this.stats,
            activeOperations: this.activeTimeouts.size,
            timeoutRate: this.stats.totalRequests > 0 ?
                (this.stats.timeouts / this.stats.totalRequests * 100).toFixed(2) + '%' : '0%'
        };
    }

    /**
     * 獲取活躍的超時操作
     * @returns {Array} 活躍操作列表
     */
    getActiveTimeouts() {
        return Array.from(this.activeTimeouts.entries()).map(([id, info]) => ({
            id,
            operation: info.operation,
            runningTime: Date.now() - info.startTime,
            remainingTime: Math.max(0, info.timeoutMs - (Date.now() - info.startTime)),
            timeoutMs: info.timeoutMs
        }));
    }

    /**
     * 手動取消指定的超時操作
     * @param {string} timeoutId - 超時操作ID
     * @returns {boolean} 取消是否成功
     */
    cancelTimeout(timeoutId) {
        const timeoutInfo = this.activeTimeouts.get(timeoutId);
        if (timeoutInfo) {
            clearTimeout(timeoutInfo.timer);
            this.activeTimeouts.delete(timeoutId);

            this.emit('cancelled', {
                operation: timeoutInfo.operation,
                timeoutId,
                timestamp: new Date()
            });

            return true;
        }
        return false;
    }

    /**
     * 清理所有活躍的超時操作
     */
    cleanup() {
        for (const [timeoutId, timeoutInfo] of this.activeTimeouts) {
            clearTimeout(timeoutInfo.timer);
        }
        this.activeTimeouts.clear();

        this.emit('cleanup', {
            timestamp: new Date(),
            clearedCount: this.activeTimeouts.size
        });
    }

    /**
     * 重置統計信息
     */
    resetStats() {
        this.stats = {
            totalRequests: 0,
            timeouts: 0,
            completed: 0
        };
    }
}

/**
 * 自定義超時錯誤類
 */
class TimeoutError extends Error {
    constructor(message, timeoutMs, operation) {
        super(message);
        this.name = 'TimeoutError';
        this.timeoutMs = timeoutMs;
        this.operation = operation;
        this.timestamp = new Date();

        // 保持錯誤堆棧
        if (Error.captureStackTrace) {
            Error.captureStackTrace(this, TimeoutError);
        }
    }
}

// 創建全域實例
const globalTimeoutHandler = new TimeoutHandler();

// 監聽超時事件並記錄
globalTimeoutHandler.on('timeout', (data) => {
    console.warn(`⏰ 操作超時: ${data.operation} (${data.timeoutMs}ms)`);
});

globalTimeoutHandler.on('error', (data) => {
    console.error(`❌ 操作失敗: ${data.operation}`, data.error.message);
});

// 定期輸出統計信息（僅在開發模式）
if (process.env.NODE_ENV === 'development') {
    setInterval(() => {
        const stats = globalTimeoutHandler.getStats();
        if (stats.totalRequests > 0) {
            console.log('📊 超時處理統計:', stats);
        }
    }, 60000); // 每分鐘輸出一次
}

// 優雅關機時清理
process.on('SIGTERM', () => {
    globalTimeoutHandler.cleanup();
});

process.on('SIGINT', () => {
    globalTimeoutHandler.cleanup();
});

module.exports = {
    TimeoutHandler,
    TimeoutError,
    globalTimeoutHandler
};