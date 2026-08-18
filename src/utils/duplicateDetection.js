/**
 * 重複資料檢測系統
 * 使用多種演算法檢測藝術史資料庫中的重複記錄
 */

const { logger } = require('./logger');
const { TextCleaner } = require('./dataCleaner');

class DuplicateDetector {
    constructor(options = {}) {
        this.options = {
            // 相似度閾值
            similarityThresholds: {
                exact: 1.0,           // 完全相同
                high: 0.95,           // 高度相似
                medium: 0.85,         // 中度相似
                low: 0.75             // 低度相似
            },
            // 檢測算法權重
            algorithmWeights: {
                exactMatch: 0.4,      // 精確匹配
                levenshtein: 0.3,     // 編輯距離
                jaccard: 0.2,         // Jaccard相似度
                soundex: 0.1          // 音韻相似度
            },
            // 字段權重（用於綜合評分）
            fieldWeights: {
                title: 0.35,
                artist_name: 0.25,
                creation_year: 0.15,
                medium: 0.1,
                dimensions: 0.1,
                location: 0.05
            },
            batchSize: 100,           // 批次處理大小
            enableCaching: true,      // 啟用快取
            cacheSize: 1000,         // 快取大小
            ...options
        };

        // 快取系統
        this.cache = new Map();
        this.similarityCache = new Map();

        // 檢測結果統計
        this.stats = {
            totalChecked: 0,
            duplicatesFound: 0,
            lastCheck: null,
            processingTime: 0
        };

        logger.info('重複資料檢測系統初始化完成');
    }

    /**
     * 檢測重複資料 - 主要入口點
     */
    async detectDuplicates(data, options = {}) {
        const startTime = Date.now();

        try {
            logger.info('開始重複資料檢測', {
                recordCount: data.length,
                type: options.type || 'unknown'
            });

            // 資料預處理
            const normalizedData = await this.preprocessData(data);

            // 執行重複檢測
            let duplicates = [];

            switch (options.method || 'comprehensive') {
                case 'fast':
                    duplicates = await this.fastDuplicateDetection(normalizedData);
                    break;
                case 'accurate':
                    duplicates = await this.accurateDuplicateDetection(normalizedData);
                    break;
                case 'comprehensive':
                default:
                    duplicates = await this.comprehensiveDuplicateDetection(normalizedData);
                    break;
            }

            // 結果後處理
            const processedResults = this.processDuplicateResults(duplicates);

            // 更新統計
            this.updateStats(data.length, processedResults.length, Date.now() - startTime);

            logger.info('重複資料檢測完成', {
                totalRecords: data.length,
                duplicateGroups: processedResults.length,
                processingTime: Date.now() - startTime
            });

            return processedResults;

        } catch (error) {
            logger.error('重複資料檢測失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 資料預處理
     */
    async preprocessData(data) {
        return data.map((record, index) => ({
            id: record.id || `temp_${index}`,
            originalRecord: record,
            normalized: {
                title: this.normalizeText(record.title),
                artist_name: this.normalizeText(record.artist_name || record.name),
                creation_year: this.normalizeYear(record.creation_year || record.birth_year),
                medium: this.normalizeText(record.medium),
                dimensions: this.normalizeDimensions(record.dimensions),
                location: this.normalizeText(record.location || record.current_location),
                // 生成複合鍵用於快速比較
                compositeKey: this.generateCompositeKey(record)
            }
        }));
    }

    /**
     * 文本標準化
     */
    normalizeText(text) {
        if (!text || typeof text !== 'string') return '';

        return TextCleaner.cleanText(text)
            .toLowerCase()
            .replace(/[^\w\s]/g, '')  // 移除標點符號
            .replace(/\s+/g, ' ')     // 標準化空格
            .trim();
    }

    /**
     * 年份標準化
     */
    normalizeYear(year) {
        if (!year) return null;

        const numYear = parseInt(year);
        if (isNaN(numYear)) return null;

        return numYear;
    }

    /**
     * 尺寸標準化
     */
    normalizeDimensions(dimensions) {
        if (!dimensions) return '';

        return dimensions
            .toLowerCase()
            .replace(/[^\d.,x×\s]/g, '')  // 只保留數字、小數點、x、×
            .replace(/\s+/g, ' ')
            .trim();
    }

    /**
     * 生成複合鍵
     */
    generateCompositeKey(record) {
        const title = this.normalizeText(record.title);
        const artist = this.normalizeText(record.artist_name || record.name);
        const year = this.normalizeYear(record.creation_year || record.birth_year);

        return `${title}_${artist}_${year}`.replace(/\s/g, '');
    }

    /**
     * 快速重複檢測（基於雜湊）
     */
    async fastDuplicateDetection(normalizedData) {
        const hashGroups = new Map();

        // 按複合鍵分組
        normalizedData.forEach(record => {
            const key = record.normalized.compositeKey;
            if (!hashGroups.has(key)) {
                hashGroups.set(key, []);
            }
            hashGroups.get(key).push(record);
        });

        // 找出有重複的組
        const duplicates = [];
        for (const [key, group] of hashGroups) {
            if (group.length > 1) {
                duplicates.push({
                    type: 'exact_hash',
                    similarity: 1.0,
                    records: group,
                    confidence: 'high'
                });
            }
        }

        return duplicates;
    }

    /**
     * 精確重複檢測（多演算法組合）
     */
    async accurateDuplicateDetection(normalizedData) {
        const duplicates = [];
        const processed = new Set();

        for (let i = 0; i < normalizedData.length; i++) {
            if (processed.has(i)) continue;

            const record1 = normalizedData[i];
            const similarRecords = [record1];
            processed.add(i);

            for (let j = i + 1; j < normalizedData.length; j++) {
                if (processed.has(j)) continue;

                const record2 = normalizedData[j];
                const similarity = await this.calculateSimilarity(record1, record2);

                if (similarity.overall >= this.options.similarityThresholds.medium) {
                    similarRecords.push(record2);
                    processed.add(j);
                }
            }

            if (similarRecords.length > 1) {
                duplicates.push({
                    type: 'similarity_based',
                    similarity: this.calculateGroupSimilarity(similarRecords),
                    records: similarRecords,
                    confidence: this.assessConfidence(similarRecords)
                });
            }
        }

        return duplicates;
    }

    /**
     * 綜合重複檢測（快速+精確）
     */
    async comprehensiveDuplicateDetection(normalizedData) {
        // 先執行快速檢測找出明顯重複
        const fastDuplicates = await this.fastDuplicateDetection(normalizedData);

        // 從快速檢測結果中移除已確認重複的記錄
        const fastDuplicateIds = new Set();
        fastDuplicates.forEach(group => {
            group.records.forEach(record => {
                fastDuplicateIds.add(record.id);
            });
        });

        // 對剩餘記錄執行精確檢測
        const remainingData = normalizedData.filter(record =>
            !fastDuplicateIds.has(record.id)
        );

        const accurateDuplicates = await this.accurateDuplicateDetection(remainingData);

        // 合併結果
        return [...fastDuplicates, ...accurateDuplicates];
    }

    /**
     * 計算兩筆記錄的相似度
     */
    async calculateSimilarity(record1, record2) {
        const cacheKey = `${record1.id}_${record2.id}`;

        // 檢查快取
        if (this.options.enableCaching && this.similarityCache.has(cacheKey)) {
            return this.similarityCache.get(cacheKey);
        }

        const similarities = {};
        let weightedSum = 0;
        let totalWeight = 0;

        // 計算各欄位相似度
        for (const [field, weight] of Object.entries(this.options.fieldWeights)) {
            const value1 = record1.normalized[field];
            const value2 = record2.normalized[field];

            if (value1 && value2) {
                similarities[field] = this.calculateFieldSimilarity(value1, value2, field);
                weightedSum += similarities[field] * weight;
                totalWeight += weight;
            }
        }

        const overallSimilarity = totalWeight > 0 ? weightedSum / totalWeight : 0;

        const result = {
            overall: overallSimilarity,
            fields: similarities,
            details: this.getDetailedComparison(record1, record2)
        };

        // 加入快取
        if (this.options.enableCaching) {
            this.addToCache(cacheKey, result);
        }

        return result;
    }

    /**
     * 計算單一欄位相似度
     */
    calculateFieldSimilarity(value1, value2, fieldType) {
        if (value1 === value2) return 1.0;
        if (!value1 || !value2) return 0;

        switch (fieldType) {
            case 'creation_year':
                return this.calculateYearSimilarity(value1, value2);
            case 'title':
            case 'artist_name':
                return this.calculateTextSimilarity(value1, value2);
            case 'dimensions':
                return this.calculateDimensionSimilarity(value1, value2);
            default:
                return this.calculateTextSimilarity(value1, value2);
        }
    }

    /**
     * 年份相似度計算
     */
    calculateYearSimilarity(year1, year2) {
        if (year1 === year2) return 1.0;

        const diff = Math.abs(year1 - year2);
        if (diff === 0) return 1.0;
        if (diff <= 1) return 0.9;
        if (diff <= 2) return 0.8;
        if (diff <= 5) return 0.6;
        if (diff <= 10) return 0.4;

        return 0.0;
    }

    /**
     * 文本相似度計算（多演算法組合）
     */
    calculateTextSimilarity(text1, text2) {
        const similarities = {};

        // 精確匹配
        similarities.exact = text1 === text2 ? 1.0 : 0.0;

        // Levenshtein距離
        similarities.levenshtein = this.levenshteinSimilarity(text1, text2);

        // Jaccard相似度
        similarities.jaccard = this.jaccardSimilarity(text1, text2);

        // Soundex相似度
        similarities.soundex = this.soundexSimilarity(text1, text2);

        // 加權平均
        let weightedSum = 0;
        let totalWeight = 0;

        for (const [algorithm, weight] of Object.entries(this.options.algorithmWeights)) {
            if (similarities[algorithm] !== undefined) {
                weightedSum += similarities[algorithm] * weight;
                totalWeight += weight;
            }
        }

        return totalWeight > 0 ? weightedSum / totalWeight : 0;
    }

    /**
     * 尺寸相似度計算
     */
    calculateDimensionSimilarity(dim1, dim2) {
        if (dim1 === dim2) return 1.0;

        // 提取數字
        const nums1 = dim1.match(/\d+(\.\d+)?/g) || [];
        const nums2 = dim2.match(/\d+(\.\d+)?/g) || [];

        if (nums1.length !== nums2.length) return 0.5;

        let totalSimilarity = 0;
        for (let i = 0; i < nums1.length; i++) {
            const val1 = parseFloat(nums1[i]);
            const val2 = parseFloat(nums2[i]);
            const diff = Math.abs(val1 - val2);
            const avg = (val1 + val2) / 2;
            const similarity = avg > 0 ? Math.max(0, 1 - (diff / avg)) : 1;
            totalSimilarity += similarity;
        }

        return nums1.length > 0 ? totalSimilarity / nums1.length : 0;
    }

    /**
     * Levenshtein相似度
     */
    levenshteinSimilarity(str1, str2) {
        const distance = this.levenshteinDistance(str1, str2);
        const maxLength = Math.max(str1.length, str2.length);
        return maxLength > 0 ? 1 - (distance / maxLength) : 1;
    }

    /**
     * Levenshtein距離計算
     */
    levenshteinDistance(str1, str2) {
        const matrix = [];

        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }

        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }

        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }

        return matrix[str2.length][str1.length];
    }

    /**
     * Jaccard相似度
     */
    jaccardSimilarity(str1, str2) {
        const set1 = new Set(str1.split(/\s+/));
        const set2 = new Set(str2.split(/\s+/));

        const intersection = new Set([...set1].filter(x => set2.has(x)));
        const union = new Set([...set1, ...set2]);

        return union.size > 0 ? intersection.size / union.size : 0;
    }

    /**
     * Soundex相似度
     */
    soundexSimilarity(str1, str2) {
        const soundex1 = this.soundex(str1);
        const soundex2 = this.soundex(str2);
        return soundex1 === soundex2 ? 1.0 : 0.0;
    }

    /**
     * Soundex演算法實現
     */
    soundex(str) {
        if (!str) return '';

        str = str.toUpperCase().replace(/[^A-Z]/g, '');
        if (str.length === 0) return '';

        const firstLetter = str[0];
        let code = firstLetter;

        const mapping = {
            'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
            'L': '4', 'MN': '5', 'R': '6'
        };

        for (let i = 1; i < str.length; i++) {
            const char = str[i];
            for (const [chars, digit] of Object.entries(mapping)) {
                if (chars.includes(char)) {
                    if (code[code.length - 1] !== digit) {
                        code += digit;
                    }
                    break;
                }
            }
        }

        return (code + '000').substring(0, 4);
    }

    /**
     * 計算組內平均相似度
     */
    calculateGroupSimilarity(records) {
        if (records.length < 2) return 1.0;

        let totalSimilarity = 0;
        let pairCount = 0;

        for (let i = 0; i < records.length; i++) {
            for (let j = i + 1; j < records.length; j++) {
                const similarity = this.calculateSimilarity(records[i], records[j]);
                totalSimilarity += similarity.overall;
                pairCount++;
            }
        }

        return pairCount > 0 ? totalSimilarity / pairCount : 0;
    }

    /**
     * 評估信心度
     */
    assessConfidence(records) {
        if (records.length < 2) return 'low';

        const avgSimilarity = this.calculateGroupSimilarity(records);

        if (avgSimilarity >= this.options.similarityThresholds.high) return 'high';
        if (avgSimilarity >= this.options.similarityThresholds.medium) return 'medium';
        return 'low';
    }

    /**
     * 獲取詳細比較資訊
     */
    getDetailedComparison(record1, record2) {
        return {
            id1: record1.id,
            id2: record2.id,
            differences: this.findDifferences(record1.normalized, record2.normalized),
            commonFields: this.findCommonFields(record1.normalized, record2.normalized)
        };
    }

    /**
     * 找出差異
     */
    findDifferences(data1, data2) {
        const differences = {};

        for (const key in data1) {
            if (data1[key] !== data2[key]) {
                differences[key] = {
                    value1: data1[key],
                    value2: data2[key]
                };
            }
        }

        return differences;
    }

    /**
     * 找出共同欄位
     */
    findCommonFields(data1, data2) {
        const common = {};

        for (const key in data1) {
            if (data1[key] === data2[key] && data1[key]) {
                common[key] = data1[key];
            }
        }

        return common;
    }

    /**
     * 處理重複檢測結果
     */
    processDuplicateResults(duplicates) {
        return duplicates.map((group, index) => ({
            groupId: `dup_group_${index + 1}`,
            type: group.type,
            similarity: Math.round(group.similarity * 10000) / 100, // 百分比，保留2位小數
            confidence: group.confidence,
            recordCount: group.records.length,
            records: group.records.map(record => ({
                id: record.id,
                data: record.originalRecord,
                normalized: record.normalized
            })),
            suggestions: this.generateMergeSuggestions(group.records),
            createdAt: new Date()
        }));
    }

    /**
     * 生成合併建議
     */
    generateMergeSuggestions(records) {
        if (records.length < 2) return [];

        const suggestions = [];

        // 建議保留最完整的記錄
        const mostComplete = records.reduce((best, current) => {
            const bestScore = this.calculateCompletenessScore(best.originalRecord);
            const currentScore = this.calculateCompletenessScore(current.originalRecord);
            return currentScore > bestScore ? current : best;
        });

        suggestions.push({
            type: 'keep_most_complete',
            recommendedRecord: mostComplete.id,
            reason: '此記錄資料最完整'
        });

        // 建議最新記錄
        const newest = records.reduce((latest, current) => {
            const latestDate = new Date(latest.originalRecord.created_at || latest.originalRecord.updated_at || 0);
            const currentDate = new Date(current.originalRecord.created_at || current.originalRecord.updated_at || 0);
            return currentDate > latestDate ? current : latest;
        });

        if (newest.id !== mostComplete.id) {
            suggestions.push({
                type: 'keep_newest',
                recommendedRecord: newest.id,
                reason: '此記錄最新'
            });
        }

        return suggestions;
    }

    /**
     * 計算記錄完整度評分
     */
    calculateCompletenessScore(record) {
        const importantFields = ['title', 'artist_name', 'creation_year', 'description', 'medium'];
        let filledFields = 0;

        importantFields.forEach(field => {
            if (record[field] && record[field].toString().trim()) {
                filledFields++;
            }
        });

        return filledFields / importantFields.length;
    }

    /**
     * 添加到快取
     */
    addToCache(key, value) {
        if (this.similarityCache.size >= this.options.cacheSize) {
            // 刪除最舊的條目
            const firstKey = this.similarityCache.keys().next().value;
            this.similarityCache.delete(firstKey);
        }

        this.similarityCache.set(key, value);
    }

    /**
     * 更新統計資訊
     */
    updateStats(totalChecked, duplicatesFound, processingTime) {
        this.stats = {
            totalChecked: this.stats.totalChecked + totalChecked,
            duplicatesFound: this.stats.duplicatesFound + duplicatesFound,
            lastCheck: new Date(),
            processingTime: processingTime,
            averageProcessingTime: (this.stats.processingTime + processingTime) / 2
        };
    }

    /**
     * 獲取檢測統計
     */
    getStats() {
        return {
            ...this.stats,
            cacheSize: this.similarityCache.size,
            options: this.options
        };
    }

    /**
     * 清除快取
     */
    clearCache() {
        this.cache.clear();
        this.similarityCache.clear();
        logger.info('重複檢測快取已清除');
    }

    /**
     * 重設統計
     */
    resetStats() {
        this.stats = {
            totalChecked: 0,
            duplicatesFound: 0,
            lastCheck: null,
            processingTime: 0
        };
        logger.info('重複檢測統計已重設');
    }
}

module.exports = DuplicateDetector;