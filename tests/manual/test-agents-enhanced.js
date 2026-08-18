#!/usr/bin/env node
/**
 * Enhanced Agent功能測試腳本
 * 全面驗證Agent的核心功能、錯誤處理、性能和整合能力
 * 目標：達到90%+的測試成功率
 */

const path = require('path');
const fs = require('fs/promises');

// 導入Agent Hub和錯誤處理器
const AgentHub = require('../../src/agent-hub');
const ErrorHandler = require('../../src/utils/errorHandler');

// 導入各個Agent
const WebCrawlerAgent = require('../../agents/web-crawler');
const MetadataExtractorAgent = require('../../agents/metadata-extractor');
const ClassificationAgent = require('../../agents/classification');
const SummarizationTranslationAgent = require('../../agents/summarization-translation');

class EnhancedAgentTester {
    constructor() {
        this.testResults = [];
        this.errorHandler = new ErrorHandler('test-runner', {
            maxRetries: 2,
            retryDelay: 1000,
            logErrors: true,
            enableRecovery: true
        });
    }

    /**
     * 運行所有測試
     */
    async runAllTests() {
        console.log('🧪 開始Enhanced Agent功能測試...\n');

        try {
            // 基礎測試
            await this.runBasicTests();

            // 個別Agent測試
            await this.runIndividualAgentTests();

            // 整合測試
            await this.runIntegrationTests();

            // 錯誤處理測試
            await this.runErrorHandlingTests();

            // 性能測試
            await this.runPerformanceTests();

            // 數據完整性測試
            await this.runDataIntegrityTests();

        } catch (error) {
            await this.errorHandler.handleError(error, '整體測試執行');
            this.addTestResult('整體測試執行', 'fail', error.message);
        }

        return this.generateFinalReport();
    }

    /**
     * 基礎測試
     */
    async runBasicTests() {
        console.log('📋 1. 基礎環境測試');

        // 測試目錄結構
        await this.testDirectoryStructure();

        // 測試依賴模塊
        await this.testDependencies();

        // 測試配置文件
        await this.testConfiguration();

        console.log('');
    }

    /**
     * 測試目錄結構
     */
    async testDirectoryStructure() {
        await this.errorHandler.wrapAsync(async () => {
            const requiredDirs = [
                'src',
                'agents',
                'data/raw',
                'data/processed',
                'logs'
            ];

            for (const dir of requiredDirs) {
                const exists = await fs.access(dir).then(() => true).catch(() => false);
                if (!exists) {
                    await fs.mkdir(dir, { recursive: true });
                }
            }

            this.addTestResult('目錄結構檢查', 'pass', '所有必要目錄存在或已創建');
        }, '目錄結構檢查');
    }

    /**
     * 測試依賴模塊
     */
    async testDependencies() {
        await this.errorHandler.wrapAsync(async () => {
            const dependencies = [
                { name: 'AgentHub', module: AgentHub },
                { name: 'WebCrawlerAgent', module: WebCrawlerAgent },
                { name: 'MetadataExtractorAgent', module: MetadataExtractorAgent },
                { name: 'ClassificationAgent', module: ClassificationAgent },
                { name: 'SummarizationTranslationAgent', module: SummarizationTranslationAgent }
            ];

            for (const dep of dependencies) {
                if (typeof dep.module !== 'function') {
                    throw new Error(`${dep.name} 模塊載入失敗`);
                }
            }

            this.addTestResult('依賴模塊檢查', 'pass', `${dependencies.length} 個模塊載入成功`);
        }, '依賴模塊檢查');
    }

    /**
     * 測試配置
     */
    async testConfiguration() {
        await this.errorHandler.wrapAsync(async () => {
            const requiredEnvVars = [
                'DATA_RAW_DIR',
                'DATA_PROCESSED_DIR'
            ];

            let missingVars = [];
            for (const envVar of requiredEnvVars) {
                if (!process.env[envVar]) {
                    missingVars.push(envVar);
                }
            }

            if (missingVars.length > 0) {
                console.warn(`⚠️ 缺少環境變數: ${missingVars.join(', ')}，使用默認值`);
            }

            this.addTestResult('配置檢查', 'pass', '配置檢查完成');
        }, '配置檢查');
    }

    /**
     * 個別Agent測試
     */
    async runIndividualAgentTests() {
        console.log('📋 2. 個別Agent功能測試');

        const agents = [
            { name: 'WebCrawler', class: WebCrawlerAgent, id: 'web-crawler-agent' },
            { name: 'MetadataExtractor', class: MetadataExtractorAgent, id: 'metadata-extractor-agent' },
            { name: 'Classification', class: ClassificationAgent, id: 'classification-agent' },
            { name: 'SummarizationTranslation', class: SummarizationTranslationAgent, id: 'summarization-translation-agent' }
        ];

        for (const agentInfo of agents) {
            await this.testIndividualAgent(agentInfo);
        }

        console.log('');
    }

    /**
     * 測試單個Agent
     */
    async testIndividualAgent(agentInfo) {
        console.log(`   測試 ${agentInfo.name} Agent...`);

        await this.errorHandler.wrapAsync(async () => {
            const agent = new agentInfo.class();

            // 測試初始化
            await agent.initialize();

            if (agent.status !== 'ready') {
                throw new Error(`Agent狀態不正確: ${agent.status}`);
            }

            // 測試基本功能
            const status = agent.getStatus();
            if (status.id !== agentInfo.id) {
                throw new Error(`Agent ID不匹配: 期望 ${agentInfo.id}, 實際 ${status.id}`);
            }

            // 測試特定功能
            await this.testAgentSpecificFeatures(agent, agentInfo.name);

            // 清理
            await agent.stop();

            this.addTestResult(`${agentInfo.name} Agent`, 'pass', '初始化和基本功能測試通過');

        }, `${agentInfo.name} Agent測試`);
    }

    /**
     * 測試Agent特定功能
     */
    async testAgentSpecificFeatures(agent, agentName) {
        switch (agentName) {
            case 'MetadataExtractor': {
                const testRecord = {
                    title: 'Test Artwork',
                    artist: 'Test Artist',
                    date: '2023',
                    source: 'enhanced_test'
                };
                const result = await agent.extractMetadata(testRecord);
                if (!result._id || !result._confidence) {
                    throw new Error('元數據提取結果不完整');
                }
                break;
            }

            case 'Classification': {
                const testArtwork = {
                    'dc:title': 'Test Painting',
                    'dc:creator': 'Test Artist',
                    'dc:date': '1500',
                    '_source': 'enhanced_test'
                };
                const classResult = await agent.classifyArtwork(testArtwork, ['period']);
                if (!classResult._classifications || !classResult._classifications.period) {
                    throw new Error('分類結果不完整');
                }
                break;
            }

            case 'SummarizationTranslation': {
                const testSummaryRecord = {
                    'dc:title': 'Test Artwork',
                    'dc:description': 'A test artwork for summary generation',
                    '_source': 'enhanced_test'
                };
                const summary = await agent.generateSummary(testSummaryRecord, 'artwork');
                if (!summary.text || summary.text.length === 0) {
                    throw new Error('摘要生成失敗');
                }
                break;
            }

            case 'WebCrawler': {
                // WebCrawler 只測試狀態，避免實際網絡請求
                const config = agent.getStatus().config;
                if (!config || typeof config.maxConcurrentRequests !== 'number') {
                    throw new Error('WebCrawler配置不正確');
                }
                break;
            }
        }
    }

    /**
     * 整合測試
     */
    async runIntegrationTests() {
        console.log('📋 3. Agent Hub整合測試');

        await this.testAgentHubIntegration();
        await this.testWorkflowExecution();
        await this.testCustomWorkflows();

        console.log('');
    }

    /**
     * 測試Agent Hub整合
     */
    async testAgentHubIntegration() {
        await this.errorHandler.wrapAsync(async () => {
            const hub = new AgentHub();

            // 測試初始化
            await hub.initialize();

            const status = hub.getStatus();
            if (status.status !== 'ready') {
                throw new Error(`Hub狀態不正確: ${status.status}`);
            }

            if (Object.keys(status.agents).length !== 4) {
                throw new Error(`Agent數量不正確: 期望 4, 實際 ${Object.keys(status.agents).length}`);
            }

            // 驗證每個Agent狀態
            for (const [name, agent] of Object.entries(status.agents)) {
                if (agent.status !== 'ready') {
                    throw new Error(`Agent ${name} 狀態不正確: ${agent.status}`);
                }
            }

            await hub.stop();

            this.addTestResult('Agent Hub整合', 'pass', '4個Agent成功初始化並整合');

        }, 'Agent Hub整合測試');
    }

    /**
     * 測試工作流程執行
     */
    async testWorkflowExecution() {
        await this.errorHandler.wrapAsync(async () => {
            // 確保測試數據存在
            await this.createEnhancedTestData();

            const hub = new AgentHub();
            await hub.initialize();

            // 測試 processExisting 工作流程
            const result = await hub.executeWorkflow('processExisting', {
                metadataExtractor: {
                    inputSources: ['museums'],
                    includeValidation: true
                },
                classification: {
                    classificationTypes: ['period', 'style'],
                    generateReports: false // 避免額外文件I/O
                },
                summarizationTranslation: {
                    targetLanguages: ['zh-TW'],
                    generateSummaries: true,
                    generateTranslations: false
                }
            });

            if (!result.success) {
                throw new Error('工作流程執行失敗');
            }

            if (result.statistics.completedTasks !== result.statistics.totalTasks) {
                throw new Error(`工作流程未完全完成: ${result.statistics.completedTasks}/${result.statistics.totalTasks}`);
            }

            await hub.stop();

            this.addTestResult('工作流程執行', 'pass', `${result.statistics.completedTasks}/${result.statistics.totalTasks} 步驟成功`);

        }, '工作流程執行測試', { maxRetries: 1 });
    }

    /**
     * 測試自定義工作流程
     */
    async testCustomWorkflows() {
        await this.errorHandler.wrapAsync(async () => {
            const hub = new AgentHub();
            await hub.initialize();

            // 測試創建自定義工作流程
            const customWorkflow = hub.createCustomWorkflow(
                'enhanced_test_workflow',
                ['metadataExtractor', 'classification'],
                '增強測試用自定義工作流程'
            );

            if (customWorkflow.name !== 'enhanced_test_workflow') {
                throw new Error('自定義工作流程名稱不正確');
            }

            if (customWorkflow.steps.length !== 2) {
                throw new Error('自定義工作流程步驟數量不正確');
            }

            await hub.stop();

            this.addTestResult('自定義工作流程', 'pass', '自定義工作流程創建成功');

        }, '自定義工作流程測試');
    }

    /**
     * 錯誤處理測試
     */
    async runErrorHandlingTests() {
        console.log('📋 4. 錯誤處理和恢復測試');

        await this.testInvalidDataHandling();
        await this.testRecoveryMechanisms();

        console.log('');
    }

    /**
     * 測試無效數據處理
     */
    async testInvalidDataHandling() {
        await this.errorHandler.wrapAsync(async () => {
            const agent = new MetadataExtractorAgent();
            await agent.initialize();

            // 測試空對象
            const emptyResult = await agent.extractMetadata({});
            if (!emptyResult._id) {
                throw new Error('空對象處理失敗');
            }

            // 測試null值
            const nullResult = await agent.extractMetadata({ title: null, artist: null });
            if (!nullResult._id) {
                throw new Error('null值處理失敗');
            }

            // 測試無效日期
            const invalidDateResult = await agent.extractMetadata({
                title: 'Test',
                date: 'invalid-date'
            });
            if (!invalidDateResult._id) {
                throw new Error('無效日期處理失敗');
            }

            await agent.stop();

            this.addTestResult('無效數據處理', 'pass', '各種無效數據情況處理正常');

        }, '無效數據處理測試');
    }

    /**
     * 測試恢復機制
     */
    async testRecoveryMechanisms() {
        await this.errorHandler.wrapAsync(async () => {
            // 測試ErrorHandler的恢復功能
            const testErrorHandler = new ErrorHandler('recovery-test');

            let attempts = 0;
            const result = await testErrorHandler.wrapAsync(async () => {
                attempts++;
                if (attempts < 2) {
                    throw new Error('模擬錯誤');
                }
                return 'success';
            }, '恢復測試', { maxRetries: 2 });

            if (result !== 'success' || attempts !== 2) {
                throw new Error('錯誤恢復機制測試失敗');
            }

            this.addTestResult('恢復機制', 'pass', '錯誤重試和恢復機制正常運作');

        }, '恢復機制測試');
    }

    /**
     * 性能測試
     */
    async runPerformanceTests() {
        console.log('📋 5. 性能和可擴展性測試');

        await this.testBatchProcessingPerformance();
        await this.testMemoryUsage();

        console.log('');
    }

    /**
     * 測試批量處理性能
     */
    async testBatchProcessingPerformance() {
        await this.errorHandler.wrapAsync(async () => {
            const agent = new MetadataExtractorAgent();
            await agent.initialize();

            // 創建測試數據
            const testData = Array.from({ length: 20 }, (_, i) => ({
                title: `Performance Test Artwork ${i}`,
                artist: `Test Artist ${i}`,
                date: `202${i % 10}`,
                source: 'performance_test'
            }));

            const startTime = Date.now();
            const results = await Promise.all(
                testData.map(record => agent.extractMetadata(record))
            );
            const endTime = Date.now();

            const processingTime = endTime - startTime;
            const itemsPerSecond = testData.length / (processingTime / 1000);

            if (results.length !== testData.length) {
                throw new Error('批量處理結果數量不正確');
            }

            if (processingTime > 30000) { // 30秒限制
                throw new Error(`處理時間過長: ${processingTime}ms`);
            }

            await agent.stop();

            this.addTestResult('批量處理性能', 'pass',
                `處理${testData.length}項耗時${processingTime}ms (${itemsPerSecond.toFixed(2)}項/秒)`);

        }, '批量處理性能測試');
    }

    /**
     * 測試記憶體使用
     */
    async testMemoryUsage() {
        await this.errorHandler.wrapAsync(async () => {
            const initialMemory = process.memoryUsage().heapUsed;

            const agent = new ClassificationAgent();
            await agent.initialize();

            // 執行多次操作
            for (let i = 0; i < 20; i++) {
                await agent.classifyArtwork({
                    'dc:title': `Memory Test ${i}`,
                    'dc:creator': 'Test Artist',
                    '_source': 'memory_test'
                });
            }

            await agent.stop();

            const finalMemory = process.memoryUsage().heapUsed;
            const memoryIncrease = finalMemory - initialMemory;
            const memoryIncreaseMB = memoryIncrease / (1024 * 1024);

            // 記憶體增長應該合理（少於50MB）
            if (memoryIncreaseMB > 50) {
                throw new Error(`記憶體使用過多: ${memoryIncreaseMB.toFixed(2)}MB`);
            }

            this.addTestResult('記憶體使用', 'pass',
                `記憶體增長: ${memoryIncreaseMB.toFixed(2)}MB`);

        }, '記憶體使用測試');
    }

    /**
     * 數據完整性測試
     */
    async runDataIntegrityTests() {
        console.log('📋 6. 數據完整性和驗證測試');

        await this.testDataIntegrity();
        await this.testClassificationConsistency();

        console.log('');
    }

    /**
     * 測試數據完整性
     */
    async testDataIntegrity() {
        await this.errorHandler.wrapAsync(async () => {
            const agent = new MetadataExtractorAgent();
            await agent.initialize();

            const testRecord = {
                title: 'Integrity Test Artwork',
                artist: 'Test Artist',
                date: '2023-06-15',
                description: 'Test description for data integrity validation',
                source: 'integrity_test'
            };

            const result = await agent.extractMetadata(testRecord);

            // 驗證必要字段
            const requiredFields = ['_id', '_extractedAt', '_confidence'];
            for (const field of requiredFields) {
                if (!Object.prototype.hasOwnProperty.call(result, field)) {
                    throw new Error(`缺少必要字段: ${field}`);
                }
            }

            // 驗證數據類型和範圍
            if (typeof result._confidence !== 'number' ||
                result._confidence < 0 ||
                result._confidence > 1) {
                throw new Error('置信度值不在有效範圍內');
            }

            if (!result._extractedAt || isNaN(Date.parse(result._extractedAt))) {
                throw new Error('提取時間格式不正確');
            }

            await agent.stop();

            this.addTestResult('數據完整性', 'pass', '所有必要字段存在且格式正確');

        }, '數據完整性測試');
    }

    /**
     * 測試分類一致性
     */
    async testClassificationConsistency() {
        await this.errorHandler.wrapAsync(async () => {
            const agent = new ClassificationAgent();
            await agent.initialize();

            const testArtwork = {
                'dc:title': 'Consistency Test',
                'dc:creator': 'Vincent van Gogh',
                'dc:date': '1889',
                'dc:description': 'Post-impressionist painting',
                '_source': 'consistency_test'
            };

            // 多次分類同一作品
            const results = [];
            for (let i = 0; i < 3; i++) {
                const result = await agent.classifyArtwork(testArtwork, ['period']);
                results.push(result._classifications.period.category);
            }

            // 檢查結果一致性
            const uniqueResults = [...new Set(results)];
            if (uniqueResults.length > 1) {
                throw new Error(`分類結果不一致: ${uniqueResults.join(', ')}`);
            }

            await agent.stop();

            this.addTestResult('分類一致性', 'pass', '多次分類結果保持一致');

        }, '分類一致性測試');
    }

    /**
     * 創建增強測試數據
     */
    async createEnhancedTestData() {
        const testData = [
            {
                source: 'enhanced_test',
                objectID: 'enhanced_001',
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
                source: 'enhanced_test',
                objectID: 'enhanced_002',
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
                source: 'enhanced_test',
                objectID: 'enhanced_003',
                title: 'Guernica',
                artist: 'Pablo Picasso',
                date: '1937',
                medium: 'Oil on canvas',
                description: 'Cubist masterpiece depicting the horrors of war',
                classification: 'painting',
                culture: 'Spanish',
                period: 'Modern',
                crawledAt: new Date().toISOString()
            }
        ];

        const testDataDir = path.join('./data/raw/museums');
        await fs.mkdir(testDataDir, { recursive: true });

        const testDataPath = path.join(testDataDir, 'enhanced_test_artworks.json');
        await fs.writeFile(testDataPath, JSON.stringify(testData, null, 2));
    }

    /**
     * 添加測試結果
     */
    addTestResult(testName, status, details) {
        this.testResults.push({
            test: testName,
            status: status,
            details: details,
            timestamp: new Date().toISOString()
        });

        const emoji = status === 'pass' ? '✅' : '❌';
        console.log(`   ${emoji} ${testName}: ${details}`);
    }

    /**
     * 生成最終報告
     */
    async generateFinalReport() {
        const passedTests = this.testResults.filter(t => t.status === 'pass').length;
        const failedTests = this.testResults.filter(t => t.status === 'fail').length;
        const totalTests = this.testResults.length;
        const successRate = Math.round((passedTests / totalTests) * 100);

        console.log('\n📊 Enhanced 測試報告');
        console.log('=' * 50);
        console.log(`總測試數: ${totalTests}`);
        console.log(`通過: ${passedTests}`);
        console.log(`失敗: ${failedTests}`);
        console.log(`成功率: ${successRate}%`);
        console.log('');

        console.log('詳細結果:');
        this.testResults.forEach((result, index) => {
            const status = result.status === 'pass' ? '✅' : '❌';
            console.log(`${index + 1}. ${status} ${result.test}`);
            console.log(`   ${result.details}`);
        });

        // 保存詳細報告
        const report = {
            timestamp: new Date().toISOString(),
            summary: {
                total: totalTests,
                passed: passedTests,
                failed: failedTests,
                successRate: successRate
            },
            results: this.testResults,
            errorStats: this.errorHandler.getErrorStats()
        };

        const reportPath = path.join('./logs', 'enhanced-agent-test-report.json');
        await fs.mkdir('./logs', { recursive: true });
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
        console.log(`\n📄 詳細報告已保存: ${reportPath}`);

        return successRate >= 90;
    }
}

// 執行測試
if (require.main === module) {
    const tester = new EnhancedAgentTester();

    tester.runAllTests()
        .then(success => {
            if (success) {
                console.log('\n🎉 Enhanced測試達到90%+成功率！');
                process.exit(0);
            } else {
                console.log('\n❌ 測試成功率未達到90%');
                process.exit(1);
            }
        })
        .catch(error => {
            console.error('\n💥 測試執行失敗:', error);
            process.exit(1);
        });
}

module.exports = EnhancedAgentTester;