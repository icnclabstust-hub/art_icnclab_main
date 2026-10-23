/**
 * 重複資料檢測API路由
 * 提供重複檢測、管理和分析功能
 */

const express = require('express');
const { logger } = require('../../utils/logger');
const DuplicateDetector = require('../../utils/duplicateDetection');
const { Artist, Artwork } = require('../../database/models');

const router = express.Router();

// 初始化重複檢測器
const duplicateDetector = new DuplicateDetector({
    similarityThresholds: {
        exact: 1.0,
        high: 0.95,
        medium: 0.85,
        low: 0.75
    },
    fieldWeights: {
        title: 0.35,
        artist_name: 0.25,
        creation_year: 0.15,
        medium: 0.1,
        dimensions: 0.1,
        location: 0.05
    }
});

/**
 * POST /detect/artworks - 檢測藝術作品重複
 */
router.post('/detect/artworks', async (req, res) => {
    try {
        const { method = 'comprehensive', limit = 1000 } = req.body;

        logger.info('開始檢測藝術作品重複資料', { method, limit });

        // 從資料庫獲取藝術作品資料
        const artworks = await Artwork.findAll(limit);

        if (artworks.length === 0) {
            return res.json({
                success: true,
                data: {
                    duplicates: [],
                    totalRecords: 0,
                    duplicateGroups: 0
                },
                message: '沒有找到藝術作品資料'
            });
        }

        // 執行重複檢測
        const duplicates = await duplicateDetector.detectDuplicates(artworks, {
            type: 'artworks',
            method
        });

        res.json({
            success: true,
            data: {
                duplicates,
                totalRecords: artworks.length,
                duplicateGroups: duplicates.length,
                stats: duplicateDetector.getStats()
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('檢測藝術作品重複失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '檢測重複資料失敗',
            message: error.message
        });
    }
});

/**
 * POST /detect/artists - 檢測藝術家重複
 */
router.post('/detect/artists', async (req, res) => {
    try {
        const { method = 'comprehensive', limit = 1000 } = req.body;

        logger.info('開始檢測藝術家重複資料', { method, limit });

        // 從資料庫獲取藝術家資料
        const artists = await Artist.findAll(limit);

        if (artists.length === 0) {
            return res.json({
                success: true,
                data: {
                    duplicates: [],
                    totalRecords: 0,
                    duplicateGroups: 0
                },
                message: '沒有找到藝術家資料'
            });
        }

        // 執行重複檢測
        const duplicates = await duplicateDetector.detectDuplicates(artists, {
            type: 'artists',
            method
        });

        res.json({
            success: true,
            data: {
                duplicates,
                totalRecords: artists.length,
                duplicateGroups: duplicates.length,
                stats: duplicateDetector.getStats()
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('檢測藝術家重複失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '檢測重複資料失敗',
            message: error.message
        });
    }
});

/**
 * POST /detect/batch - 批次檢測自訂資料
 */
router.post('/detect/batch', async (req, res) => {
    try {
        const { data, options = {} } = req.body;

        if (!Array.isArray(data) || data.length === 0) {
            return res.status(400).json({
                success: false,
                error: '無效的資料格式',
                message: '請提供有效的資料陣列'
            });
        }

        logger.info('開始批次重複檢測', {
            recordCount: data.length,
            method: options.method || 'comprehensive'
        });

        // 執行重複檢測
        const duplicates = await duplicateDetector.detectDuplicates(data, options);

        res.json({
            success: true,
            data: {
                duplicates,
                totalRecords: data.length,
                duplicateGroups: duplicates.length,
                stats: duplicateDetector.getStats()
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('批次重複檢測失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '批次檢測失敗',
            message: error.message
        });
    }
});

/**
 * POST /compare - 比較兩筆記錄的相似度
 */
router.post('/compare', async (req, res) => {
    try {
        const { record1, record2 } = req.body;

        if (!record1 || !record2) {
            return res.status(400).json({
                success: false,
                error: '缺少比較資料',
                message: '請提供兩筆要比較的記錄'
            });
        }

        // 預處理資料
        const normalizedData = await duplicateDetector.preprocessData([record1, record2]);

        // 計算相似度
        const similarity = await duplicateDetector.calculateSimilarity(
            normalizedData[0],
            normalizedData[1]
        );

        res.json({
            success: true,
            data: {
                similarity: Math.round(similarity.overall * 10000) / 100,
                details: similarity,
                confidence: similarity.overall >= 0.95 ? 'high' :
                          similarity.overall >= 0.85 ? 'medium' : 'low'
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('記錄比較失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '記錄比較失敗',
            message: error.message
        });
    }
});

/**
 * GET /stats - 獲取重複檢測統計
 */
router.get('/stats', async (req, res) => {
    try {
        const stats = duplicateDetector.getStats();

        res.json({
            success: true,
            data: stats,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('獲取重複檢測統計失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '獲取統計資料失敗',
            message: error.message
        });
    }
});

/**
 * POST /merge-suggestions - 獲取合併建議
 */
router.post('/merge-suggestions', async (req, res) => {
    try {
        const { records } = req.body;

        if (!Array.isArray(records) || records.length < 2) {
            return res.status(400).json({
                success: false,
                error: '無效的記錄資料',
                message: '請提供至少兩筆記錄'
            });
        }

        // 預處理資料
        const normalizedData = await duplicateDetector.preprocessData(records);

        // 生成合併建議
        const suggestions = duplicateDetector.generateMergeSuggestions(normalizedData);

        // 計算每筆記錄的完整度評分
        const completenessScores = records.map(record => ({
            id: record.id,
            score: duplicateDetector.calculateCompletenessScore(record),
            percentage: Math.round(duplicateDetector.calculateCompletenessScore(record) * 100)
        }));

        res.json({
            success: true,
            data: {
                suggestions,
                completenessScores,
                totalRecords: records.length
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('獲取合併建議失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '獲取合併建議失敗',
            message: error.message
        });
    }
});

/**
 * POST /auto-merge - 自動合併重複記錄（謹慎使用）
 */
router.post('/auto-merge', async (req, res) => {
    try {
        const { duplicateGroups, strategy = 'keep_most_complete', dryRun = true } = req.body;

        if (!Array.isArray(duplicateGroups) || duplicateGroups.length === 0) {
            return res.status(400).json({
                success: false,
                error: '無效的重複群組',
                message: '請提供有效的重複群組資料'
            });
        }

        logger.info('開始自動合併處理', {
            groupCount: duplicateGroups.length,
            strategy,
            dryRun
        });

        const mergeResults = [];

        for (const group of duplicateGroups) {
            try {
                const result = await processMergeGroup(group, strategy, dryRun);
                mergeResults.push(result);
            } catch (error) {
                mergeResults.push({
                    groupId: group.groupId,
                    success: false,
                    error: error.message
                });
            }
        }

        const successCount = mergeResults.filter(r => r.success).length;
        const failCount = mergeResults.filter(r => !r.success).length;

        res.json({
            success: true,
            data: {
                results: mergeResults,
                summary: {
                    totalGroups: duplicateGroups.length,
                    successCount,
                    failCount,
                    strategy,
                    dryRun
                }
            },
            message: dryRun ? '乾跑模式：未實際執行合併' : '合併處理完成',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('自動合併失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '自動合併失敗',
            message: error.message
        });
    }
});

/**
 * DELETE /cache - 清除檢測快取
 */
router.delete('/cache', async (req, res) => {
    try {
        duplicateDetector.clearCache();

        res.json({
            success: true,
            message: '檢測快取已清除',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('清除快取失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '清除快取失敗',
            message: error.message
        });
    }
});

/**
 * DELETE /stats - 重設統計資料
 */
router.delete('/stats', async (req, res) => {
    try {
        duplicateDetector.resetStats();

        res.json({
            success: true,
            message: '統計資料已重設',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('重設統計失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '重設統計失敗',
            message: error.message
        });
    }
});

/**
 * 處理合併群組
 */
async function processMergeGroup(group, strategy, dryRun) {
    const { groupId, records } = group;

    // 根據策略選擇要保留的記錄
    let recordToKeep;
    switch (strategy) {
        case 'keep_most_complete':
            recordToKeep = records.reduce((best, current) => {
                const bestScore = duplicateDetector.calculateCompletenessScore(best.data);
                const currentScore = duplicateDetector.calculateCompletenessScore(current.data);
                return currentScore > bestScore ? current : best;
            });
            break;
        case 'keep_newest':
            recordToKeep = records.reduce((newest, current) => {
                const newestDate = new Date(newest.data.updated_at || newest.data.created_at || 0);
                const currentDate = new Date(current.data.updated_at || current.data.created_at || 0);
                return currentDate > newestDate ? current : newest;
            });
            break;
        case 'keep_first':
        default:
            recordToKeep = records[0];
            break;
    }

    const recordsToDelete = records.filter(r => r.id !== recordToKeep.id);

    const result = {
        groupId,
        success: true,
        recordToKeep: recordToKeep.id,
        recordsToDelete: recordsToDelete.map(r => r.id),
        strategy
    };

    if (!dryRun) {
        // 實際執行合併操作
        // 這裡需要實現實際的資料庫操作
        logger.info('執行實際合併操作', result);
        // TODO: 實現實際的合併邏輯
    }

    return result;
}

/**
 * GET /algorithms - 獲取可用的檢測算法資訊
 */
router.get('/algorithms', async (req, res) => {
    try {
        const algorithms = {
            methods: {
                fast: {
                    name: '快速檢測',
                    description: '基於雜湊值的快速重複檢測',
                    complexity: 'O(n)',
                    accuracy: 'high',
                    recommended: '大量資料初步篩選'
                },
                accurate: {
                    name: '精確檢測',
                    description: '多演算法組合的精確相似度計算',
                    complexity: 'O(n²)',
                    accuracy: 'very_high',
                    recommended: '小量資料精確檢測'
                },
                comprehensive: {
                    name: '綜合檢測',
                    description: '結合快速和精確檢測的最佳方案',
                    complexity: 'O(n + m²)',
                    accuracy: 'very_high',
                    recommended: '一般用途推薦'
                }
            },
            similarities: {
                levenshtein: {
                    name: 'Levenshtein距離',
                    description: '基於字元編輯距離的文字相似度'
                },
                jaccard: {
                    name: 'Jaccard相似度',
                    description: '基於詞組集合交集的相似度'
                },
                soundex: {
                    name: 'Soundex音韻',
                    description: '基於發音相似度的比較'
                }
            },
            thresholds: duplicateDetector.options.similarityThresholds
        };

        res.json({
            success: true,
            data: algorithms,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('獲取演算法資訊失敗', { error: error.message });
        res.status(500).json({
            success: false,
            error: '獲取演算法資訊失敗',
            message: error.message
        });
    }
});

// 錯誤處理中間件
router.use((error, req, res, next) => {
    logger.error('重複檢測API錯誤', {
        error: error.message,
        path: req.path,
        method: req.method
    });

    res.status(500).json({
        success: false,
        error: '內部服務錯誤',
        message: error.message
    });
});

module.exports = router;