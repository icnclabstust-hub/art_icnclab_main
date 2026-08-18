#!/usr/bin/env node
/**
 * 倫敦 維多利亞與艾伯特博物館 (Victoria and Albert Museum, V&A) API 爬蟲
 * 官方 API 免費開放，不需要 API Key: https://developers.vam.ac.uk/
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

const SEARCH_QUERIES = [
    'Renaissance', 'Baroque', 'Victorian', 'Art Nouveau', 'Art Deco',
    'ceramics', 'textiles', 'furniture', 'jewellery', 'fashion',
    'sculpture', 'painting', 'photography', 'prints', 'metalwork',
    'Islamic art', 'Asian art', 'medieval', 'glass', 'silver'
];

class VAMuseumCrawler {
    constructor() {
        this.baseUrl = 'https://api.vam.ac.uk/v2';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'va_museum');
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
            const url = `${this.baseUrl}/objects/search`;
            const response = await axios.get(url, {
                params: { q: query, page_size: limit, images: 1 },
                timeout: 30000
            });

            const records = response.data?.records || [];
            const total = response.data?.info?.record_count || 0;
            console.log(`   📊 找到 ${total} 件作品，收集 ${records.length} 件`);
            return records;
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
        if (normalized.artist && normalized.artist !== 'Unknown Maker') score += 10;
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
        const normalized = {
            id: item.systemNumber,
            title: item._primaryTitle || 'Untitled',
            artist: item._primaryMaker?.name || 'Unknown Maker',
            date: item._primaryDate || 'Unknown Date',
            medium: item.objectType || null,
            department: item._objectType || item.objectType || null,
            culture: item._primaryPlace || null,
            description: item.briefDescription || null,
            imageUrl: item._images?.["_iiif_image_base_url"]
                ? `${item._images["_iiif_image_base_url"]}/full/843,/0/default.jpg`
                : null,
            objectURL: item.systemNumber ? `https://collections.vam.ac.uk/item/${item.systemNumber}` : null,
            source: 'Victoria and Albert Museum',
            crawledAt: new Date().toISOString()
        };
        normalized.qualityScore = this.calculateQualityScore(normalized);
        return normalized;
    }

    async crawlArtworks() {
        console.log('🚀 開始 V&A 博物館資料收集...');
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
        const filename = `va_museum_crawled_${timestamp}.json`;
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
        console.log('🎨 V&A 博物館爬蟲啟動');
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
    const crawler = new VAMuseumCrawler();
    crawler.run();
}

module.exports = VAMuseumCrawler;
