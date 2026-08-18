#!/usr/bin/env node
/**
 * 為 Neo4j 資料庫添加資料來源標記
 * 使用 Neo4j HTTP API (Cypher Transactional Endpoint)
 */

const axios = require('axios');

class SourceMetadataAdder {
    constructor() {
        this.neo4jUrl = 'http://localhost:7474';
        this.username = 'neo4j';
        this.password = 'CHANGE_ME_NEO4J_PASSWORD';
        this.auth = Buffer.from(`${this.username}:${this.password}`).toString('base64');

        this.stats = {
            artists_wikiart: 0,
            artists_met: 0,
            artworks_met: 0,
            artworks_other: 0,
            total_updated: 0
        };
    }

    async executeCypher(query) {
        /**
         * 執行 Cypher 查詢
         */
        try {
            const response = await axios.post(
                `${this.neo4jUrl}/db/neo4j/tx/commit`,
                {
                    statements: [
                        {
                            statement: query,
                            resultDataContents: ['row'],
                            includeStats: true
                        }
                    ]
                },
                {
                    headers: {
                        'Authorization': `Basic ${this.auth}`,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                }
            );

            if (response.data.errors && response.data.errors.length > 0) {
                throw new Error(JSON.stringify(response.data.errors));
            }

            return response.data.results[0];

        } catch (error) {
            console.error(`❌ 查詢失敗: ${error.message}`);
            if (error.response) {
                console.error(`詳情: ${JSON.stringify(error.response.data)}`);
            }
            throw error;
        }
    }

    async testConnection() {
        /**
         * 測試 Neo4j 連接
         */
        try {
            console.log('🔌 測試 Neo4j 連接...');
            const result = await this.executeCypher('RETURN 1 as test');
            console.log('✅ Neo4j 連接成功\n');
            return true;
        } catch (error) {
            console.error('❌ Neo4j 連接失敗');
            return false;
        }
    }

    async addWikiArtSource() {
        /**
         * 為 WikiArt 藝術家添加來源
         */
        console.log('📊 為 WikiArt 藝術家添加來源...');

        const query = `
            MATCH (a:Artist)
            WHERE a.url IS NOT NULL
              AND (a.url CONTAINS 'wikiart' OR a.url CONTAINS 'WikiArt')
              AND a.original_source IS NULL
            SET a.original_source = 'WikiArt',
                a.source_type = 'api',
                a.source_url = a.url,
                a.source_database = 'neo4j',
                a.source_collection = 'graph_database'
            RETURN count(a) as count
        `;

        try {
            const result = await this.executeCypher(query);
            const count = result.data[0]?.row[0] || 0;
            this.stats.artists_wikiart = count;
            console.log(`✅ 更新了 ${count} 位 WikiArt 藝術家\n`);
            return count;
        } catch (error) {
            console.error('❌ WikiArt 藝術家更新失敗\n');
            return 0;
        }
    }

    async addMetArtistsSource() {
        /**
         * 為 Met Museum 藝術家添加來源
         */
        console.log('📊 為 Met Museum 藝術家添加來源...');

        const query = `
            MATCH (a:Artist)<-[:CREATED_BY]-(w:Artwork)
            WHERE w.objectID IS NOT NULL
              AND a.original_source IS NULL
            WITH DISTINCT a
            SET a.original_source = 'Met Museum API',
                a.source_type = 'api',
                a.source_database = 'neo4j',
                a.source_collection = 'graph_database'
            RETURN count(a) as count
        `;

        try {
            const result = await this.executeCypher(query);
            const count = result.data[0]?.row[0] || 0;
            this.stats.artists_met = count;
            console.log(`✅ 更新了 ${count} 位 Met Museum 藝術家\n`);
            return count;
        } catch (error) {
            console.error('❌ Met Museum 藝術家更新失敗\n');
            return 0;
        }
    }

    async addMetArtworksSource() {
        /**
         * 為 Met Museum 作品添加來源
         */
        console.log('📊 為 Met Museum 作品添加來源...');

        const query = `
            MATCH (w:Artwork)
            WHERE w.objectID IS NOT NULL
              AND w.original_source IS NULL
            SET w.original_source = 'Met Museum API',
                w.source_type = 'api',
                w.source_url = 'https://www.metmuseum.org/art/collection/search/' + toString(w.objectID),
                w.source_database = 'neo4j',
                w.source_collection = 'graph_database'
            RETURN count(w) as count
        `;

        try {
            const result = await this.executeCypher(query);
            const count = result.data[0]?.row[0] || 0;
            this.stats.artworks_met = count;
            console.log(`✅ 更新了 ${count} 件 Met Museum 作品\n`);
            return count;
        } catch (error) {
            console.error('❌ Met Museum 作品更新失敗\n');
            return 0;
        }
    }

    async addOtherArtworksSource() {
        /**
         * 為其他來源作品添加標記
         */
        console.log('📊 為其他來源作品添加來源...');

        const query = `
            MATCH (w:Artwork)
            WHERE w.objectID IS NULL
              AND w.original_source IS NULL
            SET w.original_source = 'Internal Knowledge Base',
                w.source_type = 'curated',
                w.source_database = 'neo4j',
                w.source_collection = 'graph_database'
            RETURN count(w) as count
        `;

        try {
            const result = await this.executeCypher(query);
            const count = result.data[0]?.row[0] || 0;
            this.stats.artworks_other = count;
            console.log(`✅ 更新了 ${count} 件內部知識庫作品\n`);
            return count;
        } catch (error) {
            console.error('❌ 其他作品更新失敗\n');
            return 0;
        }
    }

    async verifyUpdates() {
        /**
         * 驗證更新結果
         */
        console.log('📊 驗證更新結果...\n');

        const query = `
            MATCH (a:Artist)
            WHERE a.original_source = 'WikiArt'
            RETURN 'WikiArt Artists' as type, count(a) as count
            UNION ALL
            MATCH (a:Artist)
            WHERE a.original_source = 'Met Museum API'
            RETURN 'Met Museum Artists' as type, count(a) as count
            UNION ALL
            MATCH (w:Artwork)
            WHERE w.original_source = 'Met Museum API'
            RETURN 'Met Museum Artworks' as type, count(w) as count
            UNION ALL
            MATCH (w:Artwork)
            WHERE w.original_source = 'Internal Knowledge Base'
            RETURN 'Internal Artworks' as type, count(w) as count
            UNION ALL
            MATCH (n)
            WHERE (n:Artist OR n:Artwork)
              AND n.original_source IS NULL
            RETURN 'Unmarked Nodes' as type, count(n) as count
        `;

        try {
            const result = await this.executeCypher(query);

            console.log('='.repeat(60));
            console.log('資料來源統計:');
            console.log('='.repeat(60));

            result.data.forEach(item => {
                const type = item.row[0];
                const count = item.row[1];
                console.log(`${type}: ${count}`);
            });

            console.log('='.repeat(60) + '\n');

        } catch (error) {
            console.error('❌ 驗證失敗\n');
        }
    }

    async run() {
        /**
         * 執行所有更新
         */
        console.log('🚀 開始為 Neo4j 添加資料來源標記...\n');
        console.log('='.repeat(60) + '\n');

        // 測試連接
        if (!await this.testConnection()) {
            return false;
        }

        try {
            // 1. WikiArt 藝術家
            await this.addWikiArtSource();

            // 2. Met Museum 藝術家
            await this.addMetArtistsSource();

            // 3. Met Museum 作品
            await this.addMetArtworksSource();

            // 4. 其他作品
            await this.addOtherArtworksSource();

            // 5. 驗證
            await this.verifyUpdates();

            // 計算總數
            this.stats.total_updated =
                this.stats.artists_wikiart +
                this.stats.artists_met +
                this.stats.artworks_met +
                this.stats.artworks_other;

            // 顯示統計
            console.log('='.repeat(60));
            console.log('更新統計:');
            console.log('='.repeat(60));
            console.log(`WikiArt 藝術家: ${this.stats.artists_wikiart}`);
            console.log(`Met Museum 藝術家: ${this.stats.artists_met}`);
            console.log(`Met Museum 作品: ${this.stats.artworks_met}`);
            console.log(`內部知識庫作品: ${this.stats.artworks_other}`);
            console.log(`總更新數: ${this.stats.total_updated}`);
            console.log('='.repeat(60));

            console.log('\n✅ 資料來源標記添加完成！');

            console.log('\n💡 下一步:');
            console.log('   1. 測試多資料庫檢索:');
            console.log('      node test-multi-database-retrieval.js');
            console.log('');
            console.log('   2. 創建多資料庫 RAG 服務器');
            console.log('   3. 更新 OpenWebUI v4.0');

            return true;

        } catch (error) {
            console.error('\n❌ 執行失敗:', error.message);
            return false;
        }
    }
}

async function main() {
    const adder = new SourceMetadataAdder();
    const success = await adder.run();

    if (success) {
        console.log('\n🎉 成功！');
        process.exit(0);
    } else {
        console.error('\n❌ 失敗');
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = SourceMetadataAdder;
