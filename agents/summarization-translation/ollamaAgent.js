#!/usr/bin/env node
/**
 * Ollama 驅動的摘要翻譯代理
 * 使用本地 Ollama 模型替代 OpenAI API，提供隱私保護和成本控制
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const { ollamaService } = require('../../src/services/ollamaService');
const { logger } = require('../../src/utils/logger');

class OllamaSummarizationAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'ollama-summarization-agent';
        this.name = 'Ollama 摘要翻譯代理';
        this.status = 'initializing';
        this.version = '2.0.0';

        // 配置設定
        this.config = {
            batchSize: 10,
            maxRetries: 3,
            timeout: 120000,
            enableSummaries: true,
            enableTranslations: true,
            enableCulturalAdaptation: true
        };

        // 支援的語言
        this.supportedLanguages = {
            'zh-TW': {
                name: '繁體中文',
                culturalContext: 'Traditional Chinese',
                adaptations: {
                    'Renaissance': '文藝復興',
                    'Baroque': '巴洛克',
                    'Impressionism': '印象派',
                    'Modern Art': '現代美術',
                    'Contemporary Art': '當代藝術'
                }
            },
            'zh-CN': {
                name: '简体中文',
                culturalContext: 'Simplified Chinese',
                adaptations: {
                    'Renaissance': '文艺复兴',
                    'Baroque': '巴洛克',
                    'Impressionism': '印象派',
                    'Modern Art': '现代美术'
                }
            },
            'ja': {
                name: '日本語',
                culturalContext: 'Japanese',
                adaptations: {
                    'Renaissance': 'ルネサンス',
                    'Baroque': 'バロック',
                    'Impressionism': '印象派',
                    'Modern Art': '近代美術'
                }
            },
            'en': {
                name: 'English',
                culturalContext: 'English',
                adaptations: {}
            }
        };

        // 摘要模板
        this.summaryTemplates = {
            artwork: {
                structure: ['title', 'artist', 'period', 'description', 'significance'],
                maxLength: 500
            },
            artist: {
                structure: ['name', 'period', 'style', 'major_works', 'legacy'],
                maxLength: 600
            },
            movement: {
                structure: ['name', 'period', 'characteristics', 'key_artists', 'influence'],
                maxLength: 700
            }
        };

        // 處理統計
        this.stats = {
            processed: 0,
            summariesGenerated: 0,
            translationsGenerated: 0,
            errors: 0,
            startTime: null
        };

        // 輸入和輸出路徑
        this.inputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'classified');
        this.outputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'final');

        logger.info(`🦙 ${this.name} 初始化完成`);
    }

    /**
     * 初始化 Agent
     */
    async initialize() {
        try {
            this.status = 'initializing';
            logger.info('🔧 正在初始化 Ollama 摘要翻譯代理...');

            // 檢查 Ollama 服務狀態
            const health = await ollamaService.checkHealth();
            if (health.status !== 'healthy') {
                throw new Error(`Ollama 服務不可用: ${health.error}`);
            }

            logger.info(`✅ Ollama 服務正常，可用模型: ${health.models.length} 個`);

            // 確保輸出目錄存在
            await this.ensureDirectories();

            // 測試模型功能
            await this.testModelCapabilities();

            this.status = 'ready';
            logger.info('🚀 Ollama 摘要翻譯代理初始化完成');

            this.emit('initialized', {
                agent: this.id,
                status: this.status,
                models: health.models
            });

        } catch (error) {
            this.status = 'error';
            logger.error('❌ Ollama 摘要翻譯代理初始化失敗:', error);
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
     * 測試模型功能
     */
    async testModelCapabilities() {
        logger.info('🧪 測試 Ollama 模型功能...');

        try {
            // 測試文本生成
            const testGeneration = await ollamaService.generateText(
                '請用繁體中文簡短回答：什麼是藝術史？',
                { maxTokens: 100 }
            );
            logger.info('✅ 文本生成測試通過');

            // 測試嵌入向量
            const testEmbedding = await ollamaService.generateEmbedding(
                '藝術史是研究藝術發展歷程的學科'
            );
            logger.info(`✅ 嵌入向量測試通過 (維度: ${testEmbedding.dimensions})`);

            // 測試藝術史摘要
            const testData = {
                title: 'Mona Lisa',
                artist: 'Leonardo da Vinci',
                period: 'Renaissance',
                description: 'Famous portrait painting'
            };

            const testSummary = await ollamaService.generateArtSummary(testData, 'artwork');
            logger.info('✅ 藝術史摘要測試通過');

            // 測試翻譯
            const testTranslation = await ollamaService.translateArtText(
                'Renaissance art is characterized by realism and humanism.',
                'en',
                'zh-TW'
            );
            logger.info('✅ 翻譯功能測試通過');

        } catch (error) {
            logger.error('❌ 模型功能測試失敗:', error.message);
            throw new Error(`模型功能測試失敗: ${error.message}`);
        }
    }

    /**
     * 開始處理任務
     */
    async startProcessing(options = {}) {
        try {
            this.status = 'processing';
            this.stats.startTime = Date.now();

            const {
                inputSources = ['classified'],
                targetLanguages = ['zh-TW'],
                generateSummaries = true,
                generateTranslations = true,
                culturalAdaptation = true
            } = options;

            logger.info(`🚀 開始 Ollama 摘要翻譯任務...`);
            logger.info(`目標語言: ${targetLanguages.join(', ')}`);

            // 掃描輸入文件
            const inputFiles = await this.scanInputFiles(inputSources);

            if (inputFiles.length === 0) {
                logger.warn('⚠️ 沒有找到待處理的文件');
                return [];
            }

            logger.info(`📄 找到 ${inputFiles.length} 個待處理文件`);

            // 處理文件
            const results = await this.processFiles(
                inputFiles,
                targetLanguages,
                generateSummaries,
                generateTranslations,
                culturalAdaptation
            );

            this.status = 'completed';
            const duration = Date.now() - this.stats.startTime;

            logger.info(`✅ 處理完成！`);
            logger.info(`📊 統計: 處理 ${this.stats.processed} 個項目，生成 ${this.stats.summariesGenerated} 個摘要，${this.stats.translationsGenerated} 個翻譯`);
            logger.info(`⏱️ 總耗時: ${Math.round(duration / 1000)} 秒`);

            this.emit('processingComplete', {
                filesProcessed: results.length,
                languages: targetLanguages.length,
                stats: this.stats,
                duration: duration,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            this.stats.errors++;
            logger.error('❌ Ollama 摘要翻譯任務失敗:', error);
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
                    logger.warn(`輸入目錄不存在: ${sourceDir}`);
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
    async processFiles(files, targetLanguages, generateSummaries, generateTranslations, culturalAdaptation) {
        const results = [];

        // 分批處理
        for (let i = 0; i < files.length; i += this.config.batchSize) {
            const batch = files.slice(i, i + this.config.batchSize);
            logger.info(`📦 處理批次 ${Math.floor(i / this.config.batchSize) + 1}/${Math.ceil(files.length / this.config.batchSize)} (${batch.length} 個文件)`);

            const batchResults = await Promise.allSettled(
                batch.map(file => this.processFile(file, targetLanguages, generateSummaries, generateTranslations, culturalAdaptation))
            );

            for (const result of batchResults) {
                if (result.status === 'fulfilled') {
                    results.push(...result.value);
                } else {
                    logger.error('批次處理失敗:', result.reason);
                    this.stats.errors++;
                }
            }

            // 批次間短暫休息
            if (i + this.config.batchSize < files.length) {
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        return results;
    }

    /**
     * 處理單個文件
     */
    async processFile(fileInfo, targetLanguages, generateSummaries, generateTranslations, culturalAdaptation) {
        try {
            // 讀取原始數據
            const rawData = await fs.readFile(fileInfo.path, 'utf-8');
            const data = JSON.parse(rawData);

            if (!data || !data.metadata) {
                throw new Error('無效的數據格式');
            }

            const results = [];

            for (const lang of targetLanguages) {
                const result = {
                    originalFile: fileInfo.filename,
                    language: lang,
                    timestamp: new Date().toISOString(),
                    data: { ...data }
                };

                // 生成摘要
                if (generateSummaries) {
                    const summaryType = this.detectContentType(data.metadata);
                    const summary = await ollamaService.generateArtSummary(data.metadata, summaryType);

                    result.data.summary = {
                        text: summary.summary,
                        type: summaryType,
                        model: summary.model,
                        language: lang
                    };

                    this.stats.summariesGenerated++;
                }

                // 生成翻譯
                if (generateTranslations && lang !== 'en') {
                    const translations = {};

                    // 翻譯主要字段
                    const fieldsToTranslate = ['title', 'description', 'artist', 'period'];

                    for (const field of fieldsToTranslate) {
                        if (data.metadata[field]) {
                            try {
                                const translation = await ollamaService.translateArtText(
                                    data.metadata[field],
                                    'en',
                                    lang
                                );
                                translations[field] = translation.translation;
                            } catch (error) {
                                logger.warn(`翻譯 ${field} 失敗:`, error.message);
                                translations[field] = data.metadata[field]; // 使用原文
                            }
                        }
                    }

                    result.data.translations = translations;
                    this.stats.translationsGenerated++;
                }

                // 文化適應
                if (culturalAdaptation && this.supportedLanguages[lang]) {
                    const adaptations = this.supportedLanguages[lang].adaptations;
                    result.data.culturalAdaptations = this.applyCulturalAdaptations(
                        result.data,
                        adaptations
                    );
                }

                // 保存結果
                const outputFilename = this.generateOutputFilename(fileInfo.filename, lang);
                const outputPath = path.join(this.outputDir, outputFilename);

                await fs.writeFile(outputPath, JSON.stringify(result, null, 2), 'utf-8');
                results.push({
                    language: lang,
                    outputPath: outputPath,
                    filename: outputFilename
                });
            }

            this.stats.processed++;
            logger.debug(`✅ 處理完成: ${fileInfo.filename} (${targetLanguages.length} 語言版本)`);

            return results;

        } catch (error) {
            logger.error(`處理文件失敗: ${fileInfo.path}`, error);
            this.stats.errors++;
            throw error;
        }
    }

    /**
     * 偵測內容類型
     */
    detectContentType(metadata) {
        if (metadata.artist && metadata.title) {
            return 'artwork';
        } else if (metadata.name && metadata.birthDate) {
            return 'artist';
        } else if (metadata.period && metadata.characteristics) {
            return 'movement';
        }
        return 'artwork'; // 預設
    }

    /**
     * 應用文化適應
     */
    applyCulturalAdaptations(data, adaptations) {
        const adapted = {};

        for (const [key, value] of Object.entries(adaptations)) {
            // 在文本中查找並替換術語
            let text = JSON.stringify(data);
            text = text.replace(new RegExp(key, 'gi'), value);

            try {
                const adaptedData = JSON.parse(text);
                if (adaptedData !== data) {
                    adapted[key] = value;
                }
            } catch (error) {
                // 忽略解析錯誤
            }
        }

        return adapted;
    }

    /**
     * 生成輸出文件名
     */
    generateOutputFilename(originalFilename, language) {
        const basename = path.basename(originalFilename, '.json');
        return `${basename}_${language}_ollama.json`;
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
            errorRate: this.stats.processed > 0 ? (this.stats.errors / this.stats.processed * 100).toFixed(2) + '%' : '0%'
        };
    }

    /**
     * 重置統計
     */
    resetStats() {
        this.stats = {
            processed: 0,
            summariesGenerated: 0,
            translationsGenerated: 0,
            errors: 0,
            startTime: null
        };
    }

    /**
     * 關閉代理
     */
    async shutdown() {
        this.status = 'shutdown';
        logger.info('🛑 Ollama 摘要翻譯代理已關閉');
        this.emit('shutdown');
    }
}

module.exports = OllamaSummarizationAgent;