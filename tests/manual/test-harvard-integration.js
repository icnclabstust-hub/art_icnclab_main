#!/usr/bin/env node
/**
 * Harvard Art Museums API 整合測試腳本
 * 測試Harvard API與系統的整合情況
 */

const HarvardArtMuseumsCrawler = require('../../crawlers/harvard-art-museums-crawler');
const UnifiedDataSourceManager = require('./unified-data-sources-manager');

class HarvardIntegrationTester {
    constructor() {
        this.testResults = {
            timestamp: new Date().toISOString(),
            tests: [],
            summary: {
                totalTests: 0,
                passed: 0,
                failed: 0,
                warnings: 0
            }
        };
    }

    log(level, message, details = null) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            level: level,
            message: message,
            details: details
        };

        console.log(`${level === 'ERROR' ? '❌' : level === 'WARN' ? '⚠️' : level === 'PASS' ? '✅' : 'ℹ️'} ${message}`);

        this.testResults.tests.push(logEntry);

        if (level === 'PASS') this.testResults.summary.passed++;
        else if (level === 'ERROR') this.testResults.summary.failed++;
        else if (level === 'WARN') this.testResults.summary.warnings++;

        this.testResults.summary.totalTests++;
    }

    async testAPIDocumentation() {
        console.log('\n🧪 測試 Harvard Art Museums API 文檔檢查...');

        try {
            // 測試基本配置
            const crawler = new HarvardArtMuseumsCrawler(); // 不提供API Key

            this.log('INFO', 'Harvard Art Museums 爬蟲初始化');

            // 檢查基本配置
            if (crawler.baseUrl === 'https://api.harvardartmuseums.org') {
                this.log('PASS', 'API 基礎URL 配置正確');
            } else {
                this.log('ERROR', `API 基礎URL 錯誤: ${crawler.baseUrl}`);
            }

            // 檢查每日限制設定
            if (crawler.dailyLimit === 2500) {
                this.log('PASS', '每日API調用限制設定正確: 2,500');
            } else {
                this.log('WARN', `每日限制設定異常: ${crawler.dailyLimit}`);
            }

            // 檢查搜索分類
            if (crawler.artHistoryClassifications.length >= 10) {
                this.log('PASS', `藝術史分類完整: ${crawler.artHistoryClassifications.length} 個分類`);
            } else {
                this.log('WARN', '藝術史分類數量較少');
            }

            // 檢查文化列表
            if (crawler.cultures.length >= 8) {
                this.log('PASS', `文化分類豐富: ${crawler.cultures.length} 種文化`);
            } else {
                this.log('WARN', '文化分類數量較少');
            }

            // 檢查著名藝術家列表
            if (crawler.famousArtists.length >= 8) {
                this.log('PASS', `著名藝術家列表完整: ${crawler.famousArtists.length} 位藝術家`);
            } else {
                this.log('WARN', '著名藝術家列表較短');
            }

        } catch (error) {
            this.log('ERROR', 'API 文檔檢查失敗', error.message);
        }
    }

    async testAPIAuthentication() {
        console.log('\n🧪 測試 Harvard Art Museums API 認證...');

        try {
            // 測試沒有API Key的情況
            const crawlerNoKey = new HarvardArtMuseumsCrawler();

            this.log('INFO', '測試無API Key情況');

            try {
                await crawlerNoKey.makeApiCall('/object', { size: 1 });
                this.log('ERROR', '應該要求API Key但沒有拋出錯誤');
            } catch (error) {
                if (error.message.includes('需要Harvard Art Museums API Key')) {
                    this.log('PASS', '正確檢測並要求API Key');
                } else {
                    this.log('WARN', `API Key檢查錯誤類型: ${error.message}`);
                }
            }

            // 測試無效API Key的情況
            this.log('INFO', '測試無效API Key情況');
            const crawlerBadKey = new HarvardArtMuseumsCrawler('invalid_key');

            try {
                const result = await crawlerBadKey.makeApiCall('/object', { size: 1 });
                if (result === null) {
                    this.log('PASS', '正確處理無效API Key');
                } else {
                    this.log('WARN', '無效API Key應該返回null');
                }
            } catch (error) {
                if (error.message.includes('API Key 無效')) {
                    this.log('PASS', '正確識別無效API Key');
                } else {
                    this.log('WARN', `無效API Key錯誤處理: ${error.message}`);
                }
            }

        } catch (error) {
            this.log('ERROR', 'API 認證測試失敗', error.message);
        }
    }

    async testDataProcessing() {
        console.log('\n🧪 測試 Harvard 資料處理邏輯...');

        try {
            const crawler = new HarvardArtMuseumsCrawler();

            // 測試資料物件處理
            const sampleHarvardObject = {
                id: 123456,
                objectnumber: "2019.123",
                title: "The Starry Night",
                classification: "Paintings",
                people: [
                    {
                        name: "Vincent van Gogh",
                        role: "Artist",
                        culture: "Dutch",
                        displaydate: "1853-1890"
                    }
                ],
                culture: "Dutch",
                period: "Post-Impressionist",
                century: "19th century",
                dated: "1889",
                medium: "Oil on canvas",
                dimensions: "73.7 cm × 92.1 cm",
                description: "A famous painting depicting a swirling night sky",
                primaryimageurl: "https://example.com/starry-night.jpg",
                accessionyear: "2019",
                department: "European and American Art"
            };

            this.log('INFO', '處理樣本Harvard物件');

            const processedObject = await crawler.processObject(sampleHarvardObject, "test query");

            if (processedObject) {
                this.log('PASS', '成功處理Harvard物件');

                // 檢查必要欄位
                const requiredFields = ['harvardId', 'title', 'source', 'qualityScore', 'artHistoryCategories'];
                const missingFields = requiredFields.filter(field => !Object.prototype.hasOwnProperty.call(processedObject, field));

                if (missingFields.length === 0) {
                    this.log('PASS', '物件結構完整，包含所有必要欄位');
                } else {
                    this.log('WARN', `缺少欄位: ${missingFields.join(', ')}`);
                }

                // 檢查品質分數
                if (processedObject.qualityScore >= 0 && processedObject.qualityScore <= 100) {
                    this.log('PASS', `品質分數合理: ${processedObject.qualityScore}/100`);
                } else {
                    this.log('ERROR', `品質分數異常: ${processedObject.qualityScore}`);
                }

                // 檢查分類
                if (processedObject.artHistoryCategories.length > 0) {
                    this.log('PASS', `自動分類成功: ${processedObject.artHistoryCategories.length} 個類別`);
                } else {
                    this.log('WARN', '沒有生成藝術史分類');
                }

                // 檢查人員資訊提取
                if (processedObject.people.length > 0) {
                    this.log('PASS', `成功提取藝術家資訊: ${processedObject.people[0].name}`);
                } else {
                    this.log('WARN', '沒有提取到藝術家資訊');
                }

            } else {
                this.log('ERROR', '物件處理失敗');
            }

        } catch (error) {
            this.log('ERROR', '資料處理測試失敗', error.message);
        }
    }

    async testQualityAssessment() {
        console.log('\n🧪 測試 Harvard 資料品質評估...');

        try {
            const crawler = new HarvardArtMuseumsCrawler();

            // 高品質物件
            const highQualityObject = {
                title: "Mona Lisa Study",
                people: [{ name: "Leonardo da Vinci" }],
                dated: "1503-1519",
                medium: "Oil on poplar panel",
                primaryimageurl: "https://example.com/mona-lisa.jpg",
                images: [{ url: "image1.jpg" }, { url: "image2.jpg" }],
                description: "A detailed study of the famous Mona Lisa painting...",
                commentary: "This work represents da Vinci's mastery...",
                provenance: "Acquired from the Louvre in 1911...",
                accessionyear: "1911",
                exhibition: [{ title: "Renaissance Masters" }],
                publication: [{ title: "Leonardo Studies" }]
            };

            // 中等品質物件
            const mediumQualityObject = {
                title: "Unknown Work",
                people: [{ name: "Anonymous" }],
                medium: "Oil on canvas",
                primaryimageurl: "https://example.com/unknown.jpg",
                description: "A painting of unknown origin",
                accessionyear: "1950"
            };

            // 低品質物件
            const lowQualityObject = {
                title: "Untitled",
                people: []
            };

            const highScore = crawler.calculateQualityScore(highQualityObject);
            const mediumScore = crawler.calculateQualityScore(mediumQualityObject);
            const lowScore = crawler.calculateQualityScore(lowQualityObject);

            this.log('INFO', `品質評估結果: 高品質 ${highScore}, 中品質 ${mediumScore}, 低品質 ${lowScore}`);

            // 驗證品質分數合理性
            if (highScore > mediumScore && mediumScore > lowScore) {
                this.log('PASS', '品質評估算法能正確區分不同品質等級');
            } else {
                this.log('ERROR', '品質評估算法邏輯有誤');
            }

            if (highScore >= 80) {
                this.log('PASS', `高品質物件獲得高分: ${highScore}/100`);
            } else {
                this.log('WARN', `高品質物件分數偏低: ${highScore}/100`);
            }

            if (lowScore < 30) {
                this.log('PASS', `低品質物件獲得低分: ${lowScore}/100`);
            } else {
                this.log('WARN', `低品質物件分數偏高: ${lowScore}/100`);
            }

        } catch (error) {
            this.log('ERROR', '品質評估測試失敗', error.message);
        }
    }

    async testUnifiedManagerIntegration() {
        console.log('\n🧪 測試統一管理器整合...');

        try {
            const manager = new UnifiedDataSourceManager();

            // 檢查Harvard是否已註冊
            const status = await manager.getDataSourcesStatus();

            const harvardSource = status.sources.find(s => s.id === 'harvard_art_museums');

            if (harvardSource) {
                this.log('PASS', 'Harvard Art Museums 已成功註冊到統一管理器');

                // 檢查配置
                if (harvardSource.priority === 10) {
                    this.log('PASS', 'Harvard 優先級設定正確 (10/10)');
                } else {
                    this.log('WARN', `Harvard 優先級設定: ${harvardSource.priority}/10`);
                }

                if (harvardSource.dataQuality === 'very_high') {
                    this.log('PASS', 'Harvard 資料品質等級設定為最高');
                } else {
                    this.log('WARN', `Harvard 資料品質等級: ${harvardSource.dataQuality}`);
                }

                // 檢查分類
                const expectedCategories = ['museum', 'academic_collection', 'research'];
                const hasExpectedCategories = expectedCategories.every(cat =>
                    harvardSource.categories.includes(cat)
                );

                if (hasExpectedCategories) {
                    this.log('PASS', 'Harvard 分類標籤設定完整');
                } else {
                    this.log('WARN', `Harvard 分類標籤: ${harvardSource.categories.join(', ')}`);
                }

            } else {
                this.log('ERROR', 'Harvard Art Museums 沒有註冊到統一管理器');
            }

            // 檢查總資料來源數量
            if (status.totalSources === 5) {
                this.log('PASS', `總資料來源數量正確: ${status.totalSources}`);
            } else {
                this.log('WARN', `總資料來源數量: ${status.totalSources}，預期: 5`);
            }

        } catch (error) {
            this.log('ERROR', '統一管理器整合測試失敗', error.message);
        }
    }

    async testAPIKeyInstructions() {
        console.log('\n🧪 測試 API Key 申請指南...');

        try {
            // 檢查是否提供了清楚的API Key申請指南
            const crawler = new HarvardArtMuseumsCrawler();

            this.log('INFO', '檢查API Key申請指南');

            // 測試錯誤訊息是否包含申請網址
            try {
                crawler.checkApiKey();
                this.log('ERROR', '應該拋出API Key錯誤但沒有');
            } catch (error) {
                if (error.message.includes('harvard')) {
                    this.log('PASS', '錯誤訊息提及Harvard');
                } else {
                    this.log('WARN', '錯誤訊息缺少Harvard相關信息');
                }

                if (error.message.includes('API Key')) {
                    this.log('PASS', '錯誤訊息明確提及API Key需求');
                } else {
                    this.log('WARN', '錯誤訊息沒有明確說明API Key需求');
                }
            }

            this.log('INFO', '使用指南檢查完成');
            this.log('INFO', '申請網址: https://www.harvardartmuseums.org/collections/api');
            this.log('INFO', '使用限制: 每日2,500次調用，僅限非商業使用');

        } catch (error) {
            this.log('ERROR', 'API Key指南測試失敗', error.message);
        }
    }

    async runAllTests() {
        console.log('🚀 開始 Harvard Art Museums 整合測試...\n');

        // 執行所有測試
        await this.testAPIDocumentation();
        await this.testAPIAuthentication();
        await this.testDataProcessing();
        await this.testQualityAssessment();
        await this.testUnifiedManagerIntegration();
        await this.testAPIKeyInstructions();

        // 生成摘要
        console.log('\n📊 Harvard Art Museums 整合測試摘要:');
        console.log('=========================================');
        console.log(`✅ 通過: ${this.testResults.summary.passed}`);
        console.log(`❌ 失敗: ${this.testResults.summary.failed}`);
        console.log(`⚠️  警告: ${this.testResults.summary.warnings}`);
        console.log(`📋 總計: ${this.testResults.summary.totalTests}`);

        const passRate = (this.testResults.summary.passed / this.testResults.summary.totalTests * 100).toFixed(1);
        console.log(`📈 通過率: ${passRate}%`);

        // 提供使用建議
        console.log('\n💡 使用建議:');
        console.log('1. 申請Harvard Art Museums API Key: https://www.harvardartmuseums.org/collections/api');
        console.log('2. 設定環境變數: export HARVARD_API_KEY="your_api_key"');
        console.log('3. 執行爬蟲: node harvard-art-museums-crawler.js your_api_key');
        console.log('4. 或使用統一管理器: node unified-data-sources-manager.js --harvardApiKey your_api_key');

        if (this.testResults.summary.failed === 0) {
            console.log('\n🎉 Harvard Art Museums 整合測試全部通過！');
            console.log('系統已準備好使用Harvard API（需要有效API Key）');
        } else {
            console.log('\n⚠️  部分測試失敗，建議檢查並修復問題');
        }

        return this.testResults;
    }
}

// 主程序
if (require.main === module) {
    async function main() {
        const tester = new HarvardIntegrationTester();

        try {
            await tester.runAllTests();
            process.exit(0);
        } catch (error) {
            console.error('❌ 測試執行失敗:', error.message);
            process.exit(1);
        }
    }

    main();
}

module.exports = HarvardIntegrationTester;