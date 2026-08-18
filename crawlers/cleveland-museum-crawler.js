#!/usr/bin/env node
/**
 * 克里夫蘭藝術博物館 (Cleveland Museum of Art) API 爬蟲
 * 官方 Open Access API 免費開放，不需要 API Key: https://openaccess-api.clevelandart.org/
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

const SEARCH_QUERIES = [
    'Renaissance', 'Baroque', 'Impressionism', 'Modern art', 'Contemporary art',
    'American art', 'Asian art', 'African art', 'Egyptian art', 'Islamic art',
    'medieval art', 'photography', 'textile', 'ceramics', 'sculpture',
    'painting', 'drawing', 'print', 'decorative arts', 'ancient art'
];

class ClevelandMuseumCrawler {
    constructor() {
        this.baseUrl = 'https://openaccess-api.clevelandart.org/api/artworks';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'cleveland_museum');
        this.collectedData = [];
        this.perQueryLimit = 15;
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    async searchQuery(query, limit) {
        try {
            console.log(`🔍 搜尋: "${query}"`);
            const response = await axios.get(this.baseUrl, {
                params: { q: query, limit, has_image: 1 },
                timeout: 30000
            });

            const data = response.data?.data || [];
            console.log(`   📊 收集 ${data.length} 件`);
            return data;
        } catch (error) {
            console.error(`❌ 搜尋失敗 ("${query}"):`, error.message);
            return [];
        }
    }

    // 品質分數：比照 Europeana 的 4 大類 100 分制，依本 API 實際可取得的欄位調整配分
    calculateQualityScore(normalized) {
        let score = 0;
        // 基本資訊完整性 (40分)
        if (normalized.title && normalized.title !== 'Untitled') score += 10;
        if (normalized.artist && normalized.artist !== 'Unknown Artist') score += 10;
        if (normalized.date && normalized.date !== 'Unknown Date') score += 10;
        if (normalized.description) score += 10;
        // 媒體資源 (30分)
        if (normalized.imageUrl) score += 20;
        if (normalized.objectURL) score += 10;
        // 元數據豐富度 (20分)
        if (normalized.medium) score += 10;
        if (normalized.department) score += 10;
        // 來源可信度 (10分，有明確產地/文化脈絡資訊視為文獻紀錄較完整)
        if (normalized.culture) score += 10;
        return Math.min(score, 100);
    }

    normalizeItem(item) {
        // creators[].description 格式為 "姓名 (國籍, 生卒年)"，本身就含逗號，
        // 只取名字部分（第一個左括號之前），避免後續依逗號拆分多位創作者時被誤切開
        const creators = (item.creators || [])
            .map(c => (c.description || '').split('(')[0].trim())
            .filter(Boolean);
        const normalized = {
            id: item.id,
            title: item.title || 'Untitled',
            artist: creators.length ? creators.join(', ') : 'Unknown Artist',
            date: item.creation_date || 'Unknown Date',
            medium: item.technique || null,
            department: item.department || null,
            culture: item.culture ? (Array.isArray(item.culture) ? item.culture.join(', ') : item.culture) : null,
            description: item.description || item.wall_description || null,
            imageUrl: item.images?.web?.url || item.images?.print?.url || null,
            objectURL: item.url || null,
            source: 'Cleveland Museum of Art',
            crawledAt: new Date().toISOString()
        };
        normalized.qualityScore = this.calculateQualityScore(normalized);
        return normalized;
    }

    async crawlArtworks() {
        console.log('🚀 開始克里夫蘭藝術博物館資料收集...');
        await this.ensureOutputDir();

        for (const query of SEARCH_QUERIES) {
            const items = await this.searchQuery(query, this.perQueryLimit);
            for (const item of items) {
                this.collectedData.push(this.normalizeItem(item));
            }
            await new Promise(resolve => setTimeout(resolve, 800));
        }

        console.log(`\n🎉 收集完成！總共收集了 ${this.collectedData.length} 件藝術品`);
    }

    async saveData() {
        if (this.collectedData.length === 0) {
            console.log('❌ 沒有資料可保存');
            return null;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `cleveland_museum_crawled_${timestamp}.json`;
        const filePath = path.join(this.outputDir, filename);

        await fs.writeFile(filePath, JSON.stringify(this.collectedData, null, 2), 'utf8');
        const avgScore = this.collectedData.reduce((sum, a) => sum + a.qualityScore, 0) / this.collectedData.length;
        console.log(`💾 資料已保存到: ${filePath}`);
        console.log(`📊 總作品數: ${this.collectedData.length}`);
        console.log(`📊 有圖片的作品: ${this.collectedData.filter(a => a.imageUrl).length}`);
        console.log(`⭐ 平均品質分數: ${avgScore.toFixed(2)}/100`);

        return filePath;
    }

    async run() {
        console.log('🎨 克里夫蘭藝術博物館爬蟲啟動');
        console.log('⏰ 開始時間:', new Date().toLocaleString());

        try {
            await this.crawlArtworks();
            await this.saveData();
            console.log('\n✅ 爬蟲任務完成！');
        } catch (error) {
            console.error('❌ 爬蟲執行失敗:', error.message);
        }
    }
}

if (require.main === module) {
    const crawler = new ClevelandMuseumCrawler();
    crawler.run();
}

module.exports = ClevelandMuseumCrawler;
