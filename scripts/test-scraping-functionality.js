#!/usr/bin/env node
/**
 * 資料爬取功能測試腳本
 * 測試各種爬取功能和 Agent 的正常運作
 */

const axios = require('axios');
const { chromium } = require('playwright');

class ScrapingFunctionalityTester {
    constructor() {
        this.results = {
            basicScraping: null,
            dynamicScraping: null,
            museumAPIs: null,
            webCrawlerAgent: null,
            dataProcessing: null
        };
    }

    /**
     * 執行完整爬取功能測試
     */
    async runFullTest() {
        console.log('🕷️ 開始資料爬取功能測試...\n');

        try {
            // 1. 基礎網頁爬取測試
            await this.testBasicScraping();

            // 2. 動態內容爬取測試
            await this.testDynamicScraping();

            // 3. 博物館 API 測試
            await this.testMuseumAPIs();

            // 4. Web Crawler Agent 測試
            await this.testWebCrawlerAgent();

            // 5. 資料處理流程測試
            await this.testDataProcessing();

            // 6. 生成測試報告
            this.generateReport();

        } catch (error) {
            console.error('❌ 測試過程中發生錯誤:', error);
            process.exit(1);
        }
    }

    /**
     * 基礎網頁爬取測試
     */
    async testBasicScraping() {
        console.log('📄 測試基礎網頁爬取功能...');

        try {
            const cheerio = require('cheerio');

            // 測試基本 HTTP 請求
            const response = await axios.get('https://www.metmuseum.org/art/online-features', {
                timeout: 10000,
                headers: {
                    'User-Agent': 'Art History Database Crawler 1.0'
                }
            });

            if (response.status === 200) {
                const $ = cheerio.load(response.data);
                const title = $('title').text();
                const links = $('a').length;

                this.results.basicScraping = {
                    status: 'success',
                    url: 'https://www.metmuseum.org/art/online-features',
                    statusCode: response.status,
                    contentLength: response.data.length,
                    title: title.trim(),
                    linksFound: links,
                    hasContent: response.data.length > 1000
                };

                console.log(`✅ 基礎爬取成功 - 狀態: ${response.status}, 內容長度: ${response.data.length}`);
                console.log(`   頁面標題: ${title.trim()}`);
                console.log(`   找到連結: ${links} 個`);

            } else {
                throw new Error(`HTTP ${response.status}`);
            }

        } catch (error) {
            console.log(`❌ 基礎爬取失敗: ${error.message}`);
            this.results.basicScraping = {
                status: 'failed',
                error: error.message
            };
        }
    }

    /**
     * 動態內容爬取測試
     */
    async testDynamicScraping() {
        console.log('🌐 測試動態內容爬取功能...');

        let browser = null;

        try {
            // 啟動瀏覽器
            browser = await chromium.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-setuid-sandbox']
            });

            const page = await browser.newPage();
            await page.setUserAgent('Art History Database Crawler 1.0');

            // 測試動態載入的頁面
            await page.goto('https://www.moma.org/collection/', {
                waitUntil: 'domcontentloaded',
                timeout: 15000
            });

            // 等待動態內容載入
            await page.waitForTimeout(3000);

            const title = await page.title();
            const bodyContent = await page.textContent('body');
            const images = await page.$$('img');

            this.results.dynamicScraping = {
                status: 'success',
                url: 'https://www.moma.org/collection/',
                title: title,
                contentLength: bodyContent.length,
                imagesFound: images.length,
                hasContent: bodyContent.length > 1000
            };

            console.log(`✅ 動態爬取成功`);
            console.log(`   頁面標題: ${title}`);
            console.log(`   內容長度: ${bodyContent.length}`);
            console.log(`   圖片數量: ${images.length}`);

        } catch (error) {
            console.log(`❌ 動態爬取失敗: ${error.message}`);
            this.results.dynamicScraping = {
                status: 'failed',
                error: error.message
            };

        } finally {
            if (browser) {
                await browser.close();
            }
        }
    }

    /**
     * 博物館 API 測試
     */
    async testMuseumAPIs() {
        console.log('🏛️ 測試博物館 API 連接...');

        const apiTests = [
            {
                name: '大都會藝術博物館',
                url: 'https://collectionapi.metmuseum.org/public/collection/v1/objects/1',
                expectedFields: ['objectID', 'title', 'artistDisplayName']
            },
            {
                name: '哈佛藝術博物館',
                url: 'https://api.harvardartmuseums.org/object?apikey=demo&size=1',
                expectedFields: ['records']
            },
            {
                name: 'Google Books API (藝術史)',
                url: 'https://www.googleapis.com/books/v1/volumes?q=art+history&maxResults=1',
                expectedFields: ['items']
            }
        ];

        const apiResults = [];

        for (const api of apiTests) {
            try {
                console.log(`   測試 ${api.name}...`);

                const response = await axios.get(api.url, {
                    timeout: 10000,
                    headers: {
                        'User-Agent': 'Art History Database Crawler 1.0'
                    }
                });

                if (response.status === 200) {
                    const data = response.data;
                    const hasExpectedFields = api.expectedFields.some(field =>
                        Object.prototype.hasOwnProperty.call(data, field)
                    );

                    const result = {
                        name: api.name,
                        status: 'success',
                        statusCode: response.status,
                        dataSize: JSON.stringify(data).length,
                        hasExpectedStructure: hasExpectedFields,
                        sampleData: typeof data === 'object' ? Object.keys(data).slice(0, 5) : 'N/A'
                    };

                    apiResults.push(result);
                    console.log(`   ✅ ${api.name} - 狀態: ${response.status}, 數據大小: ${result.dataSize}bytes`);

                } else {
                    throw new Error(`HTTP ${response.status}`);
                }

            } catch (error) {
                const result = {
                    name: api.name,
                    status: 'failed',
                    error: error.message
                };

                apiResults.push(result);
                console.log(`   ❌ ${api.name} - 失敗: ${error.message}`);
            }
        }

        this.results.museumAPIs = {
            totalTested: apiTests.length,
            successful: apiResults.filter(r => r.status === 'success').length,
            results: apiResults
        };
    }

    /**
     * Web Crawler Agent 測試
     */
    async testWebCrawlerAgent() {
        console.log('🤖 測試 Web Crawler Agent...');

        try {
            // 檢查 Agent 檔案是否存在
            const agentPath = './agents/web-crawler/index.js';
            const fs = require('fs');

            if (!fs.existsSync(agentPath)) {
                throw new Error('Web Crawler Agent 檔案不存在');
            }

            // 讀取 Agent 代碼並檢查結構
            const agentCode = fs.readFileSync(agentPath, 'utf-8');

            const hasRequiredMethods = [
                'initialize',
                'startCrawling',
                'processData'
            ].every(method => agentCode.includes(method));

            const hasRequiredImports = [
                'axios',
                'cheerio',
                'playwright'
            ].every(lib => agentCode.includes(lib));

            this.results.webCrawlerAgent = {
                status: 'available',
                fileExists: true,
                codeSize: agentCode.length,
                hasRequiredMethods: hasRequiredMethods,
                hasRequiredImports: hasRequiredImports,
                structure: 'valid'
            };

            console.log('✅ Web Crawler Agent 可用');
            console.log(`   檔案大小: ${agentCode.length}bytes`);
            console.log(`   必要方法: ${hasRequiredMethods ? '完整' : '缺失'}`);
            console.log(`   必要匯入: ${hasRequiredImports ? '完整' : '缺失'}`);

        } catch (error) {
            console.log(`❌ Web Crawler Agent 測試失敗: ${error.message}`);
            this.results.webCrawlerAgent = {
                status: 'failed',
                error: error.message
            };
        }
    }

    /**
     * 資料處理流程測試
     */
    async testDataProcessing() {
        console.log('📊 測試資料處理流程...');

        try {
            // 模擬資料處理流程
            const testData = {
                source: 'test',
                url: 'https://example.com/artwork/123',
                title: 'Test Artwork',
                artist: 'Test Artist',
                date: '2023',
                description: 'This is a test artwork for processing pipeline validation.'
            };

            // 測試資料驗證
            const isValidData = this.validateArtworkData(testData);

            // 測試資料清理
            const cleanedData = this.cleanArtworkData(testData);

            // 測試資料結構化
            const structuredData = this.structureArtworkData(cleanedData);

            this.results.dataProcessing = {
                status: 'success',
                originalData: testData,
                validationPassed: isValidData,
                cleaningPassed: cleanedData !== null,
                structuringPassed: structuredData !== null,
                finalDataStructure: Object.keys(structuredData || {})
            };

            console.log('✅ 資料處理流程正常');
            console.log(`   資料驗證: ${isValidData ? '通過' : '失敗'}`);
            console.log(`   資料清理: ${cleanedData ? '成功' : '失敗'}`);
            console.log(`   資料結構化: ${structuredData ? '成功' : '失敗'}`);

        } catch (error) {
            console.log(`❌ 資料處理測試失敗: ${error.message}`);
            this.results.dataProcessing = {
                status: 'failed',
                error: error.message
            };
        }
    }

    /**
     * 驗證藝術作品資料
     */
    validateArtworkData(data) {
        const requiredFields = ['title', 'source', 'url'];
        return requiredFields.every(field => data[field] && data[field].trim().length > 0);
    }

    /**
     * 清理藝術作品資料
     */
    cleanArtworkData(data) {
        try {
            return {
                ...data,
                title: data.title?.trim(),
                artist: data.artist?.trim() || 'Unknown Artist',
                date: data.date?.trim() || 'Unknown Date',
                description: data.description?.trim().substring(0, 1000) || ''
            };
        } catch (error) {
            return null;
        }
    }

    /**
     * 結構化藝術作品資料
     */
    structureArtworkData(data) {
        try {
            return {
                metadata: {
                    'dc:title': data.title,
                    'dc:creator': data.artist,
                    'dc:date': data.date,
                    'dc:description': data.description,
                    'dc:source': data.source
                },
                processing: {
                    timestamp: new Date().toISOString(),
                    status: 'processed',
                    agent: 'test-crawler'
                },
                urls: {
                    source: data.url
                }
            };
        } catch (error) {
            return null;
        }
    }

    /**
     * 生成測試報告
     */
    generateReport() {
        console.log('\n' + '='.repeat(60));
        console.log('📋 資料爬取功能測試報告');
        console.log('='.repeat(60));

        const totalTests = Object.keys(this.results).length;
        let successCount = 0;

        // 計算成功率
        Object.values(this.results).forEach(result => {
            if (result && (result.status === 'success' || result.status === 'available')) {
                successCount++;
            }
        });

        const successRate = Math.round((successCount / totalTests) * 100);

        console.log(`\n📊 測試摘要:`);
        console.log(`   總測試項目: ${totalTests}`);
        console.log(`   成功項目: ${successCount}`);
        console.log(`   成功率: ${successRate}%`);
        console.log(`   整體狀態: ${successRate >= 80 ? '✅ 良好' : successRate >= 60 ? '⚠️ 需改善' : '❌ 有問題'}`);

        // 詳細結果
        console.log('\n📋 詳細測試結果:');

        // 基礎爬取
        if (this.results.basicScraping) {
            console.log(`\n📄 基礎網頁爬取:`);
            const basic = this.results.basicScraping;
            console.log(`   狀態: ${basic.status === 'success' ? '✅ 成功' : '❌ 失敗'}`);
            if (basic.status === 'success') {
                console.log(`   測試URL: ${basic.url}`);
                console.log(`   內容長度: ${basic.contentLength}bytes`);
                console.log(`   連結數量: ${basic.linksFound}`);
            } else {
                console.log(`   錯誤: ${basic.error}`);
            }
        }

        // 動態爬取
        if (this.results.dynamicScraping) {
            console.log(`\n🌐 動態內容爬取:`);
            const dynamic = this.results.dynamicScraping;
            console.log(`   狀態: ${dynamic.status === 'success' ? '✅ 成功' : '❌ 失敗'}`);
            if (dynamic.status === 'success') {
                console.log(`   測試URL: ${dynamic.url}`);
                console.log(`   內容長度: ${dynamic.contentLength}bytes`);
                console.log(`   圖片數量: ${dynamic.imagesFound}`);
            } else {
                console.log(`   錯誤: ${dynamic.error}`);
            }
        }

        // 博物館 API
        if (this.results.museumAPIs) {
            console.log(`\n🏛️ 博物館 API 連接:`);
            const apis = this.results.museumAPIs;
            console.log(`   測試數量: ${apis.totalTested}`);
            console.log(`   成功連接: ${apis.successful}`);
            console.log(`   成功率: ${Math.round((apis.successful / apis.totalTested) * 100)}%`);

            apis.results.forEach(api => {
                const status = api.status === 'success' ? '✅' : '❌';
                console.log(`   ${status} ${api.name}`);
            });
        }

        // Web Crawler Agent
        if (this.results.webCrawlerAgent) {
            console.log(`\n🤖 Web Crawler Agent:`);
            const agent = this.results.webCrawlerAgent;
            console.log(`   狀態: ${agent.status === 'available' ? '✅ 可用' : '❌ 不可用'}`);
            if (agent.status === 'available') {
                console.log(`   代碼完整性: ${agent.hasRequiredMethods && agent.hasRequiredImports ? '✅ 完整' : '⚠️ 不完整'}`);
            }
        }

        // 資料處理
        if (this.results.dataProcessing) {
            console.log(`\n📊 資料處理流程:`);
            const processing = this.results.dataProcessing;
            console.log(`   狀態: ${processing.status === 'success' ? '✅ 正常' : '❌ 異常'}`);
            if (processing.status === 'success') {
                console.log(`   驗證: ${processing.validationPassed ? '✅' : '❌'}`);
                console.log(`   清理: ${processing.cleaningPassed ? '✅' : '❌'}`);
                console.log(`   結構化: ${processing.structuringPassed ? '✅' : '❌'}`);
            }
        }

        // 問題和建議
        console.log('\n💡 改善建議:');
        const recommendations = this.generateRecommendations();
        recommendations.forEach((rec, index) => {
            console.log(`   ${index + 1}. ${rec}`);
        });

        // 後續步驟
        console.log('\n🚀 後續步驟:');
        const nextSteps = this.generateNextSteps();
        nextSteps.forEach((step, index) => {
            console.log(`   ${index + 1}. ${step}`);
        });

        console.log('\n🎉 爬取功能測試完成！');
    }

    /**
     * 生成改善建議
     */
    generateRecommendations() {
        const recommendations = [];

        // 基於測試結果生成建議
        if (this.results.basicScraping?.status === 'failed') {
            recommendations.push('檢查網路連接和基礎爬取功能');
        }

        if (this.results.dynamicScraping?.status === 'failed') {
            recommendations.push('檢查 Playwright 安裝和配置');
        }

        if (this.results.museumAPIs?.successful < this.results.museumAPIs?.totalTested) {
            recommendations.push('部分博物館 API 不可用，檢查 API 金鑰或網路');
        }

        if (this.results.webCrawlerAgent?.status === 'failed') {
            recommendations.push('修復或重新建立 Web Crawler Agent');
        }

        if (recommendations.length === 0) {
            recommendations.push('爬取功能運作正常，可以開始資料收集');
        }

        return recommendations;
    }

    /**
     * 生成後續步驟
     */
    generateNextSteps() {
        const steps = [];

        const successRate = Object.values(this.results).filter(r =>
            r && (r.status === 'success' || r.status === 'available')
        ).length / Object.keys(this.results).length * 100;

        if (successRate >= 80) {
            steps.push('🚀 啟動完整資料爬取流程');
            steps.push('📊 監控爬取效能和品質');
            steps.push('🔄 設定定期爬取排程');
        } else {
            steps.push('🔧 修復識別的問題');
            steps.push('🧪 重新執行測試驗證');
        }

        steps.push('📈 建立爬取監控和警報');
        steps.push('🗄️ 設定資料儲存和備份');

        return steps;
    }
}

// 執行測試
async function main() {
    const tester = new ScrapingFunctionalityTester();

    try {
        await tester.runFullTest();
        process.exit(0);
    } catch (error) {
        console.error('測試執行失敗:', error);
        process.exit(1);
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    main();
}

module.exports = ScrapingFunctionalityTester;