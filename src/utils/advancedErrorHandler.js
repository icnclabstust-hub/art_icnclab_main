/**
 * 進階錯誤處理與重試機制
 * 專為藝術史資料庫設計的智能錯誤管理系統
 */

const EventEmitter = require('events');
const fs = require('fs/promises');
const path = require('path');
const { logger } = require('./logger');

class AdvancedErrorHandler extends EventEmitter {
    constructor(agentId, options = {}) {
        super();
        this.agentId = agentId;
        this.options = {
            // 基本重試配置
            maxRetries: options.maxRetries || 3,
            baseDelay: options.baseDelay || 1000,
            maxDelay: options.maxDelay || 30000,
            backoffMultiplier: options.backoffMultiplier || 2,
            jitterMax: options.jitterMax || 0.1,

            // 斷路器配置
            circuitBreakerThreshold: options.circuitBreakerThreshold || 5,
            circuitBreakerTimeout: options.circuitBreakerTimeout || 60000,
            halfOpenMaxCalls: options.halfOpenMaxCalls || 3,

            // 錯誤分類配置
            enableSmartRetry: options.enableSmartRetry !== false,
            enableErrorPattern: options.enableErrorPattern !== false,
            enableAutoRecovery: options.enableAutoRecovery !== false,

            // 監控配置
            metricsEnabled: options.metricsEnabled !== false,
            healthCheckInterval: options.healthCheckInterval || 300000, // 5分鐘
            alertThreshold: options.alertThreshold || 10,

            // 日誌配置
            logLevel: options.logLevel || 'info',
            logPath: options.logPath || './logs/errors',
            rotateLogsDaily: options.rotateLogsDaily !== false,
        };

        // 錯誤狀態管理
        this.circuitBreaker = {
            state: 'CLOSED', // CLOSED, OPEN, HALF_OPEN
            failures: 0,
            lastFailureTime: null,
            successCount: 0,
            nextAttempt: null
        };

        // 錯誤統計與模式識別
        this.errorRegistry = new Map();
        this.retryRegistry = new Map();
        this.recoveryStrategies = new Map();
        this.errorPatterns = new Map();

        // 性能指標
        this.metrics = {
            totalOperations: 0,
            totalFailures: 0,
            totalRetries: 0,
            totalRecoveries: 0,
            avgResponseTime: 0,
            circuitBreakerTrips: 0,
            patternDetections: 0,
            lastHealthCheck: Date.now()
        };

        // 警報狀態
        this.alertState = {
            active: false,
            lastAlert: null,
            cooldownUntil: null
        };

        this.initializeRecoveryStrategies();
        this.startHealthMonitoring();
    }

    /**
     * 初始化恢復策略
     */
    initializeRecoveryStrategies() {
        // 資料庫相關錯誤
        this.recoveryStrategies.set('DATABASE_CONNECTION', {
            maxRetries: 5,
            baseDelay: 2000,
            strategy: 'exponentialBackoff',
            autoRecover: async (error, context) => {
                logger.warn('資料庫連接失敗，嘗試重新連接...', { error: error.message });
                // 可以在這裡實現資料庫重連邏輯
                return false;
            }
        });

        // API請求錯誤
        this.recoveryStrategies.set('API_REQUEST', {
            maxRetries: 3,
            baseDelay: 1000,
            strategy: 'linearBackoff',
            autoRecover: async (error, context) => {
                if (error.status === 429) { // Rate limiting
                    const retryAfter = error.headers?.['retry-after'] || 60;
                    logger.info(`API速率限制，等待 ${retryAfter} 秒`);
                    await this.delay(retryAfter * 1000);
                    return true;
                }
                return false;
            }
        });

        // 網路錯誤
        this.recoveryStrategies.set('NETWORK_ERROR', {
            maxRetries: 4,
            baseDelay: 1500,
            strategy: 'exponentialBackoffWithJitter',
            autoRecover: async (error, context) => {
                logger.warn('網路錯誤，檢查連接狀況', { error: error.message });
                return false;
            }
        });

        // 文件系統錯誤
        this.recoveryStrategies.set('FILE_SYSTEM', {
            maxRetries: 2,
            baseDelay: 500,
            strategy: 'fixedDelay',
            autoRecover: async (error, context) => {
                if (error.code === 'ENOENT') {
                    return await this.handleMissingFileError(error);
                }
                return false;
            }
        });

        // 解析錯誤
        this.recoveryStrategies.set('PARSING_ERROR', {
            maxRetries: 1,
            baseDelay: 100,
            strategy: 'immediate',
            autoRecover: async (error, context) => {
                logger.warn('資料解析失敗，嘗試備用解析方法', { error: error.message });
                // 可以實現備用解析邏輯
                return false;
            }
        });

        // 驗證錯誤
        this.recoveryStrategies.set('VALIDATION_ERROR', {
            maxRetries: 0, // 驗證錯誤通常不應重試
            strategy: 'noRetry',
            autoRecover: async (error, context) => {
                logger.error('資料驗證失敗', { error: error.message, context });
                return false;
            }
        });
    }

    /**
     * 智能執行包裝器
     */
    async executeWithRetry(operation, context = '', options = {}) {
        const operationId = this.generateOperationId(context);
        const startTime = Date.now();

        // 檢查斷路器狀態
        if (!this.canExecute()) {
            const error = new Error(`Circuit breaker is ${this.circuitBreaker.state}. Operation rejected.`);
            error.circuitBreakerState = this.circuitBreaker.state;
            throw error;
        }

        const errorType = this.determineErrorType(context, options);
        const strategy = this.recoveryStrategies.get(errorType) || this.getDefaultStrategy();
        const maxRetries = options.maxRetries || strategy.maxRetries || this.options.maxRetries;

        let lastError = null;
        let attempt = 0;

        while (attempt <= maxRetries) {
            try {
                this.metrics.totalOperations++;

                // 執行操作
                const result = await operation();

                // 操作成功
                this.handleSuccess(operationId, startTime, attempt);
                return result;

            } catch (error) {
                lastError = error;
                attempt++;

                // 處理錯誤
                await this.processError(error, context, operationId, attempt);

                if (attempt > maxRetries) {
                    // 所有重試都失敗了
                    this.handleFinalFailure(error, context, operationId, attempt - 1);
                    throw this.createEnhancedError(error, context, attempt - 1);
                }

                // 嘗試自動恢復
                if (this.options.enableAutoRecovery && strategy.autoRecover) {
                    try {
                        const recovered = await strategy.autoRecover(error, context);
                        if (recovered) {
                            this.metrics.totalRecoveries++;
                            logger.info('自動恢復成功', { context, attempt });
                            continue; // 直接重試，不等待
                        }
                    } catch (recoveryError) {
                        logger.warn('自動恢復失敗', {
                            context,
                            error: recoveryError.message
                        });
                    }
                }

                // 計算重試延遲
                const delay = this.calculateRetryDelay(strategy, attempt - 1, error);
                if (delay > 0) {
                    logger.info(`操作失敗，${delay}ms後重試 (${attempt}/${maxRetries})`, {
                        context,
                        error: error.message,
                        attempt,
                        maxRetries
                    });
                    await this.delay(delay);
                }
            }
        }

        // 不應該到達這裡
        throw lastError;
    }

    /**
     * 檢查是否可以執行操作
     */
    canExecute() {
        switch (this.circuitBreaker.state) {
            case 'CLOSED':
                return true;

            case 'OPEN':
                if (Date.now() > this.circuitBreaker.nextAttempt) {
                    this.circuitBreaker.state = 'HALF_OPEN';
                    this.circuitBreaker.successCount = 0;
                    logger.info('斷路器轉換為半開狀態');
                    return true;
                }
                return false;

            case 'HALF_OPEN':
                return this.circuitBreaker.successCount < this.options.halfOpenMaxCalls;

            default:
                return false;
        }
    }

    /**
     * 處理操作成功
     */
    handleSuccess(operationId, startTime, attempts) {
        const duration = Date.now() - startTime;
        this.metrics.avgResponseTime = this.updateAverage(
            this.metrics.avgResponseTime,
            duration,
            this.metrics.totalOperations
        );

        // 處理斷路器狀態
        if (this.circuitBreaker.state === 'HALF_OPEN') {
            this.circuitBreaker.successCount++;
            if (this.circuitBreaker.successCount >= this.options.halfOpenMaxCalls) {
                this.circuitBreaker.state = 'CLOSED';
                this.circuitBreaker.failures = 0;
                logger.info('斷路器重置為關閉狀態');
            }
        }

        // 移除重試記錄
        this.retryRegistry.delete(operationId);

        this.emit('operationSuccess', {
            operationId,
            duration,
            attempts,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * 處理錯誤
     */
    async processError(error, context, operationId, attempt) {
        this.metrics.totalFailures++;
        if (attempt > 1) {
            this.metrics.totalRetries++;
        }

        // 錯誤分類和記錄
        const errorInfo = {
            operationId,
            context,
            attempt,
            timestamp: new Date().toISOString(),
            error: {
                name: error.name,
                message: error.message,
                code: error.code,
                status: error.status,
                stack: this.options.logLevel === 'debug' ? error.stack : undefined
            }
        };

        this.errorRegistry.set(operationId, errorInfo);

        // 錯誤模式識別
        if (this.options.enableErrorPattern) {
            await this.analyzeErrorPattern(error, context);
        }

        // 記錄錯誤
        logger.error('操作失敗', errorInfo);

        this.emit('operationError', errorInfo);
    }

    /**
     * 處理最終失敗
     */
    handleFinalFailure(error, context, operationId, attempts) {
        this.circuitBreaker.failures++;
        this.circuitBreaker.lastFailureTime = Date.now();

        // 檢查是否觸發斷路器
        if (this.circuitBreaker.failures >= this.options.circuitBreakerThreshold) {
            this.openCircuitBreaker();
        }

        // 檢查警報條件
        this.checkAlertConditions();

        this.emit('operationFinalFailure', {
            operationId,
            context,
            attempts,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * 打開斷路器
     */
    openCircuitBreaker() {
        this.circuitBreaker.state = 'OPEN';
        this.circuitBreaker.nextAttempt = Date.now() + this.options.circuitBreakerTimeout;
        this.metrics.circuitBreakerTrips++;

        logger.warn('斷路器打開', {
            failures: this.circuitBreaker.failures,
            nextAttempt: new Date(this.circuitBreaker.nextAttempt).toISOString()
        });

        this.emit('circuitBreakerOpened', {
            agentId: this.agentId,
            failures: this.circuitBreaker.failures,
            timeout: this.options.circuitBreakerTimeout
        });
    }

    /**
     * 錯誤模式分析
     */
    async analyzeErrorPattern(error, context) {
        const patternKey = this.generatePatternKey(error);

        if (!this.errorPatterns.has(patternKey)) {
            this.errorPatterns.set(patternKey, {
                count: 0,
                contexts: new Set(),
                firstOccurrence: Date.now(),
                lastOccurrence: Date.now(),
                severity: this.classifyErrorSeverity(error)
            });
        }

        const pattern = this.errorPatterns.get(patternKey);
        pattern.count++;
        pattern.contexts.add(context);
        pattern.lastOccurrence = Date.now();

        // 如果模式頻繁出現，觸發警報
        if (pattern.count > 5 && !this.alertState.active) {
            this.metrics.patternDetections++;

            const suggestion = await this.generatePatternSuggestion(patternKey, pattern);

            this.emit('patternDetected', {
                pattern: patternKey,
                count: pattern.count,
                contexts: Array.from(pattern.contexts),
                severity: pattern.severity,
                suggestion
            });

            logger.warn('檢測到錯誤模式', {
                pattern: patternKey,
                count: pattern.count,
                suggestion
            });
        }
    }

    /**
     * 生成錯誤模式建議
     */
    async generatePatternSuggestion(patternKey, pattern) {
        const suggestions = [];

        if (patternKey.includes('timeout')) {
            suggestions.push('考慮增加超時時間或優化網路連接');
            suggestions.push('檢查是否存在資源爭用問題');
        }

        if (patternKey.includes('ENOTFOUND')) {
            suggestions.push('檢查DNS配置和網域名稱');
            suggestions.push('確認服務端點是否可達');
        }

        if (patternKey.includes('429')) {
            suggestions.push('實施請求速率限制和退避策略');
            suggestions.push('考慮使用API密鑰池或負載均衡');
        }

        if (patternKey.includes('validation')) {
            suggestions.push('檢查輸入資料格式和驗證規則');
            suggestions.push('考慮增強資料清理邏輯');
        }

        if (pattern.severity === 'critical') {
            suggestions.push('這是關鍵錯誤，建議立即人工介入');
        }

        return suggestions.length > 0 ? suggestions : ['暫無特定建議，請檢查系統日誌'];
    }

    /**
     * 計算重試延遲
     */
    calculateRetryDelay(strategy, attempt, error) {
        let delay = strategy.baseDelay || this.options.baseDelay;

        switch (strategy.strategy) {
            case 'immediate':
                return 0;

            case 'fixedDelay':
                return delay;

            case 'linearBackoff':
                return delay * (attempt + 1);

            case 'exponentialBackoff':
                return Math.min(
                    delay * Math.pow(this.options.backoffMultiplier, attempt),
                    this.options.maxDelay
                );

            case 'exponentialBackoffWithJitter': {
                const expDelay = Math.min(
                    delay * Math.pow(this.options.backoffMultiplier, attempt),
                    this.options.maxDelay
                );
                const jitter = expDelay * this.options.jitterMax * Math.random();
                return expDelay + jitter;
            }

            case 'noRetry':
                return -1; // 表示不重試

            default:
                return delay;
        }
    }

    /**
     * 確定錯誤類型
     */
    determineErrorType(context, options) {
        if (options.errorType) {
            return options.errorType;
        }

        if (context.includes('database') || context.includes('資料庫')) {
            return 'DATABASE_CONNECTION';
        }
        if (context.includes('api') || context.includes('request')) {
            return 'API_REQUEST';
        }
        if (context.includes('network') || context.includes('網路')) {
            return 'NETWORK_ERROR';
        }
        if (context.includes('file') || context.includes('文件')) {
            return 'FILE_SYSTEM';
        }
        if (context.includes('parse') || context.includes('解析')) {
            return 'PARSING_ERROR';
        }
        if (context.includes('validation') || context.includes('驗證')) {
            return 'VALIDATION_ERROR';
        }

        return 'GENERIC';
    }

    /**
     * 獲取默認策略
     */
    getDefaultStrategy() {
        return {
            maxRetries: this.options.maxRetries,
            baseDelay: this.options.baseDelay,
            strategy: 'exponentialBackoff',
            autoRecover: null
        };
    }

    /**
     * 檢查警報條件
     */
    checkAlertConditions() {
        if (this.alertState.active || Date.now() < this.alertState.cooldownUntil) {
            return;
        }

        const recentErrors = Array.from(this.errorRegistry.values())
            .filter(e => Date.now() - new Date(e.timestamp).getTime() < 600000) // 10分鐘內
            .length;

        if (recentErrors >= this.options.alertThreshold) {
            this.triggerAlert(recentErrors);
        }
    }

    /**
     * 觸發警報
     */
    triggerAlert(recentErrorCount) {
        this.alertState.active = true;
        this.alertState.lastAlert = Date.now();
        this.alertState.cooldownUntil = Date.now() + 1800000; // 30分鐘冷卻

        const alertInfo = {
            agentId: this.agentId,
            recentErrorCount,
            threshold: this.options.alertThreshold,
            circuitBreakerState: this.circuitBreaker.state,
            topPatterns: this.getTopErrorPatterns(3),
            recommendations: this.generateHealthRecommendations()
        };

        logger.warn('錯誤警報觸發', alertInfo);
        this.emit('alertTriggered', alertInfo);

        // 30分鐘後重置警報狀態
        setTimeout(() => {
            this.alertState.active = false;
        }, 1800000);
    }

    /**
     * 開始健康監控
     */
    startHealthMonitoring() {
        setInterval(() => {
            this.performHealthCheck();
        }, this.options.healthCheckInterval);
    }

    /**
     * 執行健康檢查
     */
    performHealthCheck() {
        this.metrics.lastHealthCheck = Date.now();

        const healthReport = this.generateHealthReport();

        if (healthReport.status === 'unhealthy') {
            logger.warn('系統健康檢查異常', healthReport);
            this.emit('healthCheckFailed', healthReport);
        } else {
            logger.debug('系統健康檢查正常', healthReport);
        }

        // 清理舊數據
        this.cleanupOldData();
    }

    /**
     * 生成健康報告
     */
    generateHealthReport() {
        const now = Date.now();
        const last24Hours = 24 * 60 * 60 * 1000;

        const recentErrors = Array.from(this.errorRegistry.values())
            .filter(e => now - new Date(e.timestamp).getTime() < last24Hours);

        const errorRate = this.metrics.totalOperations > 0
            ? (this.metrics.totalFailures / this.metrics.totalOperations) * 100
            : 0;

        const status = this.determineHealthStatus(errorRate, recentErrors.length);

        return {
            agentId: this.agentId,
            timestamp: new Date().toISOString(),
            status,
            metrics: { ...this.metrics },
            circuitBreakerState: this.circuitBreaker.state,
            recentErrors: recentErrors.length,
            errorRate: Math.round(errorRate * 100) / 100,
            topPatterns: this.getTopErrorPatterns(3),
            recommendations: this.generateHealthRecommendations()
        };
    }

    /**
     * 確定健康狀態
     */
    determineHealthStatus(errorRate, recentErrorCount) {
        if (this.circuitBreaker.state === 'OPEN') {
            return 'critical';
        }
        if (errorRate > 50 || recentErrorCount > 20) {
            return 'unhealthy';
        }
        if (errorRate > 20 || recentErrorCount > 10) {
            return 'degraded';
        }
        return 'healthy';
    }

    /**
     * 生成健康建議
     */
    generateHealthRecommendations() {
        const recommendations = [];
        const errorRate = this.metrics.totalOperations > 0
            ? (this.metrics.totalFailures / this.metrics.totalOperations) * 100
            : 0;

        if (errorRate > 30) {
            recommendations.push('錯誤率過高，建議檢查系統配置');
        }

        if (this.circuitBreaker.failures > 3) {
            recommendations.push('斷路器頻繁觸發，考慮調整閾值或檢查服務依賴');
        }

        if (this.metrics.avgResponseTime > 5000) {
            recommendations.push('平均響應時間過長，建議優化性能');
        }

        const topPattern = this.getTopErrorPatterns(1)[0];
        if (topPattern && topPattern.count > 10) {
            recommendations.push(`頻繁出現${topPattern.pattern}錯誤，建議針對性處理`);
        }

        return recommendations;
    }

    /**
     * 獲取頂級錯誤模式
     */
    getTopErrorPatterns(limit = 10) {
        return Array.from(this.errorPatterns.entries())
            .sort(([,a], [,b]) => b.count - a.count)
            .slice(0, limit)
            .map(([pattern, data]) => ({
                pattern,
                count: data.count,
                severity: data.severity,
                contexts: Array.from(data.contexts).slice(0, 3) // 只顯示前3個上下文
            }));
    }

    /**
     * 清理舊資料
     */
    cleanupOldData() {
        const cutoff = Date.now() - 24 * 60 * 60 * 1000; // 24小時

        // 清理錯誤記錄
        for (const [id, error] of this.errorRegistry.entries()) {
            if (new Date(error.timestamp).getTime() < cutoff) {
                this.errorRegistry.delete(id);
            }
        }

        // 清理錯誤模式
        for (const [pattern, data] of this.errorPatterns.entries()) {
            if (data.lastOccurrence < cutoff) {
                this.errorPatterns.delete(pattern);
            }
        }
    }

    // 工具方法
    generateOperationId(context) {
        return `${this.agentId}_${context}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    generatePatternKey(error) {
        return `${error.name}_${error.code || 'unknown'}_${error.status || 'nostatus'}`;
    }

    classifyErrorSeverity(error) {
        if (error.code === 'EACCES' || error.status === 500) {
            return 'critical';
        }
        if (error.status === 429 || error.code === 'ETIMEDOUT') {
            return 'warning';
        }
        return 'error';
    }

    updateAverage(current, newValue, count) {
        return ((current * (count - 1)) + newValue) / count;
    }

    createEnhancedError(originalError, context, attempts) {
        const enhancedError = new Error(
            `[${this.agentId}] ${context}: ${originalError.message} (${attempts + 1}次嘗試後失敗)`
        );

        enhancedError.originalError = originalError;
        enhancedError.agentId = this.agentId;
        enhancedError.context = context;
        enhancedError.attempts = attempts + 1;
        enhancedError.circuitBreakerState = this.circuitBreaker.state;
        enhancedError.timestamp = new Date().toISOString();

        return enhancedError;
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async handleMissingFileError(error) {
        if (!error.path) return false;

        try {
            const dir = path.dirname(error.path);
            await fs.mkdir(dir, { recursive: true });

            if (path.extname(error.path) === '.json') {
                await fs.writeFile(error.path, '[]', 'utf8');
            } else {
                await fs.writeFile(error.path, '', 'utf8');
            }

            logger.info('自動創建缺失文件', { path: error.path });
            return true;
        } catch (createError) {
            logger.error('創建文件失敗', { error: createError.message });
            return false;
        }
    }

    // 公共API方法
    getMetrics() {
        return { ...this.metrics };
    }

    getCircuitBreakerState() {
        return { ...this.circuitBreaker };
    }

    getErrorPatterns() {
        return this.getTopErrorPatterns();
    }

    reset() {
        this.errorRegistry.clear();
        this.retryRegistry.clear();
        this.errorPatterns.clear();

        this.circuitBreaker.state = 'CLOSED';
        this.circuitBreaker.failures = 0;
        this.circuitBreaker.successCount = 0;

        this.metrics = {
            totalOperations: 0,
            totalFailures: 0,
            totalRetries: 0,
            totalRecoveries: 0,
            avgResponseTime: 0,
            circuitBreakerTrips: 0,
            patternDetections: 0,
            lastHealthCheck: Date.now()
        };

        this.alertState.active = false;
        this.alertState.cooldownUntil = null;

        logger.info('錯誤處理器已重置');
    }
}

module.exports = AdvancedErrorHandler;