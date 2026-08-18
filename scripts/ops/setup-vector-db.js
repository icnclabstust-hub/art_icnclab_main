#!/usr/bin/env node

/**
 * ChromaDB 向量資料庫初始化腳本
 * 根據 rag-system-config.yaml 配置自動建立集合
 */

const { ChromaClient } = require('chromadb');
const yaml = require('js-yaml');
const fs = require('fs');
const path = require('path');

class VectorDBSetup {
    constructor() {
        this.client = new ChromaClient({
            host: process.env.CHROMADB_HOST || 'localhost',
            port: process.env.CHROMADB_PORT || 8000
        });

        this.config = this.loadConfig();
    }

    loadConfig() {
        try {
            const configPath = path.join(__dirname, '../../rag-system-config.yaml');
            const configFile = fs.readFileSync(configPath, 'utf8');
            return yaml.load(configFile);
        } catch (error) {
            console.error('❌ 載入配置檔案失敗:', error.message);
            process.exit(1);
        }
    }

    async initializeCollections() {
        console.log('🚀 開始初始化 ChromaDB 向量資料庫...\n');

        const vectorConfig = this.config.vector_databases.chromadb;
        const collections = vectorConfig.collections;

        try {
            // 測試連接
            await this.testConnection();

            // 建立各個集合
            for (const [collectionName, config] of Object.entries(collections)) {
                await this.createCollection(collectionName, config, vectorConfig.collection_prefix);
            }

            console.log('\n✅ 向量資料庫初始化完成！');
            return true;

        } catch (error) {
            console.error('❌ 初始化失敗:', error.message);
            return false;
        }
    }

    async testConnection() {
        try {
            const heartbeat = await this.client.heartbeat();
            console.log('💚 ChromaDB 連接成功');
            console.log(`🔧 伺服器版本: ${heartbeat}`);
            return true;
        } catch (error) {
            throw new Error(`無法連接到 ChromaDB: ${error.message}`);
        }
    }

    async createCollection(name, config, prefix = 'art_history') {
        const fullName = `${prefix}_${name}`;

        try {
            // 檢查集合是否已存在
            let collection;
            try {
                collection = await this.client.getCollection({
                    name: fullName
                });
                console.log(`📋 集合 "${fullName}" 已存在，跳過建立`);
                return collection;
            } catch (error) {
                // 集合不存在，建立新的
            }

            // 建立新集合 - 不使用預設嵌入函數，將由外部系統提供
            collection = await this.client.createCollection({
                name: fullName,
                metadata: {
                    description: `藝術史資料庫 - ${name} 向量集合`,
                    embedding_model: config.embedding_model,
                    dimension: config.dimension,
                    index_type: config.index_type || 'HNSW',
                    distance_metric: 'cosine',
                    created_at: new Date().toISOString(),
                    specialized: config.specialized || false
                },
                embeddingFunction: null  // 不使用預設嵌入函數
            });

            console.log(`✅ 已建立集合: ${fullName}`);
            console.log(`   📊 嵌入模型: ${config.embedding_model}`);
            console.log(`   📐 向量維度: ${config.dimension}`);
            console.log(`   🔍 索引類型: ${config.index_type || 'HNSW'}\n`);

            return collection;

        } catch (error) {
            console.error(`❌ 建立集合 "${fullName}" 失敗:`, error.message);
            throw error;
        }
    }

    async listCollections() {
        try {
            const collections = await this.client.listCollections();
            console.log('\n📚 現有集合列表:');
            if (collections.length === 0) {
                console.log('   (無集合)');
            } else {
                collections.forEach((collection, index) => {
                    console.log(`   ${index + 1}. ${collection.name}`);
                    if (collection.metadata) {
                        console.log(`      🏷️  描述: ${collection.metadata.description || 'N/A'}`);
                        console.log(`      📊 嵌入模型: ${collection.metadata.embedding_model || 'N/A'}`);
                        console.log(`      📐 向量維度: ${collection.metadata.dimension || 'N/A'}`);
                    }
                    console.log('');
                });
            }
        } catch (error) {
            console.error('❌ 獲取集合列表失敗:', error.message);
        }
    }

    async getCollectionStats() {
        try {
            const collections = await this.client.listCollections();
            console.log('\n📊 集合統計資訊:');

            for (const collectionInfo of collections) {
                try {
                    const collection = await this.client.getCollection({
                        name: collectionInfo.name
                    });

                    const count = await collection.count();
                    console.log(`   ${collectionInfo.name}: ${count} 個向量`);
                } catch (error) {
                    console.log(`   ${collectionInfo.name}: 無法獲取統計 (${error.message})`);
                }
            }
        } catch (error) {
            console.error('❌ 獲取統計資訊失敗:', error.message);
        }
    }
}

// 主執行程序
async function main() {
    const setup = new VectorDBSetup();

    console.log('='.repeat(60));
    console.log('🎨 藝術史資料庫向量資料庫配置工具');
    console.log('='.repeat(60));

    // 解析命令列參數
    const args = process.argv.slice(2);
    const command = args[0] || 'init';

    switch (command) {
        case 'init': {
            const success = await setup.initializeCollections();
            if (success) {
                await setup.listCollections();
                await setup.getCollectionStats();
            }
            process.exit(success ? 0 : 1);
            break;
        }

        case 'list':
            await setup.testConnection();
            await setup.listCollections();
            await setup.getCollectionStats();
            break;

        case 'stats':
            await setup.testConnection();
            await setup.getCollectionStats();
            break;

        default:
            console.log('使用方法:');
            console.log('  node setup-vector-db.js [命令]');
            console.log('');
            console.log('可用命令:');
            console.log('  init    - 初始化向量資料庫集合（預設）');
            console.log('  list    - 列出所有集合');
            console.log('  stats   - 顯示集合統計資訊');
            process.exit(1);
    }
}

// 處理未捕獲的異常
process.on('unhandledRejection', (reason, promise) => {
    console.error('❌ 未處理的 Promise 拒絕:', reason);
    process.exit(1);
});

if (require.main === module) {
    main().catch(error => {
        console.error('❌ 執行失敗:', error);
        process.exit(1);
    });
}

module.exports = VectorDBSetup;