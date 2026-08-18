#!/usr/bin/env node
/**
 * Metadata Extractor Agent - 元數據提取代理
 * 專責從原始數據中提取和規範化元數據，確保數據質量和一致性
 */

const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const axios = require('axios');
const UnifiedErrorHandler = require('../../src/utils/unifiedErrorHandler');

class MetadataExtractorAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'metadata-extractor-agent';
        this.name = '元數據提取代理';
        this.status = 'initializing';
        this.version = '1.0.0';

        // 配置設定
        this.config = {
            confidenceThreshold: parseFloat(process.env.METADATA_CONFIDENCE_THRESHOLD) || 0.85,
            dublinCoreValidation: process.env.DUBLIN_CORE_VALIDATION === 'true',
            batchSize: 50,
            maxFileSize: 100 * 1024 * 1024, // 100MB
        };

        // 元數據映射和規範
        this.metadataMapping = {
            // Dublin Core 標準映射
            dublinCore: {
                'dc:title': ['title', 'name', 'artwork_name'],
                'dc:creator': ['artist', 'creator', 'author', 'artistDisplayName'],
                'dc:subject': ['subject', 'topic', 'classification', 'category'],
                'dc:description': ['description', 'about', 'summary'],
                'dc:date': ['date', 'created', 'objectDate', 'creation_date'],
                'dc:type': ['type', 'medium', 'classification', 'objectName'],
                'dc:format': ['format', 'dimensions', 'size'],
                'dc:identifier': ['id', 'objectID', 'accessionNumber'],
                'dc:source': ['source', 'museum', 'collection', 'repository'],
                'dc:language': ['language', 'lang'],
                'dc:relation': ['related', 'series', 'collection'],
                'dc:coverage': ['location', 'geography', 'culture', 'period'],
                'dc:rights': ['rights', 'copyright', 'license']
            },
            // 藝術史專用字段
            artHistory: {
                'ah:style': ['style', 'movement', 'period', 'school'],
                'ah:technique': ['technique', 'method', 'medium'],
                'ah:provenance': ['provenance', 'history', 'ownership'],
                'ah:exhibition': ['exhibitions', 'displayed', 'shown'],
                'ah:attribution': ['attribution', 'attributed_to'],
                'ah:condition': ['condition', 'state', 'conservation'],
                'ah:significance': ['significance', 'importance', 'note']
            }
        };

        // 數據清理規則
        this.cleaningRules = {
            // 日期格式標準化
            datePatterns: [
                /(\d{4})-(\d{2})-(\d{2})/,  // YYYY-MM-DD
                /(\d{4})\/(\d{2})\/(\d{2})/,  // YYYY/MM/DD
                /(\d{4})\s*-\s*(\d{4})/,      // YYYY-YYYY (範圍)
                /ca?\.\s*(\d{4})/,           // ca. YYYY
                /(\d{4})\s*(CE|AD|BC|BCE)/i   // YYYY CE/AD/BC/BCE
            ],
            // 人名標準化
            artistPatterns: [
                /^(.*?),\s*(\w+\.?\s*\w*\.?)$/, // Last, First M.
                /^(.*?)\s*\(([^)]+)\)$/,        // Name (dates)
                /^(.*?),?\s*(\d{4})\s*[-–]\s*(\d{4})?/ // Name, year-year
            ],
            // 維度標準化
            dimensionPatterns: [
                /(\d+(?:\.\d+)?)\s*×\s*(\d+(?:\.\d+)?)\s*cm/, // XX × YY cm
                /(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*in/, // XX × YY in
                /H\.\s*(\d+(?:\.\d+)?),?\s*W\.\s*(\d+(?:\.\d+)?)/ // H. XX, W. YY
            ]
        };

        // 任務追蹤
        this.processingQueue = [];
        this.completedTasks = [];
        this.errors = [];

        // 輸入和輸出路徑
        this.inputDir = process.env.DATA_RAW_DIR || './data/raw';
        this.outputDir = process.env.DATA_PROCESSED_DIR || './data/processed';

        // 初始化錯誤處理器
        this.errorHandler = new UnifiedErrorHandler(this.id, {
            maxRetries: 3,
            retryDelay: 2000,
            logErrors: true,
            enableRecovery: true
        });

        console.log(`🔍 ${this.name} 初始化完成`);
    }

    /**
     * 初始化Agent
     */
    async initialize() {
        try {
            this.status = 'initializing';
            console.log('🔧 正在初始化Metadata Extractor Agent...');

            // 確保輸出目錄存在
            await this.ensureDirectories();

            // 初始化元數據驗證器
            await this.initializeValidators();

            // 測試處理能力
            await this.testProcessingCapabilities();

            this.status = 'ready';
            console.log('✅ Metadata Extractor Agent 初始化完成');
            this.emit('initialized');

        } catch (error) {
            this.status = 'error';
            console.error('❌ Metadata Extractor Agent 初始化失敗:', error.message);
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
            path.join(this.outputDir, 'metadata'),
            path.join(this.outputDir, 'cleaned'),
            path.join(this.outputDir, 'validated'),
            path.join(this.outputDir, 'reports')
        ];

        for (const dir of dirs) {
            await fs.mkdir(dir, { recursive: true });
        }

        console.log('📁 處理目錄準備完成');
    }

    /**
     * 初始化驗證器
     */
    async initializeValidators() {
        // 這裡可以初始化外部驗證服務
        console.log('🔒 元數據驗證器初始化完成');
    }

    /**
     * 測試處理能力
     */
    async testProcessingCapabilities() {
        const testData = {
            title: 'Mona Lisa',
            artist: 'Leonardo da Vinci',
            date: 'c. 1503-1519',
            source: 'test'
        };

        const processed = await this.extractMetadata(testData);
        console.log('🧪 處理能力測試通過');
    }

    /**
     * 開始元數據提取任務
     */
    async startExtraction(config = {}) {
        try {
            this.status = 'extracting';
            console.log('🚀 開始元數據提取任務...');

            const {
                inputSources = ['museums', 'academic'],
                outputFormat = 'dublin-core',
                includeValidation = true
            } = config;

            // 掃描輸入文件
            const inputFiles = await this.scanInputFiles(inputSources);
            console.log(`📄 找到 ${inputFiles.length} 個待處理文件`);

            if (inputFiles.length === 0) {
                console.log('⚠️ 沒有找到待處理的文件');
                return [];
            }

            // 處理文件
            const results = await this.processFiles(inputFiles, outputFormat, includeValidation);

            this.status = 'completed';
            console.log(`✅ 元數據提取完成，處理了 ${results.length} 個文件`);

            this.emit('extractionComplete', {
                filesProcessed: results.length,
                errors: this.errors.length,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            console.error('❌ 元數據提取任務失敗:', error.message);
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
                    const stats = await fs.stat(filePath);

                    if (stats.size <= this.config.maxFileSize) {
                        files.push({
                            path: filePath,
                            source: source,
                            filename: file,
                            size: stats.size,
                            modified: stats.mtime
                        });
                    } else {
                        console.warn(`⚠️ 文件過大，跳過: ${file} (${stats.size} bytes)`);
                    }
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
    async processFiles(files, outputFormat, includeValidation) {
        const results = [];

        // 分批處理
        for (let i = 0; i < files.length; i += this.config.batchSize) {
            const batch = files.slice(i, i + this.config.batchSize);

            console.log(`🔄 處理批次 ${Math.floor(i/this.config.batchSize) + 1}/${Math.ceil(files.length/this.config.batchSize)}`);

            for (const file of batch) {
                try {
                    const result = await this.processFile(file, outputFormat, includeValidation);
                    if (result) {
                        results.push(result);
                    }
                } catch (error) {
                    console.error(`❌ 處理文件失敗 ${file.filename}:`, error.message);
                    this.errors.push({
                        file: file.filename,
                        error: error.message,
                        timestamp: new Date()
                    });
                }
            }
        }

        return results;
    }

    /**
     * 處理單個文件
     */
    async processFile(file, outputFormat, includeValidation) {
        console.log(`📝 處理文件: ${file.filename}`);

        return await this.errorHandler.wrapAsync(async () => {
            // 讀取原始數據
            const rawData = await fs.readFile(file.path, 'utf8');
            const jsonData = JSON.parse(rawData);

            if (!Array.isArray(jsonData)) {
                throw new Error('數據格式錯誤：期望數組格式');
            }

            // 並行處理每個記錄 - 使用性能優化器
            const processedRecords = await this.performanceOptimizer.processParallel(
                jsonData,
                async (record) => {
                    const extractedMetadata = await this.extractMetadata(record);

                    if (includeValidation) {
                        const validationResult = await this.validateMetadata(extractedMetadata);
                        extractedMetadata._validation = validationResult;
                    }

                    return extractedMetadata;
                },
                {
                    concurrency: Math.min(4, jsonData.length),
                    enableProgress: false
                }
            );

            // 保存處理後的數據
            const outputFilename = `processed_${file.filename}`;
            const outputPath = path.join(this.outputDir, 'metadata', outputFilename);

            await fs.writeFile(outputPath, JSON.stringify(processedRecords, null, 2), 'utf8');

            console.log(`💾 處理完成: ${outputFilename} (${processedRecords.length} 記錄)`);

            return {
                inputFile: file.filename,
                outputFile: outputFilename,
                recordsProcessed: processedRecords.length,
                outputPath: outputPath,
                processedAt: new Date().toISOString()
            };

        }, `處理文件 ${file.filename}`, { maxRetries: 2 });
    }

    /**
     * 提取和標準化元數據
     */
    async extractMetadata(record) {
        let metadata = {
            // 基本信息
            _id: this.generateId(record),
            _source: record.source || 'unknown',
            _extractedAt: new Date().toISOString(),
            _confidence: 1.0
        };

        // 映射Dublin Core字段
        for (const [dcField, sourceFields] of Object.entries(this.metadataMapping.dublinCore)) {
            const value = this.findValueByFields(record, sourceFields);
            if (value) {
                metadata[dcField] = this.cleanValue(value, dcField);
            }
        }

        // 映射藝術史專用字段
        for (const [ahField, sourceFields] of Object.entries(this.metadataMapping.artHistory)) {
            const value = this.findValueByFields(record, sourceFields);
            if (value) {
                metadata[ahField] = this.cleanValue(value, ahField);
            }
        }

        // 特殊處理
        metadata = await this.applySpecialProcessing(metadata, record);

        // 計算置信度
        metadata._confidence = this.calculateConfidence(metadata);

        return metadata;
    }

    /**
     * 根據字段列表查找值
     */
    findValueByFields(record, fields) {
        for (const field of fields) {
            if (record[field] !== undefined && record[field] !== null && record[field] !== '') {
                return record[field];
            }
        }
        return null;
    }

    /**
     * 清理和標準化值
     */
    cleanValue(value, fieldType) {
        if (!value) return null;

        let cleaned = value;

        // 基本清理
        if (typeof cleaned === 'string') {
            cleaned = cleaned.trim();
            cleaned = cleaned.replace(/\s+/g, ' '); // 合併多個空格
            cleaned = cleaned.replace(/[\r\n\t]/g, ' '); // 移除換行和制表符
        }

        // 根據字段類型進行特殊處理
        switch (fieldType) {
            case 'dc:date':
                return this.standardizeDate(cleaned);
            case 'dc:creator':
                return this.standardizeArtistName(cleaned);
            case 'dc:format':
                return this.standardizeDimensions(cleaned);
            case 'dc:subject':
                return this.standardizeSubjects(cleaned);
            default:
                return cleaned;
        }
    }

    /**
     * 標準化日期
     */
    standardizeDate(dateString) {
        if (!dateString) return null;

        const str = dateString.toString();

        // 嘗試各種日期格式
        for (const pattern of this.cleaningRules.datePatterns) {
            const match = str.match(pattern);
            if (match) {
                if (match[2] && match[3]) {
                    // 完整日期 YYYY-MM-DD
                    return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
                } else if (match[2]) {
                    // 年份範圍 YYYY-YYYY
                    return `${match[1]}-${match[2]}`;
                } else {
                    // 單一年份
                    return match[1];
                }
            }
        }

        // 如果沒有匹配，保持原始值
        return str;
    }

    /**
     * 標準化藝術家姓名
     */
    standardizeArtistName(name) {
        if (!name) return null;

        let cleaned = name.toString().trim();

        // 移除括號中的日期信息（保存到另一個字段）
        const dateMatch = cleaned.match(/^(.*?)\s*\(([^)]+)\)$/);
        if (dateMatch) {
            cleaned = dateMatch[1].trim();
            // 可以返回包含生卒年的對象
            return {
                name: cleaned,
                dates: dateMatch[2]
            };
        }

        // 處理 "Last, First" 格式
        const nameMatch = cleaned.match(/^(.*?),\s*(.+)$/);
        if (nameMatch) {
            const lastName = nameMatch[1].trim();
            const firstName = nameMatch[2].trim();
            return `${firstName} ${lastName}`;
        }

        return cleaned;
    }

    /**
     * 標準化尺寸信息
     */
    standardizeDimensions(dimensions) {
        if (!dimensions) return null;

        const str = dimensions.toString();

        // 嘗試各種尺寸格式
        for (const pattern of this.cleaningRules.dimensionPatterns) {
            const match = str.match(pattern);
            if (match) {
                return {
                    width: parseFloat(match[1]),
                    height: parseFloat(match[2]),
                    unit: str.includes('cm') ? 'cm' : 'in',
                    original: str
                };
            }
        }

        return str;
    }

    /**
     * 標準化主題標籤
     */
    standardizeSubjects(subjects) {
        if (!subjects) return null;

        if (Array.isArray(subjects)) {
            return subjects.map(s => s.toString().trim().toLowerCase());
        }

        if (typeof subjects === 'string') {
            return subjects.split(/[,;]/).map(s => s.trim().toLowerCase()).filter(Boolean);
        }

        return [subjects.toString().trim().toLowerCase()];
    }

    /**
     * 特殊處理規則
     */
    async applySpecialProcessing(metadata, originalRecord) {
        // 生成縮略圖URL（如果有原圖）
        if (originalRecord.primaryImage) {
            metadata['dc:relation'] = {
                type: 'thumbnail',
                url: originalRecord.primaryImage
            };
        }

        // 地理位置標準化
        if (originalRecord.culture || originalRecord.geography) {
            metadata['dc:coverage'] = this.standardizeGeography(
                originalRecord.culture,
                originalRecord.geography
            );
        }

        // 材料和技法分析
        if (originalRecord.medium) {
            const materials = this.extractMaterials(originalRecord.medium);
            if (materials.length > 0) {
                metadata['ah:materials'] = materials;
            }
        }

        return metadata;
    }

    /**
     * 標準化地理信息
     */
    standardizeGeography(culture, geography) {
        const locations = [];

        if (culture) {
            locations.push({ type: 'culture', value: culture });
        }

        if (geography) {
            locations.push({ type: 'geography', value: geography });
        }

        return locations;
    }

    /**
     * 提取材料信息
     */
    extractMaterials(mediumText) {
        if (!mediumText) return [];

        const materials = [];
        const commonMaterials = [
            'oil', 'canvas', 'wood', 'paper', 'bronze', 'marble',
            'tempera', 'fresco', 'watercolor', 'ink', 'gold', 'silver'
        ];

        const text = mediumText.toLowerCase();
        for (const material of commonMaterials) {
            if (text.includes(material)) {
                materials.push(material);
            }
        }

        return materials;
    }

    /**
     * 計算元數據置信度
     */
    calculateConfidence(metadata) {
        let score = 0;
        let maxScore = 0;

        // 必需字段權重
        const requiredFields = {
            'dc:title': 0.3,
            'dc:creator': 0.25,
            'dc:date': 0.2,
            'dc:type': 0.1,
            'dc:source': 0.15
        };

        for (const [field, weight] of Object.entries(requiredFields)) {
            maxScore += weight;
            if (metadata[field] && metadata[field] !== null) {
                if (typeof metadata[field] === 'string' && metadata[field].length > 0) {
                    score += weight;
                } else if (typeof metadata[field] === 'object') {
                    score += weight;
                }
            }
        }

        return Math.round((score / maxScore) * 100) / 100;
    }

    /**
     * 驗證元數據
     */
    async validateMetadata(metadata) {
        const validation = {
            isValid: true,
            errors: [],
            warnings: [],
            score: 1.0
        };

        // Dublin Core必需字段檢查
        const requiredFields = ['dc:title', 'dc:creator', 'dc:source'];
        for (const field of requiredFields) {
            if (!metadata[field]) {
                validation.errors.push(`缺少必需字段: ${field}`);
                validation.isValid = false;
            }
        }

        // 置信度檢查
        if (metadata._confidence < this.config.confidenceThreshold) {
            validation.warnings.push(`置信度低於閾值: ${metadata._confidence} < ${this.config.confidenceThreshold}`);
        }

        // 日期格式驗證
        if (metadata['dc:date']) {
            const dateValid = this.validateDate(metadata['dc:date']);
            if (!dateValid) {
                validation.warnings.push('日期格式可能不正確');
            }
        }

        validation.score = validation.isValid ?
            (validation.warnings.length > 0 ? 0.8 : 1.0) : 0.0;

        return validation;
    }

    /**
     * 日期驗證
     */
    validateDate(dateValue) {
        if (!dateValue) return false;

        const dateStr = dateValue.toString();

        // 檢查基本格式
        const basicPatterns = [
            /^\d{4}$/,                    // YYYY
            /^\d{4}-\d{4}$/,              // YYYY-YYYY
            /^\d{4}-\d{2}-\d{2}$/,        // YYYY-MM-DD
            /^ca?\.\s*\d{4}$/             // ca. YYYY
        ];

        return basicPatterns.some(pattern => pattern.test(dateStr));
    }

    /**
     * 生成唯一ID
     */
    generateId(record) {
        if (record.objectID || record.id) {
            return `${record.source || 'unknown'}_${record.objectID || record.id}`;
        }

        // 基於內容生成ID
        const crypto = require('crypto');
        const content = `${record.title || ''}_${record.artist || ''}_${record.source || ''}`;
        return crypto.createHash('md5').update(content).digest('hex').substring(0, 16);
    }

    /**
     * 生成處理報告
     */
    async generateReport() {
        const report = {
            agent: {
                id: this.id,
                name: this.name,
                version: this.version
            },
            processing: {
                totalFiles: this.completedTasks.length,
                totalErrors: this.errors.length,
                successRate: this.completedTasks.length / (this.completedTasks.length + this.errors.length)
            },
            timestamp: new Date().toISOString(),
            configuration: this.config
        };

        const reportPath = path.join(this.outputDir, 'reports', `metadata_extraction_report_${Date.now()}.json`);
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

        console.log(`📊 處理報告已生成: ${reportPath}`);
        return report;
    }

    /**
     * 停止Agent
     */
    async stop() {
        console.log('⏹️ 停止Metadata Extractor Agent...');
        this.status = 'stopping';

        // 生成最終報告
        if (this.completedTasks.length > 0) {
            await this.generateReport();
        }

        this.status = 'stopped';
        console.log('✅ Metadata Extractor Agent 已停止');
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
            config: this.config
        };
    }
}

module.exports = MetadataExtractorAgent;

// 如果直接運行此文件
if (require.main === module) {
    const agent = new MetadataExtractorAgent();

    agent.on('initialized', async () => {
        console.log('🚀 開始測試元數據提取...');
        await agent.startExtraction({
            inputSources: ['museums'],
            outputFormat: 'dublin-core',
            includeValidation: true
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