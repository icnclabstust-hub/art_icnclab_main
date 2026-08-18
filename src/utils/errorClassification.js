/**
 * 錯誤分類和恢復策略系統
 * 提供智能錯誤分類、恢復策略管理和自動化恢復機制
 */

const { logger } = require('./logger');

/**
 * 錯誤嚴重程度級別
 */
const SEVERITY_LEVELS = {
    CRITICAL: 'critical',    // 系統無法繼續運行
    HIGH: 'high',           // 重要功能受影響
    MEDIUM: 'medium',       // 部分功能受影響
    LOW: 'low',             // 輕微影響
    INFO: 'info'            // 僅供參考
};

/**
 * 錯誤分類
 */
const ERROR_CATEGORIES = {
    // 系統錯誤
    SYSTEM: {
        DATABASE_CONNECTION: 'database_connection',
        FILE_SYSTEM: 'file_system',
        MEMORY_OVERFLOW: 'memory_overflow',
        CPU_OVERLOAD: 'cpu_overload',
        DISK_SPACE: 'disk_space'
    },

    // 網路錯誤
    NETWORK: {
        CONNECTION_TIMEOUT: 'connection_timeout',
        CONNECTION_REFUSED: 'connection_refused',
        DNS_RESOLUTION: 'dns_resolution',
        SSL_CERTIFICATE: 'ssl_certificate',
        RATE_LIMIT: 'rate_limit'
    },

    // 資料錯誤
    DATA: {
        VALIDATION_FAILED: 'validation_failed',
        PARSING_ERROR: 'parsing_error',
        ENCODING_ERROR: 'encoding_error',
        SCHEMA_MISMATCH: 'schema_mismatch',
        DATA_CORRUPTION: 'data_corruption'
    },

    // 外部服務錯誤
    EXTERNAL: {
        API_UNAVAILABLE: 'api_unavailable',
        SERVICE_DEGRADED: 'service_degraded',
        AUTHENTICATION_FAILED: 'authentication_failed',
        QUOTA_EXCEEDED: 'quota_exceeded'
    },

    // 業務邏輯錯誤
    BUSINESS: {
        RESOURCE_NOT_FOUND: 'resource_not_found',
        PERMISSION_DENIED: 'permission_denied',
        INVALID_OPERATION: 'invalid_operation',
        CONSTRAINT_VIOLATION: 'constraint_violation'
    }
};

/**
 * 錯誤分類器
 */
class ErrorClassifier {
    constructor() {
        this.classificationRules = new Map();
        this.initializeClassificationRules();
    }

    /**
     * 初始化分類規則
     */
    initializeClassificationRules() {
        // 資料庫相關錯誤
        this.addRule({
            pattern: /connection.*refused|ECONNREFUSED/i,
            category: ERROR_CATEGORIES.SYSTEM.DATABASE_CONNECTION,
            severity: SEVERITY_LEVELS.CRITICAL,
            recoverable: true,
            description: '資料庫連接被拒絕'
        });

        this.addRule({
            pattern: /timeout.*database|query.*timeout/i,
            category: ERROR_CATEGORIES.SYSTEM.DATABASE_CONNECTION,
            severity: SEVERITY_LEVELS.HIGH,
            recoverable: true,
            description: '資料庫查詢超時'
        });

        // 網路相關錯誤
        this.addRule({
            pattern: /ETIMEDOUT|timeout/i,
            category: ERROR_CATEGORIES.NETWORK.CONNECTION_TIMEOUT,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: true,
            description: '網路連接超時'
        });

        this.addRule({
            pattern: /ENOTFOUND|getaddrinfo/i,
            category: ERROR_CATEGORIES.NETWORK.DNS_RESOLUTION,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: true,
            description: 'DNS解析失敗'
        });

        this.addRule({
            pattern: /rate.*limit|429/i,
            category: ERROR_CATEGORIES.NETWORK.RATE_LIMIT,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: true,
            description: 'API速率限制'
        });

        // 文件系統錯誤
        this.addRule({
            pattern: /ENOENT|no such file/i,
            category: ERROR_CATEGORIES.SYSTEM.FILE_SYSTEM,
            severity: SEVERITY_LEVELS.LOW,
            recoverable: true,
            description: '文件或目錄不存在'
        });

        this.addRule({
            pattern: /EACCES|permission denied/i,
            category: ERROR_CATEGORIES.SYSTEM.FILE_SYSTEM,
            severity: SEVERITY_LEVELS.HIGH,
            recoverable: false,
            description: '文件權限被拒絕'
        });

        // 資料驗證錯誤
        this.addRule({
            pattern: /validation.*failed|invalid.*input/i,
            category: ERROR_CATEGORIES.DATA.VALIDATION_FAILED,
            severity: SEVERITY_LEVELS.LOW,
            recoverable: false,
            description: '資料驗證失敗'
        });

        this.addRule({
            pattern: /JSON.*parse|SyntaxError/i,
            category: ERROR_CATEGORIES.DATA.PARSING_ERROR,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: true,
            description: '資料解析錯誤'
        });

        // 外部API錯誤
        this.addRule({
            pattern: /502|bad gateway/i,
            category: ERROR_CATEGORIES.EXTERNAL.API_UNAVAILABLE,
            severity: SEVERITY_LEVELS.HIGH,
            recoverable: true,
            description: '外部API不可用'
        });

        this.addRule({
            pattern: /503|service unavailable/i,
            category: ERROR_CATEGORIES.EXTERNAL.SERVICE_DEGRADED,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: true,
            description: '外部服務降級'
        });

        // 業務邏輯錯誤
        this.addRule({
            pattern: /404|not found/i,
            category: ERROR_CATEGORIES.BUSINESS.RESOURCE_NOT_FOUND,
            severity: SEVERITY_LEVELS.LOW,
            recoverable: false,
            description: '資源未找到'
        });

        this.addRule({
            pattern: /401|unauthorized/i,
            category: ERROR_CATEGORIES.BUSINESS.PERMISSION_DENIED,
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: false,
            description: '權限不足'
        });

        // 系統資源錯誤
        this.addRule({
            pattern: /out of memory|ENOMEM/i,
            category: ERROR_CATEGORIES.SYSTEM.MEMORY_OVERFLOW,
            severity: SEVERITY_LEVELS.CRITICAL,
            recoverable: false,
            description: '記憶體不足'
        });

        this.addRule({
            pattern: /ENOSPC|no space left/i,
            category: ERROR_CATEGORIES.SYSTEM.DISK_SPACE,
            severity: SEVERITY_LEVELS.CRITICAL,
            recoverable: false,
            description: '磁碟空間不足'
        });
    }

    /**
     * 添加分類規則
     */
    addRule(rule) {
        this.classificationRules.set(rule.pattern, rule);
    }

    /**
     * 分類錯誤
     */
    classify(error) {
        const errorMessage = error.message || '';
        const errorCode = error.code || '';
        const errorStatus = error.status || error.statusCode || 0;
        const errorName = error.name || '';

        // 組合錯誤信息進行匹配
        const searchText = `${errorMessage} ${errorCode} ${errorStatus} ${errorName}`;

        // 遍歷分類規則
        for (const [pattern, rule] of this.classificationRules) {
            if (pattern.test(searchText)) {
                return {
                    category: rule.category,
                    severity: rule.severity,
                    recoverable: rule.recoverable,
                    description: rule.description,
                    confidence: this.calculateConfidence(pattern, searchText)
                };
            }
        }

        // 如果沒有匹配的規則，返回默認分類
        return {
            category: 'unknown',
            severity: SEVERITY_LEVELS.MEDIUM,
            recoverable: false,
            description: '未知錯誤類型',
            confidence: 0.1
        };
    }

    /**
     * 計算分類信心度
     */
    calculateConfidence(pattern, text) {
        const matches = text.match(pattern);
        if (!matches) return 0;

        // 基於匹配長度和位置計算信心度
        const matchLength = matches[0].length;
        const totalLength = text.length;
        const confidence = Math.min(matchLength / totalLength * 2, 1);

        return Math.round(confidence * 100) / 100;
    }
}

/**
 * 恢復策略管理器
 */
class RecoveryStrategyManager {
    constructor() {
        this.strategies = new Map();
        this.initializeStrategies();
    }

    /**
     * 初始化恢復策略
     */
    initializeStrategies() {
        // 資料庫連接恢復
        this.addStrategy(ERROR_CATEGORIES.SYSTEM.DATABASE_CONNECTION, {
            name: 'database_reconnect',
            maxAttempts: 5,
            baseDelay: 2000,
            backoffMultiplier: 1.5,
            execute: async (error, context, attempt) => {
                logger.info('嘗試重新連接資料庫', { attempt, context });

                // 模擬資料庫重連邏輯
                await this.delay(1000 + attempt * 500);

                // 這裡應該實現實際的資料庫重連邏輯
                // 例如: await dbManager.reconnect();

                // 暫時隨機成功/失敗
                const success = Math.random() > 0.3;
                if (success) {
                    logger.info('資料庫重連成功', { attempt });
                    return { success: true, message: '資料庫連接已恢復' };
                } else {
                    logger.warn('資料庫重連失敗', { attempt });
                    return { success: false, message: '資料庫重連失敗' };
                }
            }
        });

        // 文件系統恢復
        this.addStrategy(ERROR_CATEGORIES.SYSTEM.FILE_SYSTEM, {
            name: 'file_system_repair',
            maxAttempts: 2,
            baseDelay: 500,
            backoffMultiplier: 1,
            execute: async (error, context, attempt) => {
                if (error.code === 'ENOENT' && error.path) {
                    try {
                        const fs = require('fs/promises');
                        const path = require('path');

                        // 創建缺失的目錄
                        const dir = path.dirname(error.path);
                        await fs.mkdir(dir, { recursive: true });

                        // 如果是JSON文件，創建空文件
                        if (path.extname(error.path) === '.json') {
                            await fs.writeFile(error.path, '[]', 'utf8');
                        }

                        logger.info('文件系統恢復成功', { path: error.path });
                        return { success: true, message: `已創建缺失的文件: ${error.path}` };
                    } catch (repairError) {
                        logger.error('文件系統恢復失敗', { error: repairError.message });
                        return { success: false, message: '文件系統恢復失敗' };
                    }
                }

                return { success: false, message: '無法自動修復此文件系統錯誤' };
            }
        });

        // 網路重試策略
        this.addStrategy(ERROR_CATEGORIES.NETWORK.CONNECTION_TIMEOUT, {
            name: 'network_retry',
            maxAttempts: 3,
            baseDelay: 1000,
            backoffMultiplier: 2,
            execute: async (error, context, attempt) => {
                logger.info('網路重試中', { attempt, context });

                // 檢查網路連接狀況
                const networkCheck = await this.checkNetworkConnectivity();

                if (networkCheck.available) {
                    return { success: true, message: '網路連接已恢復' };
                } else {
                    return { success: false, message: '網路連接仍然不穩定' };
                }
            }
        });

        // API速率限制處理
        this.addStrategy(ERROR_CATEGORIES.NETWORK.RATE_LIMIT, {
            name: 'rate_limit_backoff',
            maxAttempts: 3,
            baseDelay: 60000, // 1分鐘
            backoffMultiplier: 1,
            execute: async (error, context, attempt) => {
                const retryAfter = error.retryAfter || 60;
                const waitTime = retryAfter * 1000;

                logger.info('API速率限制，等待恢復', { retryAfter, attempt });
                await this.delay(waitTime);

                return { success: true, message: `已等待${retryAfter}秒，可以重試` };
            }
        });

        // 資料解析錯誤恢復
        this.addStrategy(ERROR_CATEGORIES.DATA.PARSING_ERROR, {
            name: 'data_parsing_fallback',
            maxAttempts: 2,
            baseDelay: 100,
            backoffMultiplier: 1,
            execute: async (error, context, attempt) => {
                logger.info('嘗試備用資料解析', { attempt, context });

                // 這裡可以實現備用解析邏輯
                // 例如：使用更寬鬆的解析規則，或清理資料後重新解析

                return { success: false, message: '暫無備用解析策略' };
            }
        });
    }

    /**
     * 添加恢復策略
     */
    addStrategy(category, strategy) {
        this.strategies.set(category, strategy);
    }

    /**
     * 獲取恢復策略
     */
    getStrategy(category) {
        return this.strategies.get(category);
    }

    /**
     * 執行恢復策略
     */
    async executeRecovery(error, classification, context = '') {
        const strategy = this.getStrategy(classification.category);

        if (!strategy) {
            logger.warn('沒有找到對應的恢復策略', {
                category: classification.category,
                error: error.message
            });
            return { success: false, message: '沒有可用的恢復策略' };
        }

        logger.info('執行恢復策略', {
            strategy: strategy.name,
            category: classification.category,
            context
        });

        for (let attempt = 1; attempt <= strategy.maxAttempts; attempt++) {
            try {
                // 計算延遲時間
                const delay = strategy.baseDelay * Math.pow(strategy.backoffMultiplier, attempt - 1);
                if (attempt > 1 && delay > 0) {
                    logger.debug('恢復策略等待中', { delay, attempt });
                    await this.delay(delay);
                }

                // 執行恢復操作
                const result = await strategy.execute(error, context, attempt);

                if (result.success) {
                    logger.info('恢復策略成功', {
                        strategy: strategy.name,
                        attempt,
                        message: result.message
                    });
                    return result;
                }

                logger.warn('恢復策略失敗', {
                    strategy: strategy.name,
                    attempt,
                    maxAttempts: strategy.maxAttempts,
                    message: result.message
                });

            } catch (recoveryError) {
                logger.error('恢復策略執行錯誤', {
                    strategy: strategy.name,
                    attempt,
                    error: recoveryError.message
                });
            }
        }

        return {
            success: false,
            message: `恢復策略 ${strategy.name} 在 ${strategy.maxAttempts} 次嘗試後失敗`
        };
    }

    /**
     * 檢查網路連通性
     */
    async checkNetworkConnectivity() {
        try {
            const https = require('https');
            const url = 'https://www.google.com';

            return new Promise((resolve) => {
                const timeout = setTimeout(() => {
                    resolve({ available: false, latency: null });
                }, 5000);

                const startTime = Date.now();
                const req = https.get(url, (res) => {
                    clearTimeout(timeout);
                    const latency = Date.now() - startTime;
                    resolve({ available: true, latency, status: res.statusCode });
                });

                req.on('error', () => {
                    clearTimeout(timeout);
                    resolve({ available: false, latency: null });
                });
            });
        } catch (error) {
            return { available: false, latency: null };
        }
    }

    /**
     * 延遲函數
     */
    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 獲取所有策略
     */
    getAllStrategies() {
        return Array.from(this.strategies.entries()).map(([category, strategy]) => ({
            category,
            name: strategy.name,
            maxAttempts: strategy.maxAttempts,
            baseDelay: strategy.baseDelay,
            backoffMultiplier: strategy.backoffMultiplier
        }));
    }
}

/**
 * 綜合錯誤分析器
 */
class ErrorAnalyzer {
    constructor() {
        this.classifier = new ErrorClassifier();
        this.recoveryManager = new RecoveryStrategyManager();
        this.errorHistory = new Map();
        this.patternAnalyzer = new ErrorPatternAnalyzer();
    }

    /**
     * 分析錯誤
     */
    async analyzeError(error, context = '') {
        const startTime = Date.now();

        // 分類錯誤
        const classification = this.classifier.classify(error);

        // 記錄錯誤歷史
        this.recordError(error, classification, context);

        // 模式分析
        const patterns = await this.patternAnalyzer.analyzePattern(error, context);

        // 生成建議
        const suggestions = this.generateSuggestions(classification, patterns);

        const analysisTime = Date.now() - startTime;

        const analysis = {
            classification,
            patterns,
            suggestions,
            recoverable: classification.recoverable,
            analysisTime,
            timestamp: new Date().toISOString()
        };

        logger.debug('錯誤分析完成', analysis);

        return analysis;
    }

    /**
     * 嘗試自動恢復
     */
    async attemptRecovery(error, classification, context = '') {
        if (!classification.recoverable) {
            return {
                attempted: false,
                success: false,
                message: '錯誤類型不支持自動恢復'
            };
        }

        const startTime = Date.now();

        try {
            const result = await this.recoveryManager.executeRecovery(error, classification, context);
            const recoveryTime = Date.now() - startTime;

            return {
                attempted: true,
                success: result.success,
                message: result.message,
                strategy: result.strategy,
                recoveryTime
            };
        } catch (recoveryError) {
            logger.error('自動恢復過程中出錯', {
                error: recoveryError.message,
                originalError: error.message
            });

            return {
                attempted: true,
                success: false,
                message: `恢復過程中出錯: ${recoveryError.message}`,
                recoveryTime: Date.now() - startTime
            };
        }
    }

    /**
     * 記錄錯誤歷史
     */
    recordError(error, classification, context) {
        const errorKey = `${classification.category}_${context}`;

        if (!this.errorHistory.has(errorKey)) {
            this.errorHistory.set(errorKey, {
                count: 0,
                firstOccurrence: Date.now(),
                lastOccurrence: Date.now(),
                contexts: new Set()
            });
        }

        const history = this.errorHistory.get(errorKey);
        history.count++;
        history.lastOccurrence = Date.now();
        history.contexts.add(context);
    }

    /**
     * 生成改進建議
     */
    generateSuggestions(classification, patterns) {
        const suggestions = [];

        // 基於錯誤分類的建議
        switch (classification.category) {
            case ERROR_CATEGORIES.SYSTEM.DATABASE_CONNECTION:
                suggestions.push('檢查資料庫連接配置');
                suggestions.push('確認資料庫服務是否正常運行');
                suggestions.push('考慮增加連接池大小');
                break;

            case ERROR_CATEGORIES.NETWORK.CONNECTION_TIMEOUT:
                suggestions.push('增加請求超時時間');
                suggestions.push('檢查網路連接穩定性');
                suggestions.push('考慮實施指數退避重試');
                break;

            case ERROR_CATEGORIES.DATA.VALIDATION_FAILED:
                suggestions.push('檢查輸入資料格式');
                suggestions.push('更新資料驗證規則');
                suggestions.push('加強資料預處理');
                break;

            case ERROR_CATEGORIES.NETWORK.RATE_LIMIT:
                suggestions.push('實施請求速率控制');
                suggestions.push('使用API密鑰池');
                suggestions.push('考慮快取策略減少請求');
                break;
        }

        // 基於模式分析的建議
        if (patterns.frequency === 'high') {
            suggestions.push('此錯誤頻繁發生，建議優先處理');
        }

        if (patterns.trend === 'increasing') {
            suggestions.push('錯誤趨勢增加，可能需要系統維護');
        }

        return suggestions;
    }

    /**
     * 獲取錯誤統計
     */
    getErrorStatistics() {
        const stats = {
            totalErrors: 0,
            byCategory: {},
            byContext: {},
            frequentErrors: []
        };

        for (const [key, history] of this.errorHistory) {
            stats.totalErrors += history.count;

            const [category] = key.split('_');
            stats.byCategory[category] = (stats.byCategory[category] || 0) + history.count;

            if (history.count > 5) {
                stats.frequentErrors.push({
                    key,
                    count: history.count,
                    category,
                    contexts: Array.from(history.contexts)
                });
            }
        }

        stats.frequentErrors.sort((a, b) => b.count - a.count);

        return stats;
    }
}

/**
 * 錯誤模式分析器
 */
class ErrorPatternAnalyzer {
    constructor() {
        this.patterns = new Map();
    }

    async analyzePattern(error, context) {
        const patternKey = `${error.name}_${context}`;

        if (!this.patterns.has(patternKey)) {
            this.patterns.set(patternKey, {
                occurrences: [],
                frequency: 'low',
                trend: 'stable'
            });
        }

        const pattern = this.patterns.get(patternKey);
        pattern.occurrences.push(Date.now());

        // 保持最近100次記錄
        if (pattern.occurrences.length > 100) {
            pattern.occurrences = pattern.occurrences.slice(-100);
        }

        // 分析頻率
        const recentOccurrences = pattern.occurrences.filter(
            time => Date.now() - time < 3600000 // 最近1小時
        ).length;

        if (recentOccurrences > 10) {
            pattern.frequency = 'high';
        } else if (recentOccurrences > 3) {
            pattern.frequency = 'medium';
        } else {
            pattern.frequency = 'low';
        }

        // 分析趨勢
        if (pattern.occurrences.length >= 10) {
            const recent = pattern.occurrences.slice(-5);
            const previous = pattern.occurrences.slice(-10, -5);

            const recentAvg = this.calculateAverageInterval(recent);
            const previousAvg = this.calculateAverageInterval(previous);

            if (recentAvg < previousAvg * 0.8) {
                pattern.trend = 'increasing';
            } else if (recentAvg > previousAvg * 1.2) {
                pattern.trend = 'decreasing';
            } else {
                pattern.trend = 'stable';
            }
        }

        return {
            frequency: pattern.frequency,
            trend: pattern.trend,
            recentOccurrences
        };
    }

    calculateAverageInterval(occurrences) {
        if (occurrences.length < 2) return 0;

        let totalInterval = 0;
        for (let i = 1; i < occurrences.length; i++) {
            totalInterval += occurrences[i] - occurrences[i - 1];
        }

        return totalInterval / (occurrences.length - 1);
    }
}

// 創建全局實例
const errorAnalyzer = new ErrorAnalyzer();

module.exports = {
    ErrorClassifier,
    RecoveryStrategyManager,
    ErrorAnalyzer,
    ErrorPatternAnalyzer,
    errorAnalyzer,
    SEVERITY_LEVELS,
    ERROR_CATEGORIES
};