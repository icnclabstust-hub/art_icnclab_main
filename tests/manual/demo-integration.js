#!/usr/bin/env node

/**
 * 藝術史資料庫與CUDA ML服務整合演示
 * 展示完整的GPU加速機器學習功能
 */

const axios = require('axios');

const ML_SERVICE_URL = 'http://localhost:8080';

console.log('🎨 藝術史資料庫 x CUDA ML服務整合演示');
console.log('=' .repeat(60));

async function demonstrateMLIntegration() {
    try {
        console.log('\n🔍 1. 檢查CUDA ML服務狀態...');

        const healthResponse = await axios.get(`${ML_SERVICE_URL}/health`);
        console.log('✅ ML服務健康檢查通過');
        console.log(`   🎮 GPU: ${healthResponse.data.gpu_stats.gpu_name}`);
        console.log(`   ⚡ 設備: ${healthResponse.data.device}`);
        console.log(`   💾 GPU記憶體: ${healthResponse.data.gpu_stats.gpu_memory_used}/${healthResponse.data.gpu_stats.gpu_memory_total}`);

        console.log('\n🧠 2. 藝術品智能分類演示...');

        const artworks = [
            {
                title: "蒙娜麗莎",
                description: "達文西創作的文藝復興時期經典肖像畫，展現神秘微笑和精湛的繪畫技巧",
                artist: "李奧納多·達·芬奇"
            },
            {
                title: "星夜",
                description: "梵谷的印象派代表作，描繪夜空中旋轉的星雲和月亮",
                artist: "文森·梵谷"
            },
            {
                title: "思想者",
                description: "羅丹創作的現代主義雕塑傑作，表現人類深度思考的姿態",
                artist: "奧古斯特·羅丹"
            }
        ];

        for (let i = 0; i < artworks.length; i++) {
            const artwork = artworks[i];
            const text = `${artwork.title} ${artwork.description} ${artwork.artist}`;

            console.log(`\n   📝 分析作品 ${i+1}: ${artwork.title}`);

            const classifyResponse = await axios.post(`${ML_SERVICE_URL}/classify/artwork`, {
                text: text
            });

            const result = classifyResponse.data;
            console.log(`   🎯 時期: ${result.classification.period} (${(result.confidence_scores.period * 100).toFixed(1)}%)`);
            console.log(`   🎨 風格: ${result.classification.style} (${(result.confidence_scores.style * 100).toFixed(1)}%)`);
            console.log(`   🌍 地區: ${result.classification.region} (${(result.confidence_scores.region * 100).toFixed(1)}%)`);
            console.log(`   🖼️ 媒材: ${result.classification.medium} (${(result.confidence_scores.medium * 100).toFixed(1)}%)`);
        }

        console.log('\n🔬 3. 批量向量嵌入生成...');

        const texts = artworks.map(a => `${a.title} ${a.description}`);
        const embeddingResponse = await axios.post(`${ML_SERVICE_URL}/embeddings`, {
            texts: texts,
            model: 'multilingual-bert'
        });

        console.log(`   ✅ 成功生成 ${embeddingResponse.data.embeddings.length} 個向量嵌入`);
        console.log(`   📏 嵌入維度: ${embeddingResponse.data.embedding_dim}`);
        console.log(`   ⚡ 處理時間: ${embeddingResponse.data.processing_time}`);
        console.log(`   🎮 使用設備: ${embeddingResponse.data.device}`);

        console.log('\n🚀 4. GPU加速模型訓練演示...');

        const trainingData = artworks.map((artwork, index) => ({
            text: `${artwork.title} ${artwork.description}`,
            labels: {
                period: index === 0 ? '文藝復興' : index === 1 ? '印象派' : '現代',
                style: index === 0 ? '寫實主義' : index === 1 ? '印象主義' : '現代主義'
            }
        }));

        const trainResponse = await axios.post(`${ML_SERVICE_URL}/train`, {
            model_type: 'classification',
            config: {
                epochs: 3,
                batch_size: 16,
                learning_rate: 1e-5
            },
            data: trainingData
        });

        console.log(`   🎯 訓練作業已啟動: ${trainResponse.data.job_id}`);
        console.log(`   📊 資料量: ${trainResponse.data.data_size} 個樣本`);
        console.log(`   ⏱️ 預估時間: ${trainResponse.data.eta}`);
        console.log(`   🎮 訓練設備: ${trainResponse.data.device}`);

        // 監控訓練進度
        const jobId = trainResponse.data.job_id;
        console.log('\n   📈 監控訓練進度...');

        for (let i = 0; i < 5; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));

            const progressResponse = await axios.get(`${ML_SERVICE_URL}/train/${jobId}/progress`);
            const progress = progressResponse.data;

            console.log(`   📊 Epoch ${progress.current_epoch}/${progress.total_epochs} - 進度: ${progress.progress.toFixed(1)}%`);

            if (progress.current_loss) {
                console.log(`      損失: ${progress.current_loss}, 準確率: ${(progress.current_accuracy * 100).toFixed(1)}%`);
            }

            if (progress.status === 'completed') {
                console.log(`   ✅ 訓練完成！最終準確率: ${(progress.current_accuracy * 100).toFixed(1)}%`);
                break;
            }
        }

        console.log('\n🔍 5. 相似作品推薦演示...');

        const similarityResponse = await axios.post(`${ML_SERVICE_URL}/similarity/search`, {
            query_text: '文藝復興時期的肖像畫，展現精湛的繪畫技巧',
            top_k: 5
        });

        console.log('   🎯 推薦結果:');
        similarityResponse.data.similar_items.forEach((item, index) => {
            const score = similarityResponse.data.scores[index];
            console.log(`   ${index + 1}. ${item.title} (相似度: ${(score * 100).toFixed(1)}%)`);
            console.log(`      ${item.description}`);
        });

        console.log('\n🎊 整合演示完成！');
        console.log('=' .repeat(60));
        console.log('✅ 成功展示了以下功能:');
        console.log('   🎮 GPU狀態監控和硬體資訊');
        console.log('   🧠 多任務藝術品分類 (時期/風格/地區/媒材)');
        console.log('   📊 批量向量嵌入生成');
        console.log('   🚀 GPU加速模型訓練');
        console.log('   🔍 基於相似性的作品推薦');
        console.log('\n💡 CUDA/cuDNN環境已成功整合到藝術史資料庫系統！');

    } catch (error) {
        console.error(`❌ 演示過程中發生錯誤: ${error.message}`);

        if (error.code === 'ECONNREFUSED') {
            console.log('🔧 請確認ML服務已啟動: python3 ml-service/simple-app.py');
        } else if (error.response) {
            console.log(`   狀態碼: ${error.response.status}`);
            console.log(`   錯誤詳情: ${error.response.data?.error || error.response.data?.message || 'Unknown error'}`);
        }
    }
}

// 執行演示
if (require.main === module) {
    demonstrateMLIntegration()
        .then(() => {
            console.log('\n🎉 演示執行完成！');
            process.exit(0);
        })
        .catch((error) => {
            console.error('\n💥 演示執行失敗:', error.message);
            process.exit(1);
        });
}

module.exports = { demonstrateMLIntegration };