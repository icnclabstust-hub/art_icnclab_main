/**
 * 資料清理工具模組
 * 提供統一的資料清理和標準化功能
 */

const { logger } = require('./logger');

/**
 * 文本清理工具類
 */
class TextCleaner {
    /**
     * 清理和標準化文本
     * @param {string} text - 待清理的文本
     * @param {Object} options - 清理選項
     * @returns {string} - 清理後的文本
     */
    static cleanText(text, options = {}) {
        const {
            trimWhitespace = true,
            normalizeSpaces = true,
            removeEmptyLines = true,
            maxLength = null,
            preserveLineBreaks = false
        } = options;

        if (!text || typeof text !== 'string') {
            return '';
        }

        let cleaned = text;

        // 移除特殊字符和控制字符（但保留必要的標點符號）
            // eslint-disable-next-line no-control-regex -- 清除控制字元正是本行的目的
        cleaned = cleaned.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, '');

        // 標準化空白字符
        if (normalizeSpaces) {
            cleaned = cleaned.replace(/\s+/g, ' ');
        }

        // 移除空行
        if (removeEmptyLines && !preserveLineBreaks) {
            cleaned = cleaned.replace(/^\s*[\r\n]/gm, '');
        }

        // 修剪空白
        if (trimWhitespace) {
            cleaned = cleaned.trim();
        }

        // 長度限制
        if (maxLength && cleaned.length > maxLength) {
            cleaned = cleaned.substring(0, maxLength).trim();
            // 確保不在單詞中間截斷
            const lastSpace = cleaned.lastIndexOf(' ');
            if (lastSpace > maxLength * 0.8) {
                cleaned = cleaned.substring(0, lastSpace);
            }
            cleaned += '...';
        }

        return cleaned;
    }

    /**
     * 清理和驗證URL
     * @param {string|Array} urls - 單個URL或URL數組
     * @returns {Array} - 有效的URL數組
     */
    static cleanUrls(urls) {
        if (!urls) return [];

        const urlArray = Array.isArray(urls) ? urls : [urls];
        const validUrls = [];

        for (const url of urlArray) {
            if (typeof url === 'string') {
                const cleaned = url.trim();
                if (this.isValidUrl(cleaned)) {
                    validUrls.push(cleaned);
                }
            }
        }

        return validUrls;
    }

    /**
     * 驗證URL格式
     * @param {string} url - 待驗證的URL
     * @returns {boolean} - 是否為有效URL
     */
    static isValidUrl(url) {
        try {
            const urlObj = new URL(url);
            return ['http:', 'https:'].includes(urlObj.protocol);
        } catch {
            return false;
        }
    }

    /**
     * 清理和標準化名稱變體
     * @param {Array} variants - 名稱變體數組
     * @param {string} mainName - 主要名稱
     * @returns {Array} - 清理後的變體數組
     */
    static cleanNameVariants(variants, mainName) {
        if (!Array.isArray(variants)) return [];

        const cleaned = [];
        const seen = new Set();

        // 添加主名稱到已見集合
        if (mainName) {
            seen.add(mainName.toLowerCase().trim());
        }

        for (const variant of variants) {
            if (typeof variant === 'string') {
                const cleanedVariant = this.cleanText(variant, { maxLength: 200 });
                const normalized = cleanedVariant.toLowerCase();

                // 避免重複和空值
                if (cleanedVariant && !seen.has(normalized)) {
                    cleaned.push(cleanedVariant);
                    seen.add(normalized);
                }
            }
        }

        return cleaned;
    }
}

/**
 * 數值清理工具類
 */
class NumberCleaner {
    /**
     * 清理和驗證年份
     * @param {*} year - 待清理的年份
     * @param {Object} options - 清理選項
     * @returns {number|null} - 清理後的年份或null
     */
    static cleanYear(year, options = {}) {
        const {
            minYear = -3000,
            maxYear = new Date().getFullYear() + 10,
            allowNull = true
        } = options;

        if (year === null || year === undefined || year === '') {
            return allowNull ? null : undefined;
        }

        // 嘗試轉換為數字
        let numYear = Number(year);

        // 如果不是有效數字，嘗試從字符串中提取
        if (isNaN(numYear) && typeof year === 'string') {
            const match = year.match(/-?\d+/);
            if (match) {
                numYear = parseInt(match[0], 10);
            }
        }

        // 驗證範圍
        if (isNaN(numYear) || numYear < minYear || numYear > maxYear) {
            return allowNull ? null : undefined;
        }

        return Math.floor(numYear);
    }

    /**
     * 清理尺寸字符串
     * @param {string} dimensions - 尺寸字符串
     * @returns {string} - 清理後的尺寸字符串
     */
    static cleanDimensions(dimensions) {
        if (!dimensions || typeof dimensions !== 'string') {
            return '';
        }

        // 標準化尺寸格式
        let cleaned = dimensions.trim()
            .replace(/\s*[xX×]\s*/g, ' × ')  // 標準化乘號
            .replace(/\s*cm\s*/gi, ' cm')    // 標準化單位
            .replace(/\s*mm\s*/gi, ' mm')
            .replace(/\s*m\s*/gi, ' m')
            .replace(/\s*in\s*/gi, ' in')
            .replace(/\s+/g, ' ');

        return cleaned;
    }
}

/**
 * 藝術史專用資料清理器
 */
class ArtDataCleaner {
    /**
     * 清理藝術作品資料
     * @param {Object} artworkData - 原始藝術作品資料
     * @returns {Object} - 清理後的資料
     */
    static cleanArtworkData(artworkData) {
        if (!artworkData || typeof artworkData !== 'object') {
            throw new Error('無效的藝術作品資料');
        }

        const cleaned = {};

        // 清理標題
        if (artworkData.title) {
            cleaned.title = TextCleaner.cleanText(artworkData.title, { maxLength: 500 });
        }

        // 清理標題變體
        if (artworkData.title_variants) {
            cleaned.title_variants = TextCleaner.cleanNameVariants(
                artworkData.title_variants,
                cleaned.title
            );
        }

        // 清理創作年份
        if (artworkData.creation_year !== undefined) {
            cleaned.creation_year = NumberCleaner.cleanYear(artworkData.creation_year);
        }

        // 清理媒材
        if (artworkData.medium) {
            cleaned.medium = TextCleaner.cleanText(artworkData.medium, { maxLength: 200 });
        }

        // 清理尺寸
        if (artworkData.dimensions) {
            cleaned.dimensions = NumberCleaner.cleanDimensions(artworkData.dimensions);
        }

        // 清理描述
        if (artworkData.description) {
            cleaned.description = TextCleaner.cleanText(artworkData.description, {
                maxLength: 5000,
                preserveLineBreaks: true
            });
        }

        // 清理風格
        if (artworkData.style) {
            cleaned.style = TextCleaner.cleanText(artworkData.style, { maxLength: 100 });
        }

        // 清理主題內容
        if (artworkData.subject_matter) {
            cleaned.subject_matter = TextCleaner.cleanText(artworkData.subject_matter, { maxLength: 200 });
        }

        // 清理位置信息
        if (artworkData.location) {
            cleaned.location = TextCleaner.cleanText(artworkData.location, { maxLength: 300 });
        }

        if (artworkData.current_location) {
            cleaned.current_location = TextCleaner.cleanText(artworkData.current_location, { maxLength: 300 });
        }

        // 清理來源和意義
        if (artworkData.provenance) {
            cleaned.provenance = TextCleaner.cleanText(artworkData.provenance, {
                maxLength: 2000,
                preserveLineBreaks: true
            });
        }

        if (artworkData.significance) {
            cleaned.significance = TextCleaner.cleanText(artworkData.significance, {
                maxLength: 2000,
                preserveLineBreaks: true
            });
        }

        // 清理URL
        if (artworkData.source_urls) {
            cleaned.source_urls = TextCleaner.cleanUrls(artworkData.source_urls);
        }

        if (artworkData.image_urls) {
            cleaned.image_urls = TextCleaner.cleanUrls(artworkData.image_urls);
        }

        // 保留其他字段
        if (artworkData.artist_id) {
            cleaned.artist_id = artworkData.artist_id;
        }

        if (artworkData.metadata && typeof artworkData.metadata === 'object') {
            cleaned.metadata = artworkData.metadata;
        }

        logger.debug('藝術作品資料清理完成', {
            originalFields: Object.keys(artworkData).length,
            cleanedFields: Object.keys(cleaned).length
        });

        return cleaned;
    }

    /**
     * 清理藝術家資料
     * @param {Object} artistData - 原始藝術家資料
     * @returns {Object} - 清理後的資料
     */
    static cleanArtistData(artistData) {
        if (!artistData || typeof artistData !== 'object') {
            throw new Error('無效的藝術家資料');
        }

        const cleaned = {};

        // 清理姓名
        if (artistData.name) {
            cleaned.name = TextCleaner.cleanText(artistData.name, { maxLength: 200 });
        }

        // 清理姓名變體
        if (artistData.name_variants) {
            cleaned.name_variants = TextCleaner.cleanNameVariants(
                artistData.name_variants,
                cleaned.name
            );
        }

        // 清理年份
        if (artistData.birth_year !== undefined) {
            cleaned.birth_year = NumberCleaner.cleanYear(artistData.birth_year);
        }

        if (artistData.death_year !== undefined) {
            cleaned.death_year = NumberCleaner.cleanYear(artistData.death_year);
        }

        // 驗證死亡年份不早於出生年份
        if (cleaned.birth_year && cleaned.death_year && cleaned.death_year < cleaned.birth_year) {
            logger.warn('死亡年份早於出生年份，已調整', {
                name: cleaned.name,
                birth_year: cleaned.birth_year,
                death_year: cleaned.death_year
            });
            cleaned.death_year = null;
        }

        // 清理國籍
        if (artistData.nationality) {
            cleaned.nationality = TextCleaner.cleanText(artistData.nationality, { maxLength: 100 });
        }

        // 清理藝術運動
        if (artistData.art_movement) {
            cleaned.art_movement = TextCleaner.cleanText(artistData.art_movement, { maxLength: 100 });
        }

        // 清理傳記
        if (artistData.biography) {
            cleaned.biography = TextCleaner.cleanText(artistData.biography, {
                maxLength: 10000,
                preserveLineBreaks: true
            });
        }

        // 清理URL
        if (artistData.source_urls) {
            cleaned.source_urls = TextCleaner.cleanUrls(artistData.source_urls);
        }

        // 保留其他字段
        if (artistData.metadata && typeof artistData.metadata === 'object') {
            cleaned.metadata = artistData.metadata;
        }

        logger.debug('藝術家資料清理完成', {
            originalFields: Object.keys(artistData).length,
            cleanedFields: Object.keys(cleaned).length
        });

        return cleaned;
    }

    /**
     * 批量清理資料
     * @param {Array} dataArray - 資料數組
     * @param {string} type - 資料類型（'artwork' 或 'artist'）
     * @returns {Array} - 清理後的資料數組
     */
    static bulkCleanData(dataArray, type) {
        if (!Array.isArray(dataArray)) {
            throw new Error('資料必須是數組格式');
        }

        const results = [];
        const errors = [];

        for (let i = 0; i < dataArray.length; i++) {
            try {
                let cleaned;
                switch (type) {
                    case 'artwork':
                        cleaned = this.cleanArtworkData(dataArray[i]);
                        break;
                    case 'artist':
                        cleaned = this.cleanArtistData(dataArray[i]);
                        break;
                    default:
                        throw new Error(`不支持的資料類型: ${type}`);
                }
                results.push(cleaned);
            } catch (error) {
                errors.push({
                    index: i,
                    data: dataArray[i],
                    error: error.message
                });
                logger.error('資料清理失敗', {
                    index: i,
                    type,
                    error: error.message
                });
            }
        }

        logger.info('批量資料清理完成', {
            type,
            total: dataArray.length,
            success: results.length,
            errors: errors.length
        });

        return {
            success: results,
            errors: errors
        };
    }
}

/**
 * 資料品質檢查器
 */
class DataQualityChecker {
    /**
     * 檢查資料完整性
     * @param {Object} data - 待檢查的資料
     * @param {Array} requiredFields - 必填字段
     * @returns {Object} - 檢查結果
     */
    static checkCompleteness(data, requiredFields = []) {
        const missing = [];
        const present = [];

        for (const field of requiredFields) {
            if (data[field] === undefined || data[field] === null || data[field] === '') {
                missing.push(field);
            } else {
                present.push(field);
            }
        }

        return {
            score: present.length / requiredFields.length,
            missing,
            present,
            isComplete: missing.length === 0
        };
    }

    /**
     * 檢查資料一致性
     * @param {Object} data - 待檢查的資料
     * @returns {Object} - 檢查結果
     */
    static checkConsistency(data) {
        const issues = [];

        // 檢查年份一致性
        if (data.birth_year && data.death_year) {
            if (data.death_year < data.birth_year) {
                issues.push('死亡年份早於出生年份');
            }
        }

        // 檢查URL有效性
        if (data.source_urls) {
            for (const url of data.source_urls) {
                if (!TextCleaner.isValidUrl(url)) {
                    issues.push(`無效的來源URL: ${url}`);
                }
            }
        }

        if (data.image_urls) {
            for (const url of data.image_urls) {
                if (!TextCleaner.isValidUrl(url)) {
                    issues.push(`無效的圖像URL: ${url}`);
                }
            }
        }

        return {
            isConsistent: issues.length === 0,
            issues
        };
    }
}

module.exports = {
    TextCleaner,
    NumberCleaner,
    ArtDataCleaner,
    DataQualityChecker
};