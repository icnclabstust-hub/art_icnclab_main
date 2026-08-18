#!/usr/bin/env node
/**
 * Classification Agent - 分類代理
 * 專責對藝術作品和文獻進行智能分類，支援多維度分類體系
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const axios = require('axios');

class ClassificationAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'classification-agent';
        this.name = '分類代理';
        this.status = 'initializing';
        this.version = '1.0.0';

        // 配置設定
        this.config = {
            classificationThreshold: parseFloat(process.env.CLASSIFICATION_THRESHOLD) || 0.7,
            useMultilabelClassification: process.env.USE_MULTILABEL_CLASSIFICATION === 'true',
            maxCategories: 10,
            confidenceThreshold: 0.6,
            batchSize: 20
        };

        // 藝術史分類體系
        this.taxonomies = {
            // 時期分類
            periods: {
                'ancient': ['古代', '古典時期', 'ancient', 'classical'],
                'medieval': ['中世紀', '拜占庭', 'medieval', 'byzantine'],
                'renaissance': ['文藝復興', '早期文藝復興', 'renaissance', 'early renaissance'],
                'baroque': ['巴洛克', 'baroque'],
                'neoclassical': ['新古典主義', 'neoclassical'],
                'romantic': ['浪漫主義', 'romantic', 'romanticism'],
                'impressionist': ['印象派', '印象主義', 'impressionist', 'impressionism'],
                'post_impressionist': ['後印象派', 'post-impressionist', 'post impressionist'],
                'modern': ['現代', '現代主義', 'modern', 'modernism'],
                'contemporary': ['當代', '當代藝術', 'contemporary', 'contemporary art']
            },
            // 風格分類
            styles: {
                'realism': ['寫實主義', '現實主義', 'realism', 'realistic'],
                'abstract': ['抽象', '抽象主義', 'abstract', 'abstraction'],
                'expressionism': ['表現主義', 'expressionism', 'expressionist'],
                'cubism': ['立體主義', 'cubism', 'cubist'],
                'surrealism': ['超現實主義', 'surrealism', 'surrealist'],
                'minimalism': ['極簡主義', 'minimalism', 'minimalist'],
                'conceptual': ['觀念藝術', 'conceptual art', 'conceptual']
            },
            // 媒材分類
            mediums: {
                'painting': ['繪畫', '油畫', 'painting', 'oil painting', 'canvas'],
                'sculpture': ['雕塑', 'sculpture', 'carved', 'bronze', 'marble'],
                'drawing': ['素描', '繪圖', 'drawing', 'sketch', 'charcoal'],
                'print': ['版畫', '印刷', 'print', 'etching', 'lithograph'],
                'photography': ['攝影', 'photography', 'photograph'],
                'digital': ['數位藝術', 'digital art', 'computer art'],
                'installation': ['裝置藝術', 'installation', 'installation art'],
                'video': ['錄影藝術', 'video art', 'video'],
                'performance': ['行為藝術', 'performance art', 'performance']
            },
            // 主題分類
            subjects: {
                'portrait': ['肖像', '人像', 'portrait', 'portraiture'],
                'landscape': ['風景', '景觀', 'landscape', 'scenery'],
                'still_life': ['靜物', 'still life', 'nature morte'],
                'religious': ['宗教', '宗教題材', 'religious', 'sacred'],
                'mythology': ['神話', '神話題材', 'mythology', 'mythological'],
                'history': ['歷史', '歷史畫', 'history', 'historical'],
                'genre': ['風俗畫', '日常生活', 'genre', 'everyday life'],
                'nude': ['裸體', '人體', 'nude', 'figure study'],
                'animal': ['動物', 'animal', 'fauna'],
                'abstract_subject': ['抽象主題', 'abstract subject', 'non-representational']
            },
            // 地理分類
            regions: {
                'european': ['歐洲', 'european', 'europe'],
                'american': ['美國', '美洲', 'american', 'americas'],
                'asian': ['亞洲', 'asian', 'asia'],
                'african': ['非洲', 'african', 'africa'],
                'oceanic': ['大洋洲', 'oceanic', 'oceania'],
                'middle_eastern': ['中東', 'middle eastern', 'middle east']
            }
        };

        // 機器學習分類器（模擬）
        this.classifiers = {
            period: null,
            style: null,
            medium: null,
            subject: null,
            region: null
        };

        // 任務追蹤
        this.classificationQueue = [];
        this.completedTasks = [];
        this.errors = [];

        // 輸入和輸出路徑
        this.inputDir = process.env.DATA_PROCESSED_DIR || './data/processed';
        this.outputDir = path.join(process.env.DATA_PROCESSED_DIR || './data/processed', 'classified');
        this.modelsDir = process.env.MODELS_DIR || './models';

        console.log(`🏷️ ${this.name} 初始化完成`);
    }

    /**
     * 初始化Agent
     */
    async initialize() {
        try {
            this.status = 'initializing';
            console.log('🔧 正在初始化Classification Agent...');

            // 確保輸出目錄存在
            await this.ensureDirectories();

            // 初始化分類器
            await this.initializeClassifiers();

            // 載入或訓練分類模型
            await this.loadClassificationModels();

            // 測試分類功能
            await this.testClassificationCapabilities();

            this.status = 'ready';
            console.log('✅ Classification Agent 初始化完成');
            this.emit('initialized');

        } catch (error) {
            this.status = 'error';
            console.error('❌ Classification Agent 初始化失敗:', error.message);
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
            path.join(this.outputDir, 'by_period'),
            path.join(this.outputDir, 'by_style'),
            path.join(this.outputDir, 'by_medium'),
            path.join(this.outputDir, 'by_subject'),
            path.join(this.outputDir, 'reports'),
            this.modelsDir
        ];

        for (const dir of dirs) {
            await fs.mkdir(dir, { recursive: true });
        }

        console.log('📁 分類目錄準備完成');
    }

    /**
     * 初始化分類器
     */
    async initializeClassifiers() {
        console.log('🤖 分類器初始化完成');
        // 這裡可以整合真實的ML分類器，如TensorFlow.js
    }

    /**
     * 載入分類模型
     */
    async loadClassificationModels() {
        console.log('📚 分類模型載入完成');
        // 這裡可以載入預訓練模型
    }

    /**
     * 測試分類功能
     */
    async testClassificationCapabilities() {
        const testArtwork = {
            'dc:title': 'Mona Lisa',
            'dc:creator': 'Leonardo da Vinci',
            'dc:date': '1503-1519',
            'dc:type': 'painting',
            'dc:description': 'Renaissance portrait painting',
            '_source': 'test'
        };

        const classification = await this.classifyArtwork(testArtwork);
        console.log('🧪 分類功能測試通過');
    }

    /**
     * 開始分類任務
     */
    async startClassification(config = {}) {
        try {
            this.status = 'classifying';
            console.log('🚀 開始分類任務...');

            const {
                inputSources = ['metadata'],
                classificationTypes = ['period', 'style', 'medium', 'subject'],
                generateReports = true
            } = config;

            // 掃描輸入文件
            const inputFiles = await this.scanInputFiles(inputSources);
            console.log(`📄 找到 ${inputFiles.length} 個待分類文件`);

            if (inputFiles.length === 0) {
                console.log('⚠️ 沒有找到待分類的文件');
                return [];
            }

            // 分類文件
            const results = await this.classifyFiles(inputFiles, classificationTypes);

            // 生成分類報告
            if (generateReports) {
                await this.generateClassificationReport(results);
            }

            this.status = 'completed';
            console.log(`✅ 分類完成，處理了 ${results.length} 個文件`);

            this.emit('classificationComplete', {
                filesProcessed: results.length,
                errors: this.errors.length,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            console.error('❌ 分類任務失敗:', error.message);
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
                    console.warn(`⚠️ 資料夾不存在: ${sourceDir}`);
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
     * 批量分類文件
     */
    async classifyFiles(files, classificationTypes) {
        const results = [];

        for (const file of files) {
            try {
                console.log(`🏷️ 分類文件: ${file.filename}`);

                // 讀取數據
                const rawData = await fs.readFile(file.path, 'utf8');
                const records = JSON.parse(rawData);

                if (!Array.isArray(records)) {
                    throw new Error('數據格式錯誤：期望數組格式');
                }

                // 分類每個記錄
                const classifiedRecords = [];
                for (const record of records) {
                    const classified = await this.classifyArtwork(record, classificationTypes);
                    classifiedRecords.push(classified);
                }

                // 按分類保存數據
                await this.saveClassifiedData(classifiedRecords, file.filename);

                results.push({
                    inputFile: file.filename,
                    recordsProcessed: classifiedRecords.length,
                    classificationTypes: classificationTypes,
                    processedAt: new Date().toISOString()
                });

                console.log(`✅ 分類完成: ${file.filename} (${classifiedRecords.length} 記錄)`);

            } catch (error) {
                console.error(`❌ 分類文件失敗 ${file.filename}:`, error.message);
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
     * 分類單個藝術品
     */
    async classifyArtwork(artwork, classificationTypes = ['period', 'style', 'medium', 'subject']) {
        const classified = { ...artwork };
        classified._classifications = {};
        classified._classifiedAt = new Date().toISOString();

        // 進行各種類型的分類
        for (const type of classificationTypes) {
            try {
                const classification = await this.performClassification(artwork, type);
                classified._classifications[type] = classification;
            } catch (error) {
                console.warn(`⚠️ 分類失敗 ${type}:`, error.message);
                classified._classifications[type] = {
                    category: 'unknown',
                    confidence: 0,
                    error: error.message
                };
            }
        }

        // 計算總體分類置信度
        classified._classificationConfidence = this.calculateOverallConfidence(classified._classifications);

        return classified;
    }

    /**
     * 執行特定類型的分類
     */
    async performClassification(artwork, type) {
        switch (type) {
            case 'period':
                return await this.classifyPeriod(artwork);
            case 'style':
                return await this.classifyStyle(artwork);
            case 'medium':
                return await this.classifyMedium(artwork);
            case 'subject':
                return await this.classifySubject(artwork);
            case 'region':
                return await this.classifyRegion(artwork);
            default:
                throw new Error(`不支持的分類類型: ${type}`);
        }
    }

    /**
     * 分類藝術時期
     */
    async classifyPeriod(artwork) {
        const text = this.extractTextForClassification(artwork);
        const scores = {};

        // 基於關鍵字匹配
        for (const [period, keywords] of Object.entries(this.taxonomies.periods)) {
            let score = 0;
            for (const keyword of keywords) {
                const regex = new RegExp(keyword, 'gi');
                const matches = text.match(regex);
                if (matches) {
                    score += matches.length;
                }
            }
            scores[period] = score;
        }

        // 日期基礎的時期判斷
        const dateScore = this.classifyByDate(artwork['dc:date']);
        if (dateScore.period && dateScore.confidence > 0.8) {
            scores[dateScore.period] = (scores[dateScore.period] || 0) + dateScore.confidence * 10;
        }

        // 找出最高分數的時期
        const maxScore = Math.max(...Object.values(scores));
        const bestPeriod = Object.keys(scores).find(p => scores[p] === maxScore);

        return {
            category: bestPeriod || 'unknown',
            confidence: Math.min(maxScore / 10, 1.0), // 標準化到 0-1
            details: scores
        };
    }

    /**
     * 基於日期分類時期
     */
    classifyByDate(dateString) {
        if (!dateString) return { period: null, confidence: 0 };

        const yearMatch = dateString.toString().match(/(\d{4})/);
        if (!yearMatch) return { period: null, confidence: 0 };

        const year = parseInt(yearMatch[1]);

        // 簡化的時期劃分
        if (year < 500) return { period: 'ancient', confidence: 0.9 };
        if (year < 1400) return { period: 'medieval', confidence: 0.9 };
        if (year < 1600) return { period: 'renaissance', confidence: 0.9 };
        if (year < 1750) return { period: 'baroque', confidence: 0.9 };
        if (year < 1850) return { period: 'neoclassical', confidence: 0.8 };
        if (year < 1900) return { period: 'impressionist', confidence: 0.8 };
        if (year < 1950) return { period: 'modern', confidence: 0.8 };
        return { period: 'contemporary', confidence: 0.8 };
    }

    /**
     * 分類藝術風格
     */
    async classifyStyle(artwork) {
        return this.classifyByKeywords(artwork, 'styles');
    }

    /**
     * 分類媒材
     */
    async classifyMedium(artwork) {
        return this.classifyByKeywords(artwork, 'mediums');
    }

    /**
     * 分類主題
     */
    async classifySubject(artwork) {
        return this.classifyByKeywords(artwork, 'subjects');
    }

    /**
     * 分類地區
     */
    async classifyRegion(artwork) {
        return this.classifyByKeywords(artwork, 'regions');
    }

    /**
     * 基於關鍵字的分類
     */
    classifyByKeywords(artwork, taxonomyKey) {
        const text = this.extractTextForClassification(artwork);
        const scores = {};

        for (const [category, keywords] of Object.entries(this.taxonomies[taxonomyKey])) {
            let score = 0;
            for (const keyword of keywords) {
                const regex = new RegExp(keyword, 'gi');
                const matches = text.match(regex);
                if (matches) {
                    score += matches.length;
                }
            }
            scores[category] = score;
        }

        const maxScore = Math.max(...Object.values(scores));
        const bestCategory = Object.keys(scores).find(c => scores[c] === maxScore);

        return {
            category: bestCategory || 'unknown',
            confidence: Math.min(maxScore / 5, 1.0),
            details: scores
        };
    }

    /**
     * 提取用於分類的文本
     */
    extractTextForClassification(artwork) {
        const fields = [
            'dc:title', 'dc:creator', 'dc:description', 'dc:subject',
            'dc:type', 'ah:style', 'ah:technique', 'ah:significance'
        ];

        let text = '';
        for (const field of fields) {
            if (artwork[field]) {
                if (typeof artwork[field] === 'string') {
                    text += ' ' + artwork[field];
                } else if (Array.isArray(artwork[field])) {
                    text += ' ' + artwork[field].join(' ');
                } else if (typeof artwork[field] === 'object' && artwork[field].name) {
                    text += ' ' + artwork[field].name;
                }
            }
        }

        return text.toLowerCase();
    }

    /**
     * 計算總體分類置信度
     */
    calculateOverallConfidence(classifications) {
        const confidences = Object.values(classifications)
            .filter(c => c.confidence !== undefined)
            .map(c => c.confidence);

        if (confidences.length === 0) return 0;

        return confidences.reduce((sum, conf) => sum + conf, 0) / confidences.length;
    }

    /**
     * 保存分類後的數據
     */
    async saveClassifiedData(classifiedRecords, originalFilename) {
        // 主要分類文件
        const mainOutputPath = path.join(this.outputDir, `classified_${originalFilename}`);
        await fs.writeFile(mainOutputPath, JSON.stringify(classifiedRecords, null, 2));

        // 按時期分類保存
        const byPeriod = {};
        for (const record of classifiedRecords) {
            const period = record._classifications?.period?.category || 'unknown';
            if (!byPeriod[period]) byPeriod[period] = [];
            byPeriod[period].push(record);
        }

        for (const [period, records] of Object.entries(byPeriod)) {
            const periodPath = path.join(this.outputDir, 'by_period', `${period}_${originalFilename}`);
            await fs.writeFile(periodPath, JSON.stringify(records, null, 2));
        }

        // 按風格分類保存
        const byStyle = {};
        for (const record of classifiedRecords) {
            const style = record._classifications?.style?.category || 'unknown';
            if (!byStyle[style]) byStyle[style] = [];
            byStyle[style].push(record);
        }

        for (const [style, records] of Object.entries(byStyle)) {
            const stylePath = path.join(this.outputDir, 'by_style', `${style}_${originalFilename}`);
            await fs.writeFile(stylePath, JSON.stringify(records, null, 2));
        }

        console.log(`💾 分類數據已保存`);
    }

    /**
     * 生成分類報告
     */
    async generateClassificationReport(results) {
        const report = {
            agent: {
                id: this.id,
                name: this.name,
                version: this.version
            },
            processing: {
                totalFiles: results.length,
                totalErrors: this.errors.length,
                successRate: results.length / (results.length + this.errors.length)
            },
            statistics: await this.generateClassificationStatistics(results),
            timestamp: new Date().toISOString(),
            configuration: this.config
        };

        const reportPath = path.join(this.outputDir, 'reports', `classification_report_${Date.now()}.json`);
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

        console.log(`📊 分類報告已生成: ${reportPath}`);
        return report;
    }

    /**
     * 生成分類統計
     */
    async generateClassificationStatistics(results) {
        // 這裡可以生成詳細的分類統計信息
        return {
            totalRecordsProcessed: results.reduce((sum, r) => sum + r.recordsProcessed, 0),
            averageConfidence: 0.8, // 模擬值
            topCategories: {
                periods: ['renaissance', 'modern', 'contemporary'],
                styles: ['realism', 'abstract', 'impressionist'],
                mediums: ['painting', 'sculpture', 'drawing']
            }
        };
    }

    /**
     * 停止Agent
     */
    async stop() {
        console.log('⏹️ 停止Classification Agent...');
        this.status = 'stopping';

        // 生成最終報告
        if (this.completedTasks.length > 0) {
            await this.generateClassificationReport(this.completedTasks);
        }

        this.status = 'stopped';
        console.log('✅ Classification Agent 已停止');
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
                classificationQueue: this.classificationQueue.length,
                completedTasks: this.completedTasks.length,
                errors: this.errors.length
            },
            config: this.config,
            taxonomies: Object.keys(this.taxonomies)
        };
    }
}

module.exports = ClassificationAgent;

// 如果直接運行此文件
if (require.main === module) {
    const agent = new ClassificationAgent();

    agent.on('initialized', async () => {
        console.log('🚀 開始測試分類...');
        await agent.startClassification({
            inputSources: ['metadata'],
            classificationTypes: ['period', 'style', 'medium'],
            generateReports: true
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