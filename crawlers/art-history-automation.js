#!/usr/bin/env node

/**
 * 藝術史資料庫 - N8N 整合自動化腳本
 * 這個腳本提供了一個簡單的方式來自動化藝術史資料庫的Agent功能
 */

const axios = require('axios');

// 配置
const CONFIG = {
    API_BASE: 'http://localhost:3000',
    N8N_KEY: 'CHANGE_ME_N8N_API_KEY',
    TIMEOUT: 30000
};

// 顏色輸出工具
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    green: '\x1b[32m',
    red: '\x1b[31m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    magenta: '\x1b[35m',
    cyan: '\x1b[36m'
};

function colorLog(message, color = 'reset') {
    console.log(`${colors[color]}${message}${colors.reset}`);
}

// Agent觸發器類
class ArtHistoryAgentTrigger {
    constructor() {
        this.client = axios.create({
            baseURL: CONFIG.API_BASE,
            timeout: CONFIG.TIMEOUT,
            headers: {
                'Content-Type': 'application/json',
                'X-N8N-Key': CONFIG.N8N_KEY
            }
        });
    }

    // 檢查系統狀態
    async checkHealth() {
        colorLog('\n🔍 檢查系統健康狀態...', 'cyan');

        try {
            // 檢查主API
            const healthResponse = await this.client.get('/health');
            colorLog('✅ 藝術史資料庫：運行正常', 'green');

            // 檢查N8N整合API
            const n8nResponse = await this.client.get('/api/v1/n8n/health');
            colorLog('✅ N8N整合API：運行正常', 'green');

            return true;
        } catch (error) {
            colorLog('❌ 系統健康檢查失敗:', 'red');
            colorLog(`   錯誤: ${error.message}`, 'red');
            return false;
        }
    }

    // 觸發Agent
    async triggerAgent(agentType, parameters, options = {}) {
        const { workflowId = 'automation-script', executionId = `exec-${Date.now()}` } = options;

        colorLog(`\n🚀 觸發 ${agentType} Agent...`, 'yellow');

        try {
            const startTime = Date.now();

            const response = await this.client.post('/api/v1/n8n/webhook/trigger', {
                agentType,
                workflowId,
                executionId,
                parameters
            });

            const endTime = Date.now();
            const executionTime = endTime - startTime;

            colorLog(`✅ ${agentType} Agent 執行成功 (${executionTime}ms)`, 'green');

            if (response.data.success) {
                colorLog('📊 執行結果:', 'blue');
                console.log(JSON.stringify(response.data.data, null, 2));

                if (response.data.metadata) {
                    colorLog(`\n📈 元數據: 執行時間 ${response.data.metadata.executionTime}`, 'magenta');
                }
            }

            return response.data;
        } catch (error) {
            colorLog(`❌ ${agentType} Agent 執行失敗:`, 'red');
            if (error.response) {
                colorLog(`   HTTP ${error.response.status}: ${error.response.data.message || error.response.statusText}`, 'red');
            } else {
                colorLog(`   錯誤: ${error.message}`, 'red');
            }
            throw error;
        }
    }

    // 批量處理
    async batchProcess(tasks, options = {}) {
        const { workflowId = 'batch-automation', executionId = `batch-${Date.now()}` } = options;

        colorLog('\n📦 啟動批量處理...', 'yellow');
        colorLog(`   任務數量: ${tasks.length}`, 'cyan');

        try {
            const startTime = Date.now();

            const response = await this.client.post('/api/v1/n8n/batch/process', {
                workflowId,
                executionId,
                tasks
            });

            const endTime = Date.now();
            const executionTime = endTime - startTime;

            colorLog(`✅ 批量處理完成 (${executionTime}ms)`, 'green');

            if (response.data.success) {
                const { summary } = response.data.data;
                colorLog(`📊 處理摘要:`, 'blue');
                colorLog(`   總任務: ${summary.total}`, 'cyan');
                colorLog(`   成功: ${summary.successful}`, 'green');
                colorLog(`   失敗: ${summary.failed}`, 'red');
                colorLog(`   總執行時間: ${summary.totalExecutionTime}`, 'magenta');

                if (summary.failed > 0) {
                    colorLog(`\n⚠️  失敗的任務:`, 'yellow');
                    response.data.data.results
                        .filter(result => !result.success)
                        .forEach(result => {
                            colorLog(`   - ${result.taskId}: ${result.error}`, 'red');
                        });
                }
            }

            return response.data;
        } catch (error) {
            colorLog('❌ 批量處理失敗:', 'red');
            colorLog(`   錯誤: ${error.message}`, 'red');
            throw error;
        }
    }

    // 預定義的測試場景
    async runTestScenarios() {
        colorLog('\n🧪 執行測試場景...', 'bright');

        const scenarios = [
            {
                name: 'WebCrawler - 文藝復興繪畫',
                agentType: 'webCrawler',
                parameters: {
                    sources: ['met', 'louvre', 'europeana'],
                    keywords: ['Renaissance', 'painting'],
                    maxResults: 5
                }
            },
            {
                name: 'Metadata Extractor - 蒙娜麗莎',
                agentType: 'metadataExtractor',
                parameters: {
                    inputData: {
                        title: '蒙娜麗莎',
                        artist: '達文西',
                        date: '1503-1519',
                        medium: '油畫',
                        dimensions: '77cm × 53cm'
                    },
                    outputFormat: 'dublin-core',
                    validationEnabled: true
                }
            },
            {
                name: 'Classification - 藝術風格分析',
                agentType: 'classification',
                parameters: {
                    inputData: {
                        title: '星夜',
                        artist: '梵谷',
                        description: '描繪夜晚天空中旋轉的星雲'
                    },
                    categories: ['period', 'style', 'movement'],
                    confidenceThreshold: 0.8
                }
            },
            {
                name: 'Translation - 藝術描述翻譯',
                agentType: 'summarizationtranslation',
                parameters: {
                    inputText: '這幅畫展現了後印象派的特色，運用了大膽的色彩和動態的筆觸',
                    targetLanguage: 'en',
                    summaryLength: 'medium',
                    includeKeywords: true
                }
            }
        ];

        for (const scenario of scenarios) {
            try {
                colorLog(`\n📋 場景: ${scenario.name}`, 'bright');
                await this.triggerAgent(scenario.agentType, scenario.parameters);
                await new Promise(resolve => setTimeout(resolve, 1000)); // 短暫延遲
            } catch (error) {
                colorLog(`   跳過場景: ${scenario.name}`, 'yellow');
            }
        }
    }

    // 自動化工作流程範例
    async runAutomationWorkflow() {
        colorLog('\n⚡ 執行自動化工作流程...', 'bright');

        try {
            // 步驟1：爬取資料
            colorLog('\n步驟1: 爬取藝術作品資料', 'cyan');
            const crawlResult = await this.triggerAgent('webCrawler', {
                sources: ['met'],
                keywords: ['impressionism'],
                maxResults: 3
            });

            // 步驟2：提取元數據
            if (crawlResult.success && crawlResult.data.results) {
                colorLog('\n步驟2: 提取和標準化元數據', 'cyan');

                const metadataTasks = crawlResult.data.results.map((artwork, index) => ({
                    id: `metadata-${index}`,
                    agentType: 'metadataExtractor',
                    parameters: {
                        inputData: artwork.data || artwork,
                        outputFormat: 'dublin-core',
                        validationEnabled: true
                    }
                }));

                await this.batchProcess(metadataTasks);
            }

            colorLog('\n🎉 自動化工作流程完成!', 'green');

        } catch (error) {
            colorLog('\n❌ 自動化工作流程失敗', 'red');
            throw error;
        }
    }
}

// CLI介面
async function main() {
    colorLog('🎨 藝術史資料庫 - N8N 整合自動化腳本', 'bright');
    colorLog('================================================', 'cyan');

    const agent = new ArtHistoryAgentTrigger();

    // 檢查健康狀態
    const isHealthy = await agent.checkHealth();
    if (!isHealthy) {
        colorLog('\n❌ 系統未就緒，請確認服務狀態後重試', 'red');
        process.exit(1);
    }

    const args = process.argv.slice(2);
    const command = args[0] || 'help';

    switch (command) {
        case 'test':
            await agent.runTestScenarios();
            break;

        case 'workflow':
            await agent.runAutomationWorkflow();
            break;

        case 'crawler':
            await agent.triggerAgent('webCrawler', {
                sources: ['met', 'louvre', 'europeana'],
                keywords: args.slice(1) || ['art'],
                maxResults: 10
            });
            break;

        case 'metadata':
            await agent.triggerAgent('metadataExtractor', {
                inputData: { title: args[1] || 'Unknown Artwork' },
                outputFormat: 'dublin-core'
            });
            break;

        case 'classify':
            await agent.triggerAgent('classification', {
                inputData: { title: args[1] || 'Unknown Artwork' },
                categories: ['period', 'style', 'movement']
            });
            break;

        case 'translate':
            await agent.triggerAgent('summarizationtranslation', {
                inputText: args.slice(1).join(' ') || '這是一幅美麗的藝術作品',
                targetLanguage: 'en'
            });
            break;

        case 'help':
        default:
            colorLog('\n📖 使用說明:', 'yellow');
            colorLog('  node art-history-automation.js test        # 執行所有測試場景', 'cyan');
            colorLog('  node art-history-automation.js workflow    # 執行自動化工作流程', 'cyan');
            colorLog('  node art-history-automation.js crawler [keywords...]  # 執行爬蟲Agent', 'cyan');
            colorLog('  node art-history-automation.js metadata <title>       # 執行元數據提取', 'cyan');
            colorLog('  node art-history-automation.js classify <title>       # 執行分類Agent', 'cyan');
            colorLog('  node art-history-automation.js translate <text>       # 執行翻譯Agent', 'cyan');
            colorLog('  node art-history-automation.js help        # 顯示此說明', 'cyan');
            break;
    }

    colorLog('\n✨ 腳本執行完成!', 'green');
}

// 錯誤處理
process.on('unhandledRejection', (reason, promise) => {
    colorLog('\n💥 未處理的Promise拒絕:', 'red');
    colorLog(reason, 'red');
    process.exit(1);
});

process.on('uncaughtException', (error) => {
    colorLog('\n💥 未捕獲的異常:', 'red');
    colorLog(error.message, 'red');
    process.exit(1);
});

// 執行主函數
if (require.main === module) {
    main().catch(error => {
        colorLog('\n💥 腳本執行錯誤:', 'red');
        colorLog(error.message, 'red');
        process.exit(1);
    });
}

module.exports = { ArtHistoryAgentTrigger, CONFIG };