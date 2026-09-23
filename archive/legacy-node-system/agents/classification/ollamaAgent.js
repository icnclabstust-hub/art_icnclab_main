#!/usr/bin/env node
/**
 * Ollama 驅動的分類代理
 * 使用本地 Ollama 模型進行藝術作品智能分類
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const { ollamaService } = require('../../src/services/ollamaService');
const { logger } = require('../../src/utils/logger');

class OllamaClassificationAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'ollama-classification-agent';
        this.name = 'Ollama 分類代理';
        this.status = 'initializing';
        this.version = '2.0.0';

        // 配置設定
        this.config = {
            classificationThreshold: 0.7,
            useMultilabelClassification: true,
            maxCategories: 10,
            confidenceThreshold: 0.6,
            batchSize: 15
        };

        // 藝術史分類體系
        this.taxonomies = {
            periods: {
                'ancient': ['古代', '古典時期', 'ancient', 'classical', 'antiquity'],
                'medieval': ['中世紀', '拜占庭', 'medieval', 'byzantine', 'gothic'],
                'renaissance': ['文藝復興', '早期文藝復興', 'renaissance', 'early renaissance'],
                'baroque': ['巴洛克', 'baroque', 'counter-reformation'],
                'neoclassical': ['新古典主義', 'neoclassical', 'neoclassicism'],
                'romantic': ['浪漫主義', 'romantic', 'romanticism'],
                'impressionist': ['印象派', '印象主義', 'impressionist', 'impressionism'],
                'post_impressionist': ['後印象派', 'post-impressionist', 'post impressionist'],
                'modern': ['現代', '現代主義', 'modern', 'modernism'],
                'contemporary': ['當代', '當代藝術', 'contemporary', 'contemporary art']
            },
            styles: {
                'realism': ['寫實主義', '現實主義', 'realism', 'realistic'],
                'abstract': ['抽象', '抽象主義', 'abstract', 'abstraction'],
                'expressionism': ['表現主義', 'expressionism', 'expressionist'],
                'cubism': ['立體主義', 'cubism', 'cubist'],
                'surrealism': ['超現實主義', 'surrealism', 'surrealist'],
                'minimalism': ['極簡主義', 'minimalism', 'minimalist'],
                'pop_art': ['普普藝術', 'pop art', 'popular art']
            },
            mediums: {
                'oil_painting': ['油畫', 'oil painting', 'oil on canvas'],
                'watercolor': ['水彩', 'watercolor', 'aquarelle'],
                'sculpture': ['雕塑', 'sculpture', 'sculptural'],
                'photography': ['攝影', 'photography', 'photographic'],
                'printmaking': ['版畫', 'printmaking', 'print'],
                'drawing': ['繪圖', 'drawing', 'sketch'],
                'digital_art': ['數位藝術', 'digital art', 'computer art'],
                'installation': ['裝置藝術', 'installation', 'installation art']
            },
            subjects: {
                'portrait': ['肖像', 'portrait', 'portraiture'],
                'landscape': ['風景', 'landscape', 'scenery'],
                'still_life': ['靜物', 'still life', 'nature morte'],
                'religious': ['宗教', 'religious', 'sacred'],
                'mythology': ['神話', 'mythology', 'mythological'],
                'historical': ['歷史', 'historical', 'history painting'],
                'genre': ['風俗畫', 'genre', 'everyday life'],
                'abstract': ['抽象', 'abstract', 'non-figurative']
            }
        };

        // 處理統計
        this.stats = {
            processed: 0,
            classified: 0,
            errors: 0,
            startTime: null,
            classifications: {}
        };

        // 輸入和輸出路徑
        this.inputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'metadata');
        this.outputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'classified');

        logger.info(`🦙 ${this.name} 初始化完成`);
    }

    /**
     * 初始化 Agent
     */
    async initialize() {
        try {
            this.status = 'initializing';
            logger.info('🔧 正在初始化 Ollama 分類代理...');

            // 檢查 Ollama 服務狀態
            const health = await ollamaService.checkHealth();
            if (health.status !== 'healthy') {
                throw new Error(`Ollama 服務不可用: ${health.error}`);
            }

            logger.info(`✅ Ollama 服務正常，可用模型: ${health.models.length} 個`);

            // 確保輸出目錄存在
            await this.ensureDirectories();

            // 測試分類功能
            await this.testClassificationCapabilities();

            // 初始化分類緩存
            this.initializeClassificationCache();

            this.status = 'ready';
            logger.info('🚀 Ollama 分類代理初始化完成');

            this.emit('initialized', {
                agent: this.id,
                status: this.status,
                taxonomies: Object.keys(this.taxonomies).length
            });

        } catch (error) {
            this.status = 'error';
            logger.error('❌ Ollama 分類代理初始化失敗:', error);
            this.emit('error', error);
            throw error;
        }
    }

    /**
     * 確保目錄存在
     */
    async ensureDirectories() {
        const dirs = [this.outputDir];

        for (const dir of dirs) {
            try {
                await fs.mkdir(dir, { recursive: true });
                logger.debug(`📁 目錄已確保存在: ${dir}`);
            } catch (error) {
                logger.error(`創建目錄失敗: ${dir}`, error);
                throw error;
            }
        }
    }

    /**
     * 測試分類功能
     */
    async testClassificationCapabilities() {
        logger.info('🧪 測試 Ollama 分類功能...');

        try {
            const testArtwork = {
                title: 'Mona Lisa',
                artist: 'Leonardo da Vinci',
                description: 'Famous Renaissance portrait painting',
                date: '1503-1519',
                medium: 'oil on panel'
            };

            const classification = await ollamaService.classifyArtwork(testArtwork);
            logger.info('✅ 分類功能測試通過');
            logger.debug('測試分類結果:', classification);

        } catch (error) {
            logger.error('❌ 分類功能測試失敗:', error.message);
            throw new Error(`分類功能測試失敗: ${error.message}`);
        }
    }

    /**
     * 初始化分類緩存
     */
    initializeClassificationCache() {
        this.classificationCache = new Map();
        logger.info('💾 分類緩存已初始化');
    }

    /**
     * 開始分類任務
     */
    async startClassification(options = {}) {
        try {
            this.status = 'processing';
            this.stats.startTime = Date.now();

            const {
                inputSources = ['metadata'],
                outputFormat = 'detailed',
                enableCaching = true
            } = options;

            logger.info('🚀 開始 Ollama 分類任務...');

            // 掃描輸入文件
            const inputFiles = await this.scanInputFiles(inputSources);

            if (inputFiles.length === 0) {
                logger.warn('⚠️ 沒有找到待分類的文件');
                return [];
            }

            logger.info(`📄 找到 ${inputFiles.length} 個待分類文件`);

            // 處理文件
            const results = await this.processFiles(inputFiles, outputFormat, enableCaching);

            this.status = 'completed';
            const duration = Date.now() - this.stats.startTime;

            logger.info('✅ 分類完成！');
            logger.info(`📊 統計: 處理 ${this.stats.processed} 個項目，分類 ${this.stats.classified} 個作品`);
            logger.info(`⏱️ 總耗時: ${Math.round(duration / 1000)} 秒`);

            this.emit('classificationComplete', {
                filesProcessed: results.length,
                stats: this.stats,
                duration: duration,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            this.stats.errors++;
            logger.error('❌ Ollama 分類任務失敗:', error);
            this.emit('error', error);
            throw error;
        }
    }

    /**
     * 掃描輸入文件
     */
    async scanInputFiles(sources) {
        const files = [];

        for (const source of sources) {
            const sourceDir = path.join(this.inputDir, source);

            try {
                const dirExists = await fs.access(sourceDir).then(() => true).catch(() => false);
                if (!dirExists) {
                    // 如果 metadata 目錄不存在，嘗試直接使用 inputDir
                    const items = await fs.readdir(this.inputDir).catch(() => []);
                    for (const item of items) {
                        const itemPath = path.join(this.inputDir, item);
                        const stat = await fs.stat(itemPath).catch(() => null);

                        if (stat?.isFile() && item.endsWith('.json')) {
                            files.push({
                                path: itemPath,
                                source: 'direct',
                                filename: item
                            });
                        }
                    }
                    continue;
                }

                const items = await fs.readdir(sourceDir);
                for (const item of items) {
                    const itemPath = path.join(sourceDir, item);
                    const stat = await fs.stat(itemPath);

                    if (stat.isFile() && item.endsWith('.json')) {
                        files.push({
                            path: itemPath,
                            source: source,
                            filename: item
                        });
                    }
                }
            } catch (error) {
                logger.error(`掃描目錄失敗: ${sourceDir}`, error);
            }
        }

        return files;
    }

    /**
     * 處理文件批次
     */
    async processFiles(files, outputFormat, enableCaching) {
        const results = [];

        // 分批處理
        for (let i = 0; i < files.length; i += this.config.batchSize) {
            const batch = files.slice(i, i + this.config.batchSize);
            logger.info(`📦 處理批次 ${Math.floor(i / this.config.batchSize) + 1}/${Math.ceil(files.length / this.config.batchSize)} (${batch.length} 個文件)`);

            const batchResults = await Promise.allSettled(
                batch.map(file => this.processFile(file, outputFormat, enableCaching))
            );

            for (const result of batchResults) {
                if (result.status === 'fulfilled') {
                    results.push(result.value);
                } else {
                    logger.error('批次處理失敗:', result.reason);
                    this.stats.errors++;
                }
            }

            // 批次間短暫休息
            if (i + this.config.batchSize < files.length) {
                await new Promise(resolve => setTimeout(resolve, 800));
            }
        }

        return results;
    }

    /**
     * 處理單個文件
     */
    async processFile(fileInfo, outputFormat, enableCaching) {
        try {
            // 讀取原始數據
            const rawData = await fs.readFile(fileInfo.path, 'utf-8');
            const data = JSON.parse(rawData);

            if (!data || !data.metadata) {
                throw new Error('無效的數據格式');
            }

            // 檢查緩存
            const cacheKey = this.generateCacheKey(data.metadata);
            if (enableCaching && this.classificationCache.has(cacheKey)) {
                logger.debug(`💾 使用緩存分類: ${fileInfo.filename}`);
                const cachedResult = this.classificationCache.get(cacheKey);
                return this.saveClassificationResult(fileInfo, data, cachedResult, outputFormat);
            }

            // 執行 AI 分類
            const classification = await this.performAIClassification(data.metadata);

            // 後處理和驗證
            const processedClassification = await this.postProcessClassification(
                classification,
                data.metadata
            );

            // 緩存結果
            if (enableCaching) {
                this.classificationCache.set(cacheKey, processedClassification);
            }

            // 保存結果
            const result = await this.saveClassificationResult(
                fileInfo,
                data,
                processedClassification,
                outputFormat
            );

            this.stats.processed++;
            this.stats.classified++;

            logger.debug(`✅ 分類完成: ${fileInfo.filename}`);
            return result;

        } catch (error) {
            logger.error(`處理文件失敗: ${fileInfo.path}`, error);
            this.stats.errors++;
            throw error;
        }
    }

    /**
     * 執行 AI 分類
     */
    async performAIClassification(metadata) {
        try {
            // 使用 Ollama 進行分類
            const classification = await ollamaService.classifyArtwork(metadata);

            // 增強分類：添加規則式分類
            const enhancedClassification = await this.enhanceWithRuleBasedClassification(
                metadata,
                classification.classification
            );

            return {
                ...classification.classification,
                ...enhancedClassification,
                aiModel: classification.model,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            logger.warn(`AI 分類失敗，使用規則式分類: ${error.message}`);

            // 降級到規則式分類
            return await this.ruleBasedClassification(metadata);
        }
    }

    /**
     * 增強規則式分類
     */
    async enhanceWithRuleBasedClassification(metadata, aiClassification) {
        const enhanced = {};

        // 檢查每個分類維度
        for (const [dimension, categories] of Object.entries(this.taxonomies)) {
            if (!aiClassification[dimension]) {
                // AI 沒有分類這個維度，使用規則式分類
                const ruleBasedResult = this.classifyByRules(metadata, categories);
                if (ruleBasedResult.category) {
                    enhanced[dimension] = ruleBasedResult.category;
                    enhanced[`${dimension}_confidence`] = ruleBasedResult.confidence;
                    enhanced[`${dimension}_method`] = 'rule-based';
                }
            } else {
                enhanced[`${dimension}_method`] = 'ai-based';
            }
        }

        return enhanced;
    }

    /**
     * 規則式分類
     */
    ruleBasedClassification(metadata) {
        const classification = {
            method: 'rule-based',
            confidence: 0.8,
            timestamp: new Date().toISOString()
        };

        // 對每個維度進行規則式分類
        for (const [dimension, categories] of Object.entries(this.taxonomies)) {
            const result = this.classifyByRules(metadata, categories);
            if (result.category) {
                classification[dimension] = result.category;
                classification[`${dimension}_confidence`] = result.confidence;
            }
        }

        return classification;
    }

    /**
     * 基於規則的分類
     */
    classifyByRules(metadata, categories) {
        const text = JSON.stringify(metadata).toLowerCase();
        let bestMatch = null;
        let highestScore = 0;

        for (const [category, keywords] of Object.entries(categories)) {
            let score = 0;
            let matches = 0;

            for (const keyword of keywords) {
                if (text.includes(keyword.toLowerCase())) {
                    score += keyword.length; // 長關鍵字權重更高
                    matches++;
                }
            }

            if (matches > 0) {
                // 計算置信度
                const confidence = Math.min(0.95, (score / text.length) * 100 + (matches / keywords.length) * 0.3);

                if (confidence > highestScore && confidence >= this.config.confidenceThreshold) {
                    highestScore = confidence;
                    bestMatch = category;
                }
            }
        }

        return {
            category: bestMatch,
            confidence: highestScore
        };
    }

    /**
     * 後處理分類結果
     */
    async postProcessClassification(classification, metadata) {
        // 驗證分類一致性
        const validated = this.validateClassification(classification, metadata);

        // 計算整體信心度
        const overallConfidence = this.calculateOverallConfidence(validated);

        // 添加分類摘要
        const summary = this.generateClassificationSummary(validated);

        return {
            ...validated,
            overallConfidence,
            summary,
            postProcessed: true
        };
    }

    /**
     * 驗證分類一致性
     */
    validateClassification(classification, metadata) {
        const validated = { ...classification };

        // 檢查時期和風格的一致性
        if (validated.period && validated.style) {
            const periodStyleConsistency = this.checkPeriodStyleConsistency(
                validated.period,
                validated.style
            );
            validated.consistencyCheck = periodStyleConsistency;
        }

        return validated;
    }

    /**
     * 檢查時期與風格一致性
     */
    checkPeriodStyleConsistency(period, style) {
        const consistencyRules = {
            'renaissance': ['realism', 'classical'],
            'impressionist': ['impressionism'],
            'modern': ['abstract', 'expressionism', 'cubism'],
            'contemporary': ['abstract', 'minimalism', 'pop_art']
        };

        const compatibleStyles = consistencyRules[period] || [];
        const isConsistent = compatibleStyles.includes(style);

        return {
            consistent: isConsistent,
            expectedStyles: compatibleStyles,
            actualStyle: style
        };
    }

    /**
     * 計算整體信心度
     */
    calculateOverallConfidence(classification) {
        const confidenceFields = Object.keys(classification)
            .filter(key => key.endsWith('_confidence'))
            .map(key => classification[key])
            .filter(val => typeof val === 'number');

        if (confidenceFields.length === 0) return 0.5;

        const average = confidenceFields.reduce((sum, conf) => sum + conf, 0) / confidenceFields.length;
        return Math.round(average * 100) / 100;
    }

    /**
     * 生成分類摘要
     */
    generateClassificationSummary(classification) {
        const parts = [];

        if (classification.period) parts.push(classification.period);
        if (classification.style) parts.push(classification.style);
        if (classification.medium) parts.push(classification.medium);

        return parts.join(' • ');
    }

    /**
     * 生成緩存鍵
     */
    generateCacheKey(metadata) {
        const keyData = {
            title: metadata.title || '',
            artist: metadata.artist || '',
            description: metadata.description || '',
            medium: metadata.medium || ''
        };
        return Buffer.from(JSON.stringify(keyData)).toString('base64');
    }

    /**
     * 保存分類結果
     */
    async saveClassificationResult(fileInfo, originalData, classification, outputFormat) {
        const result = {
            originalFile: fileInfo.filename,
            timestamp: new Date().toISOString(),
            classification: classification,
            metadata: originalData.metadata
        };

        if (outputFormat === 'detailed') {
            result.processingDetails = {
                agent: this.id,
                version: this.version,
                taxonomies: Object.keys(this.taxonomies)
            };
        }

        // 生成輸出文件名
        const outputFilename = fileInfo.filename.replace('.json', '_classified.json');
        const outputPath = path.join(this.outputDir, outputFilename);

        await fs.writeFile(outputPath, JSON.stringify(result, null, 2), 'utf-8');

        // 更新分類統計
        const primaryClassification = classification.period || classification.style || 'unclassified';
        this.stats.classifications[primaryClassification] =
            (this.stats.classifications[primaryClassification] || 0) + 1;

        return {
            filename: outputFilename,
            outputPath: outputPath,
            classification: classification.summary || primaryClassification
        };
    }

    /**
     * 獲取處理統計
     */
    getStats() {
        const duration = this.stats.startTime ? Date.now() - this.stats.startTime : 0;

        return {
            ...this.stats,
            duration: duration,
            avgProcessingTime: this.stats.processed > 0 ? duration / this.stats.processed : 0,
            errorRate: this.stats.processed > 0 ? (this.stats.errors / this.stats.processed * 100).toFixed(2) + '%' : '0%',
            classificationDistribution: this.stats.classifications
        };
    }

    /**
     * 關閉代理
     */
    async shutdown() {
        this.status = 'shutdown';
        this.classificationCache.clear();
        logger.info('🛑 Ollama 分類代理已關閉');
        this.emit('shutdown');
    }
}

module.exports = OllamaClassificationAgent;