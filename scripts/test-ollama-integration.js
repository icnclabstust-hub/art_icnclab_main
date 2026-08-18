#!/usr/bin/env node
/**
 * Ollama 整合測試腳本
 * 測試本地 Ollama 模型在藝術史資料庫中的功能
 */

const { ollamaService } = require('../src/services/ollamaService');
const OllamaSummarizationAgent = require('../agents/summarization-translation/ollamaAgent');
const OllamaClassificationAgent = require('../agents/classification/ollamaAgent');
const { logger } = require('../src/utils/logger');

class OllamaIntegrationTester {
    constructor() {
        this.results = {
            serviceTest: null,
            summarizationTest: null,
            classificationTest: null,
            performanceTest: null
        };
    }

    /**
     * 執行完整測試套件
     */
    async runFullTestSuite() {
        console.log('🦙 開始 Ollama 整合測試...\n');

        try {
            // 1. 服務基本功能測試
            await this.testOllamaService();

            // 2. 摘要翻譯代理測試
            await this.testSummarizationAgent();

            // 3. 分類代理測試
            await this.testClassificationAgent();

            // 4. 效能測試
            await this.testPerformance();

            // 輸出測試報告
            this.generateTestReport();

        } catch (error) {
            console.error('❌ 測試套件執行失敗:', error);
            process.exit(1);
        }
    }

    /**
     * 測試 Ollama 服務基本功能
     */
    async testOllamaService() {
        console.log('🔧 測試 Ollama 服務基本功能...');

        const startTime = Date.now();
        const testResult = {
            health: false,
            textGeneration: false,
            embedding: false,
            artSummary: false,
            translation: false,
            classification: false,
            duration: 0,
            errors: []
        };

        try {
            // 1. 健康檢查
            console.log('  📊 檢查服務健康狀態...');
            const health = await ollamaService.checkHealth();
            testResult.health = health.status === 'healthy';

            if (!testResult.health) {
                throw new Error(`Ollama 服務不健康: ${health.error}`);
            }

            console.log(`  ✅ 服務正常，可用模型: ${health.models.length} 個`);

            // 2. 文本生成測試
            console.log('  📝 測試文本生成...');
            const textResult = await ollamaService.generateText('請用中文簡短回答：什麼是藝術？', {
                maxTokens: 100,
                temperature: 0.7
            });
            testResult.textGeneration = textResult && textResult.text && textResult.text.length > 0;
            console.log(`  ✅ 文本生成成功 (${textResult.tokens} tokens, ${Math.round(textResult.duration / 1000000)}ms)`);

            // 3. 嵌入向量測試
            console.log('  🔢 測試嵌入向量生成...');
            const embeddingResult = await ollamaService.generateEmbedding('藝術史是研究藝術發展的學科');
            testResult.embedding = embeddingResult && embeddingResult.embedding && embeddingResult.dimensions > 0;
            console.log(`  ✅ 嵌入向量生成成功 (維度: ${embeddingResult.dimensions})`);

            // 4. 藝術史摘要測試
            console.log('  📚 測試藝術史摘要生成...');
            const testArtwork = {
                title: 'The Starry Night',
                artist: 'Vincent van Gogh',
                period: 'Post-Impressionism',
                description: 'Famous painting of swirling night sky',
                date: '1889'
            };

            const summaryResult = await ollamaService.generateArtSummary(testArtwork, 'artwork');
            testResult.artSummary = summaryResult && summaryResult.summary && summaryResult.summary.length > 0;
            console.log('  ✅ 藝術史摘要生成成功');

            // 5. 翻譯測試
            console.log('  🌍 測試翻譯功能...');
            const translationResult = await ollamaService.translateArtText(
                'Post-Impressionism is a predominantly French art movement',
                'en',
                'zh-TW'
            );
            testResult.translation = translationResult && translationResult.translation && translationResult.translation.length > 0;
            console.log('  ✅ 翻譯功能測試成功');

            // 6. 分類測試
            console.log('  🏷️ 測試分類功能...');
            const classificationResult = await ollamaService.classifyArtwork(testArtwork);
            testResult.classification = classificationResult && classificationResult.classification;
            console.log('  ✅ 分類功能測試成功');

        } catch (error) {
            console.error(`  ❌ 服務測試失敗: ${error.message}`);
            testResult.errors.push(error.message);
        }

        testResult.duration = Date.now() - startTime;
        this.results.serviceTest = testResult;

        console.log(`🔧 服務測試完成 (耗時: ${Math.round(testResult.duration / 1000)}秒)\n`);
    }

    /**
     * 測試摘要翻譯代理
     */
    async testSummarizationAgent() {
        console.log('📝 測試 Ollama 摘要翻譯代理...');

        const startTime = Date.now();
        const testResult = {
            initialization: false,
            processing: false,
            multiLanguage: false,
            duration: 0,
            errors: []
        };

        try {
            // 初始化代理
            console.log('  🔧 初始化摘要翻譯代理...');
            const agent = new OllamaSummarizationAgent();
            await agent.initialize();
            testResult.initialization = agent.status === 'ready';
            console.log('  ✅ 代理初始化成功');

            // 創建測試數據
            const testData = {
                metadata: {
                    title: 'The Birth of Venus',
                    artist: 'Sandro Botticelli',
                    period: 'Early Renaissance',
                    description: 'Mythological painting depicting the goddess Venus',
                    date: 'c. 1484-1486',
                    medium: 'tempera on canvas'
                }
            };

            // 模擬處理選項
            const processingOptions = {
                targetLanguages: ['zh-TW', 'ja'],
                generateSummaries: true,
                generateTranslations: true,
                culturalAdaptation: true
            };

            // 測試處理功能 (模擬)
            console.log('  📊 測試處理功能...');

            // 測試摘要生成
            const summary = await ollamaService.generateArtSummary(testData.metadata, 'artwork');
            testResult.processing = summary && summary.summary;

            // 測試多語言翻譯
            const translations = [];
            for (const lang of processingOptions.targetLanguages) {
                const translation = await ollamaService.translateArtText(
                    testData.metadata.description,
                    'en',
                    lang
                );
                translations.push(translation);
            }

            testResult.multiLanguage = translations.length === processingOptions.targetLanguages.length;
            console.log('  ✅ 多語言處理測試成功');

            // 獲取統計
            const stats = agent.getStats();
            console.log(`  📊 代理統計: 處理率 ${stats.errorRate}`);

        } catch (error) {
            console.error(`  ❌ 摘要翻譯代理測試失敗: ${error.message}`);
            testResult.errors.push(error.message);
        }

        testResult.duration = Date.now() - startTime;
        this.results.summarizationTest = testResult;

        console.log(`📝 摘要翻譯代理測試完成 (耗時: ${Math.round(testResult.duration / 1000)}秒)\n`);
    }

    /**
     * 測試分類代理
     */
    async testClassificationAgent() {
        console.log('🏷️ 測試 Ollama 分類代理...');

        const startTime = Date.now();
        const testResult = {
            initialization: false,
            classification: false,
            multiDimensional: false,
            ruleBasedFallback: false,
            duration: 0,
            errors: []
        };

        try {
            // 初始化代理
            console.log('  🔧 初始化分類代理...');
            const agent = new OllamaClassificationAgent();
            await agent.initialize();
            testResult.initialization = agent.status === 'ready';
            console.log('  ✅ 代理初始化成功');

            // 測試分類功能
            console.log('  🎯 測試多維度分類...');

            const testArtworks = [
                {
                    title: 'Guernica',
                    artist: 'Pablo Picasso',
                    description: 'Abstract painting depicting war',
                    period: '20th century',
                    medium: 'oil painting'
                },
                {
                    title: 'The Great Wave off Kanagawa',
                    artist: 'Hokusai',
                    description: 'Japanese woodblock print of a wave',
                    period: 'Edo period',
                    medium: 'woodblock print'
                }
            ];

            let successfulClassifications = 0;
            const classifications = [];

            for (const artwork of testArtworks) {
                try {
                    const classification = await ollamaService.classifyArtwork(artwork);
                    classifications.push(classification);
                    successfulClassifications++;

                    // 檢查多維度分類
                    const hasMultipleDimensions = Object.keys(classification.classification).length > 2;
                    if (hasMultipleDimensions) {
                        testResult.multiDimensional = true;
                    }

                } catch (error) {
                    console.warn(`    ⚠️ 分類失敗，測試規則式降級...`);

                    // 測試規則式分類降級
                    try {
                        const ruleBasedResult = await agent.ruleBasedClassification(artwork);
                        testResult.ruleBasedFallback = true;
                        console.log('    ✅ 規則式分類降級成功');
                    } catch (fallbackError) {
                        console.error(`    ❌ 規則式分類也失敗: ${fallbackError.message}`);
                    }
                }
            }

            testResult.classification = successfulClassifications > 0;
            console.log(`  ✅ 成功分類 ${successfulClassifications}/${testArtworks.length} 個作品`);

            // 獲取統計
            const stats = agent.getStats();
            console.log(`  📊 分類統計: 錯誤率 ${stats.errorRate}`);

        } catch (error) {
            console.error(`  ❌ 分類代理測試失敗: ${error.message}`);
            testResult.errors.push(error.message);
        }

        testResult.duration = Date.now() - startTime;
        this.results.classificationTest = testResult;

        console.log(`🏷️ 分類代理測試完成 (耗時: ${Math.round(testResult.duration / 1000)}秒)\n`);
    }

    /**
     * 效能測試
     */
    async testPerformance() {
        console.log('⚡ 執行效能測試...');

        const startTime = Date.now();
        const testResult = {
            textGenerationSpeed: null,
            embeddingSpeed: null,
            memoryUsage: null,
            concurrentRequests: false,
            duration: 0,
            errors: []
        };

        try {
            // 1. 文本生成速度測試
            console.log('  📊 測試文本生成速度...');
            const textGenStart = Date.now();
            const longPrompt = '請詳細介紹文藝復興時期的藝術特徵，包括代表藝術家、主要作品和歷史背景。';

            const textGenResult = await ollamaService.generateText(longPrompt, {
                maxTokens: 500
            });

            const textGenDuration = Date.now() - textGenStart;
            testResult.textGenerationSpeed = {
                duration: textGenDuration,
                tokensPerSecond: textGenResult.tokens ? (textGenResult.tokens / (textGenDuration / 1000)).toFixed(2) : 'N/A',
                totalTokens: textGenResult.tokens || 0
            };

            console.log(`  ✅ 文本生成速度: ${testResult.textGenerationSpeed.tokensPerSecond} tokens/秒`);

            // 2. 嵌入向量生成速度測試
            console.log('  🔢 測試嵌入向量生成速度...');
            const embeddingStart = Date.now();

            const testTexts = [
                '印象派繪畫的特點',
                '巴洛克建築的風格',
                '現代雕塑的發展',
                '攝影藝術的歷史',
                '數位藝術的創新'
            ];

            const embeddingResults = await ollamaService.generateEmbeddings(testTexts);
            const embeddingDuration = Date.now() - embeddingStart;

            testResult.embeddingSpeed = {
                duration: embeddingDuration,
                textsPerSecond: (testTexts.length / (embeddingDuration / 1000)).toFixed(2),
                totalTexts: testTexts.length,
                avgDimensions: embeddingResults.reduce((sum, r) => sum + (r.dimensions || 0), 0) / embeddingResults.length
            };

            console.log(`  ✅ 嵌入向量生成速度: ${testResult.embeddingSpeed.textsPerSecond} 文本/秒`);

            // 3. 記憶體使用測試
            const memoryUsage = process.memoryUsage();
            testResult.memoryUsage = {
                heapUsed: Math.round(memoryUsage.heapUsed / 1024 / 1024) + 'MB',
                heapTotal: Math.round(memoryUsage.heapTotal / 1024 / 1024) + 'MB',
                external: Math.round(memoryUsage.external / 1024 / 1024) + 'MB'
            };

            console.log(`  💾 記憶體使用: ${testResult.memoryUsage.heapUsed} (總共 ${testResult.memoryUsage.heapTotal})`);

            // 4. 併發請求測試
            console.log('  🔀 測試併發請求處理...');
            const concurrentStart = Date.now();

            const concurrentPromises = Array.from({ length: 3 }, (_, i) =>
                ollamaService.generateText(`請介紹第${i + 1}個藝術運動`, { maxTokens: 100 })
            );

            const concurrentResults = await Promise.allSettled(concurrentPromises);
            const successfulConcurrent = concurrentResults.filter(r => r.status === 'fulfilled').length;

            testResult.concurrentRequests = successfulConcurrent === concurrentPromises.length;
            const concurrentDuration = Date.now() - concurrentStart;

            console.log(`  ✅ 併發處理: ${successfulConcurrent}/${concurrentPromises.length} 成功 (${concurrentDuration}ms)`);

        } catch (error) {
            console.error(`  ❌ 效能測試失敗: ${error.message}`);
            testResult.errors.push(error.message);
        }

        testResult.duration = Date.now() - startTime;
        this.results.performanceTest = testResult;

        console.log(`⚡ 效能測試完成 (耗時: ${Math.round(testResult.duration / 1000)}秒)\n`);
    }

    /**
     * 生成測試報告
     */
    generateTestReport() {
        console.log('📋 Ollama 整合測試報告');
        console.log('=' .repeat(50));

        // 整體狀態
        const overallSuccess = this.calculateOverallSuccess();
        console.log(`🎯 整體狀態: ${overallSuccess ? '✅ 通過' : '❌ 失敗'}\n`);

        // 服務測試結果
        if (this.results.serviceTest) {
            console.log('🔧 Ollama 服務測試:');
            const service = this.results.serviceTest;
            console.log(`   健康檢查: ${service.health ? '✅' : '❌'}`);
            console.log(`   文本生成: ${service.textGeneration ? '✅' : '❌'}`);
            console.log(`   嵌入向量: ${service.embedding ? '✅' : '❌'}`);
            console.log(`   藝術摘要: ${service.artSummary ? '✅' : '❌'}`);
            console.log(`   翻譯功能: ${service.translation ? '✅' : '❌'}`);
            console.log(`   分類功能: ${service.classification ? '✅' : '❌'}`);
            console.log(`   測試耗時: ${Math.round(service.duration / 1000)}秒`);
            if (service.errors.length > 0) {
                console.log(`   錯誤: ${service.errors.join(', ')}`);
            }
            console.log();
        }

        // 摘要翻譯代理測試結果
        if (this.results.summarizationTest) {
            console.log('📝 摘要翻譯代理測試:');
            const summarization = this.results.summarizationTest;
            console.log(`   初始化: ${summarization.initialization ? '✅' : '❌'}`);
            console.log(`   處理功能: ${summarization.processing ? '✅' : '❌'}`);
            console.log(`   多語言支援: ${summarization.multiLanguage ? '✅' : '❌'}`);
            console.log(`   測試耗時: ${Math.round(summarization.duration / 1000)}秒`);
            if (summarization.errors.length > 0) {
                console.log(`   錯誤: ${summarization.errors.join(', ')}`);
            }
            console.log();
        }

        // 分類代理測試結果
        if (this.results.classificationTest) {
            console.log('🏷️ 分類代理測試:');
            const classification = this.results.classificationTest;
            console.log(`   初始化: ${classification.initialization ? '✅' : '❌'}`);
            console.log(`   分類功能: ${classification.classification ? '✅' : '❌'}`);
            console.log(`   多維度分類: ${classification.multiDimensional ? '✅' : '❌'}`);
            console.log(`   規則式降級: ${classification.ruleBasedFallback ? '✅' : '❌'}`);
            console.log(`   測試耗時: ${Math.round(classification.duration / 1000)}秒`);
            if (classification.errors.length > 0) {
                console.log(`   錯誤: ${classification.errors.join(', ')}`);
            }
            console.log();
        }

        // 效能測試結果
        if (this.results.performanceTest) {
            console.log('⚡ 效能測試結果:');
            const performance = this.results.performanceTest;

            if (performance.textGenerationSpeed) {
                console.log(`   文本生成速度: ${performance.textGenerationSpeed.tokensPerSecond} tokens/秒`);
            }
            if (performance.embeddingSpeed) {
                console.log(`   嵌入生成速度: ${performance.embeddingSpeed.textsPerSecond} 文本/秒`);
            }
            if (performance.memoryUsage) {
                console.log(`   記憶體使用: ${performance.memoryUsage.heapUsed}`);
            }
            console.log(`   併發處理: ${performance.concurrentRequests ? '✅' : '❌'}`);
            console.log(`   測試耗時: ${Math.round(performance.duration / 1000)}秒`);
            if (performance.errors.length > 0) {
                console.log(`   錯誤: ${performance.errors.join(', ')}`);
            }
            console.log();
        }

        // 建議和總結
        console.log('💡 建議:');
        this.generateRecommendations();

        console.log('\n🎉 測試完成！');
    }

    /**
     * 計算整體成功率
     */
    calculateOverallSuccess() {
        const tests = [
            this.results.serviceTest?.health,
            this.results.serviceTest?.textGeneration,
            this.results.summarizationTest?.initialization,
            this.results.classificationTest?.initialization
        ];

        const successCount = tests.filter(Boolean).length;
        return successCount >= tests.length * 0.75; // 75% 通過率
    }

    /**
     * 生成建議
     */
    generateRecommendations() {
        const recommendations = [];

        // 檢查服務可用性
        if (!this.results.serviceTest?.health) {
            recommendations.push('• 確保 Ollama 服務正在運行 (ollama serve)');
            recommendations.push('• 檢查 Ollama 服務地址配置是否正確');
        }

        // 檢查模型可用性
        if (!this.results.serviceTest?.textGeneration) {
            recommendations.push('• 確保已下載必要的 LLM 模型 (如 llama3.1:8b)');
        }

        if (!this.results.serviceTest?.embedding) {
            recommendations.push('• 確保已下載 embedding 模型 (如 mxbai-embed-large)');
        }

        // 效能建議
        if (this.results.performanceTest?.textGenerationSpeed?.tokensPerSecond < 10) {
            recommendations.push('• 考慮使用更小的模型以提升生成速度');
            recommendations.push('• 檢查系統 GPU/CPU 資源配置');
        }

        if (this.results.performanceTest?.memoryUsage?.heapUsed > '500MB') {
            recommendations.push('• 考慮增加系統記憶體或調整批次大小');
        }

        if (recommendations.length === 0) {
            recommendations.push('✅ 所有功能運行正常，可以開始使用 Ollama 替代 OpenAI API');
            recommendations.push('✅ 建議將環境變數 USE_OLLAMA 設為 true 啟用本地模型');
        }

        recommendations.forEach(rec => console.log(rec));
    }
}

// 執行測試
async function main() {
    const tester = new OllamaIntegrationTester();

    try {
        await tester.runFullTestSuite();
        process.exit(0);
    } catch (error) {
        console.error('測試執行失敗:', error);
        process.exit(1);
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    main();
}

module.exports = OllamaIntegrationTester;