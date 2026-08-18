#!/usr/bin/env node
/**
 * Europeana API 爬蟲
 * 歐洲數位文化遺產平台資料收集
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

class EuropeanaCrawler {
    constructor() {
        this.baseUrl = 'https://api.europeana.eu/record/v2';
        this.searchUrl = 'https://api.europeana.eu/record/v2/search.json';
        this.apiKey = process.env.EUROPEANA_API_KEY || 'ltureashbo';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'europeana');
        this.collectedData = [];

        // 藝術史相關查詢關鍵字
        this.artHistoryQueries = [
            'Renaissance painting',
            'Baroque sculpture',
            'Medieval art',
            'Gothic architecture',
            'Impressionism',
            'Art Nouveau',
            'Byzantine art',
            'Romanesque',
            'Classical art',
            'Modern art',
            'Contemporary art',
            'Abstract art',
            'Cubism',
            'Surrealism',
            'Expressionism'
        ];

        // 重要藝術家查詢
        this.importantArtists = [
            'Leonardo da Vinci',
            'Michelangelo Buonarroti',
            'Raphael Sanzio',
            'Caravaggio',
            'Rembrandt van Rijn',
            'Johannes Vermeer',
            'Claude Monet',
            'Vincent van Gogh',
            'Pablo Picasso',
            'Wassily Kandinsky',
            'Paul Cézanne',
            'Henri Matisse',
            'Salvador Dalí',
            'Frida Kahlo',
            'Andy Warhol'
        ];

        // 文化機構查詢
        this.culturalInstitutions = [
            'Louvre',
            'British Museum',
            'Metropolitan Museum',
            'Uffizi Gallery',
            'Vatican Museums',
            'Rijksmuseum',
            'Hermitage',
            'Prado Museum',
            'Tate Gallery',
            'Guggenheim'
        ];
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    async searchByQuery(query, rows = 50) {
        try {
            console.log(`🔍 Europeana 搜尋: "${query}"`);

            const params = {
                wskey: this.apiKey,
                query: query,
                rows: rows,
                media: true, // 只搜尋有媒體檔案的記錄
                thumbnail: true, // 只搜尋有縮圖的記錄
                profile: 'rich', // 獲取豐富的元數據
                qf: [
                    'TYPE:IMAGE',
                    'TYPE:VIDEO',
                    'TYPE:3D',
                    'PROVIDER:*museum*'
                ]
            };

            const response = await axios.get(this.searchUrl, {
                params,
                timeout: 30000
            });

            if (!response.data || !response.data.items) {
                console.log(`   ❌ "${query}" 沒有找到結果`);
                return [];
            }

            const items = response.data.items;
            console.log(`   📊 找到 ${response.data.totalResults} 項結果，將收集 ${items.length} 項`);

            // 處理每個項目
            const processedItems = [];
            for (const item of items) {
                const processedItem = await this.processEuropeanaItem(item, query);
                if (processedItem) {
                    processedItems.push(processedItem);
                }
            }

            return processedItems;

        } catch (error) {
            if (error.response?.status === 429) {
                console.warn(`   ⚠️ API 限制達到，等待後重試...`);
                await new Promise(resolve => setTimeout(resolve, 5000));
                return this.searchByQuery(query, rows);
            } else {
                console.error(`   ⚠️ 搜尋 "${query}" 失敗:`, error.message);
                return [];
            }
        }
    }

    async processEuropeanaItem(item, searchQuery) {
        try {
            const processedItem = {
                // 基本信息
                europeanaId: item.id,
                title: this.extractTitle(item),
                creator: this.extractCreator(item),
                date: this.extractDate(item),
                type: item.type,

                // 描述和主題
                description: this.extractDescription(item),
                subject: item.subject || [],

                // 媒體資源
                thumbnail: item.edmPreview?.[0],
                media: this.extractMediaUrls(item),

                // 提供者信息
                provider: item.dataProvider?.[0],
                country: item.country?.[0],
                language: item.language?.[0],

                // 權利信息
                rights: item.rights?.[0],

                // 外部連結
                europeanaUrl: `https://www.europeana.eu/item${item.id}`,
                isShownAt: item.edmIsShownAt?.[0],

                // 元數據
                completeness: item.completeness,
                timestamp: new Date().toISOString(),
                searchQuery: searchQuery,
                source: 'Europeana'
            };

            // 藝術史分類
            processedItem.artHistoryCategories = this.categorizeArtHistoryContent(processedItem);

            // 品質評分
            processedItem.qualityScore = this.calculateQualityScore(processedItem);

            return processedItem;

        } catch (error) {
            console.warn(`   ⚠️ 處理項目失敗: ${error.message}`);
            return null;
        }
    }

    extractTitle(item) {
        if (item.title) {
            return Array.isArray(item.title) ? item.title[0] : item.title;
        }
        if (item.dcTitle) {
            return Array.isArray(item.dcTitle) ? item.dcTitle[0] : item.dcTitle;
        }
        return '無標題';
    }

    extractCreator(item) {
        const creators = [];
        if (item.dcCreator) {
            creators.push(...(Array.isArray(item.dcCreator) ? item.dcCreator : [item.dcCreator]));
        }
        if (item.dcContributor) {
            creators.push(...(Array.isArray(item.dcContributor) ? item.dcContributor : [item.dcContributor]));
        }
        return creators;
    }

    extractDate(item) {
        if (item.year) return item.year[0];
        if (item.edmTimespanLabel) return item.edmTimespanLabel[0];
        if (item.dcDate) return Array.isArray(item.dcDate) ? item.dcDate[0] : item.dcDate;
        return null;
    }

    extractDescription(item) {
        if (item.dcDescription) {
            const desc = Array.isArray(item.dcDescription) ? item.dcDescription[0] : item.dcDescription;
            return desc.substring(0, 1000); // 限制長度
        }
        return null;
    }

    extractMediaUrls(item) {
        const mediaUrls = [];
        if (item.edmIsShownBy) {
            mediaUrls.push(...(Array.isArray(item.edmIsShownBy) ? item.edmIsShownBy : [item.edmIsShownBy]));
        }
        if (item.edmHasView) {
            mediaUrls.push(...(Array.isArray(item.edmHasView) ? item.edmHasView : [item.edmHasView]));
        }
        return mediaUrls;
    }

    categorizeArtHistoryContent(item) {
        const categories = [];
        const content = `${item.title} ${item.description || ''} ${item.subject.join(' ')}`.toLowerCase();

        // 時期分類
        const periods = {
            'ancient': ['ancient', 'classical', 'roman', 'greek', 'egyptian'],
            'medieval': ['medieval', 'gothic', 'romanesque', 'byzantine'],
            'renaissance': ['renaissance', 'quattrocento', 'cinquecento'],
            'baroque': ['baroque', 'rococo'],
            'neoclassical': ['neoclassical', 'neoclassicism'],
            'romantic': ['romantic', 'romanticism'],
            'impressionist': ['impressionist', 'impressionism'],
            'modern': ['modern', 'contemporary', 'abstract', 'cubism', 'surrealism'],
            'postmodern': ['postmodern', 'conceptual', 'installation']
        };

        // 媒介分類
        const media = {
            'painting': ['painting', 'oil', 'watercolor', 'fresco'],
            'sculpture': ['sculpture', 'statue', 'bronze', 'marble'],
            'architecture': ['architecture', 'building', 'cathedral', 'palace'],
            'photography': ['photography', 'photograph', 'daguerreotype'],
            'drawing': ['drawing', 'sketch', 'charcoal', 'ink']
        };

        // 檢查時期
        for (const [period, keywords] of Object.entries(periods)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                categories.push(`period:${period}`);
            }
        }

        // 檢查媒介
        for (const [medium, keywords] of Object.entries(media)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                categories.push(`medium:${medium}`);
            }
        }

        return categories;
    }

    calculateQualityScore(item) {
        let score = 0;

        // 基本資訊完整性 (40分)
        if (item.title && item.title !== '無標題') score += 10;
        if (item.creator && item.creator.length > 0) score += 10;
        if (item.date) score += 10;
        if (item.description) score += 10;

        // 媒體資源 (30分)
        if (item.thumbnail) score += 15;
        if (item.media && item.media.length > 0) score += 15;

        // 元數據豐富度 (20分)
        if (item.subject && item.subject.length > 0) score += 10;
        if (item.completeness && item.completeness > 5) score += 10;

        // 來源可信度 (10分)
        if (item.provider) score += 5;
        if (item.rights) score += 5;

        return Math.min(score, 100);
    }

    async crawlAllSources() {
        await this.ensureOutputDir();

        console.log('🚀 開始 Europeana 全面爬取...');

        const allQueries = [
            ...this.artHistoryQueries,
            ...this.importantArtists,
            ...this.culturalInstitutions
        ];

        for (let i = 0; i < allQueries.length; i++) {
            const query = allQueries[i];

            console.log(`\n📊 進度: ${i + 1}/${allQueries.length}`);

            const items = await this.searchByQuery(query, 30);
            this.collectedData.push(...items);

            // API 限制控制
            if (i < allQueries.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        // 去重處理
        const uniqueData = this.removeDuplicates(this.collectedData);

        // 按品質排序
        uniqueData.sort((a, b) => b.qualityScore - a.qualityScore);

        // 保存結果
        await this.saveResults(uniqueData);

        return uniqueData;
    }

    removeDuplicates(data) {
        const seen = new Map();
        const unique = [];

        for (const item of data) {
            const key = `${item.title}_${item.creator.join(',')}_${item.date}`;

            if (!seen.has(key)) {
                seen.set(key, true);
                unique.push(item);
            } else {
                // 如果重複，保留品質分數更高的
                const existingIndex = unique.findIndex(u =>
                    `${u.title}_${u.creator.join(',')}_${u.date}` === key
                );
                if (existingIndex !== -1 && item.qualityScore > unique[existingIndex].qualityScore) {
                    unique[existingIndex] = item;
                }
            }
        }

        return unique;
    }

    async saveResults(data) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = path.join(this.outputDir, `europeana_crawled_${timestamp}.json`);

        const summary = {
            crawlInfo: {
                timestamp: new Date().toISOString(),
                totalItems: data.length,
                source: 'Europeana API',
                apiKey: this.apiKey.substring(0, 5) + '***',
                averageQualityScore: data.reduce((sum, item) => sum + item.qualityScore, 0) / data.length,
                categoriesDistribution: this.getCategoriesDistribution(data)
            },
            data: data
        };

        await fs.writeFile(filename, JSON.stringify(summary, null, 2));

        console.log(`\n✅ Europeana 爬取完成！`);
        console.log(`📁 資料保存至: ${filename}`);
        console.log(`📊 共收集 ${data.length} 項文化遺產資料`);
        console.log(`⭐ 平均品質分數: ${summary.crawlInfo.averageQualityScore.toFixed(2)}/100`);

        return filename;
    }

    getCategoriesDistribution(data) {
        const distribution = {};

        for (const item of data) {
            for (const category of item.artHistoryCategories) {
                distribution[category] = (distribution[category] || 0) + 1;
            }
        }

        return distribution;
    }
}

// 導出模組
module.exports = EuropeanaCrawler;

// 直接執行
if (require.main === module) {
    async function main() {
        const crawler = new EuropeanaCrawler();
        try {
            await crawler.crawlAllSources();
        } catch (error) {
            console.error('❌ Europeana 爬取失敗:', error.message);
            process.exit(1);
        }
    }

    main();
}