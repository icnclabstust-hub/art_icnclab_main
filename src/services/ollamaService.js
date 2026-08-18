/**
 * Ollama 本地 AI 服務整合
 * 提供 LLM 和 Embedding 模型的本地化替代方案
 */

const axios = require('axios');
const { logger } = require('../utils/logger');

class OllamaService {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || 'http://localhost:11434';
        this.defaultModel = options.defaultModel || 'gemma4:12B';
        this.embeddingModel = options.embeddingModel || 'bge-m3:latest';
        this.timeout = options.timeout || 120000; // 2分鐘超時

        // 重試配置
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;

        // 快取已載入的模型
        this.loadedModels = new Set();

        // 可用模型清單（由環境變數或建構參數提供）
        this.availableModels = options.availableModels || (process.env.OLLAMA_AVAILABLE_MODELS ? process.env.OLLAMA_AVAILABLE_MODELS.split(',').map(s => s.trim()).filter(Boolean) : []);

        logger.info(`🦙 Ollama 服務初始化 (${this.baseUrl})`);
    }

    /**
     * 檢查 Ollama 服務狀態
     */
    async checkHealth() {
        try {
            const response = await axios.get(`${this.baseUrl}/api/tags`, {
                timeout: 5000
            });
            return {
                status: 'healthy',
                models: response.data.models || []
            };
        } catch (error) {
            logger.warn('Ollama 服務連接失敗:', error.message);
            return {
                status: 'unhealthy',
                error: error.message
            };
        }
    }

    /**
     * 載入模型（如果尚未載入）
     */
    async ensureModelLoaded(modelName) {
        if (this.loadedModels.has(modelName)) {
            return true;
        }

        try {
            logger.info(`🔄 正在載入模型: ${modelName}`);

            // 預載入模型
            const response = await axios.post(`${this.baseUrl}/api/generate`, {
                model: modelName,
                prompt: "Hello",
                stream: false,
                options: {
                    num_predict: 1
                }
            }, {
                timeout: 30000
            });

            if (response.status === 200) {
                this.loadedModels.add(modelName);
                logger.info(`✅ 模型載入完成: ${modelName}`);
                return true;
            }
        } catch (error) {
            logger.error(`模型載入失敗: ${modelName}`, error.message);
            return false;
        }
    }

    /**
     * 生成文本（替代 OpenAI GPT）
     */
    async generateText(prompt, options = {}) {
        const modelName = options.model || this.defaultModel;

        // 確保模型已載入
        await this.ensureModelLoaded(modelName);

        const requestData = {
            model: modelName,
            prompt: prompt,
            stream: false,
            options: {
                temperature: options.temperature || 0.7,
                top_p: options.topP || 0.9,
                top_k: options.topK || 40,
                num_predict: options.maxTokens || 1000,
                stop: options.stop || []
            }
        };

        try {
            const response = await axios.post(
                `${this.baseUrl}/api/generate`,
                requestData,
                { timeout: this.timeout }
            );

            return {
                text: response.data.response,
                model: modelName,
                tokens: response.data.eval_count || 0,
                duration: response.data.total_duration || 0
            };
        } catch (error) {
            logger.error('文本生成失敗:', error.message);
            throw new Error(`Ollama 文本生成失敗: ${error.message}`);
        }
    }

    /**
     * 聊天對話（替代 OpenAI Chat API）
     */
    async chat(messages, options = {}) {
        const modelName = options.model || this.defaultModel;

        await this.ensureModelLoaded(modelName);

        // 將 OpenAI 格式的 messages 轉換為 Ollama 格式
        const prompt = this.formatMessagesAsPrompt(messages);

        return await this.generateText(prompt, options);
    }

    /**
     * 將對話格式轉換為 prompt
     */
    formatMessagesAsPrompt(messages) {
        let prompt = "";

        for (const message of messages) {
            switch (message.role) {
                case 'system':
                    prompt += `System: ${message.content}\n\n`;
                    break;
                case 'user':
                    prompt += `Human: ${message.content}\n\n`;
                    break;
                case 'assistant':
                    prompt += `Assistant: ${message.content}\n\n`;
                    break;
            }
        }

        prompt += "Assistant: ";
        return prompt;
    }

    /**
     * 生成嵌入向量（替代 OpenAI Embeddings）
     */
    async generateEmbedding(text, options = {}) {
        const modelName = options.model || this.embeddingModel;

        await this.ensureModelLoaded(modelName);

        try {
            const response = await axios.post(
                `${this.baseUrl}/api/embeddings`,
                {
                    model: modelName,
                    prompt: text
                },
                { timeout: this.timeout }
            );

            return {
                embedding: response.data.embedding,
                model: modelName,
                dimensions: response.data.embedding?.length || 0
            };
        } catch (error) {
            logger.error('嵌入向量生成失敗:', error.message);
            throw new Error(`Ollama 嵌入向量生成失敗: ${error.message}`);
        }
    }

    /**
     * 批次生成嵌入向量
     */
    async generateEmbeddings(texts, options = {}) {
        const results = [];

        for (let i = 0; i < texts.length; i++) {
            try {
                const result = await this.generateEmbedding(texts[i], options);
                results.push({
                    index: i,
                    text: texts[i],
                    ...result
                });

                logger.debug(`嵌入向量生成進度: ${i + 1}/${texts.length}`);
            } catch (error) {
                logger.error(`第 ${i + 1} 個文本嵌入失敗:`, error.message);
                results.push({
                    index: i,
                    text: texts[i],
                    error: error.message
                });
            }
        }

        return results;
    }

    /**
     * 藝術史專用摘要生成
     */
    async generateArtSummary(artworkData, type = 'artwork') {
        const templates = {
            artwork: `請為以下藝術作品生成結構化摘要，包括標題、藝術家、時期、描述和藝術意義：

作品資料：
${JSON.stringify(artworkData, null, 2)}

請以繁體中文回答，格式如下：
- 標題：
- 藝術家：
- 時期：
- 描述：
- 藝術意義：`,

            artist: `請為以下藝術家生成結構化摘要，包括姓名、活動時期、藝術風格、主要作品和歷史影響：

藝術家資料：
${JSON.stringify(artworkData, null, 2)}

請以繁體中文回答，格式如下：
- 姓名：
- 活動時期：
- 藝術風格：
- 主要作品：
- 歷史影響：`,

            movement: `請為以下藝術運動生成結構化摘要，包括名稱、時期、特徵、代表藝術家和影響：

藝術運動資料：
${JSON.stringify(artworkData, null, 2)}

請以繁體中文回答，格式如下：
- 名稱：
- 時期：
- 特徵：
- 代表藝術家：
- 影響：`
        };

        const prompt = templates[type] || templates.artwork;

        try {
            const result = await this.generateText(prompt, {
                temperature: 0.3, // 較低溫度確保一致性
                maxTokens: 800
            });

            return {
                summary: result.text,
                type: type,
                model: result.model
            };
        } catch (error) {
            logger.error(`藝術史摘要生成失敗 (${type}):`, error.message);
            throw error;
        }
    }

    /**
     * 藝術史專用翻譯
     */
    async translateArtText(text, sourceLang = 'en', targetLang = 'zh-TW') {
        const langNames = {
            'en': '英文',
            'zh-TW': '繁體中文',
            'zh-CN': '簡體中文',
            'ja': '日文',
            'ko': '韓文',
            'fr': '法文',
            'de': '德文',
            'it': '義大利文',
            'es': '西班牙文'
        };

        const prompt = `請將以下${langNames[sourceLang] || sourceLang}藝術史文本翻譯成${langNames[targetLang] || targetLang}，保持專業術語的準確性：

原文：
${text}

譯文：`;

        try {
            const result = await this.generateText(prompt, {
                temperature: 0.2, // 低溫度確保翻譯一致性
                maxTokens: Math.ceil(text.length * 2) // 預估翻譯長度
            });

            return {
                translation: result.text.trim(),
                sourceLang,
                targetLang,
                model: result.model
            };
        } catch (error) {
            logger.error(`藝術史翻譯失敗 (${sourceLang} -> ${targetLang}):`, error.message);
            throw error;
        }
    }

    /**
     * 藝術作品分類
     */
    async classifyArtwork(artworkData) {
        const prompt = `請分析以下藝術作品並進行分類，包括時期、風格、媒材類型等：

作品資料：
${JSON.stringify(artworkData, null, 2)}

請以JSON格式回答，包含以下分類：
{
  "period": "時期分類（如：renaissance, modern, contemporary等）",
  "style": "風格分類（如：impressionism, abstract, realism等）",
  "medium": "媒材類型（如：oil_painting, sculpture, photography等）",
  "subject": "主題類型（如：portrait, landscape, still_life等）",
  "confidence": "分類信心度（0-1）"
}`;

        try {
            const result = await this.generateText(prompt, {
                temperature: 0.1, // 極低溫度確保格式一致
                maxTokens: 300
            });

            // 嘗試解析 JSON
            const jsonMatch = result.text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const classification = JSON.parse(jsonMatch[0]);
                return {
                    classification,
                    model: result.model
                };
            } else {
                throw new Error('無法解析分類結果');
            }
        } catch (error) {
            logger.error('藝術作品分類失敗:', error.message);
            throw error;
        }
    }

    /**
     * 獲取模型統計資訊
     */
    async getModelStats() {
        try {
            const health = await this.checkHealth();
            return {
                service: 'ollama',
                status: health.status,
                loadedModels: Array.from(this.loadedModels),
                availableModels: this.availableModels.length ? this.availableModels : (health.models?.map(m => m.name) || []),
                defaultModel: this.defaultModel,
                embeddingModel: this.embeddingModel
            };
        } catch (error) {
            logger.error('獲取 Ollama 統計失敗:', error.message);
            return {
                service: 'ollama',
                status: 'error',
                error: error.message
            };
        }
    }
}

// 單例模式
const ollamaService = new OllamaService({
    defaultModel: process.env.OLLAMA_DEFAULT_MODEL || 'gemma4:12B',
    embeddingModel: process.env.OLLAMA_EMBEDDING_MODEL || 'bge-m3:latest',
    baseUrl: process.env.OLLAMA_BASE_URL || 'http://localhost:11434'
});

module.exports = {
    OllamaService,
    ollamaService
};