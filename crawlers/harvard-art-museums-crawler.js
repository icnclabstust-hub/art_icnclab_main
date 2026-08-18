#!/usr/bin/env node
/**
 * Harvard Art Museums API 爬蟲
 * 哈佛藝術博物館藏品和研究資料收集
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

class HarvardArtMuseumsCrawler {
    constructor(apiKey = null) {
        this.baseUrl = 'https://api.harvardartmuseums.org';
        this.apiKey = apiKey; // 需要申請API Key
        this.outputDir = path.join(__dirname, 'data', 'raw', 'harvard');
        this.collectedData = [];

        // 每日API調用限制
        this.dailyLimit = 2500;
        this.currentCalls = 0;

        // 藝術史相關分類
        this.artHistoryClassifications = [
            'Paintings',
            'Sculptures',
            'Drawings',
            'Prints',
            'Photographs',
            'Textiles',
            'Ceramics',
            'Furniture',
            'Metalwork',
            'Jewelry',
            'Books',
            'Manuscripts'
        ];

        // 重要文化和時期
        this.cultures = [
            'Italian',
            'French',
            'Dutch',
            'German',
            'Spanish',
            'British',
            'American',
            'Chinese',
            'Japanese',
            'Islamic'
        ];

        this.periods = [
            'Ancient',
            'Medieval',
            'Renaissance',
            'Baroque',
            'Neoclassical',
            'Romantic',
            'Modern',
            'Contemporary'
        ];

        // 著名藝術家
        this.famousArtists = [
            'Pablo Picasso',
            'Vincent van Gogh',
            'Claude Monet',
            'Pierre-Auguste Renoir',
            'Edgar Degas',
            'Paul Cézanne',
            'Henri Matisse',
            'Wassily Kandinsky',
            'Jackson Pollock',
            'Andy Warhol'
        ];
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    checkApiKey() {
        if (!this.apiKey) {
            console.log('⚠️  警告: 沒有設定API Key');
            console.log('請到 https://www.harvardartmuseums.org/collections/api 申請API Key');
            console.log('使用方式: new HarvardArtMuseumsCrawler("YOUR_API_KEY")');
            throw new Error('需要Harvard Art Museums API Key');
        }
    }

    async makeApiCall(endpoint, params = {}) {
        if (this.currentCalls >= this.dailyLimit) {
            throw new Error(`已達到每日API調用限制: ${this.dailyLimit}`);
        }

        this.checkApiKey();

        try {
            const url = `${this.baseUrl}${endpoint}`;
            const response = await axios.get(url, {
                params: {
                    apikey: this.apiKey,
                    ...params
                },
                timeout: 30000
            });

            this.currentCalls++;

            // API限制：每秒不超過1次請求
            await new Promise(resolve => setTimeout(resolve, 1000));

            return response.data;

        } catch (error) {
            if (error.response?.status === 429) {
                console.warn('⚠️  API 頻率限制，等待後重試...');
                await new Promise(resolve => setTimeout(resolve, 5000));
                return this.makeApiCall(endpoint, params);
            } else if (error.response?.status === 401) {
                throw new Error('API Key 無效或已過期');
            } else {
                console.error(`API 調用失敗: ${error.message}`);
                return null;
            }
        }
    }

    async searchObjects(query, params = {}) {
        const defaultParams = {
            q: query,
            size: 50, // 每頁最多100項，設為50以節省API調用
            hasimage: 1, // 只搜尋有圖像的物件
            ...params
        };

        console.log(`🔍 Harvard 搜尋: "${query}"`);

        const data = await this.makeApiCall('/object', defaultParams);

        if (!data || !data.records) {
            console.log(`   ❌ "${query}" 沒有找到結果`);
            return [];
        }

        console.log(`   📊 找到 ${data.info.totalrecords} 項結果，收集 ${data.records.length} 項`);

        // 處理每個物件
        const processedObjects = [];
        for (const obj of data.records) {
            const processedObj = await this.processObject(obj, query);
            if (processedObj) {
                processedObjects.push(processedObj);
            }
        }

        return processedObjects;
    }

    async searchByClassification(classification, limit = 30) {
        return await this.searchObjects(`classification:${classification}`, {
            size: Math.min(limit, 100)
        });
    }

    async searchByArtist(artistName, limit = 20) {
        // 先搜尋藝術家ID
        const personData = await this.makeApiCall('/person', {
            q: artistName,
            size: 1
        });

        if (personData && personData.records && personData.records.length > 0) {
            const personId = personData.records[0].id;
            console.log(`👨‍🎨 找到藝術家: ${artistName} (ID: ${personId})`);

            return await this.searchObjects(`person:${personId}`, {
                size: Math.min(limit, 100)
            });
        } else {
            // 如果沒找到具體的人員記錄，嘗試文字搜尋
            return await this.searchObjects(artistName, {
                size: Math.min(limit, 100)
            });
        }
    }

    async searchByCulture(culture, limit = 25) {
        return await this.searchObjects(`culture:${culture}`, {
            size: Math.min(limit, 100)
        });
    }

    async searchByPeriod(period, limit = 25) {
        return await this.searchObjects(`period:${period}`, {
            size: Math.min(limit, 100)
        });
    }

    async processObject(obj, searchQuery) {
        try {
            const processedObject = {
                // 基本資訊
                harvardId: obj.id,
                objectNumber: obj.objectnumber,
                title: obj.title || '無標題',
                classification: obj.classification,

                // 創作資訊
                people: this.extractPeople(obj),
                culture: obj.culture,
                period: obj.period,
                century: obj.century,
                dated: obj.dated,

                // 物理特徵
                medium: obj.medium,
                dimensions: obj.dimensions,

                // 描述和背景
                description: obj.description,
                commentary: obj.commentary,
                technique: obj.technique,

                // 圖像資源
                primaryImage: obj.primaryimageurl,
                images: this.extractImages(obj),

                // 收藏資訊
                accessionYear: obj.accessionyear,
                provenance: obj.provenance,
                exhibition: obj.exhibition,
                publication: obj.publication,

                // 分類和標籤
                workType: obj.worktype,
                department: obj.department,
                division: obj.division,

                // 外部連結
                url: obj.url,

                // 元數據
                lastUpdate: obj.lastupdate,
                rank: obj.rank,

                // 處理資訊
                source: 'Harvard Art Museums',
                searchQuery: searchQuery,
                timestamp: new Date().toISOString(),

                // 品質評分
                qualityScore: this.calculateQualityScore(obj),

                // 藝術史分類
                artHistoryCategories: this.categorizeArtwork(obj),

                // 研究價值評估
                researchValue: this.assessResearchValue(obj)
            };

            return processedObject;

        } catch (error) {
            console.warn(`   ⚠️ 處理Harvard物件失敗: ${error.message}`);
            return null;
        }
    }

    extractPeople(obj) {
        const people = [];

        if (obj.people && Array.isArray(obj.people)) {
            for (const person of obj.people) {
                people.push({
                    name: person.name,
                    role: person.role,
                    id: person.personid,
                    culture: person.culture,
                    birthplace: person.birthplace,
                    deathplace: person.deathplace,
                    displaydate: person.displaydate
                });
            }
        }

        return people;
    }

    extractImages(obj) {
        const images = [];

        if (obj.images && Array.isArray(obj.images)) {
            for (const image of obj.images) {
                images.push({
                    baseimageurl: image.baseimageurl,
                    primarydisplay: image.primarydisplay,
                    width: image.width,
                    height: image.height,
                    caption: image.caption,
                    copyright: image.copyright
                });
            }
        }

        return images;
    }

    calculateQualityScore(obj) {
        let score = 0;

        // 基本資訊完整性 (40分)
        if (obj.title && obj.title !== 'Untitled') score += 10;
        if (obj.people && obj.people.length > 0) score += 10;
        if (obj.dated || obj.century) score += 10;
        if (obj.medium) score += 10;

        // 圖像資源 (25分)
        if (obj.primaryimageurl) score += 15;
        if (obj.images && obj.images.length > 1) score += 10;

        // 描述和研究價值 (20分)
        if (obj.description) score += 10;
        if (obj.commentary || obj.technique) score += 10;

        // 收藏完整性 (15分)
        if (obj.accessionyear) score += 5;
        if (obj.provenance) score += 5;
        if (obj.exhibition || obj.publication) score += 5;

        return Math.min(score, 100);
    }

    categorizeArtwork(obj) {
        const categories = ['harvard_collection'];

        // 分類別
        if (obj.classification) {
            categories.push(`classification:${obj.classification.toLowerCase()}`);
        }

        // 按文化
        if (obj.culture) {
            categories.push(`culture:${obj.culture.toLowerCase()}`);
        }

        // 按時期
        if (obj.period) {
            categories.push(`period:${obj.period.toLowerCase()}`);
        }

        // 按世紀
        if (obj.century) {
            categories.push(`century:${obj.century.toLowerCase()}`);
        }

        // 按部門
        if (obj.department) {
            categories.push(`department:${obj.department.toLowerCase().replace(/\s+/g, '_')}`);
        }

        return categories;
    }

    assessResearchValue(obj) {
        let value = 0;

        // 有完整出版記錄
        if (obj.publication && obj.publication.length > 0) value += 30;

        // 有展覽歷史
        if (obj.exhibition && obj.exhibition.length > 0) value += 20;

        // 有詳細來源記錄
        if (obj.provenance) value += 20;

        // 有學術評論
        if (obj.commentary) value += 15;

        // 有技術分析
        if (obj.technique) value += 15;

        return Math.min(value, 100);
    }

    async crawlComprehensive(maxObjects = 500) {
        await this.ensureOutputDir();

        console.log('🚀 開始 Harvard Art Museums 綜合爬取...');
        console.log(`📊 目標收集 ${maxObjects} 項藝術品資料`);

        const crawlPlan = [
            // 按分類搜尋
            ...this.artHistoryClassifications.map(cls => ({
                type: 'classification',
                query: cls,
                limit: Math.floor(maxObjects * 0.4 / this.artHistoryClassifications.length)
            })),
            // 按著名藝術家搜尋
            ...this.famousArtists.slice(0, 5).map(artist => ({
                type: 'artist',
                query: artist,
                limit: Math.floor(maxObjects * 0.3 / 5)
            })),
            // 按文化搜尋
            ...this.cultures.slice(0, 5).map(culture => ({
                type: 'culture',
                query: culture,
                limit: Math.floor(maxObjects * 0.2 / 5)
            })),
            // 按時期搜尋
            ...this.periods.slice(0, 3).map(period => ({
                type: 'period',
                query: period,
                limit: Math.floor(maxObjects * 0.1 / 3)
            }))
        ];

        for (let i = 0; i < crawlPlan.length; i++) {
            const plan = crawlPlan[i];
            console.log(`\n📊 進度: ${i + 1}/${crawlPlan.length} - ${plan.type}: ${plan.query}`);

            try {
                let results = [];

                switch (plan.type) {
                    case 'classification':
                        results = await this.searchByClassification(plan.query, plan.limit);
                        break;
                    case 'artist':
                        results = await this.searchByArtist(plan.query, plan.limit);
                        break;
                    case 'culture':
                        results = await this.searchByCulture(plan.query, plan.limit);
                        break;
                    case 'period':
                        results = await this.searchByPeriod(plan.query, plan.limit);
                        break;
                }

                this.collectedData.push(...results);

                console.log(`   ✅ 收集 ${results.length} 項資料`);

                // 檢查API調用限制
                if (this.currentCalls >= this.dailyLimit * 0.9) {
                    console.log('⚠️  接近每日API調用限制，停止爬取');
                    break;
                }

            } catch (error) {
                console.error(`   ❌ ${plan.type} "${plan.query}" 失敗: ${error.message}`);
            }
        }

        // 去重處理
        const uniqueData = this.removeDuplicates(this.collectedData);

        // 按品質和研究價值排序
        uniqueData.sort((a, b) => {
            const scoreA = a.qualityScore * 0.6 + a.researchValue * 0.4;
            const scoreB = b.qualityScore * 0.6 + b.researchValue * 0.4;
            return scoreB - scoreA;
        });

        // 保存結果
        await this.saveResults(uniqueData);

        return uniqueData;
    }

    removeDuplicates(data) {
        const seen = new Map();
        const unique = [];

        for (const item of data) {
            const key = item.harvardId || `${item.title}_${item.people.map(p => p.name).join(',')}_${item.dated}`;

            if (!seen.has(key)) {
                seen.set(key, true);
                unique.push(item);
            } else {
                // 如果重複，保留品質分數更高的
                const existingIndex = unique.findIndex(u =>
                    (u.harvardId && u.harvardId === item.harvardId) ||
                    `${u.title}_${u.people.map(p => p.name).join(',')}_${u.dated}` === key
                );

                if (existingIndex !== -1) {
                    const existingScore = unique[existingIndex].qualityScore;
                    if (item.qualityScore > existingScore) {
                        unique[existingIndex] = item;
                    }
                }
            }
        }

        return unique;
    }

    async saveResults(data) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = path.join(this.outputDir, `harvard_art_museums_${timestamp}.json`);

        const summary = {
            crawlInfo: {
                timestamp: new Date().toISOString(),
                totalItems: data.length,
                source: 'Harvard Art Museums API',
                apiCallsUsed: this.currentCalls,
                dailyLimit: this.dailyLimit,
                averageQualityScore: data.reduce((sum, item) => sum + item.qualityScore, 0) / data.length,
                averageResearchValue: data.reduce((sum, item) => sum + item.researchValue, 0) / data.length,
                classificationDistribution: this.getClassificationDistribution(data),
                cultureDistribution: this.getCultureDistribution(data),
                periodDistribution: this.getPeriodDistribution(data)
            },
            data: data
        };

        await fs.writeFile(filename, JSON.stringify(summary, null, 2));

        console.log(`\n✅ Harvard Art Museums 爬取完成！`);
        console.log(`📁 資料保存至: ${filename}`);
        console.log(`📊 共收集 ${data.length} 項藝術品資料`);
        console.log(`🔥 API 調用次數: ${this.currentCalls}/${this.dailyLimit}`);
        console.log(`⭐ 平均品質分數: ${summary.crawlInfo.averageQualityScore.toFixed(2)}/100`);
        console.log(`🎓 平均研究價值: ${summary.crawlInfo.averageResearchValue.toFixed(2)}/100`);

        return filename;
    }

    getClassificationDistribution(data) {
        const distribution = {};
        for (const item of data) {
            const classification = item.classification || 'Unknown';
            distribution[classification] = (distribution[classification] || 0) + 1;
        }
        return distribution;
    }

    getCultureDistribution(data) {
        const distribution = {};
        for (const item of data) {
            const culture = item.culture || 'Unknown';
            distribution[culture] = (distribution[culture] || 0) + 1;
        }
        return distribution;
    }

    getPeriodDistribution(data) {
        const distribution = {};
        for (const item of data) {
            const period = item.period || 'Unknown';
            distribution[period] = (distribution[period] || 0) + 1;
        }
        return distribution;
    }

    // 快速測試方法
    async quickTest() {
        console.log('🧪 Harvard Art Museums 快速測試...');

        try {
            // 測試單一搜尋
            const results = await this.searchObjects('Monet', { size: 3 });

            if (results.length > 0) {
                console.log(`✅ 快速測試成功！找到 ${results.length} 項結果`);
                console.log(`範例: ${results[0].title} - ${results[0].people.map(p => p.name).join(', ')}`);
                return true;
            } else {
                console.log('⚠️  快速測試：沒有找到結果');
                return false;
            }

        } catch (error) {
            console.error('❌ 快速測試失敗:', error.message);
            return false;
        }
    }
}

// 導出模組
module.exports = HarvardArtMuseumsCrawler;

// 直接執行
if (require.main === module) {
    async function main() {
        // 檢查是否有API Key作為命令列參數或環境變數
        require('dotenv').config();
        const apiKey = process.argv[2] || process.env.HARVARD_API_KEY;

        if (!apiKey) {
            console.log('❌ 需要提供Harvard Art Museums API Key');
            console.log('使用方式: node harvard-art-museums-crawler.js YOUR_API_KEY');
            console.log('申請網址: https://www.harvardartmuseums.org/collections/api');
            process.exit(1);
        }

        const crawler = new HarvardArtMuseumsCrawler(apiKey);

        try {
            // 根據命令列參數決定執行模式
            if (process.argv.includes('--test')) {
                await crawler.quickTest();
            } else {
                const maxObjects = process.argv.includes('--max')
                    ? parseInt(process.argv[process.argv.indexOf('--max') + 1]) || 200
                    : 200;

                await crawler.crawlComprehensive(maxObjects);
            }
        } catch (error) {
            console.error('❌ Harvard Art Museums 爬取失敗:', error.message);
            process.exit(1);
        }
    }

    main();
}