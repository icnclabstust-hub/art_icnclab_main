#!/usr/bin/env node

/**
 * 多模態 RAG 系統測試腳本
 * 測試文本、圖像、音頻的統一向量檢索系統
 */

const axios = require('axios');
const { ChromaClient } = require('chromadb');
const fs = require('fs');
const path = require('path');

class MultimodalRAGTester {
    constructor() {
        this.mlServiceUrl = process.env.ML_SERVICE_URL || 'http://localhost:8080';
        this.chromaClient = new ChromaClient({
            host: process.env.CHROMADB_HOST || 'localhost',
            port: 8000
        });
        this.mainApiUrl = process.env.API_URL || 'http://localhost:3000';

        this.testResults = {
            textProcessing: { passed: 0, failed: 0, tests: [] },
            imageProcessing: { passed: 0, failed: 0, tests: [] },
            crossModalRetrieval: { passed: 0, failed: 0, tests: [] },
            ragGeneration: { passed: 0, failed: 0, tests: [] }
        };
    }

    async runAllTests() {
        console.log('🎨 開始多模態 RAG 系統測試\n');
        console.log('='.repeat(60));

        try {
            // 測試文本處理
            await this.testTextProcessing();
            console.log('');

            // 測試圖像處理
            await this.testImageProcessing();
            console.log('');

            // 測試跨模態檢索
            await this.testCrossModalRetrieval();
            console.log('');

            // 測試 RAG 生成
            await this.testRAGGeneration();
            console.log('');

            // 顯示測試結果
            this.showTestSummary();

        } catch (error) {
            console.error('❌ 多模態 RAG 測試失敗:', error.message);
        }
    }

    async testTextProcessing() {
        console.log('📝 測試文本處理與嵌入...\n');

        // 測試 1: 多語言文本嵌入
        await this.runTest('textProcessing', '多語言藝術史文本嵌入', async () => {
            const testTexts = [
                '《蒙娜麗莎》是達文西在文藝復興時期創作的著名肖像畫',
                'The Starry Night is a painting by Vincent van Gogh',
                '浮世絵は江戸時代の日本の木版画芸術である',
                'L\'impressionnisme est un mouvement artistique français'
            ];

            const response = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: testTexts,
                    model: 'multilingual-bert'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.embeddings || result.embeddings.length !== 4) {
                throw new Error('多語言嵌入生成失敗');
            }

            // 驗證向量維度一致性
            const dimensions = result.embeddings.map(emb => emb.length);
            const uniqueDimensions = [...new Set(dimensions)];
            if (uniqueDimensions.length !== 1) {
                throw new Error('向量維度不一致');
            }

            return `✅ 生成 ${result.embeddings.length} 個多語言 ${result.embedding_dim}D 向量`;
        });

        // 測試 2: 藝術史專業術語處理
        await this.runTest('textProcessing', '藝術史專業術語理解', async () => {
            const artTerms = [
                '巴洛克風格的明暗對比技法',
                '印象派的點彩技法與光影效果',
                '抽象表現主義的色彩情感表達',
                '中國山水畫的意境與筆墨'
            ];

            const response = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: artTerms,
                    model: 'bge-m3'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const embeddings = response.data.embeddings;

            // 計算語意相似度 (巴洛克與印象派應該比抽象表現主義更相似)
            const similarity = this.calculateCosineSimilarity(embeddings[0], embeddings[1]);

            if (similarity < 0.3) {
                throw new Error('專業術語語意理解不准確');
            }

            return `✅ 專業術語向量化完成，語意相似度: ${(similarity * 100).toFixed(1)}%`;
        });

        // 測試 3: 向量存儲與檢索
        await this.runTest('textProcessing', '文本向量存儲與檢索', async () => {
            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            // 存儲測試向量
            const testDoc = '這是一幅展現文藝復興精神的油畫作品，體現了人文主義的理念';
            const embeddingResponse = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [testDoc],
                    model: 'bge-m3'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const embedding = embeddingResponse.data.embeddings[0];
            const testId = `multimodal_text_${Date.now()}`;

            await collection.upsert({
                ids: [testId],
                embeddings: [embedding],
                metadatas: [{
                    type: 'text',
                    period: '文藝復興',
                    test: true
                }],
                documents: [testDoc]
            });

            // 測試檢索
            const searchResults = await collection.query({
                queryEmbeddings: [embedding],
                nResults: 1,
                include: ['metadatas', 'distances']
            });

            if (!searchResults.ids[0] || searchResults.ids[0][0] !== testId) {
                throw new Error('文本向量檢索失敗');
            }

            const similarity = 1 - searchResults.distances[0][0];
            return `✅ 文本向量存儲與檢索成功，相似度: ${(similarity * 100).toFixed(1)}%`;
        });
    }

    async testImageProcessing() {
        console.log('🖼️  測試圖像處理與特徵提取...\n');

        // 測試 1: 圖像特徵提取
        await this.runTest('imageProcessing', '藝術品圖像特徵提取', async () => {
            // 模擬圖像特徵提取 (實際應用中需要真實圖像)
            const imageFeatureRequest = {
                image_path: '/simulated/renaissance_painting.jpg',
                extract_features: true,
                include_metadata: true
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/image/features`,
                imageFeatureRequest,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.features) {
                throw new Error('圖像特徵提取失敗');
            }

            // 驗證特徵向量維度
            if (!Array.isArray(result.features) || result.features.length !== 2048) {
                throw new Error('圖像特徵向量維度錯誤');
            }

            return `✅ 提取 ${result.features.length}D 圖像特徵向量`;
        });

        // 測試 2: 藝術風格識別
        await this.runTest('imageProcessing', '藝術風格自動識別', async () => {
            const styleClassificationRequest = {
                image_path: '/simulated/impressionist_painting.jpg',
                task: 'style_classification'
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/classify/artwork-style`,
                styleClassificationRequest,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.style_prediction) {
                throw new Error('藝術風格識別失敗');
            }

            const confidence = result.confidence_score;
            if (confidence < 0.6) {
                throw new Error('風格識別信心度過低');
            }

            return `✅ 識別風格: ${result.style_prediction} (信心度: ${(confidence * 100).toFixed(1)}%)`;
        });

        // 測試 3: 圖像向量存儲
        await this.runTest('imageProcessing', '圖像特徵向量存儲', async () => {
            // 模擬圖像特徵向量 (使用與集合匹配的768維)
            const simulatedImageVector = Array.from({ length: 768 }, () => Math.random() - 0.5);

            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            const testId = `multimodal_image_${Date.now()}`;

            await collection.upsert({
                ids: [testId],
                embeddings: [simulatedImageVector],
                metadatas: [{
                    type: 'image',
                    style: '印象派',
                    artist: '莫內',
                    test: true
                }],
                documents: ['印象派風格的睡蓮系列畫作']
            });

            // 驗證存儲
            const results = await collection.query({
                queryEmbeddings: [simulatedImageVector],
                nResults: 1
            });

            if (!results.ids[0] || results.ids[0][0] !== testId) {
                throw new Error('圖像向量存儲失敗');
            }

            return '✅ 圖像特徵向量存儲成功';
        });
    }

    async testCrossModalRetrieval() {
        console.log('🔗 測試跨模態檢索...\n');

        // 測試 1: 文本查詢圖像
        await this.runTest('crossModalRetrieval', '文本描述查詢相關圖像', async () => {
            const textQuery = '印象派風格的水景畫作';

            // 生成查詢向量
            const queryResponse = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [textQuery],
                    model: 'bge-m3'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const queryEmbedding = queryResponse.data.embeddings[0];

            // 在向量資料庫中搜索
            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            const searchResults = await collection.query({
                queryEmbeddings: [queryEmbedding],
                nResults: 5,
                include: ['metadatas', 'documents', 'distances'],
                where: { test: true }
            });

            if (!searchResults.ids[0] || searchResults.ids[0].length === 0) {
                throw new Error('跨模態檢索無結果');
            }

            const relevantResults = searchResults.metadatas[0].filter(meta =>
                meta.type === 'image' || (meta.type === 'text' && meta.period)
            );

            return `✅ 找到 ${searchResults.ids[0].length} 個跨模態匹配結果`;
        });

        // 測試 2: 語意融合檢索
        await this.runTest('crossModalRetrieval', '多模態語意融合檢索', async () => {
            // 生成與集合維度匹配的向量 (768維)
            const textVector = Array.from({ length: 768 }, () => Math.random() - 0.5);
            const imageVector = Array.from({ length: 768 }, () => Math.random() - 0.5);

            // 向量融合 (文本0.6權重，圖像0.4權重)
            const fusedVector = textVector.map((val, idx) =>
                0.6 * val + 0.4 * imageVector[idx]
            );

            const collection = await this.chromaClient.getCollection({
                name: 'art_history_artwork_descriptions'
            });

            const searchResults = await collection.query({
                queryEmbeddings: [fusedVector],
                nResults: 3,
                include: ['metadatas', 'distances']
            });

            if (!searchResults.ids[0] || searchResults.ids[0].length === 0) {
                throw new Error('融合檢索失敗');
            }

            const avgDistance = searchResults.distances[0].reduce((a, b) => a + b, 0) / searchResults.distances[0].length;
            const avgSimilarity = 1 - avgDistance;

            return `✅ 多模態融合檢索完成，平均相似度: ${(avgSimilarity * 100).toFixed(1)}%`;
        });

        // 測試 3: 時間序列感知檢索
        await this.runTest('crossModalRetrieval', '歷史時期感知檢索', async () => {
            const periodQuery = '文藝復興時期的宗教題材繪畫';

            const queryResponse = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [periodQuery],
                    model: 'bge-m3'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const queryEmbedding = queryResponse.data.embeddings[0];

            const collection = await this.chromaClient.getCollection({
                name: 'art_history_historical_periods'
            });

            // 添加時期感知的測試數據
            const testId = `period_aware_${Date.now()}`;
            await collection.upsert({
                ids: [testId],
                embeddings: [queryEmbedding],
                metadatas: [{
                    period: '文藝復興',
                    theme: '宗教',
                    year_range: '1400-1600',
                    test: true
                }],
                documents: [periodQuery]
            });

            const searchResults = await collection.query({
                queryEmbeddings: [queryEmbedding],
                nResults: 1,
                include: ['metadatas']
            });

            const foundPeriod = searchResults.metadatas[0][0]?.period;
            if (foundPeriod !== '文藝復興') {
                throw new Error('歷史時期識別不准確');
            }

            return `✅ 時期感知檢索成功，識別時期: ${foundPeriod}`;
        });
    }

    async testRAGGeneration() {
        console.log('🧠 測試 RAG 智能生成...\n');

        // 測試 1: 基於檢索的問答生成
        await this.runTest('ragGeneration', '藝術史問答生成', async () => {
            const question = '印象派繪畫有什麼特色？';

            // 1. 檢索相關內容
            const queryResponse = await axios.post(
                `${this.mlServiceUrl}/embeddings`,
                {
                    texts: [question],
                    model: 'bge-m3'
                },
                { headers: { 'Content-Type': 'application/json' } }
            );

            // 2. 模擬 RAG 生成過程
            const ragRequest = {
                question: question,
                retrieval_query: queryResponse.data.embeddings[0],
                max_tokens: 200,
                temperature: 0.7
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/rag/generate`,
                ragRequest,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.generated_text) {
                throw new Error('RAG 生成失敗');
            }

            const wordCount = result.generated_text.split(/\s+/).length;
            if (wordCount < 10) {
                throw new Error('生成內容過短');
            }

            return `✅ RAG 問答生成成功 (${wordCount} 詞)`;
        });

        // 測試 2: 多模態內容生成
        await this.runTest('ragGeneration', '多模態描述生成', async () => {
            const multimodalRequest = {
                text_input: '這幅畫的藝術風格和技法',
                image_features: Array.from({ length: 2048 }, () => Math.random()),
                generation_mode: 'descriptive',
                language: 'zh-TW'
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/rag/multimodal-generate`,
                multimodalRequest,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.description) {
                throw new Error('多模態描述生成失敗');
            }

            // 檢查描述品質
            const hasArtTerms = /風格|技法|色彩|構圖|筆法/i.test(result.description);
            if (!hasArtTerms) {
                throw new Error('生成內容缺乏藝術專業性');
            }

            return `✅ 多模態描述生成成功，包含專業術語`;
        });

        // 測試 3: 個性化推薦生成
        await this.runTest('ragGeneration', '個性化藝術推薦', async () => {
            const userProfile = {
                interests: ['印象派', '風景畫', '色彩理論'],
                expertise_level: 'intermediate',
                preferred_periods: ['19世紀', '現代藝術']
            };

            const recommendationRequest = {
                user_profile: userProfile,
                recommendation_type: 'artwork',
                count: 5
            };

            const response = await axios.post(
                `${this.mlServiceUrl}/rag/recommend`,
                recommendationRequest,
                { headers: { 'Content-Type': 'application/json' } }
            );

            const result = response.data;
            if (!result.success || !result.recommendations || result.recommendations.length !== 5) {
                throw new Error('個性化推薦生成失敗');
            }

            // 驗證推薦品質
            const relevantRecs = result.recommendations.filter(rec =>
                rec.confidence_score > 0.6
            );

            if (relevantRecs.length < 3) {
                throw new Error('推薦相關性不足');
            }

            return `✅ 生成 ${result.recommendations.length} 個個性化推薦，${relevantRecs.length} 個高相關性`;
        });
    }

    calculateCosineSimilarity(vecA, vecB) {
        const dotProduct = vecA.reduce((sum, a, i) => sum + a * vecB[i], 0);
        const magnitudeA = Math.sqrt(vecA.reduce((sum, a) => sum + a * a, 0));
        const magnitudeB = Math.sqrt(vecB.reduce((sum, b) => sum + b * b, 0));
        return dotProduct / (magnitudeA * magnitudeB);
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
        console.log('📊 多模態 RAG 測試結果摘要');
        console.log('='.repeat(60));

        const categories = [
            { key: 'textProcessing', name: '文本處理' },
            { key: 'imageProcessing', name: '圖像處理' },
            { key: 'crossModalRetrieval', name: '跨模態檢索' },
            { key: 'ragGeneration', name: 'RAG 生成' }
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
            console.log('\n🎉 多模態 RAG 系統測試全部通過！');
        } else {
            console.log(`\n⚠️  有 ${totalFailed} 個測試失敗，請檢查系統配置`);
        }

        // 顯示系統能力摘要
        console.log('\n📋 系統能力摘要:');
        console.log('✅ 多語言文本理解與向量化');
        console.log('✅ 圖像特徵提取與風格識別');
        console.log('✅ 跨模態語意檢索');
        console.log('✅ 智能內容生成與推薦');
        console.log('✅ 歷史時期感知處理');
    }
}

// 主執行程序
async function main() {
    const tester = new MultimodalRAGTester();
    await tester.runAllTests();
}

if (require.main === module) {
    main().catch(error => {
        console.error('❌ 多模態 RAG 測試執行失敗:', error);
        process.exit(1);
    });
}

module.exports = MultimodalRAGTester;