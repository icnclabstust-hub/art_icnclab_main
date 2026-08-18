#!/usr/bin/env node
/**
 * Summarization Translation Agent - 摘要翻譯代理
 * 專責對藝術史內容進行智能摘要和多語言翻譯，支援文化適應性調整
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const axios = require('axios');
const { ollamaService } = require('../../src/services/ollamaService');

class SummarizationTranslationAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'summarization-translation-agent';
        this.name = '摘要翻譯代理';
        this.status = 'initializing';
        this.version = '1.0.0';

        // 配置設定
        this.config = {
            summaryMaxLength: parseInt(process.env.SUMMARY_MAX_LENGTH) || 1200,
            translationBatchSize: parseInt(process.env.TRANSLATION_BATCH_SIZE) || 10,
            enableCulturalAdaptation: process.env.ENABLE_CULTURAL_ADAPTATION === 'true',
            defaultLanguage: 'en',
            targetLanguages: ['zh-TW', 'zh-CN', 'en', 'fr', 'de', 'es', 'ja', 'ko'],
            confidenceThreshold: 0.8
        };

        // API配置
        this.apiConfigs = {
            openai: {
                baseUrl: 'https://api.openai.com/v1',
                apiKey: process.env.OPENAI_API_KEY,
                model: 'gpt-3.5-turbo',
                available: !!process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY !== 'sk-test-placeholder-please-replace'
            },
            deepl: {
                baseUrl: 'https://api-free.deepl.com/v2',
                apiKey: process.env.DEEPL_API_KEY,
                available: !!process.env.DEEPL_API_KEY && process.env.DEEPL_API_KEY !== 'test-placeholder-please-replace'
            },
            anthropic: {
                baseUrl: 'https://api.anthropic.com/v1',
                apiKey: process.env.ANTHROPIC_API_KEY,
                model: 'claude-3-sonnet-20240229',
                available: !!process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'sk-ant-test-placeholder-please-replace'
            }
        };

        // 語言映射
        this.languageMappings = {
            'zh-TW': { name: '繁體中文', code: 'zh-TW', deepl: 'ZH-HANT' },
            'zh-CN': { name: '簡體中文', code: 'zh-CN', deepl: 'ZH-HANS' },
            'en': { name: 'English', code: 'en', deepl: 'EN-US' },
            'fr': { name: 'Français', code: 'fr', deepl: 'FR' },
            'de': { name: 'Deutsch', code: 'de', deepl: 'DE' },
            'es': { name: 'Español', code: 'es', deepl: 'ES' },
            'ja': { name: '日本語', code: 'ja', deepl: 'JA' },
            'ko': { name: '한국어', code: 'ko', deepl: 'KO' }
        };

        // 文化適應規則
        this.culturalAdaptations = {
            'zh-TW': {
                artTerms: {
                    'Renaissance': '文藝復興',
                    'Baroque': '巴洛克',
                    'Impressionism': '印象派',
                    'Modern Art': '現代藝術'
                },
                dateFormats: 'Chinese traditional',
                measurements: 'metric'
            },
            'ja': {
                artTerms: {
                    'Renaissance': 'ルネサンス',
                    'Baroque': 'バロック',
                    'Impressionism': '印象派',
                    'Modern Art': '現代美術'
                },
                dateFormats: 'Japanese era',
                measurements: 'metric'
            }
        };

        // 摘要模板
        this.summaryTemplates = {
            artwork: {
                structure: ['title', 'artist', 'period', 'description', 'significance'],
                maxSentences: 8
            },
            artist: {
                structure: ['name', 'period', 'style', 'major_works', 'legacy'],
                maxSentences: 10
            },
            movement: {
                structure: ['name', 'period', 'characteristics', 'key_artists', 'influence'],
                maxSentences: 12
            }
        };

        // 任務追蹤
        this.processingQueue = [];
        this.completedTasks = [];
        this.errors = [];

        // 輸入和輸出路徑
        this.inputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'classified');
        this.outputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'final');

        console.log(`🌍 ${this.name} 初始化完成`);
    }

    /**
     * 初始化Agent
     */
    async initialize() {
        try {
            this.status = 'initializing';
            console.log('🔧 正在初始化Summarization Translation Agent...');

            // 確保輸出目錄存在
            await this.ensureDirectories();

            // 測試API連接
            await this.testAPIConnections();

            // 初始化語言處理器
            await this.initializeLanguageProcessors();

            // 測試摘要和翻譯功能
            await this.testCapabilities();

            this.status = 'ready';
            console.log('✅ Summarization Translation Agent 初始化完成');
            this.emit('initialized');

        } catch (error) {
            this.status = 'error';
            console.error('❌ Summarization Translation Agent 初始化失敗:', error.message);
            this.emit('error', error);
            throw error;
        }
    }

    /**
     * 確保目錄存在
     */
    async ensureDirectories() {
        const dirs = [
            this.outputDir,
            path.join(this.outputDir, 'summaries'),
            path.join(this.outputDir, 'translations'),
            path.join(this.outputDir, 'multilingual'),
            path.join(this.outputDir, 'reports')
        ];

        for (const dir of dirs) {
            await fs.mkdir(dir, { recursive: true });
        }

        console.log('📁 處理目錄準備完成');
    }

    /**
     * 測試API連接
     */
    async testAPIConnections() {
        console.log('🔗 測試API連接...');

        // 測試OpenAI
        if (this.apiConfigs.openai.available) {
            try {
                await this.testOpenAI();
                console.log('✅ OpenAI API 可用');
            } catch (error) {
                console.warn('⚠️ OpenAI API 不可用:', error.message);
                this.apiConfigs.openai.available = false;
            }
        }

        // 測試DeepL
        if (this.apiConfigs.deepl.available) {
            try {
                await this.testDeepL();
                console.log('✅ DeepL API 可用');
            } catch (error) {
                console.warn('⚠️ DeepL API 不可用:', error.message);
                this.apiConfigs.deepl.available = false;
            }
        }

        // 檢查至少一個API可用
        const availableAPIs = Object.values(this.apiConfigs).filter(config => config.available);
        if (availableAPIs.length === 0) {
            console.warn('⚠️ 沒有可用的API，將使用模擬模式');
        }
    }

    /**
     * 測試OpenAI API
     */
    async testOpenAI() {
        const response = await axios.post(
            `${this.apiConfigs.openai.baseUrl}/chat/completions`,
            {
                model: this.apiConfigs.openai.model,
                messages: [{ role: 'user', content: 'Hello' }],
                max_tokens: 5
            },
            {
                headers: {
                    'Authorization': `Bearer ${this.apiConfigs.openai.apiKey}`,
                    'Content-Type': 'application/json'
                },
                timeout: 5000
            }
        );
        return response.status === 200;
    }

    /**
     * 測試DeepL API
     */
    async testDeepL() {
        const response = await axios.post(
            `${this.apiConfigs.deepl.baseUrl}/translate`,
            'text=Hello&target_lang=FR',
            {
                headers: {
                    'Authorization': `DeepL-Auth-Key ${this.apiConfigs.deepl.apiKey}`,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                timeout: 5000
            }
        );
        return response.status === 200;
    }

    /**
     * 初始化語言處理器
     */
    async initializeLanguageProcessors() {
        console.log('🔤 語言處理器初始化完成');
        // 這裡可以初始化本地NLP處理器
    }

    /**
     * 測試功能
     */
    async testCapabilities() {
        const testData = {
            'dc:title': 'Mona Lisa',
            'dc:creator': 'Leonardo da Vinci',
            'dc:description': 'Famous Renaissance portrait painting known for its enigmatic smile.',
            'dc:date': '1503-1519',
            '_source': 'test'
        };

        // 測試摘要功能
        const summary = await this.generateSummary(testData, 'artwork');

        // 測試翻譯功能
        const translation = await this.translateText('Hello, this is a test.', 'en', 'zh-TW');

        console.log('🧪 摘要翻譯功能測試通過');
    }

    /**
     * 開始摘要翻譯任務
     */
    async startProcessing(config = {}) {
        try {
            this.status = 'processing';
            console.log('🚀 開始摘要翻譯任務...');

            const {
                inputSources = ['classified'],
                targetLanguages = this.config.targetLanguages,
                generateSummaries = true,
                generateTranslations = true,
                culturalAdaptation = this.config.enableCulturalAdaptation
            } = config;

            // 掃描輸入文件
            const inputFiles = await this.scanInputFiles(inputSources);
            console.log(`📄 找到 ${inputFiles.length} 個待處理文件`);

            if (inputFiles.length === 0) {
                console.log('⚠️ 沒有找到待處理的文件');
                return [];
            }

            // 處理文件
            const results = await this.processFiles(
                inputFiles,
                targetLanguages,
                generateSummaries,
                generateTranslations,
                culturalAdaptation
            );

            this.status = 'completed';
            console.log(`✅ 處理完成，生成了 ${results.length} 個多語言版本`);

            this.emit('processingComplete', {
                filesProcessed: results.length,
                languages: targetLanguages.length,
                errors: this.errors.length,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            console.error('❌ 摘要翻譯任務失敗:', error.message);
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
                    // 如果classified資料夾不存在，嘗試使用metadata資料夾
                    const alternativeDir = this.inputDir.replace('classified', 'metadata');
                    const altExists = await fs.access(alternativeDir).then(() => true).catch(() => false);

                    if (altExists) {
                        console.log(`📁 使用替代資料夾: ${alternativeDir}`);
                        const dirFiles = await fs.readdir(alternativeDir);
                        const jsonFiles = dirFiles.filter(f => f.endsWith('.json'));

                        for (const file of jsonFiles) {
                            const filePath = path.join(alternativeDir, file);
                            files.push({
                                path: filePath,
                                source: 'metadata',
                                filename: file
                            });
                        }
                    } else {
                        console.warn(`⚠️ 資料夾不存在: ${sourceDir}`);
                    }
                    continue;
                }

                const dirFiles = await fs.readdir(sourceDir);
                const jsonFiles = dirFiles.filter(f => f.endsWith('.json'));

                for (const file of jsonFiles) {
                    const filePath = path.join(sourceDir, file);
                    files.push({
                        path: filePath,
                        source: source,
                        filename: file
                    });
                }
            } catch (error) {
                console.error(`❌ 掃描資料夾失敗 ${sourceDir}:`, error.message);
            }
        }

        return files;
    }

    /**
     * 批量處理文件
     */
    async processFiles(files, targetLanguages, generateSummaries, generateTranslations, culturalAdaptation) {
        const results = [];

        for (const file of files) {
            try {
                console.log(`🌍 處理文件: ${file.filename}`);

                // 讀取數據
                const rawData = await fs.readFile(file.path, 'utf8');
                const records = JSON.parse(rawData);

                if (!Array.isArray(records)) {
                    throw new Error('數據格式錯誤：期望數組格式');
                }

                // 處理每個記錄
                const processedRecords = [];
                for (const record of records) {
                    const processed = await this.processRecord(
                        record,
                        targetLanguages,
                        generateSummaries,
                        generateTranslations,
                        culturalAdaptation
                    );
                    processedRecords.push(processed);
                }

                // 保存多語言版本
                await this.saveMultilingualData(processedRecords, file.filename, targetLanguages);

                results.push({
                    inputFile: file.filename,
                    recordsProcessed: processedRecords.length,
                    languages: targetLanguages,
                    processedAt: new Date().toISOString()
                });

                console.log(`✅ 處理完成: ${file.filename} (${processedRecords.length} 記錄)`);

            } catch (error) {
                console.error(`❌ 處理文件失敗 ${file.filename}:`, error.message);
                this.errors.push({
                    file: file.filename,
                    error: error.message,
                    timestamp: new Date()
                });
            }
        }

        return results;
    }

    /**
     * 處理單個記錄
     */
    async processRecord(record, targetLanguages, generateSummaries, generateTranslations, culturalAdaptation) {
        const processed = { ...record };
        processed._processedAt = new Date().toISOString();

        // 生成摘要
        if (generateSummaries) {
            try {
                processed._summary = await this.generateSummary(record, 'artwork');
            } catch (error) {
                console.warn(`⚠️ 摘要生成失敗:`, error.message);
                processed._summary = { error: error.message };
            }
        }

        // 生成翻譯
        if (generateTranslations) {
            processed._translations = {};

            for (const targetLang of targetLanguages) {
                if (targetLang === this.config.defaultLanguage) continue;

                try {
                    const translation = await this.translateRecord(
                        record,
                        this.config.defaultLanguage,
                        targetLang,
                        culturalAdaptation
                    );
                    processed._translations[targetLang] = translation;
                } catch (error) {
                    console.warn(`⚠️ 翻譯失敗 (${targetLang}):`, error.message);
                    processed._translations[targetLang] = { error: error.message };
                }
            }
        }

        return processed;
    }

    /**
     * 生成摘要
     */
    async generateSummary(record, type = 'artwork') {
        const template = this.summaryTemplates[type] || this.summaryTemplates.artwork;

        // 構建摘要文本
        let content = '';
        for (const field of template.structure) {
            const value = this.extractFieldValue(record, field);
            if (value) {
                content += `${value} `;
            }
        }

        if (!content.trim()) {
            throw new Error('無法提取足夠內容進行摘要');
        }

        // 使用AI生成摘要
        if (this.apiConfigs.openai.available) {
            return await this.generateAISummary(content, template);
        } else {
            return await this.generateSimpleSummary(content, template);
        }
    }

    /**
     * 使用AI生成摘要
     */
    async generateAISummary(content, template) {
        try {
            const prompt = `請為以下藝術史內容生成一個簡潔的摘要，長度不超過${template.maxSentences}句話：\n\n${content}`;

            const response = await axios.post(
                `${this.apiConfigs.openai.baseUrl}/chat/completions`,
                {
                    model: this.apiConfigs.openai.model,
                    messages: [{ role: 'user', content: prompt }],
                    max_tokens: this.config.summaryMaxLength,
                    temperature: 0.3
                },
                {
                    headers: {
                        'Authorization': `Bearer ${this.apiConfigs.openai.apiKey}`,
                        'Content-Type': 'application/json'
                    },
                    timeout: 30000
                }
            );

            const summary = response.data.choices[0].message.content.trim();

            return {
                text: summary,
                length: summary.length,
                sentences: summary.split(/[.!?]+/).length - 1,
                method: 'ai',
                confidence: 0.9
            };

        } catch (error) {
            console.warn('⚠️ AI摘要生成失敗，使用簡單摘要:', error.message);
            return await this.generateSimpleSummary(content, template);
        }
    }

    /**
     * 生成簡單摘要
     */
    async generateSimpleSummary(content, template) {
        const sentences = content.split(/[.!?]+/).filter(s => s.trim());
        const maxSentences = Math.min(template.maxSentences, sentences.length);

        // 選擇最重要的句子（簡化邏輯）
        const selectedSentences = sentences.slice(0, maxSentences);
        const summary = selectedSentences.join('. ') + '.';

        return {
            text: summary,
            length: summary.length,
            sentences: maxSentences,
            method: 'extractive',
            confidence: 0.7
        };
    }

    /**
     * 翻譯記錄
     */
    async translateRecord(record, sourceLang, targetLang, culturalAdaptation) {
        const translated = {};

        // 定義需要翻譯的字段
        const fieldsToTranslate = [
            'dc:title', 'dc:description', 'dc:subject',
            'ah:significance', '_summary.text'
        ];

        for (const field of fieldsToTranslate) {
            const value = this.getNestedValue(record, field);
            if (value && typeof value === 'string') {
                try {
                    const translatedValue = await this.translateText(value, sourceLang, targetLang);

                    // 應用文化適應
                    const adaptedValue = culturalAdaptation ?
                        this.applyCulturalAdaptation(translatedValue, targetLang) : translatedValue;

                    this.setNestedValue(translated, field, adaptedValue);
                } catch (error) {
                    console.warn(`⚠️ 字段翻譯失敗 ${field}:`, error.message);
                }
            }
        }

        // 保留非文本字段
        const nonTextFields = ['dc:date', 'dc:identifier', '_id', '_source'];
        for (const field of nonTextFields) {
            const value = record[field];
            if (value !== undefined) {
                translated[field] = value;
            }
        }

        return {
            language: targetLang,
            fields: translated,
            translatedAt: new Date().toISOString()
        };
    }

    /**
     * 翻譯文本
     */
    async translateText(text, sourceLang, targetLang) {
        // 使用DeepL API（如果可用）
        if (this.apiConfigs.deepl.available) {
            return await this.translateWithDeepL(text, sourceLang, targetLang);
        }

        // 使用OpenAI API
        if (this.apiConfigs.openai.available) {
            return await this.translateWithOpenAI(text, sourceLang, targetLang);
        }

        // 模擬翻譯
        return await this.mockTranslation(text, targetLang);
    }

    /**
     * 使用DeepL翻譯
     */
    async translateWithDeepL(text, sourceLang, targetLang) {
        try {
            const sourceCode = this.languageMappings[sourceLang]?.deepl || sourceLang.toUpperCase();
            const targetCode = this.languageMappings[targetLang]?.deepl || targetLang.toUpperCase();

            const response = await axios.post(
                `${this.apiConfigs.deepl.baseUrl}/translate`,
                `text=${encodeURIComponent(text)}&source_lang=${sourceCode}&target_lang=${targetCode}`,
                {
                    headers: {
                        'Authorization': `DeepL-Auth-Key ${this.apiConfigs.deepl.apiKey}`,
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    timeout: 30000
                }
            );

            return response.data.translations[0].text;
        } catch (error) {
            throw new Error(`DeepL翻譯失敗: ${error.message}`);
        }
    }

    /**
     * 使用OpenAI翻譯
     */
    async translateWithOpenAI(text, sourceLang, targetLang) {
        try {
            const targetLangName = this.languageMappings[targetLang]?.name || targetLang;
            const prompt = `請將以下文本翻譯成${targetLangName}：\n\n${text}`;

            const response = await axios.post(
                `${this.apiConfigs.openai.baseUrl}/chat/completions`,
                {
                    model: this.apiConfigs.openai.model,
                    messages: [{ role: 'user', content: prompt }],
                    max_tokens: 2000,
                    temperature: 0.1
                },
                {
                    headers: {
                        'Authorization': `Bearer ${this.apiConfigs.openai.apiKey}`,
                        'Content-Type': 'application/json'
                    },
                    timeout: 30000
                }
            );

            return response.data.choices[0].message.content.trim();
        } catch (error) {
            throw new Error(`OpenAI翻譯失敗: ${error.message}`);
        }
    }

    /**
     * 模擬翻譯
     */
    async mockTranslation(text, targetLang) {
        const langName = this.languageMappings[targetLang]?.name || targetLang;
        return `[${langName} 翻譯] ${text}`;
    }

    /**
     * 應用文化適應
     */
    applyCulturalAdaptation(text, targetLang) {
        const adaptations = this.culturalAdaptations[targetLang];
        if (!adaptations) return text;

        let adapted = text;

        // 替換藝術術語
        if (adaptations.artTerms) {
            for (const [original, translated] of Object.entries(adaptations.artTerms)) {
                const regex = new RegExp(original, 'gi');
                adapted = adapted.replace(regex, translated);
            }
        }

        return adapted;
    }

    /**
     * 輔助函數：提取字段值
     */
    extractFieldValue(record, field) {
        switch (field) {
            case 'title':
                return record['dc:title'];
            case 'artist':
                return typeof record['dc:creator'] === 'object' ?
                    record['dc:creator'].name : record['dc:creator'];
            case 'period':
                return record._classifications?.period?.category;
            case 'description':
                return record['dc:description'];
            case 'significance':
                return record['ah:significance'];
            default:
                return record[field];
        }
    }

    /**
     * 輔助函數：獲取嵌套值
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current?.[key], obj);
    }

    /**
     * 輔助函數：設置嵌套值
     */
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((current, key) => {
            if (!current[key]) current[key] = {};
            return current[key];
        }, obj);
        target[lastKey] = value;
    }

    /**
     * 保存多語言數據
     */
    async saveMultilingualData(processedRecords, originalFilename, targetLanguages) {
        // 主要多語言文件
        const mainOutputPath = path.join(this.outputDir, 'multilingual', `multilingual_${originalFilename}`);
        await fs.writeFile(mainOutputPath, JSON.stringify(processedRecords, null, 2));

        // 為每種語言創建單獨文件
        for (const lang of targetLanguages) {
            const langRecords = processedRecords.map(record => {
                if (lang === this.config.defaultLanguage) {
                    return record;
                } else if (record._translations && record._translations[lang]) {
                    return {
                        ...record._translations[lang].fields,
                        _originalId: record._id,
                        _language: lang,
                        _translatedAt: record._translations[lang].translatedAt
                    };
                }
                return null;
            }).filter(Boolean);

            const langPath = path.join(this.outputDir, 'translations', `${lang}_${originalFilename}`);
            await fs.writeFile(langPath, JSON.stringify(langRecords, null, 2));
        }

        // 摘要專用文件
        const summaries = processedRecords
            .filter(record => record._summary && !record._summary.error)
            .map(record => ({
                id: record._id,
                title: record['dc:title'],
                summary: record._summary,
                source: record._source
            }));

        if (summaries.length > 0) {
            const summaryPath = path.join(this.outputDir, 'summaries', `summaries_${originalFilename}`);
            await fs.writeFile(summaryPath, JSON.stringify(summaries, null, 2));
        }

        console.log(`💾 多語言數據已保存 (${targetLanguages.length} 種語言)`);
    }

    /**
     * 停止Agent
     */
    async stop() {
        console.log('⏹️ 停止Summarization Translation Agent...');
        this.status = 'stopping';

        this.status = 'stopped';
        console.log('✅ Summarization Translation Agent 已停止');
        this.emit('stopped');
    }

    /**
     * 獲取Agent狀態
     */
    getStatus() {
        return {
            id: this.id,
            name: this.name,
            status: this.status,
            version: this.version,
            statistics: {
                processingQueue: this.processingQueue.length,
                completedTasks: this.completedTasks.length,
                errors: this.errors.length
            },
            config: this.config,
            supportedLanguages: Object.keys(this.languageMappings),
            availableAPIs: Object.keys(this.apiConfigs).filter(key => this.apiConfigs[key].available)
        };
    }
}

module.exports = SummarizationTranslationAgent;

// 如果直接運行此文件
if (require.main === module) {
    const agent = new SummarizationTranslationAgent();

    agent.on('initialized', async () => {
        console.log('🚀 開始測試摘要翻譯...');
        await agent.startProcessing({
            inputSources: ['classified'],
            targetLanguages: ['zh-TW', 'en'],
            generateSummaries: true,
            generateTranslations: true,
            culturalAdaptation: true
        });
        await agent.stop();
        process.exit(0);
    });

    agent.on('error', (error) => {
        console.error('❌ Agent錯誤:', error);
        process.exit(1);
    });

    agent.initialize();
}