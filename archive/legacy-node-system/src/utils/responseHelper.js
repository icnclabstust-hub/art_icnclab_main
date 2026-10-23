/**
 * API響應幫助函數
 * 統一API響應格式
 */

/**
 * 成功響應格式
 * @param {Object} res - Express響應對象
 * @param {any} data - 響應資料
 * @param {Object} meta - 元資料 (分頁信息等)
 * @param {number} statusCode - HTTP狀態碼
 */
const successResponse = (res, data, meta = null, statusCode = 200) => {
    const response = {
        success: true,
        timestamp: new Date().toISOString(),
        data: data
    };

    if (meta) {
        response.meta = meta;
    }

    return res.status(statusCode).json(response);
};

/**
 * 錯誤響應格式
 * @param {Object} res - Express響應對象
 * @param {string} message - 錯誤消息
 * @param {any} details - 錯誤詳情
 * @param {number} statusCode - HTTP狀態碼
 */
const errorResponse = (res, message, details = null, statusCode = 500) => {
    const response = {
        success: false,
        timestamp: new Date().toISOString(),
        error: {
            message: message,
            code: statusCode
        }
    };

    if (details) {
        response.error.details = details;
    }

    // 在開發環境中添加堆疊跟蹤
    if (process.env.NODE_ENV === 'development' && details instanceof Error) {
        response.error.stack = details.stack;
    }

    return res.status(statusCode).json(response);
};

/**
 * 分頁響應格式
 * @param {Object} res - Express響應對象
 * @param {Array} data - 響應資料
 * @param {number} page - 當前頁面
 * @param {number} limit - 每頁項目數
 * @param {number} total - 總項目數
 * @param {number} statusCode - HTTP狀態碼
 */
const paginatedResponse = (res, data, page, limit, total, statusCode = 200) => {
    const totalPages = Math.ceil(total / limit);
    const hasNext = page < totalPages;
    const hasPrev = page > 1;

    return successResponse(res, data, {
        pagination: {
            current_page: page,
            per_page: limit,
            total_items: total,
            total_pages: totalPages,
            has_next: hasNext,
            has_previous: hasPrev,
            next_page: hasNext ? page + 1 : null,
            previous_page: hasPrev ? page - 1 : null
        }
    }, statusCode);
};

/**
 * 搜索響應格式
 * @param {Object} res - Express響應對象
 * @param {Array} data - 搜索結果
 * @param {string} query - 搜索查詢
 * @param {number} total - 結果總數
 * @param {number} responseTime - 響應時間（毫秒）
 * @param {Object} filters - 應用的過濾器
 * @param {number} statusCode - HTTP狀態碼
 */
const searchResponse = (res, data, query, total, responseTime = null, filters = null, statusCode = 200) => {
    const meta = {
        search: {
            query: query,
            total_results: total,
            result_count: data.length
        }
    };

    if (responseTime !== null) {
        meta.search.response_time_ms = responseTime;
    }

    if (filters) {
        meta.search.filters = filters;
    }

    return successResponse(res, data, meta, statusCode);
};

/**
 * 批量操作響應格式
 * @param {Object} res - Express響應對象
 * @param {number} total - 總項目數
 * @param {number} successful - 成功項目數
 * @param {number} failed - 失敗項目數
 * @param {Array} errors - 錯誤詳情
 * @param {Array} results - 成功結果
 * @param {number} statusCode - HTTP狀態碼
 */
const bulkOperationResponse = (res, total, successful, failed, errors = [], results = [], statusCode = 200) => {
    return successResponse(res, {
        results: results,
        errors: errors
    }, {
        bulk_operation: {
            total_items: total,
            successful: successful,
            failed: failed,
            success_rate: total > 0 ? (successful / total * 100).toFixed(2) + '%' : '0%'
        }
    }, statusCode);
};

/**
 * 統計響應格式
 * @param {Object} res - Express響應對象
 * @param {Object} statistics - 統計資料
 * @param {string} period - 統計期間
 * @param {Date} generatedAt - 生成時間
 * @param {number} statusCode - HTTP狀態碼
 */
const statisticsResponse = (res, statistics, period = null, generatedAt = new Date(), statusCode = 200) => {
    return successResponse(res, statistics, {
        statistics: {
            period: period,
            generated_at: generatedAt.toISOString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        }
    }, statusCode);
};

/**
 * 狀態檢查響應格式
 * @param {Object} res - Express響應對象
 * @param {Object} status - 系統狀態
 * @param {string} version - 系統版本
 * @param {Date} uptime - 運行時間
 * @param {number} statusCode - HTTP狀態碼
 */
const healthCheckResponse = (res, status, version = '1.0.0', uptime = null, statusCode = 200) => {
    return successResponse(res, {
        status: status,
        version: version,
        uptime: uptime,
        environment: process.env.NODE_ENV || 'development'
    }, {
        health_check: {
            timestamp: new Date().toISOString(),
            server_time: new Date().toLocaleString()
        }
    }, statusCode);
};

/**
 * 驗證錯誤響應格式
 * @param {Object} res - Express響應對象
 * @param {Array} validationErrors - 驗證錯誤陣列
 * @param {string} message - 主要錯誤消息
 */
const validationErrorResponse = (res, validationErrors, message = '資料驗證失敗') => {
    const formattedErrors = validationErrors.map(error => ({
        field: error.path ? error.path.join('.') : 'unknown',
        message: error.message,
        value: error.context?.value,
        type: error.type
    }));

    return errorResponse(res, message, {
        validation_errors: formattedErrors,
        error_count: formattedErrors.length
    }, 400);
};

/**
 * 未授權響應
 * @param {Object} res - Express響應對象
 * @param {string} message - 錯誤消息
 */
const unauthorizedResponse = (res, message = '未授權訪問') => {
    return errorResponse(res, message, {
        auth_required: true,
        suggestion: '請檢查您的認證令牌'
    }, 401);
};

/**
 * 禁止訪問響應
 * @param {Object} res - Express響應對象
 * @param {string} message - 錯誤消息
 */
const forbiddenResponse = (res, message = '禁止訪問') => {
    return errorResponse(res, message, {
        access_denied: true,
        suggestion: '您沒有執行此操作的權限'
    }, 403);
};

/**
 * 資源未找到響應
 * @param {Object} res - Express響應對象
 * @param {string} resource - 資源類型
 * @param {string} identifier - 資源標識符
 */
const notFoundResponse = (res, resource = 'Resource', identifier = null) => {
    const message = identifier
        ? `${resource} with identifier '${identifier}' not found`
        : `${resource} not found`;

    return errorResponse(res, message, {
        resource_type: resource,
        identifier: identifier
    }, 404);
};

/**
 * 衝突響應
 * @param {Object} res - Express響應對象
 * @param {string} message - 錯誤消息
 * @param {string} conflictField - 衝突字段
 */
const conflictResponse = (res, message = '資源衝突', conflictField = null) => {
    return errorResponse(res, message, {
        conflict_type: 'resource_conflict',
        field: conflictField
    }, 409);
};

/**
 * 請求過於頻繁響應
 * @param {Object} res - Express響應對象
 * @param {number} retryAfter - 重試等待時間（秒）
 */
const rateLimitResponse = (res, retryAfter = 60) => {
    res.set('Retry-After', retryAfter);
    return errorResponse(res, '請求過於頻繁', {
        retry_after_seconds: retryAfter,
        suggestion: `請在 ${retryAfter} 秒後重試`
    }, 429);
};

/**
 * 服務器錯誤響應
 * @param {Object} res - Express響應對象
 * @param {Error} error - 錯誤對象
 * @param {string} message - 自定義錯誤消息
 */
const serverErrorResponse = (res, error, message = '內部服務器錯誤') => {
    // 記錄錯誤（實際項目中應該使用專業的日誌系統）
    console.error('Server Error:', error);

    const errorDetails = process.env.NODE_ENV === 'development'
        ? {
            error_message: error.message,
            stack_trace: error.stack
        }
        : {
            error_id: Date.now().toString(36), // 簡單的錯誤ID
            suggestion: '請聯繫系統管理員'
        };

    return errorResponse(res, message, errorDetails, 500);
};

module.exports = {
    successResponse,
    errorResponse,
    paginatedResponse,
    searchResponse,
    bulkOperationResponse,
    statisticsResponse,
    healthCheckResponse,
    validationErrorResponse,
    unauthorizedResponse,
    forbiddenResponse,
    notFoundResponse,
    conflictResponse,
    rateLimitResponse,
    serverErrorResponse
};