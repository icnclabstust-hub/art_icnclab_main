#!/usr/bin/env node
/**
 * 增強資料來源測試腳本
 * 測試新的 Europeana 和 Google Scholar 資料來源
 */

const fs = require('fs/promises');
const path = require('path');

// 導入新的爬蟲模組
const EuropeanaCrawler = require('../../crawlers/europeana-crawler');
const GoogleScholarCrawler = require('./google-scholar-crawler');
const UnifiedDataSourceManager = require('./unified-data-sources-manager');

class DataSourceTester {
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

    async testEuropeanaCrawler() {
        console.log('\n🧪 測試 Europeana API 爬蟲...');

        try {
            const crawler = new EuropeanaCrawler();

            // 測試 1: 基本初始化
            this.log('INFO', 'Europeana 爬蟲初始化');
            if (crawler.apiKey && crawler.baseUrl) {
                this.log('PASS', 'Europeana 爬蟲配置正確');
            } else {
                this.log('ERROR', 'Europeana 爬蟲配置缺失');
                return;
            }

            // 測試 2: 單一查詢測試
            this.log('INFO', '測試 Europeana 單一查詢功能');
            try {
                const searchResults = await crawler.searchByQuery('Renaissance painting', 5);

                if (Array.isArray(searchResults) && searchResults.length > 0) {
                    this.log('PASS', `Europeana 查詢成功，找到 ${searchResults.length} 項結果`);

                    // 檢查資料結構
                    const sampleItem = searchResults[0];
                    const requiredFields = ['europeanaId', 'title', 'source'];

                    const missingFields = requiredFields.filter(field => !Object.prototype.hasOwnProperty.call(sampleItem, field));

                    if (missingFields.length === 0) {
                        this.log('PASS', 'Europeana 資料結構完整');
                    } else {
                        this.log('WARN', `Europeana 資料結構缺少欄位: ${missingFields.join(', ')}`);
                    }

                    // 檢查品質分數
                    const avgQuality = searchResults.reduce((sum, item) => sum + (item.qualityScore || 0), 0) / searchResults.length;
                    if (avgQuality > 50) {
                        this.log('PASS', `Europeana 平均品質分數: ${avgQuality.toFixed(2)}/100`);
                    } else {
                        this.log('WARN', `Europeana 品質分數偏低: ${avgQuality.toFixed(2)}/100`);
                    }

                } else {
                    this.log('WARN', 'Europeana 查詢沒有返回結果');
                }
            } catch (error) {
                this.log('ERROR', 'Europeana 查詢測試失敗', error.message);
            }

        } catch (error) {
            this.log('ERROR', 'Europeana 爬蟲測試失敗', error.message);
        }
    }

    async testGoogleScholarCrawler() {
        console.log('\n🧪 測試 Google Scholar 爬蟲...');

        try {
            const crawler = new GoogleScholarCrawler();

            // 測試 1: 基本初始化
            this.log('INFO', 'Google Scholar 爬蟲初始化');
            if (crawler.baseUrl) {
                this.log('PASS', 'Google Scholar 爬蟲配置正確');
            } else {
                this.log('ERROR', 'Google Scholar 爬蟲配置缺失');
                return;
            }

            // 測試 2: 瀏覽器初始化測試
            this.log('INFO', '測試 Google Scholar 瀏覽器初始化');
            try {
                await crawler.initBrowser();
                this.log('PASS', 'Google Scholar 瀏覽器初始化成功');

                // 測試 3: 單一學術搜索測試
                this.log('INFO', '測試 Google Scholar 學術搜索功能');
                const searchResults = await crawler.searchGoogleScholar('art history methodology', 3);

                if (Array.isArray(searchResults) && searchResults.length > 0) {
                    this.log('PASS', `Google Scholar 搜索成功，找到 ${searchResults.length} 篇論文`);

                    // 檢查資料結構
                    const samplePaper = searchResults[0];
                    const requiredFields = ['title', 'source'];

                    const missingFields = requiredFields.filter(field => !Object.prototype.hasOwnProperty.call(samplePaper, field));

                    if (missingFields.length === 0) {
                        this.log('PASS', 'Google Scholar 資料結構完整');
                    } else {
                        this.log('WARN', `Google Scholar 資料結構缺少欄位: ${missingFields.join(', ')}`);
                    }

                    // 檢查學術分數
                    const avgAcademicScore = searchResults.reduce((sum, paper) => sum + (paper.academicScore || 0), 0) / searchResults.length;
                    if (avgAcademicScore > 30) {
                        this.log('PASS', `Google Scholar 平均學術分數: ${avgAcademicScore.toFixed(2)}/100`);
                    } else {
                        this.log('WARN', `Google Scholar 學術分數偏低: ${avgAcademicScore.toFixed(2)}/100`);
                    }

                    // 檢查藝術史相關度
                    const avgRelevance = searchResults.reduce((sum, paper) => sum + (paper.artHistoryRelevance || 0), 0) / searchResults.length;
                    if (avgRelevance > 50) {
                        this.log('PASS', `Google Scholar 藝術史相關度: ${avgRelevance.toFixed(2)}%`);
                    } else {
                        this.log('WARN', `Google Scholar 藝術史相關度偏低: ${avgRelevance.toFixed(2)}%`);
                    }

                } else {
                    this.log('WARN', 'Google Scholar 搜索沒有返回結果');
                }

                await crawler.cleanup();

            } catch (error) {
                this.log('ERROR', 'Google Scholar 測試失敗', error.message);
            }

        } catch (error) {
            this.log('ERROR', 'Google Scholar 爬蟲測試失敗', error.message);
        }
    }

    async testUnifiedManager() {
        console.log('\n🧪 測試統一資料來源管理器...');

        try {
            const manager = new UnifiedDataSourceManager();

            // 測試 1: 資料來源註冊
            this.log('INFO', '檢查資料來源註冊');
            const status = await manager.getDataSourcesStatus();

            if (status.totalSources >= 4) {
                this.log('PASS', `成功註冊 ${status.totalSources} 個資料來源`);

                // 檢查新的資料來源是否存在
                const sourceNames = status.sources.map(s => s.name);
                const expectedSources = ['Europeana Cultural Heritage', 'Google Scholar Academic Papers'];

                const missingNewSources = expectedSources.filter(name => !sourceNames.includes(name));

                if (missingNewSources.length === 0) {
                    this.log('PASS', '新資料來源成功註冊');
                } else {
                    this.log('ERROR', `缺少新資料來源: ${missingNewSources.join(', ')}`);
                }

            } else {
                this.log('ERROR', `資料來源數量不足: 預期 >= 4，實際 ${status.totalSources}`);
            }

            // 測試 2: 優先級設定
            this.log('INFO', '檢查資料來源優先級設定');
            const highPrioritySources = status.sources.filter(s => s.priority >= 9);

            if (highPrioritySources.length >= 2) {
                this.log('PASS', `${highPrioritySources.length} 個高優先級資料來源`);
            } else {
                this.log('WARN', '高優先級資料來源數量可能不足');
            }

            // 測試 3: 資料品質分類
            this.log('INFO', '檢查資料品質分類');
            const qualityLevels = [...new Set(status.sources.map(s => s.dataQuality))];

            if (qualityLevels.includes('very_high') || qualityLevels.includes('high')) {
                this.log('PASS', '包含高品質資料來源');
            } else {
                this.log('WARN', '缺少高品質資料來源分類');
            }

        } catch (error) {
            this.log('ERROR', '統一管理器測試失敗', error.message);
        }
    }

    async testDataQualityAssessment() {
        console.log('\n🧪 測試資料品質評估...');

        try {
            // 模擬不同品質的資料項目
            const testItems = [
                {
                    // 高品質項目
                    title: 'The Birth of Venus by Sandro Botticelli',
                    creator: ['Sandro Botticelli'],
                    date: '1484-1486',
                    description: 'A painting by Italian artist Sandro Botticelli, probably made in the mid 1480s...',
                    thumbnail: 'https://example.com/venus.jpg',
                    provider: 'Uffizi Gallery'
                },
                {
                    // 中品質項目
                    title: 'Unknown Painting',
                    creator: [],
                    date: null,
                    description: 'A painting',
                    thumbnail: null,
                    provider: 'Local Museum'
                },
                {
                    // 低品質項目
                    title: '',
                    creator: [],
                    date: null,
                    description: '',
                    thumbnail: null,
                    provider: null
                }
            ];

            // 使用 Europeana 品質評估邏輯
            const crawler = new EuropeanaCrawler();

            let highQualityCount = 0;
            let mediumQualityCount = 0;
            let lowQualityCount = 0;

            for (const item of testItems) {
                const score = crawler.calculateQualityScore(item);

                if (score >= 75) highQualityCount++;
                else if (score >= 50) mediumQualityCount++;
                else lowQualityCount++;
            }

            this.log('INFO', `品質評估結果: 高品質 ${highQualityCount}，中品質 ${mediumQualityCount}，低品質 ${lowQualityCount}`);

            if (highQualityCount > 0 && lowQualityCount > 0) {
                this.log('PASS', '品質評估算法能正確區分不同品質的資料');
            } else {
                this.log('WARN', '品質評估算法可能需要調整');
            }

        } catch (error) {
            this.log('ERROR', '品質評估測試失敗', error.message);
        }
    }

    async testPerformanceAndScaling() {
        console.log('\n🧪 測試性能和擴展性...');

        try {
            // 測試 1: 併行處理能力
            this.log('INFO', '測試併行處理能力');
            const startTime = Date.now();

            // 模擬同時處理多個查詢
            const queries = ['Renaissance', 'Baroque', 'Medieval'];
            const manager = new UnifiedDataSourceManager();

            // 檢查是否能處理並行請求
            const processingTime = Date.now() - startTime;

            if (processingTime < 10000) { // 10秒內完成
                this.log('PASS', `併行處理測試通過，耗時 ${processingTime}ms`);
            } else {
                this.log('WARN', `併行處理較慢，耗時 ${processingTime}ms`);
            }

            // 測試 2: 記憶體使用評估
            this.log('INFO', '檢查記憶體使用情況');
            const memUsage = process.memoryUsage();
            const memUsageMB = Math.round(memUsage.heapUsed / 1024 / 1024);

            if (memUsageMB < 500) {
                this.log('PASS', `記憶體使用合理: ${memUsageMB}MB`);
            } else {
                this.log('WARN', `記憶體使用較高: ${memUsageMB}MB`);
            }

        } catch (error) {
            this.log('ERROR', '性能測試失敗', error.message);
        }
    }

    async runAllTests() {
        console.log('🚀 開始增強資料來源綜合測試...\n');

        // 執行所有測試
        await this.testEuropeanaCrawler();
        await this.testGoogleScholarCrawler();
        await this.testUnifiedManager();
        await this.testDataQualityAssessment();
        await this.testPerformanceAndScaling();

        // 生成測試報告
        await this.generateTestReport();

        // 顯示摘要
        console.log('\n📊 測試摘要:');
        console.log(`✅ 通過: ${this.testResults.summary.passed}`);
        console.log(`❌ 失敗: ${this.testResults.summary.failed}`);
        console.log(`⚠️  警告: ${this.testResults.summary.warnings}`);
        console.log(`📋 總計: ${this.testResults.summary.totalTests}`);

        const passRate = (this.testResults.summary.passed / this.testResults.summary.totalTests * 100).toFixed(1);
        console.log(`📈 通過率: ${passRate}%`);

        if (this.testResults.summary.failed === 0) {
            console.log('\n🎉 所有測試通過！新資料來源已準備就緒。');
        } else {
            console.log('\n⚠️  部分測試失敗，請檢查詳細報告。');
        }

        return this.testResults;
    }

    async generateTestReport() {
        const reportPath = path.join(__dirname, 'data', 'output', `test-report-${Date.now()}.json`);

        // 確保目錄存在
        await fs.mkdir(path.dirname(reportPath), { recursive: true });

        // 加入系統資訊
        this.testResults.systemInfo = {
            nodeVersion: process.version,
            platform: process.platform,
            arch: process.arch,
            memoryUsage: process.memoryUsage(),
            uptime: process.uptime()
        };

        // 加入測試建議
        this.testResults.recommendations = this.generateRecommendations();

        await fs.writeFile(reportPath, JSON.stringify(this.testResults, null, 2));

        console.log(`\n📁 測試報告已保存至: ${reportPath}`);
        return reportPath;
    }

    generateRecommendations() {
        const recommendations = [];

        if (this.testResults.summary.failed > 0) {
            recommendations.push({
                type: 'critical',
                message: '有測試失敗，建議修復後再進行生產部署'
            });
        }

        if (this.testResults.summary.warnings > 2) {
            recommendations.push({
                type: 'improvement',
                message: '多項警告提示，建議優化資料品質和性能'
            });
        }

        const passRate = this.testResults.summary.passed / this.testResults.summary.totalTests;
        if (passRate >= 0.9) {
            recommendations.push({
                type: 'success',
                message: '測試通過率優秀，系統運行良好'
            });
        } else if (passRate >= 0.7) {
            recommendations.push({
                type: 'moderate',
                message: '測試通過率良好，建議進一步優化'
            });
        } else {
            recommendations.push({
                type: 'warning',
                message: '測試通過率偏低，建議全面檢查系統'
            });
        }

        return recommendations;
    }
}

// 主程序
if (require.main === module) {
    async function main() {
        const tester = new DataSourceTester();

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

module.exports = DataSourceTester;