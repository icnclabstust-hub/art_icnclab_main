/**
 * 速率限制中間件
 * 防止API濫用和提供基礎保護
 */

const { dbManager } = require('../../database/connection');
const { rateLimitResponse } = require('../../utils/responseHelper');

class RateLimiter {
    constructor() {
        this.redisClient = null;
        this.windowMs = 15 * 60 * 1000; // 15分鐘
        this.maxRequests = 100; // 每個窗口的最大請求數
        this.keyPrefix = 'rate_limit:';
        this.useMemoryLimiter = false;
        this.memoryStore = new Map();
    }

    // 初始化Redis連接 - 添加超時和錯誤處理
    async init() {
        try {
            // 添加超時處理，避免無限等待
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Redis初始化超時')), 5000);
            });

            const initPromise = Promise.resolve().then(() => {
                this.redisClient = dbManager.getRedisClient();
                return this.redisClient;
            });

            await Promise.race([initPromise, timeoutPromise]);
            console.log('✅ 速率限制器初始化完成');
        } catch (error) {
            console.warn('⚠️ Redis未連接，使用內存速率限制:', error.message);
            this.useMemoryLimiter = true;
            this.memoryStore = new Map();
        }
    }

    // 檢查速率限制
    async checkRateLimit(identifier, customLimit = null, customWindow = null) {
        const limit = customLimit || this.maxRequests;
        const window = customWindow || this.windowMs;
        const key = `${this.keyPrefix}${identifier}`;

        if (this.redisClient && !this.useMemoryLimiter) {
            return await this.checkRedisRateLimit(key, limit, window);
        } else {
            return await this.checkMemoryRateLimit(identifier, limit, window);
        }
    }

    // Redis速率限制檢查
    async checkRedisRateLimit(key, limit, window) {
        try {
            const now = Date.now();
            const windowStart = now - window;

            // 使用滑動窗口計數器
            const pipeline = this.redisClient.multi();

            // 移除過期的記錄
            pipeline.zRemRangeByScore(key, '-inf', windowStart);

            // 添加當前請求 - 修復參數格式
            pipeline.zAdd(key, {
                score: now,
                value: `${now}-${Math.random()}`
            });

            // 獲取當前窗口內的請求數
            pipeline.zCard(key);

            // 設置過期時間
            pipeline.expire(key, Math.ceil(window / 1000));

            const results = await pipeline.exec();
            const currentCount = parseInt(results[2][1]) || 0; // zCard的結果，確保是數字

            if (currentCount > limit) {
                const ttl = await this.redisClient.ttl(key);
                return {
                    allowed: false,
                    currentCount,
                    limit,
                    resetTime: now + (ttl * 1000),
                    retryAfter: Math.ceil(ttl)
                };
            }

            return {
                allowed: true,
                currentCount,
                limit,
                resetTime: now + window,
                retryAfter: 0
            };

        } catch (error) {
            console.error('Redis速率限制檢查失敗:', error);
            // 發生錯誤時允許請求通過
            return {
                allowed: true,
                currentCount: 0,
                limit,
                resetTime: Date.now() + window,
                retryAfter: 0
            };
        }
    }

    // 內存速率限制檢查
    async checkMemoryRateLimit(identifier, limit, window) {
        const now = Date.now();
        const windowStart = now - window;

        // 確保memoryStore已初始化
        if (!this.memoryStore) {
            this.memoryStore = new Map();
        }

        if (!this.memoryStore.has(identifier)) {
            this.memoryStore.set(identifier, []);
        }

        const requests = this.memoryStore.get(identifier);

        // 移除過期的請求
        const validRequests = requests.filter(timestamp => timestamp > windowStart);

        // 添加當前請求
        validRequests.push(now);

        // 更新存儲
        this.memoryStore.set(identifier, validRequests);

        if (validRequests.length > limit) {
            return {
                allowed: false,
                currentCount: validRequests.length,
                limit,
                resetTime: validRequests[0] + window,
                retryAfter: Math.ceil((validRequests[0] + window - now) / 1000)
            };
        }

        return {
            allowed: true,
            currentCount: validRequests.length,
            limit,
            resetTime: now + window,
            retryAfter: 0
        };
    }

    // 清理過期記錄（內存模式）
    cleanupMemoryStore() {
        if (!this.useMemoryLimiter) return;

        const now = Date.now();
        for (const [identifier, requests] of this.memoryStore.entries()) {
            const validRequests = requests.filter(
                timestamp => timestamp > now - this.windowMs
            );

            if (validRequests.length === 0) {
                this.memoryStore.delete(identifier);
            } else {
                this.memoryStore.set(identifier, validRequests);
            }
        }
    }
}

// 創建速率限制器實例
const rateLimiter = new RateLimiter();

// 基本速率限制中間件 - 添加超時處理
const rateLimitMiddleware = (customLimit = null, customWindow = null) => {
    return async (req, res, next) => {
        try {
            // 如果速率限制器未初始化，嘗試初始化（帶超時）
            if (!rateLimiter.redisClient && !rateLimiter.useMemoryLimiter) {
                const initTimeout = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('初始化超時')), 3000);
                });

                try {
                    await Promise.race([rateLimiter.init(), initTimeout]);
                } catch (initError) {
                    console.warn('速率限制器初始化失敗，放行請求:', initError.message);
                    return next();
                }
            }

            // 生成標識符（基於IP和用戶ID）
            const identifier = req.ip + ':' + (req.user?.id || 'anonymous');

            const result = await rateLimiter.checkRateLimit(identifier, customLimit, customWindow);

            // 添加速率限制頭部
            res.set({
                'X-RateLimit-Limit': result.limit,
                'X-RateLimit-Remaining': Math.max(0, result.limit - result.currentCount),
                'X-RateLimit-Reset': new Date(result.resetTime).toISOString()
            });

            if (!result.allowed) {
                return rateLimitResponse(res, result.retryAfter);
            }

            next();
        } catch (error) {
            console.error('速率限制中間件錯誤:', error);
            // 出錯時放行請求
            next();
        }
    };
};

// 嚴格速率限制（用於敏感操作）
const strictRateLimitMiddleware = (req, res, next) => {
    return rateLimitMiddleware(20, 15 * 60 * 1000)(req, res, next); // 15分鐘20次
};

// 寬鬆速率限制（用於讀操作）
const relaxedRateLimitMiddleware = (req, res, next) => {
    return rateLimitMiddleware(200, 15 * 60 * 1000)(req, res, next); // 15分鐘200次
};

// 搜索專用速率限制
const searchRateLimitMiddleware = (req, res, next) => {
    return rateLimitMiddleware(50, 5 * 60 * 1000)(req, res, next); // 5分鐘50次
};

// 按IP的全局速率限制 - 添加超時處理
const globalRateLimitMiddleware = async (req, res, next) => {
    try {
        // 如果速率限制器未初始化，嘗試初始化（帶超時）
        if (!rateLimiter.redisClient && !rateLimiter.useMemoryLimiter) {
            const initTimeout = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('全局速率限制器初始化超時')), 3000);
            });

            try {
                await Promise.race([rateLimiter.init(), initTimeout]);
            } catch (initError) {
                console.warn('全局速率限制器初始化失敗，放行請求:', initError.message);
                return next();
            }
        }

        const identifier = `global:${req.ip}`;
        const result = await rateLimiter.checkRateLimit(identifier, 1000, 60 * 60 * 1000); // 1小時1000次

        res.set({
            'X-Global-RateLimit-Limit': result.limit,
            'X-Global-RateLimit-Remaining': Math.max(0, result.limit - result.currentCount)
        });

        if (!result.allowed) {
            return rateLimitResponse(res, result.retryAfter);
        }

        next();
    } catch (error) {
        console.error('全局速率限制錯誤:', error);
        next();
    }
};

// 清理任務（如果使用內存模式）- 延遲初始化以避免啟動時問題
setTimeout(() => {
    if (rateLimiter.useMemoryLimiter) {
        setInterval(() => {
            try {
                rateLimiter.cleanupMemoryStore();
            } catch (error) {
                console.warn('清理內存存儲失敗:', error);
            }
        }, 5 * 60 * 1000); // 每5分鐘清理一次
    }
}, 10000); // 延遲10秒啟動清理任務

module.exports = {
    RateLimiter,
    rateLimiter,
    rateLimitMiddleware,
    strictRateLimitMiddleware,
    relaxedRateLimitMiddleware,
    searchRateLimitMiddleware,
    globalRateLimitMiddleware
};