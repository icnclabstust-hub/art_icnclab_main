/**
 * 高級速率限制管理器
 * 提供動態速率限制、令牌桶演算法和智能調整功能
 */

const EventEmitter = require('events');
const { logger } = require('./logger');

class RateLimitManager extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            defaultRateLimit: options.defaultRateLimit || 100, // 每分鐘請求數
            burstLimit: options.burstLimit || 10, // 突發請求數
            windowSize: options.windowSize || 60000, // 時間窗口大小（毫秒）
            enableTokenBucket: options.enableTokenBucket !== false,
            enableSlidingWindow: options.enableSlidingWindow !== false,
            enableAdaptiveRateLimit: options.enableAdaptiveRateLimit !== false,
            backoffMultiplier: options.backoffMultiplier || 2,
            maxBackoffTime: options.maxBackoffTime || 300000, // 5分鐘
            recoveryThreshold: options.recoveryThreshold || 0.8, // 成功率閾值
            monitoringInterval: options.monitoringInterval || 30000, // 監控間隔
            ...options
        };

        // 速率限制追蹤
        this.rateLimits = new Map(); // source -> rate limit config
        this.tokenBuckets = new Map(); // source -> token bucket
        this.slidingWindows = new Map(); // source -> sliding window
        this.requestHistory = new Map(); // source -> request history
        this.backoffState = new Map(); // source -> backoff state

        // 統計資料
        this.statistics = new Map(); // source -> statistics

        // 啟動監控
        this.startMonitoring();

        logger.info('速率限制管理器初始化完成', {
            defaultRateLimit: this.options.defaultRateLimit,
            enableTokenBucket: this.options.enableTokenBucket,
            enableAdaptiveRateLimit: this.options.enableAdaptiveRateLimit
        });
    }

    /**
     * 註冊資料源的速率限制配置
     */
    registerSource(source, config) {
        const rateLimitConfig = {
            rateLimit: config.rateLimit || this.options.defaultRateLimit,
            burstLimit: config.burstLimit || this.options.burstLimit,
            windowSize: config.windowSize || this.options.windowSize,
            priority: config.priority || 'medium',
            respectRetryAfter: config.respectRetryAfter !== false,
            maxConcurrency: config.maxConcurrency || 5,
            ...config
        };

        this.rateLimits.set(source, rateLimitConfig);

        // 初始化令牌桶
        if (this.options.enableTokenBucket) {
            this.initializeTokenBucket(source, rateLimitConfig);
        }

        // 初始化滑動窗口
        if (this.options.enableSlidingWindow) {
            this.initializeSlidingWindow(source, rateLimitConfig);
        }

        // 初始化統計
        this.statistics.set(source, {
            totalRequests: 0,
            successfulRequests: 0,
            rateLimitedRequests: 0,
            backoffEvents: 0,
            averageResponseTime: 0,
            successRate: 1.0,
            currentRateLimit: rateLimitConfig.rateLimit,
            lastRequestTime: 0,
            lastSuccessTime: Date.now()
        });

        logger.info('註冊資料源速率限制', { source, config: rateLimitConfig });

        return rateLimitConfig;
    }

    /**
     * 初始化令牌桶
     */
    initializeTokenBucket(source, config) {
        const bucket = {
            capacity: config.burstLimit,
            tokens: config.burstLimit,
            refillRate: config.rateLimit / (config.windowSize / 1000), // tokens per second
            lastRefill: Date.now()
        };

        this.tokenBuckets.set(source, bucket);
        logger.debug('初始化令牌桶', { source, bucket });
    }

    /**
     * 初始化滑動窗口
     */
    initializeSlidingWindow(source, config) {
        const window = {
            requests: [],
            windowSize: config.windowSize,
            maxRequests: config.rateLimit
        };

        this.slidingWindows.set(source, window);
        logger.debug('初始化滑動窗口', { source, window });
    }

    /**
     * 檢查是否允許請求
     */
    async allowRequest(source, metadata = {}) {
        const config = this.rateLimits.get(source);
        if (!config) {
            logger.warn('未註冊的資料源', { source });
            return { allowed: true, waitTime: 0 };
        }

        const stats = this.statistics.get(source);

        // 檢查退避狀態
        const backoffCheck = this.checkBackoffState(source);
        if (!backoffCheck.allowed) {
            this.emit('requestDenied', {
                source,
                reason: 'backoff',
                waitTime: backoffCheck.waitTime
            });

            return backoffCheck;
        }

        // 令牌桶檢查
        if (this.options.enableTokenBucket) {
            const tokenCheck = this.checkTokenBucket(source);
            if (!tokenCheck.allowed) {
                stats.rateLimitedRequests++;

                this.emit('requestDenied', {
                    source,
                    reason: 'token_bucket',
                    waitTime: tokenCheck.waitTime
                });

                return tokenCheck;
            }
        }

        // 滑動窗口檢查
        if (this.options.enableSlidingWindow) {
            const windowCheck = this.checkSlidingWindow(source);
            if (!windowCheck.allowed) {
                stats.rateLimitedRequests++;

                this.emit('requestDenied', {
                    source,
                    reason: 'sliding_window',
                    waitTime: windowCheck.waitTime
                });

                return windowCheck;
            }
        }

        // 並發限制檢查
        const concurrencyCheck = this.checkConcurrency(source);
        if (!concurrencyCheck.allowed) {
            stats.rateLimitedRequests++;

            this.emit('requestDenied', {
                source,
                reason: 'concurrency_limit',
                waitTime: concurrencyCheck.waitTime
            });

            return concurrencyCheck;
        }

        // 記錄請求
        this.recordRequest(source, metadata);

        // 消費令牌
        if (this.options.enableTokenBucket) {
            this.consumeToken(source);
        }

        stats.totalRequests++;
        stats.lastRequestTime = Date.now();

        this.emit('requestAllowed', { source, metadata });

        return { allowed: true, waitTime: 0 };
    }

    /**
     * 檢查令牌桶
     */
    checkTokenBucket(source) {
        const bucket = this.tokenBuckets.get(source);
        if (!bucket) return { allowed: true, waitTime: 0 };

        // 重新填充令牌
        this.refillTokenBucket(source);

        if (bucket.tokens >= 1) {
            return { allowed: true, waitTime: 0 };
        } else {
            // 計算需要等待的時間
            const waitTime = Math.ceil(1000 / bucket.refillRate);
            return { allowed: false, waitTime };
        }
    }

    /**
     * 重新填充令牌桶
     */
    refillTokenBucket(source) {
        const bucket = this.tokenBuckets.get(source);
        if (!bucket) return;

        const now = Date.now();
        const timePassed = (now - bucket.lastRefill) / 1000;
        const tokensToAdd = Math.floor(timePassed * bucket.refillRate);

        if (tokensToAdd > 0) {
            bucket.tokens = Math.min(bucket.capacity, bucket.tokens + tokensToAdd);
            bucket.lastRefill = now;
        }
    }

    /**
     * 消費令牌
     */
    consumeToken(source) {
        const bucket = this.tokenBuckets.get(source);
        if (bucket && bucket.tokens >= 1) {
            bucket.tokens -= 1;
        }
    }

    /**
     * 檢查滑動窗口
     */
    checkSlidingWindow(source) {
        const window = this.slidingWindows.get(source);
        if (!window) return { allowed: true, waitTime: 0 };

        const now = Date.now();
        const windowStart = now - window.windowSize;

        // 清理過期請求
        window.requests = window.requests.filter(time => time > windowStart);

        if (window.requests.length < window.maxRequests) {
            return { allowed: true, waitTime: 0 };
        } else {
            // 計算最早的請求何時過期
            const earliestRequest = Math.min(...window.requests);
            const waitTime = Math.max(0, earliestRequest + window.windowSize - now);
            return { allowed: false, waitTime };
        }
    }

    /**
     * 檢查並發限制
     */
    checkConcurrency(source) {
        const config = this.rateLimits.get(source);
        const stats = this.statistics.get(source);

        if (!config.maxConcurrency) {
            return { allowed: true, waitTime: 0 };
        }

        const history = this.requestHistory.get(source) || [];
        const now = Date.now();

        // 計算當前並發請求數（假設平均響應時間為估算基準）
        const avgResponseTime = stats.averageResponseTime || 1000;
        const concurrentRequests = history.filter(
            req => (now - req.startTime) < avgResponseTime && !req.completed
        ).length;

        if (concurrentRequests < config.maxConcurrency) {
            return { allowed: true, waitTime: 0 };
        } else {
            return { allowed: false, waitTime: avgResponseTime / 2 };
        }
    }

    /**
     * 檢查退避狀態
     */
    checkBackoffState(source) {
        const backoff = this.backoffState.get(source);
        if (!backoff || !backoff.active) {
            return { allowed: true, waitTime: 0 };
        }

        const now = Date.now();
        if (now < backoff.endTime) {
            return {
                allowed: false,
                waitTime: backoff.endTime - now,
                reason: 'backoff'
            };
        } else {
            // 退避期結束，清理狀態
            backoff.active = false;
            return { allowed: true, waitTime: 0 };
        }
    }

    /**
     * 記錄請求
     */
    recordRequest(source, metadata) {
        // 記錄到滑動窗口
        if (this.options.enableSlidingWindow) {
            const window = this.slidingWindows.get(source);
            if (window) {
                window.requests.push(Date.now());
            }
        }

        // 記錄到請求歷史
        let history = this.requestHistory.get(source);
        if (!history) {
            history = [];
            this.requestHistory.set(source, history);
        }

        const requestRecord = {
            startTime: Date.now(),
            metadata,
            completed: false
        };

        history.push(requestRecord);

        // 限制歷史記錄數量
        if (history.length > 1000) {
            history.splice(0, history.length - 1000);
        }

        return requestRecord;
    }

    /**
     * 記錄請求完成
     */
    recordRequestCompletion(source, success = true, responseTime = 0, statusCode = 200) {
        const stats = this.statistics.get(source);
        if (!stats) return;

        const history = this.requestHistory.get(source) || [];
        const now = Date.now();

        // 找到最近的未完成請求
        const recentRequest = history
            .reverse()
            .find(req => !req.completed && (now - req.startTime) < 60000);

        if (recentRequest) {
            recentRequest.completed = true;
            recentRequest.success = success;
            recentRequest.responseTime = responseTime || (now - recentRequest.startTime);
            recentRequest.statusCode = statusCode;
        }

        // 更新統計
        if (success) {
            stats.successfulRequests++;
            stats.lastSuccessTime = now;
        }

        // 更新平均響應時間
        const actualResponseTime = responseTime || (recentRequest ? recentRequest.responseTime : 1000);
        stats.averageResponseTime = stats.averageResponseTime === 0
            ? actualResponseTime
            : (stats.averageResponseTime * 0.9 + actualResponseTime * 0.1);

        // 更新成功率
        stats.successRate = stats.totalRequests > 0
            ? stats.successfulRequests / stats.totalRequests
            : 1.0;

        // 檢查是否需要觸發退避
        this.checkAndTriggerBackoff(source, success, statusCode);

        // 自適應速率調整
        if (this.options.enableAdaptiveRateLimit) {
            this.adjustRateLimit(source);
        }

        this.emit('requestCompleted', {
            source,
            success,
            responseTime: actualResponseTime,
            statusCode
        });
    }

    /**
     * 檢查並觸發退避
     */
    checkAndTriggerBackoff(source, success, statusCode) {
        if (success && statusCode < 400) return;

        const stats = this.statistics.get(source);
        let backoff = this.backoffState.get(source);

        if (!backoff) {
            backoff = {
                level: 0,
                consecutiveFailures: 0,
                active: false
            };
            this.backoffState.set(source, backoff);
        }

        // 429 Too Many Requests 觸發立即退避
        if (statusCode === 429) {
            this.triggerBackoff(source, 'rate_limit_response');
            return;
        }

        // 5xx 錯誤累積觸發退避
        if (statusCode >= 500) {
            backoff.consecutiveFailures++;

            if (backoff.consecutiveFailures >= 3) {
                this.triggerBackoff(source, 'consecutive_failures');
            }
        } else if (success) {
            // 成功請求重置失敗計數
            backoff.consecutiveFailures = 0;
        }

        // 成功率過低觸發退避
        if (stats.successRate < 0.5 && stats.totalRequests > 10) {
            this.triggerBackoff(source, 'low_success_rate');
        }
    }

    /**
     * 觸發退避
     */
    triggerBackoff(source, reason) {
        const backoff = this.backoffState.get(source);
        const stats = this.statistics.get(source);

        backoff.level = Math.min(backoff.level + 1, 8); // 最大8級退避
        backoff.active = true;

        const backoffTime = Math.min(
            Math.pow(this.options.backoffMultiplier, backoff.level) * 1000,
            this.options.maxBackoffTime
        );

        backoff.endTime = Date.now() + backoffTime;
        stats.backoffEvents++;

        logger.warn('觸發退避機制', {
            source,
            reason,
            level: backoff.level,
            backoffTime,
            successRate: stats.successRate
        });

        this.emit('backoffTriggered', {
            source,
            reason,
            level: backoff.level,
            backoffTime,
            endTime: backoff.endTime
        });
    }

    /**
     * 自適應速率調整
     */
    adjustRateLimit(source) {
        const config = this.rateLimits.get(source);
        const stats = this.statistics.get(source);

        if (!config || !stats || stats.totalRequests < 20) return;

        const now = Date.now();
        const timeSinceLastSuccess = now - stats.lastSuccessTime;

        // 如果成功率高且響應時間正常，可以適度提高速率
        if (stats.successRate > this.options.recoveryThreshold &&
            timeSinceLastSuccess < 60000 &&
            stats.averageResponseTime < 3000) {

            const newRateLimit = Math.min(
                config.rateLimit * 1.1,
                this.options.defaultRateLimit * 2
            );

            if (newRateLimit > stats.currentRateLimit) {
                stats.currentRateLimit = newRateLimit;

                // 更新令牌桶配置
                const bucket = this.tokenBuckets.get(source);
                if (bucket) {
                    bucket.refillRate = newRateLimit / (config.windowSize / 1000);
                }

                logger.debug('提高速率限制', { source, newRateLimit });
            }
        }
        // 如果成功率低，降低速率
        else if (stats.successRate < 0.7) {
            const newRateLimit = Math.max(
                stats.currentRateLimit * 0.8,
                config.rateLimit * 0.3
            );

            if (newRateLimit < stats.currentRateLimit) {
                stats.currentRateLimit = newRateLimit;

                // 更新令牌桶配置
                const bucket = this.tokenBuckets.get(source);
                if (bucket) {
                    bucket.refillRate = newRateLimit / (config.windowSize / 1000);
                }

                logger.debug('降低速率限制', { source, newRateLimit });
            }
        }
    }

    /**
     * 啟動監控
     */
    startMonitoring() {
        this.monitoringInterval = setInterval(() => {
            this.performMonitoring();
        }, this.options.monitoringInterval);

        logger.info('速率限制監控已啟動');
    }

    /**
     * 執行監控
     */
    performMonitoring() {
        for (const [source, stats] of this.statistics.entries()) {
            const config = this.rateLimits.get(source);
            if (!config) continue;

            // 記錄統計資料
            logger.debug('速率限制統計', {
                source,
                totalRequests: stats.totalRequests,
                successRate: Math.round(stats.successRate * 100),
                avgResponseTime: Math.round(stats.averageResponseTime),
                currentRateLimit: Math.round(stats.currentRateLimit),
                rateLimitedRequests: stats.rateLimitedRequests
            });

            // 檢查長時間無活動的資料源
            const timeSinceLastRequest = Date.now() - stats.lastRequestTime;
            if (timeSinceLastRequest > 300000) { // 5分鐘無活動
                // 重置退避狀態
                const backoff = this.backoffState.get(source);
                if (backoff && backoff.active) {
                    backoff.active = false;
                    backoff.level = Math.max(0, backoff.level - 1);
                }

                // 逐漸恢復速率限制
                if (stats.currentRateLimit < config.rateLimit) {
                    stats.currentRateLimit = Math.min(
                        stats.currentRateLimit * 1.05,
                        config.rateLimit
                    );
                }
            }
        }

        this.emit('monitoringUpdate', {
            sources: Array.from(this.statistics.keys()),
            timestamp: Date.now()
        });
    }

    /**
     * 停止監控
     */
    stopMonitoring() {
        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }

        logger.info('速率限制監控已停止');
    }

    /**
     * 獲取統計資料
     */
    getStatistics(source = null) {
        if (source) {
            return this.statistics.get(source);
        }

        const allStats = {};
        for (const [src, stats] of this.statistics.entries()) {
            allStats[src] = { ...stats };
        }

        return allStats;
    }

    /**
     * 重設統計資料
     */
    resetStatistics(source = null) {
        if (source) {
            const stats = this.statistics.get(source);
            if (stats) {
                Object.assign(stats, {
                    totalRequests: 0,
                    successfulRequests: 0,
                    rateLimitedRequests: 0,
                    backoffEvents: 0,
                    averageResponseTime: 0,
                    successRate: 1.0
                });
            }
        } else {
            for (const [src, stats] of this.statistics.entries()) {
                Object.assign(stats, {
                    totalRequests: 0,
                    successfulRequests: 0,
                    rateLimitedRequests: 0,
                    backoffEvents: 0,
                    averageResponseTime: 0,
                    successRate: 1.0
                });
            }
        }

        logger.info('速率限制統計資料已重設', { source });
    }

    /**
     * 手動觸發恢復
     */
    triggerRecovery(source) {
        const backoff = this.backoffState.get(source);
        if (backoff) {
            backoff.active = false;
            backoff.level = Math.max(0, backoff.level - 2);
            backoff.consecutiveFailures = 0;
        }

        const stats = this.statistics.get(source);
        if (stats) {
            stats.successRate = Math.min(1.0, stats.successRate + 0.1);
        }

        logger.info('手動觸發恢復', { source });

        this.emit('recoveryTriggered', { source });
    }
}

module.exports = RateLimitManager;