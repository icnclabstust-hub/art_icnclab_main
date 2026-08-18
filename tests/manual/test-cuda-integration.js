#!/usr/bin/env node

/**
 * CUDA 加速整合測試腳本
 * 測試向量資料庫 + CUDA ML服務 + 主應用程序的完整整合
 */

const axios = require('axios');
const { ChromaClient } = require('chromadb');

class CudaIntegrationTester {
    constructor() {
        this.mlServiceUrl = process.env.ML_SERVICE_URL || 'http://localhost:8080';
        this.chromaClient = new ChromaClient({
            host: process.env.CHROMADB_HOST || 'localhost',
            port: 8000
        });
        this.mainApiUrl = process.env.API_URL || 'http://localhost:3000';

        this.testResults = {
            vectorDatabase: { passed: 0, failed: 0, tests: [] },
            cudaMlService: { passed: 0, failed: 0, tests: [] },
            integration: { passed: 0, failed: 0, tests: [] }
        };
    }

    async runAllTests() {
        console.log('🧪 開始 CUDA 加速整合測試\n');
        console.log('='.repeat(60));

        try {
            // 測試向量資料庫
            await this.testVectorDatabase();
            console.log('');

            // 測試 CUDA ML 服務
            await this.testCudaMlService();
            console.log('');

            // 測試完整整合
            await this.testFullIntegration();
            console.log('');

            // 顯示測試結果
            this.showTestSummary();

        } catch (error) {
            console.error('❌ 測試運行失敗:', error.message);
        }
    }

    async testVectorDatabase() {
        console.log('🔍 測試向量資料庫連接性...\n');

        // 測試 1: ChromaDB 連接
        await this.runTest('vectorDatabase', 'ChromaDB 連接測試', async () => {
            const heartbeat = await this.chromaClient.heartbeat();
            if (!heartbeat) throw new Error('ChromaDB 無回應');
            return '✅ ChromaDB 連接正常';
        });

        // 測試 2: 檢查集合
        await this.runTest('vectorDatabase', '向量集合檢查', async () => {
            const collections = await this.chromaClient.listCollections();
            const expectedCollections = [
                'art_history_artwork_descriptions',
                'art_history_artist_biographies',
                'art_history_historical_periods'
            ];

            const collectionNames = collections.map(c => c.name);
            const missing = expectedCollections.filter(name => !collectionNames.includes(name));

            if (missing.length > 0) {
                throw new Error(`缺少集合: ${missing.join(', ')}`);
            }
            return `✅ 發現 ${collections.length} 個集合`;
        });
    }

    async testCudaMlService() {
        console.log('🚀 測試 CUDA ML 服務功能...\n');

        // 測試 1: 健康檢查
        await this.runTest('cudaMlService', 'CUDA ML 服務健康檢查', async () => {
            const response = await axios.get(`${this.mlServiceUrl}/health`);
            const health = response.data;

            if (!health.gpu_available) {
                throw new Error('GPU 不可用');
            }

            return `✅ GPU: ${health.gpu_stats.gpu_name}, CUDA: ${health.cuda_version}`;
        });

        // 測試 2: 藝術品分類
        await this.runTest('cudaMlService', '藝術品分類測試', async () => {
            const testData = {
                text: '這是一幅描繪春天花園景色的印象派油畫，充滿了明亮的色彩和光影效果',
                title: '春日花園'
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/classify/artwork`,
                testData,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.classification) {
                throw new Error('分類失敗');
            }

            return `✅ 分類完成: ${result.classification.period} (${(result.confidence_scores.period * 100).toFixed(1)}%)`;
        });

        // 測試 3: 嵌入生成
        await this.runTest('cudaMlService', '多語言嵌入生成測試', async () => {
            const testData = {
                texts: ['中國山水畫', 'Western Renaissance art', '日本浮世繪'],
                model: 'multilingual-bert'
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                testData,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.embeddings || result.embeddings.length !== 3) {
                throw new Error('嵌入生成失敗');
            }

            return `✅ 生成 ${result.embeddings.length} 個 ${result.embedding_dim}D 嵌入向量`;
        });
    }

    async testFullIntegration() {
        console.log('🔗 測試完整系統整合...\n');

        // 測試 1: 端到端嵌入與存儲
        await this.runTest('integration', '嵌入生成與向量存儲整合', async () => {
            // 1. 生成嵌入
            const artworkText = '蒙娜麗莎是達文西創作的文藝復興傑作，以其神秘的微笑聞名於世';

            const embeddingResponse = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [artworkText],
                    model: 'multilingual-bert'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const embedding = embeddingResponse.data.embeddings[0];

            // 2. 存儲到向量資料庫
            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            const testId = `test_${Date.now()}`;
            await collection.upsert({
                ids: [testId],
                embeddings: [embedding],
                metadatas: [{
                    title: '蒙娜麗莎',
                    artist: '達文西',
                    period: '文藝復興',
                    test: true
                }],
                documents: [artworkText]
            });

            // 3. 驗證存儲
            const results = await collection.query({
                queryEmbeddings: [embedding],
                nResults: 1
            });

            if (!results.ids[0] || results.ids[0][0] !== testId) {
                throw new Error('向量存儲驗證失敗');
            }

            return '✅ 嵌入生成與存儲整合成功';
        });

        // 測試 2: 語意搜索
        await this.runTest('integration', '智能語意搜索測試', async () => {
            // 生成查詢嵌入
            const queryText = '文藝復興時期的肖像畫';

            const queryEmbedding = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [queryText],
                    model: 'multilingual-bert'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const embedding = queryEmbedding.data.embeddings[0];

            // 執行語意搜索
            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            const searchResults = await collection.query({
                queryEmbeddings: [embedding],
                nResults: 3,
                include: ['metadatas', 'documents', 'distances']
            });

            if (!searchResults.ids[0] || searchResults.ids[0].length === 0) {
                throw new Error('語意搜索無結果');
            }

            const bestMatch = searchResults.metadatas[0][0];
            const similarity = 1 - searchResults.distances[0][0]; // 轉換為相似度

            return `✅ 找到 ${searchResults.ids[0].length} 個相關結果，最佳匹配: ${bestMatch.title} (相似度: ${(similarity * 100).toFixed(1)}%)`;
        });

        // 測試 3: 系統性能測試
        await this.runTest('integration', '系統性能基準測試', async () => {
            const startTime = Date.now();

            // 批量處理測試
            const testTexts = [
                '巴洛克風格的宗教繪畫',
                '現代抽象表現主義作品',
                '古典希臘雕塑藝術',
                '中國傳統水墨畫',
                '印象派風景畫作品'
            ];

            // 並行生成嵌入
            const embeddingPromises = testTexts.map(text =>
                axios.post(
                    `${this.mlServiceUrl}/embeddings`,
                    { texts: [text], model: 'multilingual-bert' },
                    { headers: { 'Content-Type': 'application/json' } }
                )
            );

            const embeddingResults = await Promise.all(embeddingPromises);
            const processingTime = Date.now() - startTime;

            // 驗證所有結果
            const successCount = embeddingResults.filter(r =>
                r.data.embeddings && r.data.embeddings.length > 0
            ).length;

            if (successCount !== testTexts.length) {
                throw new Error(`批量處理失敗: ${successCount}/${testTexts.length}`);
            }

            const avgTimePerText = processingTime / testTexts.length;

            return `✅ 批量處理 ${testTexts.length} 個文本，平均 ${avgTimePerText.toFixed(0)}ms/文本`;
        });
    }

    async runTest(category, testName, testFn) {
        try {
            console.log(`  🧪 ${testName}...`);
            const result = await testFn();
            console.log(`     ${result}`);

            this.testResults[category].passed++;
            this.testResults[category].tests.push({
                name: testName,
                status: 'passed',
                message: result
            });

        } catch (error) {
            console.log(`     ❌ 失敗: ${error.message}`);

            this.testResults[category].failed++;
            this.testResults[category].tests.push({
                name: testName,
                status: 'failed',
                message: error.message
            });
        }
    }

    showTestSummary() {
        console.log('📊 測試結果摘要');
        console.log('='.repeat(60));

        const categories = [
            { key: 'vectorDatabase', name: '向量資料庫' },
            { key: 'cudaMlService', name: 'CUDA ML 服務' },
            { key: 'integration', name: '系統整合' }
        ];

        let totalPassed = 0;
        let totalFailed = 0;

        categories.forEach(({ key, name }) => {
            const result = this.testResults[key];
            const total = result.passed + result.failed;
            const passRate = total > 0 ? ((result.passed / total) * 100).toFixed(1) : '0.0';

            console.log(`${name}: ${result.passed}/${total} 通過 (${passRate}%)`);

            totalPassed += result.passed;
            totalFailed += result.failed;
        });

        console.log('-'.repeat(40));
        const grandTotal = totalPassed + totalFailed;
        const overallPassRate = grandTotal > 0 ? ((totalPassed / grandTotal) * 100).toFixed(1) : '0.0';

        console.log(`總計: ${totalPassed}/${grandTotal} 通過 (${overallPassRate}%)`);

        if (totalFailed === 0) {
            console.log('\n🎉 所有測試通過！CUDA 加速整合成功！');
        } else {
            console.log(`\n⚠️  有 ${totalFailed} 個測試失敗，請檢查系統配置`);
        }
    }
}

// 主執行程序
async function main() {
    const tester = new CudaIntegrationTester();
    await tester.runAllTests();
}

if (require.main === module) {
    main().catch(error => {
        console.error('❌ 測試執行失敗:', error);
        process.exit(1);
    });
}

module.exports = CudaIntegrationTester;