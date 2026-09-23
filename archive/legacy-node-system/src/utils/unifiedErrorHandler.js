#!/usr/bin/env node
/**
 * 統一錯誤處理系統 - 企業級錯誤管理
 * 提供斷路器模式、錯誤聚合、智能重試等高級功能
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');

class UnifiedErrorHandler extends EventEmitter {
    constructor(agentId, options = {}) {
        super();
        this.agentId = agentId;
        this.options = {
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 1000,
            exponentialBackoff: options.exponentialBackoff !== false,
            maxRetryDelay: options.maxRetryDelay || 30000,
            jitterRange: options.jitterRange || 0.1,
            logErrors: options.logErrors !== false,
            logPath: options.logPath || './logs/errors',
            enableRecovery: options.enableRecovery !== false,
            circuitBreakerThreshold: options.circuitBreakerThreshold || 5,
            circuitBreakerTimeout: options.circuitBreakerTimeout || 30000,
            metricsEnabled: options.metricsEnabled !== false,
            alertThreshold: options.alertThreshold || 10,
            enableClustering: options.enableClustering !== false
        };

        this.errors = [];
        this.retryCount = new Map();
        this.circuitBreaker = {
            failures: 0,
            lastFailure: null,
            state: 'CLOSED' // CLOSED, OPEN, HALF_OPEN
        };

        this.metrics = this.initializeMetrics();
        this.errorPatterns = new Map();
        this.recoveryStrategies = new Map();
        this.alertSent = false;

        // 初始化恢復策略
        this.initializeRecoveryStrategies();

        // 定期清理舊數據
        this.setupCleanupTimer();
    }

    /**
     * 初始化錯誤指標
     */
    initializeMetrics() {
        return {
            totalErrors: 0,
            totalRecoveries: 0,
            avgResponseTime: 0,
            errorRate: 0,
            circuitBreakerTrips: 0,
            patternMatches: 0,
            lastUpdated: Date.now()
        };
    }

    /**
     * 初始化恢復策略
     */
    initializeRecoveryStrategies() {
        // 文件系統錯誤
        this.recoveryStrategies.set('ENOENT', {
            strategy: 'createMissing',
            priority: 'high',
            autoRecover: true
        });

        this.recoveryStrategies.set('EACCES', {
            strategy: 'permissionFix',
            priority: 'critical',
            autoRecover: false
        });

        // 網路錯誤
        this.recoveryStrategies.set('ETIMEDOUT', {
            strategy: 'exponentialBackoff',
            priority: 'medium',
            autoRecover: true
        });

        this.recoveryStrategies.set('ECONNREFUSED', {
            strategy: 'serviceDiscovery',
            priority: 'high',
            autoRecover: true
        });

        // API錯誤
        this.recoveryStrategies.set('RATE_LIMITED', {
            strategy: 'backoffWithJitter',
            priority: 'medium',
            autoRecover: true
        });

        // 解析錯誤
        this.recoveryStrategies.set('SyntaxError', {
            strategy: 'fallbackData',
            priority: 'low',
            autoRecover: true
        });
    }

    /**
     * 智能錯誤處理包裝器
     */
    async wrapAsync(fn, context = '', options = {}) {
        const operationId = `${context}_${Date.now()}`;
        const startTime = Date.now();

        // 檢查斷路器狀態
        if (this.circuitBreaker.state === 'OPEN') {
            const timeSinceLastFailure = Date.now() - this.circuitBreaker.lastFailure;
            if (timeSinceLastFailure < this.options.circuitBreakerTimeout) {
                throw new Error(`Circuit breaker is OPEN for ${this.agentId}. Try again later.`);
            } else {
                this.circuitBreaker.state = 'HALF_OPEN';
                console.log(`🔄 [${this.agentId}] Circuit breaker transitioned to HALF_OPEN`);
            }
        }

        const maxRetries = options.maxRetries || this.options.maxRetries;
        let delay = options.retryDelay || this.options.retryDelay;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const result = await fn();

                // 操作成功，重置斷路器
                if (this.circuitBreaker.state === 'HALF_OPEN') {
                    this.circuitBreaker.state = 'CLOSED';
                    this.circuitBreaker.failures = 0;
                    console.log(`✅ [${this.agentId}] Circuit breaker CLOSED`);
                }

                // 更新指標
                this.updateMetrics('success', Date.now() - startTime);
                this.retryCount.delete(operationId);

                this.emit('operationSuccess', {
                    operationId,
                    context,
                    duration: Date.now() - startTime,
                    attempt
                });

                return result;

            } catch (error) {
                await this.processError(error, context, attempt, operationId);

                if (attempt === maxRetries) {
                    // 最終失敗，觸發斷路器
                    this.handleFinalFailure(error, context, attempt);
                    throw this.createEnhancedError(error, context, attempt);
                }

                // 智能重試延遲
                const retryDelay = this.calculateRetryDelay(delay, attempt, error);
                if (retryDelay > 0) {
                    await this.delay(retryDelay);
                }

                console.warn(`⚠️ [${this.agentId}] ${context} 失敗，智能重試 ${attempt + 1}/${maxRetries}: ${error.message}`);

                // 指數退避
                if (this.options.exponentialBackoff) {
                    delay = Math.min(delay * 2, this.options.maxRetryDelay);
                }
            }
        }
    }

    /**
     * 處理錯誤並進行模式識別
     */
    async processError(error, context, attempt, operationId) {
        const errorInfo = {
            agentId: this.agentId,
            operationId,
            context,
            message: error.message,
            stack: error.stack,
            code: error.code,
            timestamp: new Date().toISOString(),
            attempt,
            severity: this.categorizeError(error)
        };

        this.errors.push(errorInfo);
        this.updateMetrics('error');

        // 錯誤模式識別
        await this.identifyErrorPattern(error, context);

        // 記錄錯誤
        if (this.options.logErrors) {
            await this.logError(errorInfo);
        }

        // 嘗試自動恢復
        if (this.options.enableRecovery) {
            const recovered = await this.attemptIntelligentRecovery(error, context);
            if (recovered) {
                this.metrics.totalRecoveries++;
                this.emit('errorRecovered', { error: errorInfo, strategy: 'auto' });
                return true;
            }
        }

        // 發送警報（如果超過閾值）
        await this.checkAlertConditions();

        this.emit('errorProcessed', errorInfo);
        return false;
    }

    /**
     * 錯誤分類
     */
    categorizeError(error) {
        if (error.code === 'EACCES' || error.message.includes('permission')) {
            return 'critical';
        }
        if (error.code === 'ENOENT' || error.message.includes('not found')) {
            return 'warning';
        }
        if (error.message.includes('timeout') || error.code === 'ETIMEDOUT') {
            return 'warning';
        }
        if (error.name === 'SyntaxError') {
            return 'error';
        }
        return 'error';
    }

    /**
     * 錯誤模式識別
     */
    async identifyErrorPattern(error, context) {
        const patternKey = `${error.name}_${error.code || 'unknown'}`;

        if (!this.errorPatterns.has(patternKey)) {
            this.errorPatterns.set(patternKey, {
                count: 0,
                contexts: new Set(),
                firstSeen: Date.now(),
                lastSeen: Date.now(),
                severity: this.categorizeError(error)
            });
        }

        const pattern = this.errorPatterns.get(patternKey);
        pattern.count++;
        pattern.contexts.add(context);
        pattern.lastSeen = Date.now();

        this.metrics.patternMatches++;

        // 如果模式頻繁出現，觸發學習機制
        if (pattern.count > 5) {
            this.emit('patternDetected', {
                pattern: patternKey,
                count: pattern.count,
                contexts: Array.from(pattern.contexts),
                suggestion: await this.suggestSolution(patternKey, pattern)
            });
        }
    }

    /**
     * 建議解決方案
     */
    async suggestSolution(patternKey, pattern) {
        const suggestions = [];

        if (patternKey.includes('ENOENT')) {
            suggestions.push('考慮預先創建必要的目錄結構');
            suggestions.push('檢查文件路徑配置是否正確');
        }

        if (patternKey.includes('timeout')) {
            suggestions.push('增加操作超時時間');
            suggestions.push('檢查網路連接穩定性');
            suggestions.push('考慮使用連接池');
        }

        if (patternKey.includes('SyntaxError')) {
            suggestions.push('驗證輸入數據格式');
            suggestions.push('添加數據清理步驟');
        }

        return suggestions;
    }

    /**
     * 智能恢復機制
     */
    async attemptIntelligentRecovery(error, context) {
        const errorType = error.code || error.name;
        const strategy = this.recoveryStrategies.get(errorType);

        if (!strategy || !strategy.autoRecover) {
            return false;
        }

        try {
            switch (strategy.strategy) {
                case 'createMissing':
                    return await this.handleMissingFileError(error, context);

                case 'permissionFix':
                    return await this.handlePermissionError(error, context);

                case 'exponentialBackoff':
                    return await this.handleTimeoutError(error, context);

                case 'fallbackData':
                    return await this.handleDataError(error, context);

                default:
                    return false;
            }
        } catch (recoveryError) {
            console.warn(`⚠️ [${this.agentId}] 恢復策略失敗: ${recoveryError.message}`);
            return false;
        }
    }

    /**
     * 處理數據錯誤
     */
    async handleDataError(error, context) {
        if (error.name === 'SyntaxError' && context.includes('JSON')) {
            console.log(`🔧 [${this.agentId}] 嘗試使用備用JSON解析...`);
            // 這裡可以實現備用解析邏輯
            return false;
        }
        return false;
    }

    /**
     * 計算智能重試延遲
     */
    calculateRetryDelay(baseDelay, attempt, error) {
        let delay = baseDelay;

        // 指數退避
        if (this.options.exponentialBackoff) {
            delay = baseDelay * Math.pow(2, attempt);
        }

        // 限制最大延遲
        delay = Math.min(delay, this.options.maxRetryDelay);

        // 添加抖動避免雷群效應
        if (this.options.jitterRange > 0) {
            const jitter = delay * this.options.jitterRange * (Math.random() - 0.5);
            delay += jitter;
        }

        // 根據錯誤類型調整
        if (error.code === 'ETIMEDOUT') {
            delay *= 1.5; // 網路超時需要更長等待
        }

        return Math.max(0, Math.floor(delay));
    }

    /**
     * 處理最終失敗
     */
    handleFinalFailure(error, context, attempts) {
        this.circuitBreaker.failures++;
        this.circuitBreaker.lastFailure = Date.now();

        if (this.circuitBreaker.failures >= this.options.circuitBreakerThreshold) {
            this.circuitBreaker.state = 'OPEN';
            this.metrics.circuitBreakerTrips++;
            console.warn(`🚨 [${this.agentId}] Circuit breaker OPENED after ${this.circuitBreaker.failures} failures`);

            this.emit('circuitBreakerOpened', {
                agentId: this.agentId,
                failures: this.circuitBreaker.failures,
                lastError: error.message
            });
        }
    }

    /**
     * 更新指標
     */
    updateMetrics(type, responseTime = 0) {
        const now = Date.now();

        if (type === 'success') {
            this.metrics.avgResponseTime = (this.metrics.avgResponseTime + responseTime) / 2;
        } else if (type === 'error') {
            this.metrics.totalErrors++;
        }

        // 計算錯誤率（過去1小時）
        const recentErrors = this.errors.filter(e =>
            now - new Date(e.timestamp).getTime() < 60 * 60 * 1000
        ).length;

        this.metrics.errorRate = recentErrors;
        this.metrics.lastUpdated = now;
    }

    /**
     * 檢查警報條件
     */
    async checkAlertConditions() {
        const recentErrors = this.errors.filter(e =>
            Date.now() - new Date(e.timestamp).getTime() < 10 * 60 * 1000 // 過去10分鐘
        ).length;

        if (recentErrors >= this.options.alertThreshold && !this.alertSent) {
            this.alertSent = true;

            this.emit('alertTriggered', {
                agentId: this.agentId,
                recentErrors,
                threshold: this.options.alertThreshold,
                topErrors: this.getTopErrorPatterns(5)
            });

            // 30分鐘後重置警報狀態
            setTimeout(() => {
                this.alertSent = false;
            }, 30 * 60 * 1000);
        }
    }

    /**
     * 獲取最常見錯誤模式
     */
    getTopErrorPatterns(limit = 10) {
        return Array.from(this.errorPatterns.entries())
            .sort(([,a], [,b]) => b.count - a.count)
            .slice(0, limit)
            .map(([pattern, data]) => ({
                pattern,
                count: data.count,
                severity: data.severity,
                contexts: Array.from(data.contexts)
            }));
    }

    /**
     * 生成健康報告
     */
    generateHealthReport() {
        const now = Date.now();
        const last24h = 24 * 60 * 60 * 1000;

        const recentErrors = this.errors.filter(e =>
            now - new Date(e.timestamp).getTime() < last24h
        );

        return {
            agentId: this.agentId,
            timestamp: new Date().toISOString(),
            circuitBreakerState: this.circuitBreaker.state,
            metrics: { ...this.metrics },
            last24Hours: {
                totalErrors: recentErrors.length,
                criticalErrors: recentErrors.filter(e => e.severity === 'critical').length,
                topPatterns: this.getTopErrorPatterns(3)
            },
            recommendations: this.generateRecommendations()
        };
    }

    /**
     * 生成改進建議
     */
    generateRecommendations() {
        const recommendations = [];

        if (this.circuitBreaker.failures > 0) {
            recommendations.push('考慮調整斷路器閾值或超時設定');
        }

        if (this.metrics.errorRate > 5) {
            recommendations.push('錯誤率偏高，建議檢查系統健康狀況');
        }

        const topPattern = this.getTopErrorPatterns(1)[0];
        if (topPattern && topPattern.count > 10) {
            recommendations.push(`頻繁出現 ${topPattern.pattern} 錯誤，建議針對性優化`);
        }

        return recommendations;
    }

    /**
     * 設置清理計時器
     */
    setupCleanupTimer() {
        // 每小時清理一次舊數據
        setInterval(() => {
            this.cleanup();
        }, 60 * 60 * 1000);
    }

    /**
     * 高級清理功能
     */
    cleanup(maxAge = 24 * 60 * 60 * 1000) {
        const cutoff = Date.now() - maxAge;

        // 清理錯誤記錄
        this.errors = this.errors.filter(error =>
            new Date(error.timestamp).getTime() > cutoff
        );

        // 清理錯誤模式
        for (const [pattern, data] of this.errorPatterns.entries()) {
            if (data.lastSeen < cutoff) {
                this.errorPatterns.delete(pattern);
            }
        }

        // 清理重試計數
        this.retryCount.clear();
    }

    // 繼承原有方法
    async handleMissingFileError(error, context) {
        const missingPath = error.path;
        if (!missingPath) return false;

        try {
            if (context.includes('directory') || context.includes('目錄')) {
                await fs.mkdir(missingPath, { recursive: true });
                console.log(`✅ [${this.agentId}] 已創建缺失目錄: ${missingPath}`);
                return true;
            }

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

    async handlePermissionError(error, context) {
        console.warn(`⚠️ [${this.agentId}] 權限錯誤: ${error.path || 'unknown path'}`);
        console.warn(`💡 建議檢查文件權限或以適當權限運行程序`);
        return false;
    }

    async handleTimeoutError(error, context) {
        console.warn(`⚠️ [${this.agentId}] 操作超時: ${context}`);
        console.warn(`💡 建議增加超時時間或檢查網絡連接`);
        return false;
    }

    async logError(errorInfo) {
        if (!this.options.logErrors) return;

        try {
            const logDir = this.options.logPath;
            await fs.mkdir(logDir, { recursive: true });

            const logFile = path.join(logDir, `${this.agentId}_errors.log`);
            await fs.appendFile(logFile, JSON.stringify(errorInfo) + '\n', 'utf8');
        } catch (logError) {
            console.warn(`⚠️ [${this.agentId}] 錯誤日誌寫入失敗: ${logError.message}`);
        }
    }

    createEnhancedError(originalError, context, attempts) {
        const enhancedError = new Error(
            `[${this.agentId}] ${context}: ${originalError.message} (失敗於 ${attempts + 1} 次嘗試後)`
        );

        enhancedError.originalError = originalError;
        enhancedError.agentId = this.agentId;
        enhancedError.context = context;
        enhancedError.attempts = attempts + 1;
        enhancedError.stack = originalError.stack;
        enhancedError.circuitBreakerState = this.circuitBreaker.state;

        return enhancedError;
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    getErrorStats() {
        return {
            ...this.metrics,
            patterns: this.getTopErrorPatterns(10),
            circuitBreakerState: this.circuitBreaker.state,
            recentErrors: this.errors.slice(-10)
        };
    }

    reset() {
        this.errors = [];
        this.retryCount.clear();
        this.errorPatterns.clear();
        this.circuitBreaker.failures = 0;
        this.circuitBreaker.state = 'CLOSED';
        this.metrics = this.initializeMetrics();
        this.alertSent = false;
    }
}

module.exports = UnifiedErrorHandler;