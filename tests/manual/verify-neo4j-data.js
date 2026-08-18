#!/usr/bin/env node
/**
 * 驗證Neo4j中的Renaissance和Baroque資料
 */

const neo4j = require('neo4j-driver');

const NEO4J_URI = 'bolt://localhost:7687';
const NEO4J_USER = 'neo4j';
const NEO4J_PASSWORD = 'CHANGE_ME_NEO4J_PASSWORD';

async function verifyData() {
    console.log('🔍 驗證Neo4j中的Renaissance和Baroque資料\n');

    const driver = neo4j.driver(
        NEO4J_URI,
        neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD)
    );

    const session = driver.session();

    try {
        // 1. 統計Renaissance和Baroque作品
        const periodResult = await session.run(`
            MATCH (a:Artwork)
            WHERE a.period IN ['Renaissance', 'Baroque']
            RETURN a.period as period, count(a) as count
            ORDER BY count DESC
        `);

        console.log('📊 時期統計:');
        periodResult.records.forEach(record => {
            const period = record.get('period');
            const count = record.get('count').toNumber();
            console.log(`   ${period}: ${count} 件作品`);
        });

        // 2. 找出Renaissance時期的著名藝術家
        const renaissanceArtists = await session.run(`
            MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
            WHERE artwork.period = 'Renaissance'
            RETURN artist.name as name, count(artwork) as artworks
            ORDER BY artworks DESC
            LIMIT 10
        `);

        console.log('\n🎨 文藝復興時期藝術家（作品數前10）:');
        renaissanceArtists.records.forEach((record, index) => {
            const name = record.get('name');
            const artworks = record.get('artworks').toNumber();
            console.log(`   ${index + 1}. ${name}: ${artworks} 件作品`);
        });

        // 3. 找出Baroque時期的著名藝術家
        const baroqueArtists = await session.run(`
            MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
            WHERE artwork.period = 'Baroque'
            RETURN artist.name as name, count(artwork) as artworks
            ORDER BY artworks DESC
            LIMIT 10
        `);

        console.log('\n🎭 巴洛克時期藝術家（作品數前10）:');
        baroqueArtists.records.forEach((record, index) => {
            const name = record.get('name');
            const artworks = record.get('artworks').toNumber();
            console.log(`   ${index + 1}. ${name}: ${artworks} 件作品`);
        });

        // 4. 示例作品查詢
        const sampleArtworks = await session.run(`
            MATCH (artist:Artist)-[:CREATED]->(artwork:Artwork)
            WHERE artwork.period IN ['Renaissance', 'Baroque']
              AND artwork.is_highlight = true
              AND artwork.primary_image <> ''
            RETURN artwork.title as title,
                   artist.name as artist,
                   artwork.period as period,
                   artwork.date as date,
                   artwork.medium as medium
            LIMIT 5
        `);

        console.log('\n✨ 精選作品示例:');
        sampleArtworks.records.forEach((record, index) => {
            console.log(`\n   ${index + 1}. ${record.get('title')}`);
            console.log(`      藝術家: ${record.get('artist')}`);
            console.log(`      時期: ${record.get('period')}`);
            console.log(`      日期: ${record.get('date')}`);
            console.log(`      媒材: ${record.get('medium')}`);
        });

        // 5. 測試圖查詢 - 找出與Leonardo da Vinci同時期的藝術家
        console.log('\n🔗 關聯查詢測試：尋找文藝復興時期的藝術家網絡');
        const networkQuery = await session.run(`
            MATCH (a1:Artist)-[:CREATED]->(artwork1:Artwork)
            WHERE artwork1.period = 'Renaissance'
            WITH a1, count(artwork1) as works1
            WHERE works1 > 3
            RETURN a1.name as artist,
                   a1.nationality as nationality,
                   works1 as artwork_count
            ORDER BY works1 DESC
            LIMIT 8
        `);

        networkQuery.records.forEach(record => {
            const artist = record.get('artist');
            const nationality = record.get('nationality') || '未知';
            const count = record.get('artwork_count').toNumber();
            console.log(`   - ${artist} (${nationality}): ${count} 件作品`);
        });

        console.log('\n✅ 驗證完成！資料已成功匯入Neo4j並可供查詢。');

    } finally {
        await session.close();
        await driver.close();
    }
}

verifyData().catch(console.error);
