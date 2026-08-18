#!/usr/bin/env node
/**
 * 專門藝術主題爬蟲
 * 針對亞洲藝術、當代藝術、建築等專門領域的資料收集
 */

const axios = require('axios');
const fs = require('fs');
const path = require('path');

// 配置
const OUTPUT_DIR = './data/raw/specialized_art';
const BASE_DELAY = 1000; // 1秒延遲

// 專門藝術主題列表
const SPECIALIZED_TOPICS = [
    // 亞洲藝術
    "Chinese painting", "Japanese ukiyo-e", "Korean ceramics", "Islamic calligraphy",
    "Indian miniature painting", "Southeast Asian sculpture", "Persian art", "Tibetan art",

    // 當代與現代
    "Digital art", "Installation art", "Performance art", "Video art",
    "Street art", "Conceptual art", "Land art", "Minimal art",

    // 建築與設計
    "Art Deco architecture", "Bauhaus design", "Gothic cathedral", "Islamic architecture",
    "Traditional Chinese architecture", "Japanese temple", "Modernist architecture", "Sustainable design",

    // 工藝與裝飾藝術
    "Ceramic art", "Textile art", "Jewelry design", "Furniture design",
    "Stained glass", "Mosaic art", "Metalwork", "Woodcarving",

    // 地區特色藝術
    "African masks", "Aboriginal art", "Pre-Columbian gold", "Oceanic art",
    "Nordic design", "Eastern European folk art", "Latin American murals", "Mediterranean ceramics"
];

class SpecializedArtCrawler {
    constructor() {
        this.collectedItems = [];
        this.totalQueries = 0;
        this.successfulQueries = 0;
        this.startTime = Date.now();

        // 確保輸出目錄存在
        if (!fs.existsSync(OUTPUT_DIR)) {
            fs.mkdirSync(OUTPUT_DIR, { recursive: true });
        }
    }

    log(message) {
        const timestamp = new Date().toISOString();
        console.log(`[${timestamp}] ${message}`);
    }

    async searchEuropeana(query, rows = 25) {
        try {
            const apiUrl = 'https://api.europeana.eu/record/v2/search.json';
            const params = {
                wskey: 'api2demo', // 演示密鑰
                query: query,
                rows: rows,
                start: 1,
                profile: 'rich',
                media: true,
                reusability: 'open',
                sort: 'europeana_id+asc'
            };

            this.log(`🔍 搜尋主題: "${query}"`);

            const response = await axios.get(apiUrl, {
                params,
                timeout: 10000
            });

            if (response.data && response.data.items) {
                const items = response.data.items;
                this.log(`   📊 找到 ${response.data.totalResults} 項結果，收集 ${items.length} 項`);
                return items;
            }

            return [];

        } catch (error) {
            this.log(`   ❌ 搜尋失敗: ${error.message}`);
            return [];
        }
    }

    async searchMetMuseum(query, limit = 10) {
        try {
            // 先搜尋物件ID
            const searchUrl = 'https://collectionapi.metmuseum.org/public/collection/v1/search';
            const searchParams = {
                q: query,
                hasImages: true
            };

            const searchResponse = await axios.get(searchUrl, {
                params: searchParams,
                timeout: 8000
            });

            if (!searchResponse.data.objectIDs || searchResponse.data.objectIDs.length === 0) {
                this.log(`   ⚠️ Met Museum 無 "${query}" 相關結果`);
                return [];
            }

            // 隨機選擇一些物件ID
            const objectIDs = searchResponse.data.objectIDs.slice(0, limit);
            const items = [];

            this.log(`   🏛️ Met Museum: 找到 ${searchResponse.data.total} 項，獲取 ${objectIDs.length} 項詳細資料`);

            for (const objectID of objectIDs) {
                try {
                    const objectUrl = `https://collectionapi.metmuseum.org/public/collection/v1/objects/${objectID}`;
                    const objectResponse = await axios.get(objectUrl, { timeout: 5000 });

                    if (objectResponse.data) {
                        items.push({
                            source: 'Met Museum',
                            ...objectResponse.data
                        });
                    }

                    // 避免過度請求
                    await new Promise(resolve => setTimeout(resolve, 200));

                } catch (error) {
                    continue; // 跳過失敗的物件
                }
            }

            return items;

        } catch (error) {
            this.log(`   ❌ Met Museum 搜尋失敗: ${error.message}`);
            return [];
        }
    }

    processItem(item, source = 'europeana') {
        try {
            if (source === 'europeana') {
                return {
                    id: item.id || '',
                    title: this.extractTitle(item),
                    creator: this.extractCreator(item),
                    date: this.extractDate(item),
                    type: this.extractType(item),
                    subject: this.extractSubject(item),
                    description: this.extractDescription(item),
                    rights: this.extractRights(item),
                    provider: this.extractProvider(item),
                    country: this.extractCountry(item),
                    language: this.extractLanguage(item),
                    imageUrl: this.extractImageUrl(item),
                    dataProvider: item.dataProvider && item.dataProvider[0] || '',
                    source: 'Europeana',
                    sourceUrl: item.guid || '',
                    processedAt: new Date().toISOString(),
                    rawData: item
                };
            } else if (source === 'met') {
                return {
                    id: item.objectID?.toString() || '',
                    title: item.title || '未知標題',
                    creator: item.artistDisplayName || item.culture || '未知創作者',
                    date: item.objectDate || item.period || '未知年代',
                    type: item.objectName || item.classification || '藝術品',
                    subject: [item.tags?.map(tag => tag.term) || []].flat().join(', '),
                    description: item.creditLine || '',
                    rights: item.rightsAndReproduction || 'Public Domain',
                    provider: 'Metropolitan Museum of Art',
                    country: item.country || 'United States',
                    language: ['en'],
                    imageUrl: item.primaryImage || item.primaryImageSmall || '',
                    dataProvider: 'Met Museum',
                    source: 'Met Museum',
                    sourceUrl: item.objectURL || '',
                    medium: item.medium || '',
                    dimensions: item.dimensions || '',
                    accessionNumber: item.accessionNumber || '',
                    processedAt: new Date().toISOString(),
                    rawData: item
                };
            }

            return null;

        } catch (error) {
            this.log(`❌ 處理項目失敗: ${error.message}`);
            return null;
        }
    }

    // Europeana 數據提取方法
    extractTitle(item) {
        if (item.title && Array.isArray(item.title)) {
            return item.title[0] || '未知標題';
        }
        return item.title || '未知標題';
    }

    extractCreator(item) {
        if (item.dcCreator && Array.isArray(item.dcCreator)) {
            return item.dcCreator.join(', ');
        }
        return item.dcCreator || '未知創作者';
    }

    extractDate(item) {
        if (item.year && Array.isArray(item.year)) {
            return item.year.join(', ');
        }
        return item.year || item.edmTimespanBegin || '未知年代';
    }

    extractType(item) {
        if (item.type && Array.isArray(item.type)) {
            return item.type.join(', ');
        }
        return item.type || '文化遺產';
    }

    extractSubject(item) {
        if (item.subject && Array.isArray(item.subject)) {
            return item.subject.join(', ');
        }
        return item.subject || '';
    }

    extractDescription(item) {
        if (item.dcDescription && Array.isArray(item.dcDescription)) {
            return item.dcDescription[0] || '';
        }
        return item.dcDescription || '';
    }

    extractRights(item) {
        if (item.rights && Array.isArray(item.rights)) {
            return item.rights[0] || '';
        }
        return item.rights || '';
    }

    extractProvider(item) {
        if (item.provider && Array.isArray(item.provider)) {
            return item.provider[0] || '';
        }
        return item.provider || '';
    }

    extractCountry(item) {
        if (item.country && Array.isArray(item.country)) {
            return item.country[0] || '';
        }
        return item.country || '';
    }

    extractLanguage(item) {
        return item.language || [];
    }

    extractImageUrl(item) {
        if (item.edmIsShownBy && Array.isArray(item.edmIsShownBy)) {
            return item.edmIsShownBy[0] || '';
        }
        return item.edmIsShownBy || '';
    }

    async crawlSpecializedTopics() {
        this.log(`🚀 開始專門藝術主題爬取...`);
        this.log(`📊 預計處理 ${SPECIALIZED_TOPICS.length} 個專門主題`);

        for (let i = 0; i < SPECIALIZED_TOPICS.length; i++) {
            const topic = SPECIALIZED_TOPICS[i];
            this.totalQueries++;

            this.log(`📊 進度: ${i + 1}/${SPECIALIZED_TOPICS.length} - ${topic}`);

            try {
                // 從多個來源收集資料
                const [europeanaItems, metItems] = await Promise.all([
                    this.searchEuropeana(topic, 15),
                    this.searchMetMuseum(topic, 5)
                ]);

                // 處理 Europeana 結果
                for (const item of europeanaItems) {
                    const processed = this.processItem(item, 'europeana');
                    if (processed) {
                        this.collectedItems.push(processed);
                    }
                }

                // 處理 Met Museum 結果
                for (const item of metItems) {
                    const processed = this.processItem(item, 'met');
                    if (processed) {
                        this.collectedItems.push(processed);
                    }
                }

                if (europeanaItems.length > 0 || metItems.length > 0) {
                    this.successfulQueries++;
                }

                // 每10個主題保存一次進度
                if ((i + 1) % 10 === 0) {
                    await this.saveProgress();
                }

                // 延遲避免過度請求
                await new Promise(resolve => setTimeout(resolve, BASE_DELAY));

            } catch (error) {
                this.log(`❌ 主題 "${topic}" 處理失敗: ${error.message}`);
            }
        }

        await this.saveProgress();
        this.printSummary();
    }

    async saveProgress() {
        try {
            const timestamp = new Date().toISOString().replace(/:/g, '-');
            const filename = `specialized_art_${timestamp}.json`;
            const filepath = path.join(OUTPUT_DIR, filename);

            const data = {
                metadata: {
                    crawlType: 'specialized_art_topics',
                    totalTopics: SPECIALIZED_TOPICS.length,
                    totalQueries: this.totalQueries,
                    successfulQueries: this.successfulQueries,
                    totalItems: this.collectedItems.length,
                    createdAt: new Date().toISOString(),
                    topics: SPECIALIZED_TOPICS
                },
                items: this.collectedItems
            };

            fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf-8');
            this.log(`💾 進度已保存: ${filepath}`);
            this.log(`📊 目前收集: ${this.collectedItems.length} 項藝術資料`);

        } catch (error) {
            this.log(`❌ 保存失敗: ${error.message}`);
        }
    }

    printSummary() {
        const duration = (Date.now() - this.startTime) / 1000 / 60;
        const successRate = (this.successfulQueries / this.totalQueries * 100).toFixed(1);

        this.log(`\n🎉 專門藝術主題爬取完成！`);
        this.log(`📊 爬取統計:`);
        this.log(`   - 處理主題: ${this.totalQueries}`);
        this.log(`   - 成功查詢: ${this.successfulQueries}`);
        this.log(`   - 成功率: ${successRate}%`);
        this.log(`   - 收集項目: ${this.collectedItems.length}`);
        this.log(`   - 耗時: ${duration.toFixed(1)} 分鐘`);

        // 按來源統計
        const sourceStats = {};
        this.collectedItems.forEach(item => {
            sourceStats[item.source] = (sourceStats[item.source] || 0) + 1;
        });

        this.log(`📈 來源分布:`);
        Object.entries(sourceStats).forEach(([source, count]) => {
            this.log(`   - ${source}: ${count} 項`);
        });
    }
}

// 主程序
async function main() {
    try {
        const crawler = new SpecializedArtCrawler();
        await crawler.crawlSpecializedTopics();
    } catch (error) {
        console.error('❌ 爬蟲執行失敗:', error.message);
        process.exit(1);
    }
}

// 執行主程序
if (require.main === module) {
    main();
}

module.exports = SpecializedArtCrawler;