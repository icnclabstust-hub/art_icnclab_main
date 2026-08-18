/**
 * 統一驗證中間件
 * 集成資料驗證和清理功能
 */

const { ArtDataCleaner, DataQualityChecker } = require('../../utils/dataCleaner');
const { validateArtwork } = require('../validators/artworkValidator');
const { validateArtist } = require('../validators/artistValidator');
const { logger } = require('../../utils/logger');

/**
 * 創建驗證和清理中間件
 * @param {string} dataType - 資料類型 ('artwork', 'artist', 'collection')
 * @param {boolean} isUpdate - 是否為更新操作
 * @param {Object} options - 額外選項
 * @returns {Function} - Express中間件函數
 */
const createValidationMiddleware = (dataType, isUpdate = false, options = {}) => {
    const {
        enableCleaning = true,
        enableQualityCheck = true,
        requiredFields = [],
        skipValidation = false
    } = options;

    return async (req, res, next) => {
        try {
            const startTime = Date.now();

            // 記錄原始資料
            logger.debug('開始資料驗證和清理', {
                dataType,
                isUpdate,
                originalData: req.body,
                enableCleaning,
                enableQualityCheck
            });

            let processedData = { ...req.body };

            // 1. 資料清理階段
            if (enableCleaning) {
                try {
                    switch (dataType) {
                        case 'artwork':
                            processedData = ArtDataCleaner.cleanArtworkData(processedData);
                            break;
                        case 'artist':
                            processedData = ArtDataCleaner.cleanArtistData(processedData);
                            break;
                        default:
                            logger.warn('未知的資料類型，跳過專用清理', { dataType });
                    }

                    logger.debug('資料清理完成', {
                        dataType,
                        originalFields: Object.keys(req.body).length,
                        cleanedFields: Object.keys(processedData).length
                    });
                } catch (cleaningError) {
                    logger.error('資料清理失敗', {
                        dataType,
                        error: cleaningError.message
                    });

                    return res.status(400).json({
                        success: false,
                        message: '資料清理失敗',
                        error: cleaningError.message,
                        stage: 'cleaning'
                    });
                }
            }

            // 2. 資料驗證階段
            if (!skipValidation) {
                let validationResult;

                try {
                    switch (dataType) {
                        case 'artwork':
                            validationResult = validateArtwork(processedData, isUpdate);
                            break;
                        case 'artist':
                            validationResult = validateArtist(processedData, isUpdate);
                            break;
                        default:
                            logger.warn('未知的資料類型，跳過專用驗證', { dataType });
                            validationResult = { error: null, value: processedData };
                    }

                    if (validationResult.error) {
                        logger.warn('資料驗證失敗', {
                            dataType,
                            errors: validationResult.error.details
                        });

                        return res.status(400).json({
                            success: false,
                            message: '資料驗證失敗',
                            errors: validationResult.error.details.map(detail => ({
                                field: detail.path.join('.'),
                                message: detail.message,
                                value: detail.context?.value
                            })),
                            stage: 'validation'
                        });
                    }

                    processedData = validationResult.value;

                } catch (validationError) {
                    logger.error('資料驗證過程出錯', {
                        dataType,
                        error: validationError.message
                    });

                    return res.status(500).json({
                        success: false,
                        message: '資料驗證過程出錯',
                        error: validationError.message,
                        stage: 'validation'
                    });
                }
            }

            // 3. 資料品質檢查階段
            if (enableQualityCheck) {
                try {
                    const completenessCheck = DataQualityChecker.checkCompleteness(
                        processedData,
                        requiredFields
                    );

                    const consistencyCheck = DataQualityChecker.checkConsistency(processedData);

                    // 記錄品質檢查結果
                    logger.debug('資料品質檢查完成', {
                        dataType,
                        completeness: completenessCheck,
                        consistency: consistencyCheck
                    });

                    // 如果有嚴重的一致性問題，阻止請求
                    if (!consistencyCheck.isConsistent && consistencyCheck.issues.length > 0) {
                        const criticalIssues = consistencyCheck.issues.filter(issue =>
                            issue.includes('早於') || issue.includes('無效')
                        );

                        if (criticalIssues.length > 0) {
                            return res.status(400).json({
                                success: false,
                                message: '資料一致性檢查失敗',
                                issues: criticalIssues,
                                stage: 'quality_check'
                            });
                        }
                    }

                    // 將品質檢查結果添加到請求中
                    req.qualityCheck = {
                        completeness: completenessCheck,
                        consistency: consistencyCheck
                    };

                } catch (qualityCheckError) {
                    logger.error('資料品質檢查失敗', {
                        dataType,
                        error: qualityCheckError.message
                    });

                    // 品質檢查失敗不阻止請求，但記錄警告
                    req.qualityCheck = null;
                }
            }

            // 4. 處理完成
            const processingTime = Date.now() - startTime;

            logger.info('資料驗證和清理成功', {
                dataType,
                isUpdate,
                processingTime,
                fieldsProcessed: Object.keys(processedData).length,
                qualityScore: req.qualityCheck?.completeness?.score
            });

            // 將處理後的資料設置回請求體
            req.body = processedData;
            req.validationMetadata = {
                dataType,
                isUpdate,
                processingTime,
                cleaningEnabled: enableCleaning,
                validationEnabled: !skipValidation,
                qualityCheckEnabled: enableQualityCheck
            };

            next();

        } catch (error) {
            logger.error('驗證中間件執行失敗', {
                dataType,
                error: error.message,
                stack: error.stack
            });

            return res.status(500).json({
                success: false,
                message: '資料處理過程中發生錯誤',
                error: error.message,
                stage: 'middleware'
            });
        }
    };
};

/**
 * 批量驗證中間件
 * @param {string} dataType - 資料類型
 * @param {Object} options - 選項
 * @returns {Function} - Express中間件函數
 */
const createBulkValidationMiddleware = (dataType, options = {}) => {
    const {
        maxBatchSize = 100,
        enableCleaning = true,
        enableQualityCheck = true
    } = options;

    return async (req, res, next) => {
        try {
            const dataArray = req.body[`${dataType}s`] || req.body.data;

            if (!Array.isArray(dataArray)) {
                return res.status(400).json({
                    success: false,
                    message: `${dataType}資料必須是數組格式`,
                    stage: 'batch_validation'
                });
            }

            if (dataArray.length > maxBatchSize) {
                return res.status(400).json({
                    success: false,
                    message: `批量操作超過最大限制 ${maxBatchSize}`,
                    stage: 'batch_validation'
                });
            }

            // 批量清理和驗證
            if (enableCleaning) {
                const cleaningResult = ArtDataCleaner.bulkCleanData(dataArray, dataType);

                if (cleaningResult.errors.length > 0) {
                    logger.warn('批量資料清理有錯誤', {
                        dataType,
                        totalErrors: cleaningResult.errors.length,
                        errors: cleaningResult.errors
                    });
                }

                req.body.cleanedData = cleaningResult.success;
                req.body.cleaningErrors = cleaningResult.errors;
            }

            // 記錄批量處理統計
            logger.info('批量資料驗證完成', {
                dataType,
                total: dataArray.length,
                successful: req.body.cleanedData?.length || dataArray.length,
                errors: req.body.cleaningErrors?.length || 0
            });

            next();

        } catch (error) {
            logger.error('批量驗證中間件執行失敗', {
                dataType,
                error: error.message
            });

            return res.status(500).json({
                success: false,
                message: '批量資料處理過程中發生錯誤',
                error: error.message,
                stage: 'bulk_middleware'
            });
        }
    };
};

/**
 * 預定義中間件
 */
const artworkValidationMiddleware = (isUpdate = false) =>
    createValidationMiddleware('artwork', isUpdate, {
        requiredFields: ['title']
    });

const artistValidationMiddleware = (isUpdate = false) =>
    createValidationMiddleware('artist', isUpdate, {
        requiredFields: ['name']
    });

const bulkArtworkValidationMiddleware = () =>
    createBulkValidationMiddleware('artwork');

const bulkArtistValidationMiddleware = () =>
    createBulkValidationMiddleware('artist');

module.exports = {
    createValidationMiddleware,
    createBulkValidationMiddleware,
    artworkValidationMiddleware,
    artistValidationMiddleware,
    bulkArtworkValidationMiddleware,
    bulkArtistValidationMiddleware
};