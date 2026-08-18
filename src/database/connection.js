/**
 * 資料庫連接管理器
 * 處理PostgreSQL、Redis、Elasticsearch連接
 */

const { Pool } = require('pg');
const redis = require('redis');
const { Client } = require('@elastic/elasticsearch');
require('dotenv').config();

class DatabaseManager {
    constructor() {
        this.pgPool = null;
        this.redisClient = null;
        this.esClient = null;
        this.isConnected = {
            postgres: false,
            redis: false,
            elasticsearch: false
        };
    }

    // PostgreSQL連接
    async connectPostgres() {
        try {
            this.pgPool = new Pool({
                user: process.env.DB_USER || 'postgres',
                host: process.env.DB_HOST || 'localhost',
                database: process.env.DB_NAME || 'art_history_db',
                password: process.env.DB_PASSWORD || 'password',
                port: process.env.DB_PORT || 5432,
                max: 20,
                idleTimeoutMillis: 30000,
                connectionTimeoutMillis: 2000,
            });

            // 測試連接
            const client = await this.pgPool.connect();
            await client.query('SELECT NOW()');
            client.release();

            this.isConnected.postgres = true;
            console.log('✅ PostgreSQL 連接成功');
            return true;
        } catch (error) {
            console.error('❌ PostgreSQL 連接失敗:', error.message);
            this.isConnected.postgres = false;
            return false;
        }
    }

    // Redis連接
    async connectRedis() {
        try {
            this.redisClient = redis.createClient({
                url: process.env.REDIS_URL || 'redis://localhost:6379',
                retry_strategy: (options) => {
                    if (options.error && options.error.code === 'ECONNREFUSED') {
                        return new Error('Redis服務器拒絕連接');
                    }
                    if (options.total_retry_time > 1000 * 60 * 60) {
                        return new Error('重試時間過長');
                    }
                    if (options.attempt > 10) {
                        return undefined;
                    }
                    return Math.min(options.attempt * 100, 3000);
                }
            });

            this.redisClient.on('error', (err) => {
                console.error('Redis錯誤:', err);
                this.isConnected.redis = false;
            });

            this.redisClient.on('connect', () => {
                console.log('✅ Redis 連接成功');
                this.isConnected.redis = true;
            });

            await this.redisClient.connect();
            return true;
        } catch (error) {
            console.error('❌ Redis 連接失敗:', error.message);
            this.isConnected.redis = false;
            return false;
        }
    }

    // Elasticsearch連接
    async connectElasticsearch() {
        try {
            this.esClient = new Client({
                node: process.env.ES_URL || 'http://localhost:9200',
                auth: process.env.ES_USERNAME && process.env.ES_PASSWORD ? {
                    username: process.env.ES_USERNAME,
                    password: process.env.ES_PASSWORD
                } : undefined,
                maxRetries: 5,
                requestTimeout: 60000,
                sniffOnStart: true
            });

            // 測試連接
            const health = await this.esClient.cluster.health();
            console.log('🔍 Elasticsearch 健康檢查回應:', health);

            if (health && (health.statusCode === 200 || health.status === 'green' || health.status === 'yellow')) {
                this.isConnected.elasticsearch = true;
                console.log('✅ Elasticsearch 連接成功');
                return true;
            } else {
                console.warn('⚠️ Elasticsearch 健康檢查未通過:', health);
                this.isConnected.elasticsearch = false;
                return false;
            }
        } catch (error) {
            console.error('❌ Elasticsearch 連接失敗:', error.message);
            this.isConnected.elasticsearch = false;
            return false;
        }
    }

    // 連接所有資料庫
    async connectAll() {
        console.log('🔗 正在連接資料庫...');

        const results = await Promise.allSettled([
            this.connectPostgres(),
            this.connectRedis(),
            this.connectElasticsearch()
        ]);

        const connections = {
            postgres: results[0].status === 'fulfilled' && results[0].value,
            redis: results[1].status === 'fulfilled' && results[1].value,
            elasticsearch: results[2].status === 'fulfilled' && results[2].value
        };

        console.log('📊 連接狀態:', connections);
        return connections;
    }

    // 檢查連接狀態
    async checkConnections() {
        const status = { ...this.isConnected };

        // 檢查PostgreSQL
        if (this.pgPool) {
            try {
                const client = await this.pgPool.connect();
                await client.query('SELECT 1');
                client.release();
                status.postgres = true;
            } catch {
                status.postgres = false;
            }
        }

        // 檢查Redis
        if (this.redisClient && this.redisClient.isOpen) {
            try {
                await this.redisClient.ping();
                status.redis = true;
            } catch {
                status.redis = false;
            }
        }

        // 檢查Elasticsearch
        if (this.esClient) {
            try {
                const health = await this.esClient.cluster.health();
                status.elasticsearch = health && (health.statusCode === 200 || health.status === 'green' || health.status === 'yellow');
            } catch {
                status.elasticsearch = false;
            }
        }

        this.isConnected = status;
        return status;
    }

    // 獲取連接實例
    getPostgresPool() {
        if (!this.isConnected.postgres) {
            throw new Error('PostgreSQL 未連接');
        }
        return this.pgPool;
    }

    getRedisClient() {
        if (!this.isConnected.redis) {
            throw new Error('Redis 未連接');
        }
        return this.redisClient;
    }

    getElasticsearchClient() {
        if (!this.isConnected.elasticsearch) {
            throw new Error('Elasticsearch 未連接');
        }
        return this.esClient;
    }

    // 關閉所有連接
    async closeAll() {
        console.log('🔌 正在關閉資料庫連接...');

        const promises = [];

        if (this.pgPool) {
            promises.push(this.pgPool.end());
        }

        if (this.redisClient && this.redisClient.isOpen) {
            promises.push(this.redisClient.quit());
        }

        if (this.esClient) {
            promises.push(this.esClient.close());
        }

        try {
            await Promise.allSettled(promises);
            console.log('✅ 所有資料庫連接已關閉');
        } catch (error) {
            console.error('❌ 關閉連接時出錯:', error.message);
        }
    }

    // 初始化資料庫結構（開發環境用）
    async initializeDatabaseSchema() {
        if (!this.isConnected.postgres) {
            throw new Error('PostgreSQL 未連接，無法初始化結構');
        }

        try {
            const fs = require('fs');
            const path = require('path');

            // 讀取SQL結構檔案
            const schemaPath = path.join(__dirname, '../../database_schema.sql');
            const schema = fs.readFileSync(schemaPath, 'utf8');

            const client = await this.pgPool.connect();
            await client.query(schema);
            client.release();

            console.log('✅ 資料庫結構初始化完成');
            return true;
        } catch (error) {
            console.error('❌ 資料庫結構初始化失敗:', error.message);
            return false;
        }
    }

    // 設置Elasticsearch索引
    async setupElasticsearchIndices() {
        if (!this.isConnected.elasticsearch) {
            console.warn('⚠️ Elasticsearch 未連接，跳過索引設置');
            return false;
        }

        try {
            // 設置藝術作品索引
            await this.esClient.indices.create({
                index: 'artworks',
                body: {
                    mappings: {
                        properties: {
                            title: { type: 'text', analyzer: 'standard' },
                            description: { type: 'text', analyzer: 'standard' },
                            artist_name: { type: 'text', analyzer: 'standard' },
                            creation_year: { type: 'integer' },
                            style: { type: 'keyword' },
                            medium: { type: 'keyword' },
                            tags: { type: 'keyword' },
                            location: { type: 'text' },
                            significance: { type: 'text', analyzer: 'standard' },
                            created_at: { type: 'date' }
                        }
                    }
                }
            }, { ignore: [400] }); // 忽略已存在錯誤

            // 設置藝術家索引
            await this.esClient.indices.create({
                index: 'artists',
                body: {
                    mappings: {
                        properties: {
                            name: { type: 'text', analyzer: 'standard' },
                            biography: { type: 'text', analyzer: 'standard' },
                            nationality: { type: 'keyword' },
                            art_movement: { type: 'keyword' },
                            birth_year: { type: 'integer' },
                            death_year: { type: 'integer' },
                            created_at: { type: 'date' }
                        }
                    }
                }
            }, { ignore: [400] });

            console.log('✅ Elasticsearch 索引設置完成');
            return true;
        } catch (error) {
            console.error('❌ Elasticsearch 索引設置失敗:', error.message);
            return false;
        }
    }
}

// 單例模式
const dbManager = new DatabaseManager();

module.exports = {
    DatabaseManager,
    dbManager
};