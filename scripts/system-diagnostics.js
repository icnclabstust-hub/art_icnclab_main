#!/usr/bin/env node
/**
 * 藝術史資料庫系統診斷工具
 * 全面檢查系統配置、依賴項和功能狀態
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class SystemDiagnostics {
    constructor() {
        this.issues = [];
        this.warnings = [];
        this.successes = [];
        this.results = {
            environment: {},
            services: {},
            dependencies: {},
            configuration: {},
            functionality: {}
        };
    }

    /**
     * 執行完整診斷
     */
    async runFullDiagnostics() {
        console.log('🔍 開始藝術史資料庫系統診斷...\n');

        try {
            // 1. 環境檢查
            await this.checkEnvironment();

            // 2. 依賴項檢查
            await this.checkDependencies();

            // 3. 配置檢查
            await this.checkConfiguration();

            // 4. 服務檢查
            await this.checkServices();

            // 5. 功能檢查
            await this.checkFunctionality();

            // 6. 爬取功能檢查
            await this.checkScrapingFunctionality();

            // 7. 生成報告
            this.generateReport();

        } catch (error) {
            console.error('❌ 診斷過程中發生錯誤:', error);
            process.exit(1);
        }
    }

    /**
     * 環境檢查
     */
    async checkEnvironment() {
        console.log('🌍 檢查運行環境...');

        try {
            // Node.js 版本
            const nodeVersion = process.version;
            this.results.environment.nodeVersion = nodeVersion;

            if (nodeVersion >= 'v18.0.0') {
                this.addSuccess('Node.js 版本符合要求', nodeVersion);
            } else {
                this.addWarning('Node.js 版本可能過舊', `當前: ${nodeVersion}, 建議: v18+`);
            }

            // 記憶體
            const memory = process.memoryUsage();
            this.results.environment.memory = {
                heapUsed: Math.round(memory.heapUsed / 1024 / 1024) + 'MB',
                heapTotal: Math.round(memory.heapTotal / 1024 / 1024) + 'MB'
            };

            // 平台
            this.results.environment.platform = process.platform;
            this.results.environment.arch = process.arch;

            // 工作目錄
            this.results.environment.cwd = process.cwd();

            this.addSuccess('環境檢查完成');

        } catch (error) {
            this.addIssue('環境檢查失敗', error.message);
        }
    }

    /**
     * 依賴項檢查
     */
    async checkDependencies() {
        console.log('📦 檢查依賴項...');

        try {
            // 檢查 package.json
            const packagePath = path.join(process.cwd(), '../package.json');
            if (!fs.existsSync(packagePath)) {
                this.addIssue('package.json 不存在');
                return;
            }

            const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));
            this.results.dependencies.packageInfo = {
                name: packageJson.name,
                version: packageJson.version,
                description: packageJson.description
            };

            // 檢查關鍵依賴
            const criticalDeps = [
                'express', 'axios', 'cheerio', 'playwright',
                'pg', 'redis', 'winston', 'dotenv'
            ];

            const missingDeps = [];
            const availableDeps = [];

            for (const dep of criticalDeps) {
                try {
                    require.resolve(dep);
                    availableDeps.push(dep);
                } catch (error) {
                    missingDeps.push(dep);
                }
            }

            this.results.dependencies.available = availableDeps;
            this.results.dependencies.missing = missingDeps;

            if (missingDeps.length === 0) {
                this.addSuccess('所有關鍵依賴項已安裝');
            } else {
                this.addIssue('缺少關鍵依賴項', missingDeps.join(', '));
            }

        } catch (error) {
            this.addIssue('依賴項檢查失敗', error.message);
        }
    }

    /**
     * 配置檢查
     */
    async checkConfiguration() {
        console.log('⚙️ 檢查配置文件...');

        try {
            // 檢查 .env 文件
            const envPath = path.join(process.cwd(), '.env');
            if (!fs.existsSync(envPath)) {
                this.addIssue('.env 配置文件不存在');
                return;
            }

            const envContent = fs.readFileSync(envPath, 'utf-8');

            // 檢查關鍵配置項
            const requiredConfigs = [
                'NODE_ENV',
                'API_PORT',
                'USE_OLLAMA',
                'OLLAMA_BASE_URL',
                'OLLAMA_DEFAULT_MODEL',
                'OLLAMA_EMBEDDING_MODEL'
            ];

            const configStatus = {};
            for (const config of requiredConfigs) {
                const hasConfig = envContent.includes(config);
                configStatus[config] = hasConfig;

                if (hasConfig) {
                    const value = process.env[config];
                    if (value && value !== 'undefined' && !value.includes('placeholder')) {
                        this.addSuccess(`配置 ${config} 已設置`, value);
                    } else {
                        this.addWarning(`配置 ${config} 需要設置值`);
                    }
                } else {
                    this.addWarning(`缺少配置項 ${config}`);
                }
            }

            this.results.configuration.status = configStatus;

            // 檢查 Ollama 配置
            if (process.env.USE_OLLAMA === 'true') {
                this.addSuccess('Ollama 本地 AI 已啟用');
                this.results.configuration.aiMode = 'Ollama Local';
            } else {
                this.addWarning('未啟用 Ollama，將依賴外部 API');
                this.results.configuration.aiMode = 'External API';
            }

        } catch (error) {
            this.addIssue('配置檢查失敗', error.message);
        }
    }

    /**
     * 服務檢查
     */
    async checkServices() {
        console.log('🔧 檢查外部服務...');

        // 檢查 Ollama 服務
        await this.checkOllamaService();
    }

    /**
     * 檢查 Ollama 服務
     */
    async checkOllamaService() {
        try {
            const axios = require('axios');

            const response = await axios.get('http://localhost:11434/api/tags', {
                timeout: 5000
            });

            if (response.status === 200) {
                const models = response.data.models || [];
                this.results.services.ollama = {
                    status: 'running',
                    modelsCount: models.length,
                    models: models.map(m => m.name)
                };

                this.addSuccess('Ollama 服務正常運行', `${models.length} 個模型可用`);

                // 檢查必要模型
                const requiredModels = ['llama3.1:8b', 'bge-m3:latest'];
                const availableModels = models.map(m => m.name);

                for (const model of requiredModels) {
                    if (availableModels.includes(model)) {
                        this.addSuccess(`模型 ${model} 可用`);
                    } else {
                        this.addWarning(`模型 ${model} 未安裝`);
                    }
                }

            } else {
                this.addIssue('Ollama 服務回應異常', `HTTP ${response.status}`);
            }

        } catch (error) {
            this.results.services.ollama = {
                status: 'not_available',
                error: error.message
            };
            this.addIssue('Ollama 服務不可用', error.message);
        }
    }

    /**
     * 功能檢查
     */
    async checkFunctionality() {
        console.log('🧪 檢查核心功能...');

        try {
            // 檢查關鍵模組是否可以載入
            const coreModules = [
                './src/services/ollamaService',
                './agents/web-crawler/index',
                './agents/classification/index',
                './agents/summarization-translation/index'
            ];

            const moduleStatus = {};
            for (const modulePath of coreModules) {
                try {
                    const fullPath = path.join(process.cwd(), modulePath + '.js');
                    if (fs.existsSync(fullPath)) {
                        // 嘗試載入模組（但不執行）
                        const moduleContent = fs.readFileSync(fullPath, 'utf-8');
                        if (moduleContent.length > 0) {
                            moduleStatus[modulePath] = 'available';
                            this.addSuccess(`模組 ${modulePath} 可用`);
                        } else {
                            moduleStatus[modulePath] = 'empty';
                            this.addWarning(`模組 ${modulePath} 為空`);
                        }
                    } else {
                        moduleStatus[modulePath] = 'missing';
                        this.addIssue(`模組 ${modulePath} 不存在`);
                    }
                } catch (error) {
                    moduleStatus[modulePath] = 'error';
                    this.addIssue(`模組 ${modulePath} 載入失敗`, error.message);
                }
            }

            this.results.functionality.modules = moduleStatus;

        } catch (error) {
            this.addIssue('功能檢查失敗', error.message);
        }
    }

    /**
     * 檢查爬取功能
     */
    async checkScrapingFunctionality() {
        console.log('🕷️ 檢查資料爬取功能...');

        try {
            // 檢查爬蟲相關檔案
            const scraperFiles = [
                './agents/web-crawler/index.js',
                './src/utils/crawlerWorker.js',
                './src/utils/crawlerPerformanceMonitor.js'
            ];

            let scrapingStatus = 'available';
            const fileStatuses = {};

            for (const filePath of scraperFiles) {
                const fullPath = path.join(process.cwd(), filePath);
                if (fs.existsSync(fullPath)) {
                    fileStatuses[filePath] = 'exists';
                    this.addSuccess(`爬蟲檔案 ${filePath} 存在`);
                } else {
                    fileStatuses[filePath] = 'missing';
                    this.addWarning(`爬蟲檔案 ${filePath} 不存在`);
                    scrapingStatus = 'partial';
                }
            }

            this.results.functionality.scraping = {
                status: scrapingStatus,
                files: fileStatuses
            };

            // 檢查 Playwright（用於動態內容爬取）
            try {
                require.resolve('playwright');
                this.addSuccess('Playwright 瀏覽器自動化工具可用');
            } catch (error) {
                this.addWarning('Playwright 未安裝，動態內容爬取可能受限');
            }

            // 檢查網路連接
            await this.checkNetworkConnectivity();

        } catch (error) {
            this.addIssue('爬取功能檢查失敗', error.message);
        }
    }

    /**
     * 檢查網路連接
     */
    async checkNetworkConnectivity() {
        try {
            const axios = require('axios');

            // 測試外部連接
            const testUrls = [
                'https://collectionapi.metmuseum.org/public/collection/v1/objects/1',
                'https://www.googleapis.com/books/v1/volumes?q=art+history'
            ];

            for (const url of testUrls) {
                try {
                    const response = await axios.get(url, { timeout: 5000 });
                    if (response.status === 200) {
                        this.addSuccess(`網路連接測試通過`, url);
                    }
                } catch (error) {
                    this.addWarning(`網路連接測試失敗`, `${url}: ${error.message}`);
                }
            }

        } catch (error) {
            this.addWarning('網路連接測試跳過', error.message);
        }
    }

    /**
     * 添加成功項目
     */
    addSuccess(message, detail = '') {
        this.successes.push({ message, detail });
        console.log(`✅ ${message}${detail ? ` - ${detail}` : ''}`);
    }

    /**
     * 添加警告項目
     */
    addWarning(message, detail = '') {
        this.warnings.push({ message, detail });
        console.log(`⚠️ ${message}${detail ? ` - ${detail}` : ''}`);
    }

    /**
     * 添加問題項目
     */
    addIssue(message, detail = '') {
        this.issues.push({ message, detail });
        console.log(`❌ ${message}${detail ? ` - ${detail}` : ''}`);
    }

    /**
     * 生成診斷報告
     */
    generateReport() {
        console.log('\n' + '='.repeat(60));
        console.log('📋 藝術史資料庫系統診斷報告');
        console.log('='.repeat(60));

        // 整體狀態
        const totalIssues = this.issues.length;
        const totalWarnings = this.warnings.length;
        const totalSuccesses = this.successes.length;

        console.log(`\n📊 整體狀態:`);
        console.log(`   ✅ 成功項目: ${totalSuccesses}`);
        console.log(`   ⚠️ 警告項目: ${totalWarnings}`);
        console.log(`   ❌ 問題項目: ${totalIssues}`);

        const overallStatus = totalIssues === 0 ?
            (totalWarnings === 0 ? '優秀' : '良好') :
            (totalIssues <= 2 ? '需要注意' : '需要修復');

        console.log(`   🎯 系統狀態: ${overallStatus}\n`);

        // 環境資訊
        if (this.results.environment) {
            console.log('🌍 運行環境:');
            console.log(`   Node.js: ${this.results.environment.nodeVersion}`);
            console.log(`   平台: ${this.results.environment.platform} (${this.results.environment.arch})`);
            console.log(`   記憶體: ${this.results.environment.memory?.heapUsed || 'N/A'}\n`);
        }

        // AI 配置
        if (this.results.configuration) {
            console.log('🤖 AI 配置:');
            console.log(`   模式: ${this.results.configuration.aiMode || 'Unknown'}`);

            if (this.results.services.ollama) {
                const ollama = this.results.services.ollama;
                console.log(`   Ollama 狀態: ${ollama.status}`);
                if (ollama.modelsCount) {
                    console.log(`   可用模型: ${ollama.modelsCount} 個`);
                    console.log(`   模型列表: ${ollama.models?.join(', ') || 'N/A'}`);
                }
            }
            console.log('');
        }

        // 爬取功能狀態
        if (this.results.functionality?.scraping) {
            console.log('🕷️ 資料爬取功能:');
            console.log(`   狀態: ${this.results.functionality.scraping.status}`);
            console.log('');
        }

        // 主要問題
        if (totalIssues > 0) {
            console.log('❌ 需要解決的問題:');
            this.issues.forEach((issue, index) => {
                console.log(`   ${index + 1}. ${issue.message}${issue.detail ? ` (${issue.detail})` : ''}`);
            });
            console.log('');
        }

        // 改善建議
        console.log('💡 改善建議:');
        const recommendations = this.generateRecommendations();
        recommendations.forEach((rec, index) => {
            console.log(`   ${index + 1}. ${rec}`);
        });

        // 後續步驟
        console.log('\n🚀 建議的後續步驟:');
        const nextSteps = this.generateNextSteps();
        nextSteps.forEach((step, index) => {
            console.log(`   ${index + 1}. ${step}`);
        });

        console.log('\n🎉 診斷完成！');
        console.log('詳細結果已保存，可執行相應修復步驟。');
    }

    /**
     * 生成改善建議
     */
    generateRecommendations() {
        const recommendations = [];

        // 基於問題生成建議
        if (this.issues.some(i => i.message.includes('依賴項'))) {
            recommendations.push('執行 npm install 安裝缺少的依賴項');
        }

        if (this.issues.some(i => i.message.includes('Ollama'))) {
            recommendations.push('啟動 Ollama 服務: ollama serve');
            recommendations.push('下載必要模型: ollama pull llama3.1:8b && ollama pull bge-m3:latest');
        }

        if (this.warnings.some(w => w.message.includes('配置'))) {
            recommendations.push('檢查並完善 .env 配置文件');
        }

        if (this.warnings.some(w => w.message.includes('模型'))) {
            recommendations.push('下載缺少的 AI 模型');
        }

        if (this.warnings.some(w => w.message.includes('網路'))) {
            recommendations.push('檢查網路連接和防火牆設置');
        }

        if (recommendations.length === 0) {
            recommendations.push('系統配置良好，可以開始使用');
        }

        return recommendations;
    }

    /**
     * 生成後續步驟
     */
    generateNextSteps() {
        const steps = [];

        if (this.issues.length > 0) {
            steps.push('📋 解決上述問題項目');
            steps.push('🔧 執行修復腳本或手動修復');
        }

        if (this.results.services?.ollama?.status === 'running') {
            steps.push('🧪 執行 Ollama 整合測試: node scripts/test-ollama-integration.js');
        }

        steps.push('🚀 嘗試啟動應用程式: npm start');
        steps.push('🕷️ 測試資料爬取功能');
        steps.push('📊 監控系統效能和穩定性');

        return steps;
    }
}

// 執行診斷
async function main() {
    const diagnostics = new SystemDiagnostics();

    try {
        await diagnostics.runFullDiagnostics();
        process.exit(0);
    } catch (error) {
        console.error('診斷失敗:', error);
        process.exit(1);
    }
}

// 如果直接執行此腳本
if (require.main === module) {
    main();
}

module.exports = SystemDiagnostics;