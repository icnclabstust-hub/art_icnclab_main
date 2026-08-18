#!/usr/bin/env node
/**
 * RAG系統查詢演示 - Renaissance & Baroque
 * 展示如何透過Neo4j Graph RAG查詢藝術史資料
 */

const neo4j = require('neo4j-driver');

const NEO4J_URI = 'bolt://localhost:7687';
const NEO4J_USER = 'neo4j';
const NEO4J_PASSWORD = 'CHANGE_ME_NEO4J_PASSWORD';

class ArtHistoryRAG {
    constructor() {
        this.driver = neo4j.driver(
            NEO4J_URI,
            neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD)
        );
    }

    async queryByArtist(artistName) {
        const session = this.driver.session();
        try {
            console.log(`\n🔍 查詢藝術家: ${artistName}`);
            console.log('━'.repeat(60));

            const result = await session.run(`
                MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
                WHERE artist.name CONTAINS $artistName
                  AND artwork.period IN ['Renaissance', 'Baroque']
                RETURN artist.name as artist_name,
                       artist.nationality as nationality,
                       artist.birth_year as birth_year,
                       artist.death_year as death_year,
                       artwork.title as title,
                       artwork.date as date,
                       artwork.medium as medium,
                       artwork.period as period,
                       artwork.primary_image as image,
                       artwork.object_url as url
                ORDER BY artwork.date
            `, { artistName });

            if (result.records.length === 0) {
                console.log(`❌ 找不到藝術家 "${artistName}" 的作品`);
                return [];
            }

            const artworks = result.records.map(record => ({
                artist: record.get('artist_name'),
                nationality: record.get('nationality'),
                birth: record.get('birth_year'),
                death: record.get('death_year'),
                title: record.get('title'),
                date: record.get('date'),
                medium: record.get('medium'),
                period: record.get('period'),
                image: record.get('image'),
                url: record.get('url')
            }));

            const artist = artworks[0];
            console.log(`\n👨‍🎨 ${artist.artist}`);
            if (artist.nationality) console.log(`   國籍: ${artist.nationality}`);
            if (artist.birth && artist.death) {
                console.log(`   生卒年: ${artist.birth} - ${artist.death}`);
            }

            console.log(`\n📚 作品列表 (共 ${artworks.length} 件):`);
            artworks.forEach((artwork, index) => {
                console.log(`\n   ${index + 1}. ${artwork.title}`);
                console.log(`      時期: ${artwork.period}`);
                console.log(`      日期: ${artwork.date || '未知'}`);
                console.log(`      媒材: ${artwork.medium || '未知'}`);
                if (artwork.image) {
                    console.log(`      圖片: ✓`);
                }
                if (artwork.url) {
                    console.log(`      詳情: ${artwork.url}`);
                }
            });

            return artworks;

        } finally {
            await session.close();
        }
    }

    async queryByPeriod(period, limit = 10) {
        const session = this.driver.session();
        try {
            console.log(`\n🔍 查詢時期: ${period}`);
            console.log('━'.repeat(60));

            const result = await session.run(`
                MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
                WHERE artwork.period = $period
                  AND artwork.primary_image <> ''
                RETURN artist.name as artist,
                       artwork.title as title,
                       artwork.date as date,
                       artwork.medium as medium,
                       artwork.classification as classification,
                       artwork.is_highlight as is_highlight
                ORDER BY artwork.is_highlight DESC, artwork.accession_year DESC
                LIMIT $limit
            `, { period, limit: neo4j.int(limit) });

            if (result.records.length === 0) {
                console.log(`❌ 找不到 ${period} 時期的作品`);
                return [];
            }

            console.log(`\n找到 ${result.records.length} 件 ${period} 時期的作品:\n`);

            const artworks = result.records.map((record, index) => {
                const artwork = {
                    artist: record.get('artist'),
                    title: record.get('title'),
                    date: record.get('date'),
                    medium: record.get('medium'),
                    classification: record.get('classification'),
                    is_highlight: record.get('is_highlight')
                };

                console.log(`${index + 1}. ${artwork.title}`);
                console.log(`   藝術家: ${artwork.artist}`);
                console.log(`   日期: ${artwork.date || '未知'}`);
                console.log(`   類型: ${artwork.classification || '未知'}`);
                if (artwork.is_highlight) console.log(`   ⭐ 精選作品`);
                console.log();

                return artwork;
            });

            return artworks;

        } finally {
            await session.close();
        }
    }

    async compareArtists(artist1, artist2) {
        const session = this.driver.session();
        try {
            console.log(`\n🔍 比較藝術家: ${artist1} vs ${artist2}`);
            console.log('━'.repeat(60));

            const result = await session.run(`
                MATCH (a1:Artist)-[:CREATED]->(art1:Artwork)
                WHERE a1.name CONTAINS $artist1
                  AND art1.period IN ['Renaissance', 'Baroque']
                WITH a1, art1.period as period, count(art1) as count1

                MATCH (a2:Artist)-[:CREATED]->(art2:Artwork)
                WHERE a2.name CONTAINS $artist2
                  AND art2.period IN ['Renaissance', 'Baroque']
                WITH a1, period, count1, a2, art2.period as period2, count(art2) as count2
                WHERE period = period2

                RETURN a1.name as artist1_name,
                       a2.name as artist2_name,
                       period,
                       count1,
                       count2,
                       a1.nationality as nat1,
                       a2.nationality as nat2
            `, { artist1, artist2 });

            if (result.records.length === 0) {
                console.log(`❌ 找不到可比較的資料`);
                return;
            }

            result.records.forEach(record => {
                const period = record.get('period');
                const a1_name = record.get('artist1_name');
                const a2_name = record.get('artist2_name');
                const count1 = record.get('count1').toNumber();
                const count2 = record.get('count2').toNumber();
                const nat1 = record.get('nat1');
                const nat2 = record.get('nat2');

                console.log(`\n${period} 時期:`);
                console.log(`  ${a1_name} (${nat1 || '未知'}):`);
                console.log(`    作品數: ${count1}`);
                console.log(`  ${a2_name} (${nat2 || '未知'}):`);
                console.log(`    作品數: ${count2}`);
            });

        } finally {
            await session.close();
        }
    }

    async searchByKeyword(keyword) {
        const session = this.driver.session();
        try {
            console.log(`\n🔍 關鍵字搜尋: "${keyword}"`);
            console.log('━'.repeat(60));

            const result = await session.run(`
                MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
                WHERE (toLower(artwork.title) CONTAINS toLower($keyword)
                   OR toLower(artwork.medium) CONTAINS toLower($keyword)
                   OR toLower(artist.name) CONTAINS toLower($keyword))
                  AND artwork.period IN ['Renaissance', 'Baroque']
                RETURN artist.name as artist,
                       artwork.title as title,
                       artwork.period as period,
                       artwork.date as date,
                       artwork.medium as medium
                LIMIT 15
            `, { keyword });

            if (result.records.length === 0) {
                console.log(`❌ 找不到包含 "${keyword}" 的作品`);
                return [];
            }

            console.log(`\n找到 ${result.records.length} 件相關作品:\n`);

            const artworks = result.records.map((record, index) => {
                const artwork = {
                    artist: record.get('artist'),
                    title: record.get('title'),
                    period: record.get('period'),
                    date: record.get('date'),
                    medium: record.get('medium')
                };

                console.log(`${index + 1}. ${artwork.title}`);
                console.log(`   藝術家: ${artwork.artist}`);
                console.log(`   時期: ${artwork.period}`);
                console.log(`   日期: ${artwork.date || '未知'}`);
                console.log();

                return artwork;
            });

            return artworks;

        } finally {
            await session.close();
        }
    }

    async close() {
        await this.driver.close();
    }
}

async function main() {
    console.log('🎨 藝術史資料庫 - RAG查詢演示');
    console.log('Renaissance & Baroque 時期');
    console.log('='.repeat(60));

    const rag = new ArtHistoryRAG();

    try {
        // 演示1: 查詢特定藝術家
        await rag.queryByArtist('Leonardo da Vinci');

        // 演示2: 查詢特定時期
        await rag.queryByPeriod('Renaissance', 8);

        // 演示3: 比較兩位藝術家
        await rag.compareArtists('Leonardo', 'Michelangelo');

        // 演示4: 關鍵字搜尋
        await rag.searchByKeyword('portrait');

        console.log('\n' + '='.repeat(60));
        console.log('✅ RAG查詢演示完成！');
        console.log('\n💡 系統已準備好回答藝術史問題');
        console.log('   - 支援藝術家查詢');
        console.log('   - 支援時期瀏覽');
        console.log('   - 支援作品比較');
        console.log('   - 支援關鍵字搜尋');
        console.log('   - 支援圖關係查詢\n');

    } finally {
        await rag.close();
    }
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = ArtHistoryRAG;
