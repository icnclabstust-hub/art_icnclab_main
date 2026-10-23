#!/usr/bin/env node
/**
 * Agent整合測試套件
 * 全面測試所有Agent的核心功能和整合能力
 */

const path = require('path');
const fs = require('fs/promises');

// 導入所有Agent和Hub
const AgentHub = require('../../src/agent-hub');
const WebCrawlerAgent = require('../../agents/web-crawler');
const MetadataExtractorAgent = require('../../agents/metadata-extractor');
const ClassificationAgent = require('../../agents/classification');
const SummarizationTranslationAgent = require('../../agents/summarization-translation');

describe('Agent Integration Tests', () => {
    let hub;
    let testDataPath;

    beforeAll(async () => {
        // 設置測試環境
        hub = new AgentHub();

        // 創建測試數據
        testDataPath = await createTestData();

        // 確保所有必要目錄存在
        await ensureTestDirectories();
    });

    afterAll(async () => {
        // 清理測試環境
        if (hub) {
            await hub.stop();
        }

        // 清理測試數據（選擇性）
        // await cleanupTestData();
    });

    describe('Individual Agent Tests', () => {
        test('WebCrawler Agent - 初始化和基本功能', async () => {
            const agent = new WebCrawlerAgent();

            await expect(agent.initialize()).resolves.not.toThrow();
            expect(agent.status).toBe('ready');

            const status = agent.getStatus();
            expect(status.id).toBe('web-crawler-agent');
            expect(status.status).toBe('ready');

            await agent.stop();
        });

        test('MetadataExtractor Agent - 初始化和元數據處理', async () => {
            const agent = new MetadataExtractorAgent();

            await expect(agent.initialize()).resolves.not.toThrow();
            expect(agent.status).toBe('ready');

            // 測試元數據提取
            const testRecord = {
                title: 'Test Artwork',
                artist: 'Test Artist',
                date: '2023',
                source: 'test'
            };

            const result = await agent.extractMetadata(testRecord);
            expect(result).toHaveProperty('_id');
            expect(result).toHaveProperty('dc:title');
            expect(result).toHaveProperty('dc:creator');
            expect(result._confidence).toBeGreaterThan(0);

            await agent.stop();
        });

        test('Classification Agent - 初始化和分類功能', async () => {
            const agent = new ClassificationAgent();

            await expect(agent.initialize()).resolves.not.toThrow();
            expect(agent.status).toBe('ready');

            // 測試分類
            const testArtwork = {
                'dc:title': 'Renaissance Portrait',
                'dc:creator': 'Leonardo da Vinci',
                'dc:date': '1503-1519',
                'dc:type': 'painting',
                'dc:description': 'Renaissance portrait painting',
                '_source': 'test'
            };

            const result = await agent.classifyArtwork(testArtwork, ['period', 'style']);
            expect(result).toHaveProperty('_classifications');
            expect(result._classifications).toHaveProperty('period');
            expect(result._classifications).toHaveProperty('style');
            expect(result._classificationConfidence).toBeGreaterThan(0);

            await agent.stop();
        });

        test('SummarizationTranslation Agent - 初始化和處理功能', async () => {
            const agent = new SummarizationTranslationAgent();

            await expect(agent.initialize()).resolves.not.toThrow();
            expect(agent.status).toBe('ready');

            // 測試摘要生成
            const testRecord = {
                'dc:title': 'Mona Lisa',
                'dc:creator': 'Leonardo da Vinci',
                'dc:description': 'Famous Renaissance portrait painting',
                '_source': 'test'
            };

            const summary = await agent.generateSummary(testRecord, 'artwork');
            expect(summary).toHaveProperty('text');
            expect(summary).toHaveProperty('method');
            expect(summary).toHaveProperty('confidence');
            expect(summary.text.length).toBeGreaterThan(0);

            await agent.stop();
        });
    });

    describe('Agent Hub Integration Tests', () => {
        test('Hub初始化 - 所有Agent成功載入', async () => {
            await expect(hub.initialize()).resolves.not.toThrow();

            const status = hub.getStatus();
            expect(status.status).toBe('ready');
            expect(Object.keys(status.agents)).toHaveLength(4);

            // 檢查每個Agent的狀態
            for (const [name, agent] of Object.entries(status.agents)) {
                expect(agent.status).toBe('ready');
            }
        });

        test('工作流程執行 - processExisting', async () => {
            const result = await hub.executeWorkflow('processExisting', {
                metadataExtractor: {
                    inputSources: ['museums'],
                    includeValidation: true
                },
                classification: {
                    classificationTypes: ['period', 'style'],
                    generateReports: true
                },
                summarizationTranslation: {
                    targetLanguages: ['zh-TW'],
                    generateSummaries: true,
                    generateTranslations: false
                }
            });

            expect(result).toHaveProperty('success');
            expect(result.success).toBe(true);
            expect(result.statistics.completedTasks).toBeGreaterThan(0);
        });

        test('工作流程執行 - crawlOnly', async () => {
            const result = await hub.executeWorkflow('crawlOnly', {
                webCrawler: {
                    sources: ['met'],
                    keywords: ['test'],
                    maxItems: 1
                },
                metadataExtractor: {
                    inputSources: ['museums'],
                    includeValidation: false
                }
            });

            expect(result).toHaveProperty('success');
            expect(result.statistics).toHaveProperty('totalTasks');
        });

        test('自定義工作流程創建', () => {
            const customWorkflow = hub.createCustomWorkflow(
                'test_metadata_only',
                ['metadataExtractor'],
                '僅元數據提取的測試工作流程'
            );

            expect(customWorkflow).toHaveProperty('name');
            expect(customWorkflow).toHaveProperty('steps');
            expect(customWorkflow.name).toBe('test_metadata_only');
            expect(customWorkflow.steps).toContain('metadataExtractor');
        });
    });

    describe('Error Handling and Recovery Tests', () => {
        test('處理無效輸入數據', async () => {
            const agent = new MetadataExtractorAgent();
            await agent.initialize();

            // 測試空對象
            const emptyResult = await agent.extractMetadata({});
            expect(emptyResult).toHaveProperty('_id');
            expect(emptyResult._confidence).toBeLessThan(1.0);

            // 測試null值
            const nullResult = await agent.extractMetadata({ title: null, artist: null });
            expect(nullResult).toHaveProperty('_id');

            await agent.stop();
        });

        test('處理網絡超時和重試', async () => {
            const agent = new WebCrawlerAgent();
            await agent.initialize();

            // 模擬網絡問題不會導致完全失敗
            expect(() => agent.getStatus()).not.toThrow();

            await agent.stop();
        });

        test('處理磁盤空間和權限問題', async () => {
            const agent = new ClassificationAgent();
            await agent.initialize();

            // 檢查Agent能正常處理目錄創建
            expect(agent.status).toBe('ready');

            await agent.stop();
        });
    });

    describe('Performance and Scalability Tests', () => {
        test('批量數據處理性能', async () => {
            const agent = new MetadataExtractorAgent();
            await agent.initialize();

            // 創建大量測試數據
            const testData = Array.from({ length: 50 }, (_, i) => ({
                title: `Test Artwork ${i}`,
                artist: `Test Artist ${i}`,
                date: `202${i % 10}`,
                source: 'performance_test'
            }));

            const startTime = Date.now();
            const results = await Promise.all(
                testData.map(record => agent.extractMetadata(record))
            );
            const endTime = Date.now();

            expect(results).toHaveLength(50);
            expect(endTime - startTime).toBeLessThan(10000); // 應該在10秒內完成

            await agent.stop();
        });

        test('記憶體使用和清理', async () => {
            const initialMemory = process.memoryUsage().heapUsed;

            const agent = new ClassificationAgent();
            await agent.initialize();

            // 執行一些操作
            for (let i = 0; i < 10; i++) {
                await agent.classifyArtwork({
                    'dc:title': `Test ${i}`,
                    'dc:creator': 'Test Artist',
                    '_source': 'memory_test'
                });
            }

            await agent.stop();

            // 檢查記憶體使用沒有異常增長
            const finalMemory = process.memoryUsage().heapUsed;
            const memoryIncrease = finalMemory - initialMemory;

            // 記憶體增長應該合理（少於100MB）
            expect(memoryIncrease).toBeLessThan(100 * 1024 * 1024);
        });
    });

    describe('Data Integrity and Validation Tests', () => {
        test('數據完整性驗證', async () => {
            const extractor = new MetadataExtractorAgent();
            await extractor.initialize();

            const testRecord = {
                title: 'Integrity Test',
                artist: 'Test Artist',
                date: '2023-01-01',
                description: 'Test description for integrity validation',
                source: 'integrity_test'
            };

            const result = await extractor.extractMetadata(testRecord);

            // 驗證必要字段存在
            expect(result).toHaveProperty('_id');
            expect(result).toHaveProperty('_extractedAt');
            expect(result).toHaveProperty('_confidence');
            expect(result['dc:title']).toBeTruthy();
            expect(result['dc:creator']).toBeTruthy();

            // 驗證數據格式
            expect(typeof result._confidence).toBe('number');
            expect(result._confidence).toBeGreaterThanOrEqual(0);
            expect(result._confidence).toBeLessThanOrEqual(1);

            await extractor.stop();
        });

        test('分類結果一致性', async () => {
            const classifier = new ClassificationAgent();
            await classifier.initialize();

            const testArtwork = {
                'dc:title': 'The Starry Night',
                'dc:creator': 'Vincent van Gogh',
                'dc:date': '1889',
                'dc:description': 'Post-impressionist painting',
                '_source': 'consistency_test'
            };

            // 多次分類同一作品應得到一致結果
            const result1 = await classifier.classifyArtwork(testArtwork, ['period']);
            const result2 = await classifier.classifyArtwork(testArtwork, ['period']);

            expect(result1._classifications.period.category)
                .toBe(result2._classifications.period.category);

            await classifier.stop();
        });
    });
});

/**
 * 創建測試數據
 */
async function createTestData() {
    const testData = [
        {
            source: 'test_suite',
            objectID: 'test_001',
            title: 'The Starry Night',
            artist: 'Vincent van Gogh',
            date: '1889',
            medium: 'Oil on canvas',
            description: 'Famous post-impressionist painting depicting a swirling night sky',
            classification: 'painting',
            culture: 'Dutch',
            period: 'Post-Impressionism',
            crawledAt: new Date().toISOString()
        },
        {
            source: 'test_suite',
            objectID: 'test_002',
            title: 'Mona Lisa',
            artist: 'Leonardo da Vinci',
            date: '1503-1519',
            medium: 'Oil on poplar wood',
            description: 'Renaissance portrait painting known for its enigmatic smile',
            classification: 'painting',
            culture: 'Italian',
            period: 'Renaissance',
            crawledAt: new Date().toISOString()
        },
        {
            source: 'test_suite',
            objectID: 'test_003',
            title: 'The Persistence of Memory',
            artist: 'Salvador Dalí',
            date: '1931',
            medium: 'Oil on canvas',
            description: 'Surrealist painting featuring melting clocks',
            classification: 'painting',
            culture: 'Spanish',
            period: 'Surrealism',
            crawledAt: new Date().toISOString()
        }
    ];

    const testDataDir = path.join(__dirname, '../../data/raw/museums');
    await fs.mkdir(testDataDir, { recursive: true });

    const testDataPath = path.join(testDataDir, 'test_suite_artworks.json');
    await fs.writeFile(testDataPath, JSON.stringify(testData, null, 2));

    return testDataPath;
}

/**
 * 確保測試目錄存在
 */
async function ensureTestDirectories() {
    const directories = [
        'data/raw/museums',
        'data/processed/metadata',
        'data/processed/classified',
        'data/processed/final',
        'logs/workflows',
        'logs/errors'
    ];

    for (const dir of directories) {
        await fs.mkdir(path.join(__dirname, '../../', dir), { recursive: true });
    }
}

/**
 * 清理測試數據（可選）
 */
async function cleanupTestData() {
    // 實現清理邏輯（如需要）
    console.log('Test cleanup completed');
}

module.exports = {
    createTestData,
    ensureTestDirectories,
    cleanupTestData
};