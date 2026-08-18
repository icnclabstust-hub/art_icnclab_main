#!/usr/bin/env node
/**
 * 簡單測試 ChromaDB 查詢功能
 */

const axios = require('axios');

const CHROMA_BASE_URL = 'http://localhost:8001';
const TENANT = 'default_tenant';
const DATABASE = 'default_database';
const COLLECTION_NAME = 'art_history_collection';

console.log('🔍 測試 ChromaDB 查詢功能');
console.log('='.repeat(60));

async function testChromaDBQuery() {
    try {
        // 1. 獲取集合資訊
        console.log('\n📊 獲取集合資訊...');
        const collectionUrl = `${CHROMA_BASE_URL}/api/v2/tenants/${TENANT}/databases/${DATABASE}/collections/${COLLECTION_NAME}`;

        const collectionInfo = await axios.get(collectionUrl);
        console.log(`✅ 集合: ${collectionInfo.data.name}`);
        console.log(`   ID: ${collectionInfo.data.id}`);
        console.log(`   Metadata: ${JSON.stringify(collectionInfo.data.metadata, null, 2)}`);

        // 2. 測試查詢（使用文本，讓 ChromaDB 自動生成嵌入）
        const testQueries = [
            '達文西的畫作',
            '文藝復興時期',
            '巴洛克風格'
        ];

        for (const query of testQueries) {
            console.log('\n' + '='.repeat(60));
            console.log(`🔎 查詢: ${query}`);
            console.log('='.repeat(60));

            try {
                // 使用 ChromaDB 的查詢 API
                const queryUrl = `${CHROMA_BASE_URL}/api/v2/tenants/${TENANT}/databases/${DATABASE}/collections/${collectionInfo.data.id}/query`;

                const response = await axios.post(queryUrl, {
                    query_texts: [query],  // 使用文本查詢
                    n_results: 3,
                    include: ['metadatas', 'documents', 'distances']
                });

                const { documents, metadatas, distances } = response.data;

                console.log(`\n📊 找到 ${documents[0].length} 個結果:`);

                documents[0].forEach((doc, i) => {
                    const metadata = metadatas[0][i];
                    const distance = distances[0][i];
                    const score = (1 / (1 + distance)).toFixed(3);

                    console.log(`\n[結果 ${i + 1}] 相似度: ${score}`);
                    console.log(`來源: ChromaDB > ${metadata.collection || 'unknown'}`);

                    if (metadata.title) console.log(`標題: ${metadata.title}`);
                    if (metadata.artist) console.log(`藝術家: ${metadata.artist}`);
                    if (metadata.date) console.log(`年代: ${metadata.date}`);
                    if (metadata.style) console.log(`風格: ${metadata.style}`);

                    console.log(`內容: ${doc.substring(0, 150)}...`);
                });

            } catch (error) {
                console.error(`❌ 查詢失敗: ${error.message}`);
                if (error.response) {
                    console.error(`錯誤詳情: ${JSON.stringify(error.response.data)}`);
                }
            }
        }

        console.log('\n' + '='.repeat(60));
        console.log('✅ 測試完成！');
        console.log('='.repeat(60));

    } catch (error) {
        console.error(`❌ 錯誤: ${error.message}`);
        if (error.response) {
            console.error(`詳情: ${JSON.stringify(error.response.data, null, 2)}`);
        }
    }
}

testChromaDBQuery();
