#!/usr/bin/env node
/**
 * 紐約大都會博物館 (MET) API 爬蟲
 * 系統性地依「部門 (Department)」涵蓋 MET 全館收藏，取代原本只有 3 個固定關鍵字的做法
 * 不需要 API Key，不依賴 Docker
 */

const axios = require('axios');
const fs = require('fs/promises');
const path = require('path');

class SimpleMETCrawler {
    constructor() {
        this.baseUrl = 'https://collectionapi.metmuseum.org/public/collection/v1';
        this.outputDir = path.join(__dirname, 'data', 'raw', 'met_museum');
        this.collectedData = [];
        this.perDepartmentLimit = 15; // 每個部門最多收集幾件，避免單次爬蟲耗時過長/觸發限流
    }

    async ensureOutputDir() {
        try {
            await fs.access(this.outputDir);
        } catch (error) {
            await fs.mkdir(this.outputDir, { recursive: true });
        }
    }

    async getDepartments() {
        try {
            const response = await axios.get(`${this.baseUrl}/departments`, { timeout: 15000 });
            const departments = response.data?.departments || [];
            console.log(`🏛️ 取得 ${departments.length} 個 MET 部門`);
            return departments;
        } catch (error) {
            console.error('❌ 取得部門列表失敗:', error.message);
            return [];
        }
    }

    async searchDepartment(departmentId, departmentName, limit) {
        try {
            console.log(`🔍 搜尋部門: ${departmentName} (ID: ${departmentId})`);
            const searchUrl = `${this.baseUrl}/search?departmentId=${departmentId}&hasImages=true&q=art`;
            const response = await axios.get(searchUrl, { timeout: 30000 });

            if (!response.data || !response.data.objectIDs) {
                console.log(`   ⚠️ "${departmentName}" 沒有找到作品`);
                return [];
            }

            const objectIDs = response.data.objectIDs.slice(0, limit);
            console.log(`   📊 找到 ${response.data.total} 件作品，將收集前 ${objectIDs.length} 件`);
            return objectIDs;
        } catch (error) {
            console.error(`❌ 搜尋部門失敗 (${departmentName}):`, error.message);
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

            const artworkData = {
                id: artwork.objectID,
                title: artwork.title || 'Unknown Title',
                artist: artwork.artistDisplayName || 'Unknown Artist',
                date: artwork.objectDate || 'Unknown Date',
                medium: artwork.medium || 'Unknown Medium',
                department: artwork.department || null,
                culture: artwork.culture || null,
                period: artwork.period || null,
                dimensions: artwork.dimensions || null,
                classification: artwork.classification || null,
                primaryImage: artwork.primaryImage || null,
                objectURL: artwork.objectURL || null,
                isHighlight: artwork.isHighlight || false,
                accessionYear: artwork.accessionYear || null,
                source: 'Metropolitan Museum of Art',
                crawledAt: new Date().toISOString()
            };

            return artworkData;
        } catch (error) {
            console.error(`⚠️ 獲取作品詳情失敗 (ID: ${objectID}):`, error.message);
            return null;
        }
    }

    async crawlArtworks() {
        console.log('🚀 開始藝術史資料收集...');

        await this.ensureOutputDir();

        const departments = await this.getDepartments();
        if (departments.length === 0) {
            console.log('⚠️ 無法取得部門列表，改用備援關鍵字搜尋');
            await this.crawlByFallbackQueries();
            return;
        }

        for (const dept of departments) {
            console.log(`\n📚 處理部門: "${dept.displayName}"`);

            const objectIDs = await this.searchDepartment(dept.departmentId, dept.displayName, this.perDepartmentLimit);

            if (objectIDs.length === 0) {
                continue;
            }

            let successCount = 0;
            for (let i = 0; i < objectIDs.length; i++) {
                const objectID = objectIDs[i];
                console.log(`   📖 處理作品 ${i + 1}/${objectIDs.length} (ID: ${objectID})`);

                const artworkData = await this.getArtworkDetails(objectID);
                if (artworkData) {
                    this.collectedData.push(artworkData);
                    successCount++;
                }

                // 添加延遲避免請求過於頻繁
                await new Promise(resolve => setTimeout(resolve, 1000));
            }

            console.log(`   ✅ "${dept.displayName}": 成功收集 ${successCount} 件作品`);
        }

        console.log(`\n🎉 收集完成！總共收集了 ${this.collectedData.length} 件藝術品，涵蓋 ${departments.length} 個部門`);
    }

    // 備援：若部門列表 API 無法取得時，退回原本的關鍵字搜尋模式
    async crawlByFallbackQueries(queries = ['Renaissance painting', 'Impressionist painting', 'Modern sculpture']) {
        for (const query of queries) {
            console.log(`\n📚 處理查詢: "${query}"`);
            const searchUrl = `${this.baseUrl}/search?hasImages=true&q=${encodeURIComponent(query)}`;
            let objectIDs = [];
            try {
                const response = await axios.get(searchUrl, { timeout: 30000 });
                objectIDs = (response.data?.objectIDs || []).slice(0, 20);
            } catch (error) {
                console.error('❌ 搜尋失敗:', error.message);
                continue;
            }

            let successCount = 0;
            for (let i = 0; i < objectIDs.length; i++) {
                const artworkData = await this.getArtworkDetails(objectIDs[i]);
                if (artworkData) {
                    this.collectedData.push(artworkData);
                    successCount++;
                }
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            console.log(`   ✅ "${query}": 成功收集 ${successCount} 件作品`);
        }
    }

    async saveData() {
        if (this.collectedData.length === 0) {
            console.log('❌ 沒有資料可保存');
            return null;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `met_museum_crawled_${timestamp}.json`;
        const filePath = path.join(this.outputDir, filename);

        try {
            await fs.writeFile(filePath, JSON.stringify(this.collectedData, null, 2), 'utf8');
            console.log(`💾 資料已保存到: ${filePath}`);
            console.log(`📊 統計資訊:`);
            console.log(`   - 總作品數: ${this.collectedData.length}`);
            console.log(`   - 有圖片的作品: ${this.collectedData.filter(a => a.primaryImage).length}`);
            console.log(`   - 高亮作品: ${this.collectedData.filter(a => a.isHighlight).length}`);

            const byDept = {};
            for (const a of this.collectedData) {
                const d = a.department || '未知部門';
                byDept[d] = (byDept[d] || 0) + 1;
            }
            console.log(`   - 各部門分布:`);
            for (const [dept, count] of Object.entries(byDept)) {
                console.log(`       ${dept}: ${count}`);
            }

            return filePath;
        } catch (error) {
            console.error('❌ 保存資料失敗:', error.message);
            return null;
        }
    }

    async run() {
        console.log('🎨 藝術史資料收集器啟動');
        console.log('📡 目標: Metropolitan Museum of Art（依部門系統性涵蓋）');
        console.log('⏰ 開始時間:', new Date().toLocaleString());

        try {
            await this.crawlArtworks();
            const filePath = await this.saveData();

            if (filePath) {
                console.log('\n✅ 爬蟲任務完成！');
                console.log('💡 提示: 執行 import_all_museums_to_neo4j.py 即可自動匯入最新資料');
            }
        } catch (error) {
            console.error('❌ 爬蟲執行失敗:', error.message);
        }
    }
}

// 執行爬蟲
if (require.main === module) {
    const crawler = new SimpleMETCrawler();
    crawler.run();
}

module.exports = SimpleMETCrawler;
