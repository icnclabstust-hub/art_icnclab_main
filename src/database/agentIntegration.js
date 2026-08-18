/**
 * Agent系統與資料庫集成模組
 * 提供Agent系統訪問資料庫的橋接功能
 */

const { spawn } = require('child_process');
const path = require('path');
const EventEmitter = require('events');
const { Artist, Artwork, Institution, DocumentVector, CrawlTask } = require('./models');
const { dbManager } = require('./connection');

class AgentDatabaseBridge extends EventEmitter {
    constructor() {
        super();
        this.artistModel = new Artist();
        this.artworkModel = new Artwork();
        this.institutionModel = new Institution();
        this.documentVectorModel = new DocumentVector();
        this.crawlTaskModel = new CrawlTask();
        this.agentProcess = null;
        this.isAgentRunning = false;
        this.logger = require('../utils/logger');
    }

    // 啟動Agent系統
    async startAgentSystem() {
        try {
            console.log('🤖 啟動Agent系統...');

            // 檢查資料庫連接
            const dbStatus = await dbManager.checkConnections();
            if (!dbStatus.postgres) {
                throw new Error('PostgreSQL資料庫未連接，無法啟動Agent系統');
            }

            // 啟動Python Agent系統
            const agentPath = path.join(__dirname, '../mcp_agent_system.py');
            this.agentProcess = spawn('python3', [agentPath], {
                cwd: path.join(__dirname, '../..'),
                stdio: ['pipe', 'pipe', 'pipe'],
                env: {
                    ...process.env,
                    PYTHONPATH: path.join(__dirname, '../..'),
                    NODE_DB_HOST: process.env.DB_HOST || 'localhost',
                    NODE_DB_PORT: process.env.DB_PORT || '5432',
                    NODE_DB_NAME: process.env.DB_NAME || 'art_history_db',
                    NODE_DB_USER: process.env.DB_USER || 'postgres',
                    NODE_DB_PASSWORD: process.env.DB_PASSWORD || 'password'
                }
            });

            this.agentProcess.stdout.on('data', (data) => {
                const message = data.toString().trim();
                console.log(`[Agent System] ${message}`);
                this.emit('agent_output', message);
            });

            this.agentProcess.stderr.on('data', (data) => {
                const error = data.toString().trim();
                console.error(`[Agent System Error] ${error}`);
                this.emit('agent_error', error);
            });

            this.agentProcess.on('close', (code) => {
                console.log(`[Agent System] 進程結束，退出碼: ${code}`);
                this.isAgentRunning = false;
                this.emit('agent_stopped', code);
            });

            this.isAgentRunning = true;
            this.emit('agent_started');

            console.log('✅ Agent系統啟動成功');
            return true;
        } catch (error) {
            console.error('❌ Agent系統啟動失敗:', error.message);
            this.emit('agent_start_failed', error);
            return false;
        }
    }

    // 停止Agent系統
    async stopAgentSystem() {
        if (this.agentProcess && this.isAgentRunning) {
            console.log('🛑 正在停止Agent系統...');
            this.agentProcess.kill('SIGTERM');

            // 等待進程結束
            return new Promise((resolve) => {
                const timeout = setTimeout(() => {
                    this.agentProcess.kill('SIGKILL');
                    resolve(false);
                }, 5000);

                this.agentProcess.on('close', () => {
                    clearTimeout(timeout);
                    console.log('✅ Agent系統已停止');
                    resolve(true);
                });
            });
        }
        return true;
    }

    // 發送消息給Agent系統
    async sendToAgent(command, data = {}) {
        if (!this.isAgentRunning || !this.agentProcess) {
            throw new Error('Agent系統未運行');
        }

        const message = JSON.stringify({
            command: command,
            data: data,
            timestamp: new Date().toISOString()
        });

        this.agentProcess.stdin.write(message + '\n');
        return true;
    }

    // 為爬蟲Agent提供的資料庫操作
    async handleCrawlerData(crawlerResults) {
        try {
            const results = {
                artists: [],
                artworks: [],
                institutions: [],
                errors: []
            };

            for (const item of crawlerResults) {
                try {
                    switch (item.type) {
                        case 'artist': {
                            const artist = await this.artistModel.createArtist(item.data);
                            results.artists.push(artist);
                            break;
                        }

                        case 'artwork': {
                            const artwork = await this.artworkModel.createArtwork(item.data);
                            results.artworks.push(artwork);
                            break;
                        }

                        case 'institution': {
                            const institution = await this.institutionModel.createInstitution(item.data);
                            results.institutions.push(institution);
                            break;
                        }

                        default:
                            throw new Error(`未知的資料類型: ${item.type}`);
                    }
                } catch (itemError) {
                    results.errors.push({
                        item: item,
                        error: itemError.message
                    });
                }
            }

            return results;
        } catch (error) {
            this.logger.error('處理爬蟲資料時出錯:', error);
            throw error;
        }
    }

    // 為分類Agent提供的標籤操作
    async handleClassificationResults(classificationResults) {
        try {
            const results = [];

            for (const result of classificationResults) {
                const { artwork_id, tags, confidence_scores } = result;

                // 為藝術作品添加標籤
                if (tags && tags.length > 0) {
                    const tagResults = await this.artworkModel.addTags(
                        artwork_id,
                        tags,
                        'classification_agent'
                    );
                    results.push({
                        artwork_id,
                        tags_added: tagResults.length,
                        confidence: confidence_scores
                    });
                }
            }

            return results;
        } catch (error) {
            this.logger.error('處理分類結果時出錯:', error);
            throw error;
        }
    }

    // 為摘要翻譯Agent提供的文檔向量操作
    async handleSummarizationResults(summarizationResults) {
        try {
            const results = [];

            for (const result of summarizationResults) {
                const {
                    content_id,
                    content_type,
                    title,
                    summary,
                    translations,
                    embedding
                } = result;

                // 創建向量文檔
                const docData = {
                    content_id,
                    content_type,
                    title: title || `${content_type}_${content_id}`,
                    content: summary,
                    content_summary: summary,
                    embedding: embedding,
                    metadata: {
                        translations: translations || {},
                        generated_by: 'summarization_agent',
                        generated_at: new Date().toISOString()
                    }
                };

                const document = await this.documentVectorModel.createDocument(docData);
                results.push(document);
            }

            return results;
        } catch (error) {
            this.logger.error('處理摘要翻譯結果時出錯:', error);
            throw error;
        }
    }

    // 獲取爬蟲任務
    async getCrawlTasks(limit = 10) {
        try {
            return await this.crawlTaskModel.getPendingTasks(limit);
        } catch (error) {
            this.logger.error('獲取爬蟲任務時出錯:', error);
            throw error;
        }
    }

    // 更新爬蟲任務狀態
    async updateCrawlTaskStatus(taskId, status, errorMessage = null, results = null) {
        try {
            return await this.crawlTaskModel.updateTaskStatus(
                taskId,
                status,
                errorMessage,
                results
            );
        } catch (error) {
            this.logger.error('更新爬蟲任務狀態時出錯:', error);
            throw error;
        }
    }

    // 創建新的爬蟲任務
    async createCrawlTask(taskData) {
        try {
            return await this.crawlTaskModel.createTask(taskData);
        } catch (error) {
            this.logger.error('創建爬蟲任務時出錯:', error);
            throw error;
        }
    }

    // 獲取藝術作品資料（用於分類和摘要）
    async getArtworkForProcessing(artworkId) {
        try {
            const artwork = await this.artworkModel.getArtworkDetails(artworkId);
            if (!artwork) {
                throw new Error(`藝術作品不存在: ${artworkId}`);
            }

            return artwork;
        } catch (error) {
            this.logger.error('獲取藝術作品資料時出錯:', error);
            throw error;
        }
    }

    // 批量獲取需要處理的藝術作品
    async getArtworksForBatchProcessing(limit = 50, processingType = null) {
        try {
            let query = `
                SELECT a.*, ar.name as artist_name
                FROM artworks a
                LEFT JOIN artists ar ON a.artist_id = ar.id
            `;

            const params = [];

            // 根據處理類型添加篩選條件
            if (processingType === 'classification') {
                query += `
                    LEFT JOIN artwork_tags at ON a.id = at.artwork_id
                    WHERE at.artwork_id IS NULL
                `;
            } else if (processingType === 'summarization') {
                query += `
                    LEFT JOIN document_vectors dv ON a.id = dv.content_id AND dv.content_type = 'artwork'
                    WHERE dv.content_id IS NULL AND a.description IS NOT NULL
                `;
            }

            query += ` ORDER BY a.created_at DESC LIMIT $${params.length + 1}`;
            params.push(limit);

            const result = await this.artworkModel.query(query, params);
            return result.rows;
        } catch (error) {
            this.logger.error('批量獲取藝術作品時出錯:', error);
            throw error;
        }
    }

    // 搜索相似作品（用於RAG檢索）
    async searchSimilarArtworks(queryEmbedding, limit = 10) {
        try {
            return await this.documentVectorModel.semanticSearch(
                queryEmbedding,
                'artwork',
                limit
            );
        } catch (error) {
            this.logger.error('搜索相似作品時出錯:', error);
            throw error;
        }
    }

    // 獲取資料庫統計信息
    async getDatabaseStatistics() {
        try {
            const { Analytics } = require('./models');
            const analytics = new Analytics();

            const stats = await analytics.getDatabaseStats();
            const popularTags = await analytics.getPopularTags(10);
            const periodStats = await analytics.getArtworksByPeriod();
            const crawlStats = await analytics.getCrawlTaskStats();

            return {
                database_stats: stats,
                popular_tags: popularTags,
                period_distribution: periodStats,
                crawl_statistics: crawlStats,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            this.logger.error('獲取資料庫統計時出錯:', error);
            throw error;
        }
    }

    // Agent系統健康檢查
    async getSystemHealth() {
        try {
            const dbStatus = await dbManager.checkConnections();

            return {
                database: dbStatus,
                agent_system: {
                    running: this.isAgentRunning,
                    process_id: this.agentProcess ? this.agentProcess.pid : null
                },
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            this.logger.error('獲取系統健康狀態時出錯:', error);
            throw error;
        }
    }

    // 清理和關閉
    async cleanup() {
        console.log('🧹 正在清理Agent資料庫橋接...');
        await this.stopAgentSystem();
        this.removeAllListeners();
        console.log('✅ Agent資料庫橋接清理完成');
    }
}

// 創建全局單例
const agentDatabaseBridge = new AgentDatabaseBridge();

// 優雅關機處理
process.on('SIGTERM', async () => {
    await agentDatabaseBridge.cleanup();
    process.exit(0);
});

process.on('SIGINT', async () => {
    await agentDatabaseBridge.cleanup();
    process.exit(0);
});

module.exports = {
    AgentDatabaseBridge,
    agentDatabaseBridge
};