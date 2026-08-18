#!/usr/bin/env node
/**
 * 驗證核心藝術品是否成功整合到Neo4j
 */

const neo4j = require('neo4j-driver');

const masterpieces = [
    "Mona Lisa",
    "The Last Supper",
    "Vitruvian Man",
    "David",
    "The Creation of Adam",
    "Pietà",
    "The School of Athens",
    "Sistine Madonna",
    "The Birth of Venus",
    "Primavera",
    "The Calling of St Matthew",
    "The Night Watch",
    "Girl with a Pearl Earring",
    "Las Meninas",
    "The Descent from the Cross"
];

async function verifyMasterpieces() {
    const driver = neo4j.driver(
        'bolt://localhost:7687',
        neo4j.auth.basic('neo4j', 'CHANGE_ME_NEO4J_PASSWORD')
    );

    console.log('🎨 核心藝術品驗證工具');
    console.log('═══════════════════════════════════════\n');

    const session = driver.session();

    try {
        let found = 0;
        let notFound = 0;

        for (const title of masterpieces) {
            const result = await session.run(`
                MATCH (a:Artwork)
                WHERE a.title CONTAINS $title
                RETURN a.title as title, a.artist as artist, a.date as date, a.period as period
                LIMIT 1
            `, { title });

            if (result.records.length > 0) {
                const record = result.records[0];
                console.log(`✓ ${title}`);
                console.log(`  藝術家: ${record.get('artist')}`);
                console.log(`  年代: ${record.get('date') || 'N/A'}`);
                console.log(`  時期: ${record.get('period') || 'N/A'}`);
                console.log('');
                found++;
            } else {
                console.log(`✗ ${title} - 未找到`);
                console.log('');
                notFound++;
            }
        }

        console.log('═══════════════════════════════════════');
        console.log(`總計: ${masterpieces.length} 件`);
        console.log(`找到: ${found} 件 (${(found/masterpieces.length*100).toFixed(1)}%)`);
        console.log(`未找到: ${notFound} 件`);
        console.log('═══════════════════════════════════════');

    } finally {
        await session.close();
        await driver.close();
    }
}

verifyMasterpieces().catch(console.error);
