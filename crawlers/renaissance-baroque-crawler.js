#!/usr/bin/env node
/**
 * 文藝復興與巴洛克時期專門爬蟲
 * 專注收集這兩個重要藝術史時期的詳細資料
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

class RenaissanceBaroqueCrawler {
    constructor() {
        this.baseUrl = 'https://collectionapi.metmuseum.org/public/collection/v1';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'renaissance_baroque');
        this.collectedData = [];

        // 文藝復興時期重要藝術家
        this.renaissanceArtists = [
            'Leonardo da Vinci', 'Michelangelo', 'Raphael', 'Sandro Botticelli',
            'Donatello', 'Masaccio', 'Andrea Mantegna', 'Giovanni Bellini',
            'Piero della Francesca', 'Fra Angelico', 'Brunelleschi',
            'Jan van Eyck', 'Rogier van der Weyden', 'Hans Memling',
            'Albrecht Dürer', 'Lucas Cranach', 'Hans Holbein'
        ];

        // 巴洛克時期重要藝術家
        this.baroqueArtists = [
            'Caravaggio', 'Peter Paul Rubens', 'Rembrandt van Rijn',
            'Johannes Vermeer', 'Diego Velázquez', 'Gian Lorenzo Bernini',
            'Nicolas Poussin', 'Claude Lorrain', 'Annibale Carracci',
            'Guido Reni', 'Artemisia Gentileschi', 'Anthony van Dyck',
            'Frans Hals', 'Georges de La Tour', 'Bartolomé Esteban Murillo'
        ];

        // 搜尋關鍵字
        this.renaissanceKeywords = [
            'Renaissance', 'Italian Renaissance', 'High Renaissance',
            'Northern Renaissance', 'Early Renaissance', '15th century',
            '16th century', 'Quattrocento', 'Cinquecento'
        ];

        this.baroqueKeywords = [
            'Baroque', 'Counter-Reformation', 'Chiaroscuro',
            '17th century', 'Baroque painting', 'Baroque sculpture'
        ];
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    async searchByQuery(query, limit = 30) {
        try {
            console.log(`🔍 搜尋: "${query}"`);
            const searchUrl = `${this.baseUrl}/search?hasImages=true&q=${encodeURIComponent(query)}`;
            const response = await axios.get(searchUrl, { timeout: 30000 });

            if (!response.data || !response.data.objectIDs) {
                console.log(`   ❌ "${query}" 沒有找到結果`);
                return [];
            }

            const objectIDs = response.data.objectIDs.slice(0, limit);
            console.log(`   📊 找到 ${response.data.total} 件，將收集 ${objectIDs.length} 件`);
            return objectIDs;
        } catch (error) {
            console.error(`   ⚠️ 搜尋 "${query}" 失敗:`, error.message);
            return [];
        }
    }

    async searchByArtist(artistName, limit = 15) {
        try {
            console.log(`👨‍🎨 搜尋藝術家: "${artistName}"`);
            const searchUrl = `${this.baseUrl}/search?hasImages=true&artistOrCulture=true&q=${encodeURIComponent(artistName)}`;
            const response = await axios.get(searchUrl, { timeout: 30000 });

            if (!response.data || !response.data.objectIDs) {
                console.log(`   ❌ 藝術家 "${artistName}" 沒有找到作品`);
                return [];
            }

            const objectIDs = response.data.objectIDs.slice(0, limit);
            console.log(`   🎨 找到 ${response.data.total} 件作品，將收集 ${objectIDs.length} 件`);
            return objectIDs;
        } catch (error) {
            console.error(`   ⚠️ 搜尋藝術家 "${artistName}" 失敗:`, error.message);
            return [];
        }
    }

    async getArtworkDetails(objectID) {
        try {
            const detailUrl = `${this.baseUrl}/objects/${objectID}`;
            const response = await axios.get(detailUrl, { timeout: 10000 });

            if (!response.data || !response.data.objectID) {
                return null;
            }

            const artwork = response.data;

            // 判斷時期
            let period = this.determinePeriod(artwork);

            const artworkData = {
                id: artwork.objectID,
                title: artwork.title || 'Unknown Title',
                artist: artwork.artistDisplayName || 'Unknown Artist',
                artistRole: artwork.artistRole || null,
                artistNationality: artwork.artistNationality || null,
                artistBeginDate: artwork.artistBeginDate || null,
                artistEndDate: artwork.artistEndDate || null,
                date: artwork.objectDate || 'Unknown Date',
                beginDate: artwork.objectBeginDate || null,
                endDate: artwork.objectEndDate || null,
                medium: artwork.medium || 'Unknown Medium',
                department: artwork.department || null,
                culture: artwork.culture || null,
                period: period,
                originalPeriod: artwork.period || null,
                dimensions: artwork.dimensions || null,
                classification: artwork.classification || null,
                primaryImage: artwork.primaryImage || null,
                primaryImageSmall: artwork.primaryImageSmall || null,
                additionalImages: artwork.additionalImages || [],
                objectURL: artwork.objectURL || null,
                isHighlight: artwork.isHighlight || false,
                accessionYear: artwork.accessionYear || null,
                accessionNumber: artwork.accessionNumber || null,
                creditLine: artwork.creditLine || null,
                city: artwork.city || null,
                state: artwork.state || null,
                country: artwork.country || null,
                region: artwork.region || null,
                subregion: artwork.subregion || null,
                locale: artwork.locale || null,
                repository: artwork.repository || null,
                objectName: artwork.objectName || null,
                tags: artwork.tags || [],
                source: 'Metropolitan Museum of Art',
                crawledAt: new Date().toISOString()
            };

            return artworkData;
        } catch (error) {
            console.error(`   ⚠️ 獲取作品詳情失敗 (ID: ${objectID}):`, error.message);
            return null;
        }
    }

    determinePeriod(artwork) {
        const title = (artwork.title || '').toLowerCase();
        const artist = (artwork.artistDisplayName || '').toLowerCase();
        const date = (artwork.objectDate || '').toLowerCase();
        const period = (artwork.period || '').toLowerCase();
        const culture = (artwork.culture || '').toLowerCase();

        // 檢查文藝復興特徵
        const renaissanceIndicators = [
            'renaissance', 'quattrocento', 'cinquecento',
            'leonardo', 'michelangelo', 'raphael', 'botticelli',
            'donatello', 'masaccio', 'dürer', 'van eyck'
        ];

        // 檢查巴洛克特徵
        const baroqueIndicators = [
            'baroque', 'caravaggio', 'rubens', 'rembrandt',
            'vermeer', 'velázquez', 'bernini', 'poussin',
            'counter-reformation', 'chiaroscuro'
        ];

        // 檢查日期範圍
        const beginDate = artwork.objectBeginDate || 0;
        const endDate = artwork.objectEndDate || 0;

        // 文藝復興時期: 大約1400-1600
        if ((beginDate >= 1400 && beginDate <= 1600) || (endDate >= 1400 && endDate <= 1600)) {
            if (renaissanceIndicators.some(indicator =>
                title.includes(indicator) || artist.includes(indicator) ||
                period.includes(indicator) || culture.includes(indicator))) {
                return 'Renaissance';
            }
        }

        // 巴洛克時期: 大約1600-1750
        if ((beginDate >= 1600 && beginDate <= 1750) || (endDate >= 1600 && endDate <= 1750)) {
            if (baroqueIndicators.some(indicator =>
                title.includes(indicator) || artist.includes(indicator) ||
                period.includes(indicator) || culture.includes(indicator))) {
                return 'Baroque';
            }
        }

        // 基於關鍵字判斷
        if (renaissanceIndicators.some(indicator =>
            title.includes(indicator) || artist.includes(indicator) ||
            period.includes(indicator) || culture.includes(indicator))) {
            return 'Renaissance';
        }

        if (baroqueIndicators.some(indicator =>
            title.includes(indicator) || artist.includes(indicator) ||
            period.includes(indicator) || culture.includes(indicator))) {
            return 'Baroque';
        }

        return artwork.period || null;
    }

    async collectRenaissanceData() {
        console.log('\n🏛️ === 文藝復興時期資料收集 ===');

        // 1. 按關鍵字搜尋
        for (const keyword of this.renaissanceKeywords) {
            const objectIDs = await this.searchByQuery(keyword, 25);
            await this.processArtworks(objectIDs, `文藝復興-${keyword}`);
            await this.delay(2000); // 延遲避免過於頻繁請求
        }

        // 2. 按重要藝術家搜尋
        for (const artist of this.renaissanceArtists.slice(0, 10)) { // 限制前10位藝術家
            const objectIDs = await this.searchByArtist(artist, 10);
            await this.processArtworks(objectIDs, `文藝復興藝術家-${artist}`);
            await this.delay(2000);
        }
    }

    async collectBaroqueData() {
        console.log('\n🎭 === 巴洛克時期資料收集 ===');

        // 1. 按關鍵字搜尋
        for (const keyword of this.baroqueKeywords) {
            const objectIDs = await this.searchByQuery(keyword, 25);
            await this.processArtworks(objectIDs, `巴洛克-${keyword}`);
            await this.delay(2000);
        }

        // 2. 按重要藝術家搜尋
        for (const artist of this.baroqueArtists.slice(0, 10)) { // 限制前10位藝術家
            const objectIDs = await this.searchByArtist(artist, 10);
            await this.processArtworks(objectIDs, `巴洛克藝術家-${artist}`);
            await this.delay(2000);
        }
    }

    async processArtworks(objectIDs, source) {
        if (objectIDs.length === 0) return;

        console.log(`   📝 處理 ${source} 的 ${objectIDs.length} 件作品...`);
        let successCount = 0;

        for (let i = 0; i < objectIDs.length; i++) {
            const objectID = objectIDs[i];

            // 避免重複收集
            if (this.collectedData.some(item => item.id === objectID)) {
                continue;
            }

            const artworkData = await this.getArtworkDetails(objectID);
            if (artworkData) {
                this.collectedData.push(artworkData);
                successCount++;

                if (successCount % 5 === 0) {
                    console.log(`     ✓ 已處理 ${successCount}/${objectIDs.length} 件作品`);
                }
            }

            await this.delay(800); // 每次請求間隔
        }

        console.log(`   ✅ ${source}: 成功收集 ${successCount} 件作品`);
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async saveData() {
        if (this.collectedData.length === 0) {
            console.log('❌ 沒有資料可保存');
            return null;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `renaissance_baroque_${timestamp}.json`;
        const filePath = path.join(this.outputDir, filename);

        try {
            await fs.writeFile(filePath, JSON.stringify(this.collectedData, null, 2), 'utf8');

            // 統計分析
            const renaissanceCount = this.collectedData.filter(a => a.period === 'Renaissance').length;
            const baroqueCount = this.collectedData.filter(a => a.period === 'Baroque').length;
            const withImagesCount = this.collectedData.filter(a => a.primaryImage).length;
            const highlightCount = this.collectedData.filter(a => a.isHighlight).length;

            console.log(`💾 資料已保存到: ${filePath}`);
            console.log(`📊 收集統計:`);
            console.log(`   - 總作品數: ${this.collectedData.length}`);
            console.log(`   - 文藝復興時期: ${renaissanceCount} 件`);
            console.log(`   - 巴洛克時期: ${baroqueCount} 件`);
            console.log(`   - 其他時期: ${this.collectedData.length - renaissanceCount - baroqueCount} 件`);
            console.log(`   - 有圖片的作品: ${withImagesCount} 件 (${Math.round(withImagesCount/this.collectedData.length*100)}%)`);
            console.log(`   - 精選作品: ${highlightCount} 件 (${Math.round(highlightCount/this.collectedData.length*100)}%)`);

            return filePath;
        } catch (error) {
            console.error('❌ 保存資料失敗:', error.message);
            return null;
        }
    }

    async run() {
        console.log('🎨 文藝復興與巴洛克時期專門資料收集器');
        console.log('📡 目標: Metropolitan Museum of Art');
        console.log('⏰ 開始時間:', new Date().toLocaleString());
        console.log('🎯 專注時期: 文藝復興 (1400-1600) & 巴洛克 (1600-1750)');

        try {
            await this.ensureOutputDir();

            // 收集文藝復興資料
            await this.collectRenaissanceData();

            // 收集巴洛克資料
            await this.collectBaroqueData();

            // 保存資料
            const filePath = await this.saveData();

            if (filePath) {
                console.log('\n🎉 專門收集任務完成！');
                console.log('💡 匯入指令:');
                console.log(`   node import_met_data_to_neo4j.js "${path.basename(filePath)}"`);
            }
        } catch (error) {
            console.error('❌ 收集任務失敗:', error.message);
        }
    }
}

// 執行專門收集
if (require.main === module) {
    const crawler = new RenaissanceBaroqueCrawler();
    crawler.run();
}

module.exports = RenaissanceBaroqueCrawler;