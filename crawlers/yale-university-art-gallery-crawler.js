#!/usr/bin/env node
/**
 * 耶魯大學美術館 (Yale University Art Gallery) API 爬蟲
 * 透過 Yale 的 LUX 跨館藏平台（Linked Art / LOUD JSON-LD）免費開放、不需要 API Key：
 * https://lux.collections.yale.edu/
 *
 * LUX 同時收錄 YUAG、Beinecke 善本圖書館、Peabody 博物館、Yale Center for British Art
 * 四個館藏，這裡用 responsibleUnits facet 查到的 YUAG group id 把搜尋範圍鎖定在
 * Yale University Art Gallery，不會混入其他三個館藏的資料。
 *
 * search/item 只回傳物件 id 清單，還要對每個 id 再打一次 /data/object/{uuid}
 * 才能拿到完整 Linked Art 格式資料，所以比其他單次回傳完整資料的 API 多一輪請求。
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

// Yale University Art Gallery 在 LUX 的 group id（由 /api/facets/item?name=responsibleUnits 查得，
// 對應 current_owner._label === "Yale University Art Gallery"）
const YUAG_GROUP_ID = 'https://lux.collections.yale.edu/data/group/41310ca5-8137-45fe-ac2c-a6a04e2235f1';

function findReferredToByContent(obj, typeLabel, preferEnglish = false) {
    const candidates = (obj.referred_to_by || []).filter(entry =>
        (entry.classified_as || []).some(c => c._label === typeLabel)
    );
    if (candidates.length === 0) return null;
    if (preferEnglish) {
        const english = candidates.find(entry =>
            (entry.language || []).some(l => l.notation === 'en' || l._label === 'English')
        );
        if (english) return english.content;
    }
    return candidates[0].content;
}

function findIdentifiedByContent(obj, typeLabel) {
    const match = (obj.identified_by || []).find(entry =>
        (entry.classified_as || []).some(c => c._label === typeLabel)
    );
    return match ? match.content : null;
}

// 日期優先序：作品年代（Display Date）> 世紀/年代描述（Period，如「15th century」）
// > timespan 的起訖年份區間。實測發現多數 YUAG 物件沒有 Display Date，
// 落到 Period 或 timespan 才有值，三層都試過還是沒有才回傳 null。
function extractDate(raw) {
    const timespan = raw.produced_by?.timespan;
    const displayDate = (timespan?.identified_by || []).find(entry =>
        (entry.classified_as || []).some(c => c._label === 'Display Date')
    )?.content;
    if (displayDate) return displayDate;

    const period = findReferredToByContent(raw, 'Period');
    if (period) return period;

    const begin = timespan?.begin_of_the_begin;
    const end = timespan?.end_of_the_end;
    if (begin) {
        const beginYear = begin.slice(0, 4);
        const endYear = end ? end.slice(0, 4) : null;
        return endYear && endYear !== beginYear ? `${beginYear}-${endYear}` : beginYear;
    }
    return null;
}

class YaleArtGalleryCrawler {
    constructor() {
        this.searchUrl = 'https://lux.collections.yale.edu/api/search/item';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'yale_university_art_gallery');
        this.collectedData = [];
        this.perQueryLimit = 15;
        this.seenIds = new Set();
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    buildSearchQuery(text) {
        return {
            _scope: 'item',
            AND: [
                {
                    memberOf: {
                        curatedBy: {
                            OR: [
                                { memberOf: { id: YUAG_GROUP_ID } },
                                { id: YUAG_GROUP_ID }
                            ]
                        }
                    }
                },
                { text }
            ]
        };
    }

    async searchQuery(query, limit) {
        try {
            console.log(`🔍 搜尋: "${query}"`);
            const response = await axios.get(this.searchUrl, {
                params: { q: JSON.stringify(this.buildSearchQuery(query)), page: 1 },
                timeout: 30000
            });
            const items = (response.data?.orderedItems || []).slice(0, limit);
            console.log(`   📊 找到 ${items.length} 件（將逐件取完整資料）`);
            return items.map(item => item.id);
        } catch (error) {
            console.error(`❌ 搜尋失敗 ("${query}"):`, error.message);
            return [];
        }
    }

    async fetchObjectDetail(objectUrl) {
        try {
            const response = await axios.get(objectUrl, { timeout: 30000 });
            return response.data;
        } catch (error) {
            console.error(`   ⚠️ 取得物件詳細資料失敗 (${objectUrl}):`, error.message);
            return null;
        }
    }

    // 品質分數：比照其他博物館爬蟲的 4 大類 100 分制，依 LUX/Linked Art 實際可取得的欄位調整配分
    calculateQualityScore(normalized) {
        let score = 0;
        if (normalized.title && normalized.title !== 'Untitled') score += 10;
        if (normalized.artist && normalized.artist !== 'Unknown Artist') score += 10;
        if (normalized.date && normalized.date !== 'Unknown Date') score += 10;
        if (normalized.description) score += 10;
        if (normalized.imageUrl) score += 20;
        if (normalized.objectURL) score += 10;
        if (normalized.medium) score += 10;
        if (normalized.department) score += 10;
        if (normalized.culture) score += 10;
        return Math.min(score, 100);
    }

    normalizeItem(raw) {
        const uuid = (raw.id || '').split('/').pop();

        const artistLabels = (raw.produced_by?.part || [])
            .flatMap(part => part.carried_out_by || [])
            .map(person => (person._label || '').replace(/^Artist:\s*/, '').split('(')[0].trim())
            .filter(Boolean);

        const imageUrl = raw.representation?.[0]?.digitally_shown_by?.[0]?.access_point?.[0]?.id || null;

        const webPage = (raw.subject_of || []).find(s =>
            s.digitally_carried_by?.some(d => d.format === 'text/html')
        );
        const objectURL = webPage?.digitally_carried_by?.find(d => d.format === 'text/html')
            ?.access_point?.[0]?.id || null;

        const normalized = {
            id: uuid,
            title: findIdentifiedByContent(raw, 'Primary Title') || raw._label || 'Untitled',
            artist: artistLabels.length ? artistLabels.join(', ') : 'Unknown Artist',
            date: extractDate(raw) || 'Unknown Date',
            medium: findReferredToByContent(raw, 'Medium'),
            department: raw.member_of?.[0]?._label || null,
            culture: findReferredToByContent(raw, 'Culture'),
            description: findReferredToByContent(raw, 'Description', true),
            imageUrl,
            objectURL,
            currentOwner: raw.current_owner?.[0]?._label || null,
            source: 'Yale University Art Gallery',
            crawledAt: new Date().toISOString()
        };
        normalized.qualityScore = this.calculateQualityScore(normalized);
        return normalized;
    }

    async crawlArtworks() {
        console.log('🚀 開始耶魯大學美術館資料收集...');
        await this.ensureOutputDir();

        for (const query of SEARCH_QUERIES) {
            const objectUrls = await this.searchQuery(query, this.perQueryLimit);

            for (const objectUrl of objectUrls) {
                const uuid = objectUrl.split('/').pop();
                if (this.seenIds.has(uuid)) continue;

                const raw = await this.fetchObjectDetail(objectUrl);
                if (!raw) continue;

                // 保險起見再檢查一次 current_owner，理論上 search 時的 group 過濾已經確保
                // 只會查到 YUAG 的物件，這裡是雙重確認，避免混入 LUX 裡其他三個 Yale 館藏
                if (raw.current_owner?.[0]?._label !== 'Yale University Art Gallery') continue;

                this.seenIds.add(uuid);
                this.collectedData.push(this.normalizeItem(raw));

                await new Promise(resolve => setTimeout(resolve, 200));
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
        const filename = `yale_university_art_gallery_crawled_${timestamp}.json`;
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
        console.log('🎨 耶魯大學美術館爬蟲啟動');
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
    const crawler = new YaleArtGalleryCrawler();
    crawler.run();
}

module.exports = YaleArtGalleryCrawler;
