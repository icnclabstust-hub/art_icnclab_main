/**
 * 統一日誌管理模組
 * 提供結構化日誌記錄功能
 */

const winston = require('winston');
const path = require('path');

// 自定義日誌格式
const logFormat = winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    winston.format.json(),
    winston.format.printf(({ timestamp, level, message, stack, ...meta }) => {
        let logMessage = `${timestamp} [${level.toUpperCase()}]`;

        if (meta.module) {
            logMessage += ` [${meta.module}]`;
        }

        logMessage += `: ${message}`;

        if (stack) {
            logMessage += `\nStack: ${stack}`;
        }

        if (Object.keys(meta).length > 0 && !meta.module) {
            logMessage += `\nMeta: ${JSON.stringify(meta, null, 2)}`;
        }

        return logMessage;
    })
);

// 控制台格式（開發環境用）
const consoleFormat = winston.format.combine(
    winston.format.colorize(),
    winston.format.timestamp({ format: 'HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message, module }) => {
        const moduleStr = module ? `[${module}] ` : '';
        return `${timestamp} ${level}: ${moduleStr}${message}`;
    })
);

// 創建日誌目錄
const logDir = path.join(process.cwd(), 'logs');
require('fs').mkdirSync(logDir, { recursive: true });

// 創建Winston日誌器
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: logFormat,
    defaultMeta: { service: 'art-history-database' },
    transports: [
        // 錯誤日誌文件
        new winston.transports.File({
            filename: path.join(logDir, 'error.log'),
            level: 'error',
            maxsize: 50 * 1024 * 1024, // 50MB
            maxFiles: 5,
            tailable: true
        }),

        // 組合日誌文件
        new winston.transports.File({
            filename: path.join(logDir, 'combined.log'),
            maxsize: 100 * 1024 * 1024, // 100MB
            maxFiles: 10,
            tailable: true
        }),

        // Agent系統日誌
        new winston.transports.File({
            filename: path.join(logDir, 'agents.log'),
            level: 'info',
            maxsize: 50 * 1024 * 1024,
            maxFiles: 5,
            format: winston.format.combine(
                winston.format.label({ label: 'AGENT' }),
                logFormat
            ),
            // 只記錄包含agent相關的日誌
            filter: (info) => {
                return info.module && info.module.toLowerCase().includes('agent');
            }
        }),

        // 資料庫操作日誌
        new winston.transports.File({
            filename: path.join(logDir, 'database.log'),
            level: 'debug',
            maxsize: 30 * 1024 * 1024,
            maxFiles: 3,
            format: winston.format.combine(
                winston.format.label({ label: 'DB' }),
                logFormat
            ),
            filter: (info) => {
                return info.module && info.module.toLowerCase().includes('database');
            }
        })
    ],

    // 異常和拒絕處理
    exceptionHandlers: [
        new winston.transports.File({
            filename: path.join(logDir, 'exceptions.log'),
            maxsize: 20 * 1024 * 1024,
            maxFiles: 2
        })
    ],

    rejectionHandlers: [
        new winston.transports.File({
            filename: path.join(logDir, 'rejections.log'),
            maxsize: 20 * 1024 * 1024,
            maxFiles: 2
        })
    ]
});

// 開發環境添加控制台輸出
if (process.env.NODE_ENV !== 'production') {
    logger.add(new winston.transports.Console({
        format: consoleFormat,
        level: process.env.LOG_LEVEL || 'debug'
    }));
}

// 創建專用的日誌器工廠
class LoggerFactory {
    static createLogger(module) {
        return {
            debug: (message, meta = {}) => logger.debug(message, { module, ...meta }),
            info: (message, meta = {}) => logger.info(message, { module, ...meta }),
            warn: (message, meta = {}) => logger.warn(message, { module, ...meta }),
            error: (message, error = null, meta = {}) => {
                if (error instanceof Error) {
                    logger.error(message, { module, error: error.message, stack: error.stack, ...meta });
                } else {
                    logger.error(message, { module, error, ...meta });
                }
            }
        };
    }
}

// 性能測量裝飾器
class PerformanceLogger {
    static measureAsync(target, propertyName, descriptor) {
        const originalMethod = descriptor.value;

        descriptor.value = async function (...args) {
            const startTime = process.hrtime.bigint();
            const logger = LoggerFactory.createLogger('PERFORMANCE');

            try {
                const result = await originalMethod.apply(this, args);
                const endTime = process.hrtime.bigint();
                const duration = Number(endTime - startTime) / 1000000; // 轉換為毫秒

                logger.info(`${propertyName} completed`, {
                    duration_ms: duration.toFixed(2),
                    success: true
                });

                return result;
            } catch (error) {
                const endTime = process.hrtime.bigint();
                const duration = Number(endTime - startTime) / 1000000;

                logger.error(`${propertyName} failed`, error, {
                    duration_ms: duration.toFixed(2),
                    success: false
                });

                throw error;
            }
        };

        return descriptor;
    }

    static measureSync(target, propertyName, descriptor) {
        const originalMethod = descriptor.value;

        descriptor.value = function (...args) {
            const startTime = process.hrtime.bigint();
            const logger = LoggerFactory.createLogger('PERFORMANCE');

            try {
                const result = originalMethod.apply(this, args);
                const endTime = process.hrtime.bigint();
                const duration = Number(endTime - startTime) / 1000000;

                logger.info(`${propertyName} completed`, {
                    duration_ms: duration.toFixed(2),
                    success: true
                });

                return result;
            } catch (error) {
                const endTime = process.hrtime.bigint();
                const duration = Number(endTime - startTime) / 1000000;

                logger.error(`${propertyName} failed`, error, {
                    duration_ms: duration.toFixed(2),
                    success: false
                });

                throw error;
            }
        };

        return descriptor;
    }
}

// HTTP請求日誌中間件
const httpLoggerMiddleware = (req, res, next) => {
    const httpLogger = LoggerFactory.createLogger('HTTP');
    const startTime = Date.now();

    // 記錄請求開始
    httpLogger.info('Request started', {
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        userAgent: req.get('User-Agent')
    });

    // 監聽響應結束
    res.on('finish', () => {
        const duration = Date.now() - startTime;
        const logLevel = res.statusCode >= 400 ? 'error' : 'info';

        httpLogger[logLevel]('Request completed', {
            method: req.method,
            url: req.originalUrl,
            statusCode: res.statusCode,
            duration_ms: duration,
            ip: req.ip
        });
    });

    next();
};

// 錯誤處理中間件
const errorLoggerMiddleware = (error, req, res, next) => {
    const errorLogger = LoggerFactory.createLogger('ERROR');

    errorLogger.error('Unhandled request error', error, {
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        body: req.body,
        params: req.params,
        query: req.query
    });

    next(error);
};

// Agent系統專用日誌器
const agentLogger = LoggerFactory.createLogger('AGENT_SYSTEM');

// 資料庫專用日誌器
const dbLogger = LoggerFactory.createLogger('DATABASE');

// 優雅關閉處理
const gracefulShutdown = () => {
    logger.info('Shutting down logger...');

    logger.end(() => {
        console.log('Logger shutdown complete');
        process.exit(0);
    });
};

process.on('SIGINT', gracefulShutdown);
process.on('SIGTERM', gracefulShutdown);

module.exports = {
    logger,
    LoggerFactory,
    PerformanceLogger,
    httpLoggerMiddleware,
    errorLoggerMiddleware,
    agentLogger,
    dbLogger
};