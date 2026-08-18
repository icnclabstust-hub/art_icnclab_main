#!/usr/bin/env node
/**
 * 統一錯誤處理模塊
 * 為所有Agent提供標準化的錯誤處理和恢復機制
 */

const fs = require('fs/promises');
const path = require('path');

class ErrorHandler {
    constructor(agentId, options = {}) {
        this.agentId = agentId;
        this.options = {
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 1000,
            logErrors: options.logErrors !== false,
            logPath: options.logPath || './logs/errors',
            enableRecovery: options.enableRecovery !== false
        };
        this.errors = [];
        this.retryCount = new Map();
    }

    /**
     * 包裝異步函數以提供錯誤處理
     */
    async wrapAsync(fn, context = '', options = {}) {
        const maxRetries = options.maxRetries || this.options.maxRetries;
        const retryDelay = options.retryDelay || this.options.retryDelay;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const result = await fn();

                // 重置重試計數
                if (this.retryCount.has(context)) {
                    this.retryCount.delete(context);
                }

                return result;
            } catch (error) {
                await this.logError(error, context, attempt);

                if (attempt === maxRetries) {
                    // 所有重試都失敗了
                    throw this.createEnhancedError(error, context, attempt);
                }

                // 等待後重試
                if (retryDelay > 0) {
                    await this.delay(retryDelay * Math.pow(2, attempt)); // 指數退避
                }

                console.warn(`⚠️ [${this.agentId}] ${context} 失敗，重試 ${attempt + 1}/${maxRetries}: ${error.message}`);
            }
        }
    }

    /**
     * 處理和記錄錯誤
     */
    async handleError(error, context = '', options = {}) {
        const errorInfo = {
            agentId: this.agentId,
            context,
            message: error.message,
            stack: error.stack,
            timestamp: new Date().toISOString(),
            severity: options.severity || 'error'
        };

        this.errors.push(errorInfo);

        if (this.options.logErrors) {
            await this.logError(error, context);
        }

        // 根據錯誤類型決定是否嘗試恢復
        if (this.options.enableRecovery) {
            const recovered = await this.attemptRecovery(error, context);
            if (recovered) {
                console.log(`✅ [${this.agentId}] ${context} 已自動恢復`);
                return true;
            }
        }

        return false;
    }

    /**
     * 嘗試自動恢復
     */
    async attemptRecovery(error, context) {
        try {
            // 常見錯誤的恢復策略
            if (error.code === 'ENOENT') {
                // 文件或目錄不存在
                return await this.handleMissingFileError(error, context);
            }

            if (error.code === 'EACCES') {
                // 權限錯誤
                return await this.handlePermissionError(error, context);
            }

            if (error.message.includes('ETIMEDOUT') || error.message.includes('timeout')) {
                // 超時錯誤
                return await this.handleTimeoutError(error, context);
            }

            if (error.message.includes('Assignment to constant variable')) {
                // 常量賦值錯誤（已修復，但作為示例）
                console.log(`💡 [${this.agentId}] 檢測到常量賦值錯誤，建議檢查變數宣告`);
                return false;
            }

        } catch (recoveryError) {
            console.warn(`⚠️ [${this.agentId}] 恢復嘗試失敗: ${recoveryError.message}`);
        }

        return false;
    }

    /**
     * 處理缺失文件錯誤
     */
    async handleMissingFileError(error, context) {
        const missingPath = error.path;
        if (!missingPath) return false;

        try {
            // 嘗試創建缺失的目錄
            if (context.includes('directory') || context.includes('目錄')) {
                await fs.mkdir(missingPath, { recursive: true });
                console.log(`✅ [${this.agentId}] 已創建缺失目錄: ${missingPath}`);
                return true;
            }

            // 嘗試創建空文件
            if (path.extname(missingPath) === '.json') {
                await fs.writeFile(missingPath, '[]', 'utf8');
                console.log(`✅ [${this.agentId}] 已創建空JSON文件: ${missingPath}`);
                return true;
            }

        } catch (createError) {
            console.warn(`⚠️ [${this.agentId}] 無法創建缺失文件: ${createError.message}`);
        }

        return false;
    }

    /**
     * 處理權限錯誤
     */
    async handlePermissionError(error, context) {
        console.warn(`⚠️ [${this.agentId}] 權限錯誤: ${error.path || 'unknown path'}`);
        console.warn(`💡 建議檢查文件權限或以適當權限運行程序`);
        return false;
    }

    /**
     * 處理超時錯誤
     */
    async handleTimeoutError(error, context) {
        console.warn(`⚠️ [${this.agentId}] 操作超時: ${context}`);
        console.warn(`💡 建議增加超時時間或檢查網絡連接`);
        return false;
    }

    /**
     * 記錄錯誤到文件
     */
    async logError(error, context = '', attempt = 0) {
        if (!this.options.logErrors) return;

        try {
            const logDir = this.options.logPath;
            await fs.mkdir(logDir, { recursive: true });

            const logEntry = {
                timestamp: new Date().toISOString(),
                agentId: this.agentId,
                context,
                attempt,
                error: {
                    name: error.name,
                    message: error.message,
                    stack: error.stack,
                    code: error.code
                }
            };

            const logFile = path.join(logDir, `${this.agentId}_errors.log`);
            await fs.appendFile(logFile, JSON.stringify(logEntry) + '\n', 'utf8');

        } catch (logError) {
            console.warn(`⚠️ [${this.agentId}] 錯誤日誌寫入失敗: ${logError.message}`);
        }
    }

    /**
     * 創建增強的錯誤對象
     */
    createEnhancedError(originalError, context, attempts) {
        const enhancedError = new Error(
            `[${this.agentId}] ${context}: ${originalError.message} (失敗於 ${attempts + 1} 次嘗試後)`
        );

        enhancedError.originalError = originalError;
        enhancedError.agentId = this.agentId;
        enhancedError.context = context;
        enhancedError.attempts = attempts + 1;
        enhancedError.stack = originalError.stack;

        return enhancedError;
    }

    /**
     * 延遲函數
     */
    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 獲取錯誤統計
     */
    getErrorStats() {
        const stats = {
            total: this.errors.length,
            byContext: {},
            bySeverity: {
                error: 0,
                warning: 0,
                critical: 0
            },
            recent: this.errors.slice(-10) // 最近10個錯誤
        };

        this.errors.forEach(error => {
            // 按上下文統計
            stats.byContext[error.context] = (stats.byContext[error.context] || 0) + 1;

            // 按嚴重程度統計
            stats.bySeverity[error.severity] = (stats.bySeverity[error.severity] || 0) + 1;
        });

        return stats;
    }

    /**
     * 清理舊錯誤記錄
     */
    cleanup(maxAge = 24 * 60 * 60 * 1000) { // 24小時
        const cutoff = Date.now() - maxAge;

        this.errors = this.errors.filter(error => {
            return new Date(error.timestamp).getTime() > cutoff;
        });
    }

    /**
     * 重置錯誤統計
     */
    reset() {
        this.errors = [];
        this.retryCount.clear();
    }
}

module.exports = ErrorHandler;