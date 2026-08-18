#!/usr/bin/env node
/**
 * Agent Hub - Agent通信中心
 * 負責協調和管理4個AI Agent的工作流程，實現智能數據處理管線
 */

const EventEmitter = require('events');
const fs = require('fs/promises');
const path = require('path');

// 導入4個Agent
const WebCrawlerAgent = require('../../agents/web-crawler');
const MetadataExtractorAgent = require('../../agents/metadata-extractor');
const ClassificationAgent = require('../../agents/classification');
const SummarizationTranslationAgent = require('../../agents/summarization-translation');

class AgentHub extends EventEmitter {
    constructor() {
        super();
        this.id = 'agent-hub';
        this.name = 'Agent通信中心';
        this.status = 'initializing';
        this.version = '1.0.0';

        // Agent實例
        this.agents = {
            webCrawler: null,
            metadataExtractor: null,
            classification: null,
            summarizationTranslation: null
        };

        // 工作流程配置
        this.workflows = {
            // 完整的數據處理管線
            fullPipeline: [
                'webCrawler',      // 1. 爬取數據
                'metadataExtractor', // 2. 提取元數據
                'classification',    // 3. 分類
                'summarizationTranslation' // 4. 摘要翻譯
            ],
            // 僅處理現有數據
            processExisting: [
                'metadataExtractor',
                'classification',
                'summarizationTranslation'
            ],
            // 僅爬取和基本處理
            crawlOnly: [
                'webCrawler',
                'metadataExtractor'
            ]
        };

        // 任務管理
        this.currentWorkflow = null;
        this.workflowProgress = [];
        this.errors = [];
        this.statistics = {
            totalTasks: 0,
            completedTasks: 0,
            failedTasks: 0,
            startTime: null,
            endTime: null
        };

        // 數據目錄
        this.dataDir = process.env.DATA_RAW_DIR || './data';
        this.logsDir = process.env.LOGS_DIR || './logs';

        console.log(`🎯 ${this.name} 初始化完成`);
    }

    /**
     * 初始化Agent Hub
     */
    async initialize() {
        try {
            this.status = 'initializing';
            console.log('🔧 正在初始化Agent Hub...');

            // 確保目錄存在
            await this.ensureDirectories();

            // 初始化所有Agent
            await this.initializeAgents();

            // 設置Agent事件監聽
            this.setupAgentEventListeners();

            this.status = 'ready';
            console.log('✅ Agent Hub 初始化完成');
            console.log('📋 可用工作流程:', Object.keys(this.workflows));
            this.emit('initialized');

        } catch (error) {
            this.status = 'error';
            console.error('❌ Agent Hub 初始化失敗:', error.message);
            this.emit('error', error);
            throw error;
        }
    }

    /**
     * 確保目錄存在
     */
    async ensureDirectories() {
        const dirs = [
            this.logsDir,
            path.join(this.logsDir, 'workflows'),
            path.join(this.dataDir, 'pipeline-status')
        ];

        for (const dir of dirs) {
            await fs.mkdir(dir, { recursive: true });
        }

        console.log('📁 Hub目錄準備完成');
    }

    /**
     * 初始化所有Agent
     */
    async initializeAgents() {
        console.log('🤖 初始化所有Agent...');

        // 創建Agent實例
        this.agents.webCrawler = new WebCrawlerAgent();
        this.agents.metadataExtractor = new MetadataExtractorAgent();
        this.agents.classification = new ClassificationAgent();
        this.agents.summarizationTranslation = new SummarizationTranslationAgent();

        // 並行初始化所有Agent
        const initPromises = Object.entries(this.agents).map(async ([name, agent]) => {
            try {
                await agent.initialize();
                console.log(`✅ ${name} 初始化成功`);
                return { name, success: true };
            } catch (error) {
                console.error(`❌ ${name} 初始化失敗:`, error.message);
                return { name, success: false, error: error.message };
            }
        });

        const results = await Promise.all(initPromises);
        const successful = results.filter(r => r.success).length;
        const failed = results.filter(r => !r.success);

        console.log(`🎯 Agent初始化完成: ${successful}/${results.length} 成功`);

        if (failed.length > 0) {
            console.warn('⚠️ 以下Agent初始化失敗:', failed.map(f => f.name));
            // 記錄失敗但不拋出異常，允許部分Agent運行
        }
    }

    /**
     * 設置Agent事件監聽
     */
    setupAgentEventListeners() {
        Object.entries(this.agents).forEach(([name, agent]) => {
            if (!agent) return;

            // 監聽Agent完成事件
            agent.on('initialized', () => {
                console.log(`📡 ${name} 已就緒`);
            });

            agent.on('error', (error) => {
                console.error(`🚨 ${name} 發生錯誤:`, error.message);
                this.handleAgentError(name, error);
            });

            // 監聽特定Agent事件
            if (name === 'webCrawler') {
                agent.on('crawlingComplete', (result) => {
                    console.log(`🕷️ 爬取完成:`, result);
                    this.emit('stepComplete', { agent: name, result });
                });
            }

            if (name === 'metadataExtractor') {
                agent.on('extractionComplete', (result) => {
                    console.log(`🔍 元數據提取完成:`, result);
                    this.emit('stepComplete', { agent: name, result });
                });
            }

            if (name === 'classification') {
                agent.on('classificationComplete', (result) => {
                    console.log(`🏷️ 分類完成:`, result);
                    this.emit('stepComplete', { agent: name, result });
                });
            }

            if (name === 'summarizationTranslation') {
                agent.on('processingComplete', (result) => {
                    console.log(`🌍 摘要翻譯完成:`, result);
                    this.emit('stepComplete', { agent: name, result });
                });
            }
        });
    }

    /**
     * 執行工作流程
     */
    async executeWorkflow(workflowName, config = {}) {
        try {
            if (!this.workflows[workflowName]) {
                throw new Error(`未知的工作流程: ${workflowName}`);
            }

            this.status = 'running';
            this.currentWorkflow = workflowName;
            this.statistics.startTime = new Date();
            this.statistics.totalTasks = this.workflows[workflowName].length;
            this.statistics.completedTasks = 0;
            this.statistics.failedTasks = 0;

            console.log(`🚀 開始執行工作流程: ${workflowName}`);
            console.log(`📋 執行順序: ${this.workflows[workflowName].join(' → ')}`);

            const steps = this.workflows[workflowName];
            const results = {};

            // 逐步執行工作流程
            for (let i = 0; i < steps.length; i++) {
                const stepName = steps[i];
                const stepConfig = config[stepName] || {};

                console.log(`\n🔄 執行步驟 ${i + 1}/${steps.length}: ${stepName}`);

                try {
                    const stepResult = await this.executeStep(stepName, stepConfig);
                    results[stepName] = stepResult;

                    this.statistics.completedTasks++;
                    this.workflowProgress.push({
                        step: stepName,
                        status: 'completed',
                        result: stepResult,
                        timestamp: new Date()
                    });

                    console.log(`✅ 步驟 ${stepName} 完成`);

                } catch (error) {
                    console.error(`❌ 步驟 ${stepName} 失敗:`, error.message);

                    this.statistics.failedTasks++;
                    this.workflowProgress.push({
                        step: stepName,
                        status: 'failed',
                        error: error.message,
                        timestamp: new Date()
                    });

                    // 根據配置決定是否繼續執行
                    if (config.stopOnError !== false) {
                        throw error;
                    }
                }
            }

            this.statistics.endTime = new Date();
            this.status = 'completed';

            // 生成工作流程報告
            const report = await this.generateWorkflowReport(workflowName, results);

            console.log(`\n🎉 工作流程 ${workflowName} 執行完成！`);
            console.log(`📊 成功: ${this.statistics.completedTasks}/${this.statistics.totalTasks}`);

            this.emit('workflowComplete', {
                workflow: workflowName,
                results,
                report,
                statistics: this.statistics
            });

            return {
                workflow: workflowName,
                success: true,
                results,
                report,
                statistics: this.statistics
            };

        } catch (error) {
            this.status = 'error';
            this.statistics.endTime = new Date();

            console.error(`❌ 工作流程 ${workflowName} 執行失敗:`, error.message);

            this.emit('workflowError', {
                workflow: workflowName,
                error: error.message,
                statistics: this.statistics
            });

            throw error;
        }
    }

    /**
     * 執行單個步驟
     */
    async executeStep(stepName, config) {
        const agent = this.agents[stepName];
        if (!agent) {
            throw new Error(`Agent ${stepName} 不可用`);
        }

        // 檢查Agent狀態
        const status = agent.getStatus();
        if (status.status === 'error') {
            throw new Error(`Agent ${stepName} 處於錯誤狀態`);
        }

        // 根據不同Agent執行相應方法
        switch (stepName) {
            case 'webCrawler':
                return await agent.startCrawling({
                    sources: config.sources || ['met'],
                    keywords: config.keywords || ['renaissance', 'impressionism'],
                    maxItems: config.maxItems || 50
                });

            case 'metadataExtractor':
                return await agent.startExtraction({
                    inputSources: config.inputSources || ['museums'],
                    outputFormat: config.outputFormat || 'dublin-core',
                    includeValidation: config.includeValidation !== false
                });

            case 'classification':
                return await agent.startClassification({
                    inputSources: config.inputSources || ['metadata'],
                    classificationTypes: config.classificationTypes || ['period', 'style', 'medium'],
                    generateReports: config.generateReports !== false
                });

            case 'summarizationTranslation':
                return await agent.startProcessing({
                    inputSources: config.inputSources || ['classified'],
                    targetLanguages: config.targetLanguages || ['zh-TW', 'en'],
                    generateSummaries: config.generateSummaries !== false,
                    generateTranslations: config.generateTranslations !== false,
                    culturalAdaptation: config.culturalAdaptation !== false
                });

            default:
                throw new Error(`未知的步驟: ${stepName}`);
        }
    }

    /**
     * 處理Agent錯誤
     */
    handleAgentError(agentName, error) {
        this.errors.push({
            agent: agentName,
            error: error.message,
            timestamp: new Date()
        });

        // 如果正在執行工作流程，可能需要停止
        if (this.status === 'running' && this.currentWorkflow) {
            console.warn(`⚠️ 工作流程中的Agent ${agentName} 發生錯誤，可能影響執行`);
        }
    }

    /**
     * 生成工作流程報告
     */
    async generateWorkflowReport(workflowName, results) {
        const duration = this.statistics.endTime - this.statistics.startTime;

        const report = {
            workflow: workflowName,
            execution: {
                startTime: this.statistics.startTime.toISOString(),
                endTime: this.statistics.endTime.toISOString(),
                duration: Math.round(duration / 1000), // 秒
                totalSteps: this.statistics.totalTasks,
                completedSteps: this.statistics.completedTasks,
                failedSteps: this.statistics.failedTasks,
                successRate: (this.statistics.completedTasks / this.statistics.totalTasks) * 100
            },
            steps: this.workflowProgress,
            results,
            dataFlow: this.analyzeDataFlow(results),
            recommendations: this.generateRecommendations(results),
            generatedAt: new Date().toISOString()
        };

        // 保存報告
        const reportPath = path.join(
            this.logsDir,
            'workflows',
            `${workflowName}_${Date.now()}.json`
        );
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

        console.log(`📊 工作流程報告已保存: ${reportPath}`);
        return report;
    }

    /**
     * 分析數據流
     */
    analyzeDataFlow(results) {
        const dataFlow = {
            stages: []
        };

        // 分析每個階段的數據處理情況
        Object.entries(results).forEach(([stage, result]) => {
            const stageInfo = {
                stage,
                status: 'completed'
            };

            if (Array.isArray(result)) {
                stageInfo.itemsProcessed = result.length;
            } else if (result && typeof result === 'object') {
                if (result.length !== undefined) {
                    stageInfo.itemsProcessed = result.length;
                } else if (result.recordsProcessed) {
                    stageInfo.itemsProcessed = result.recordsProcessed;
                } else if (result.filesProcessed) {
                    stageInfo.filesProcessed = result.filesProcessed;
                }
            }

            dataFlow.stages.push(stageInfo);
        });

        return dataFlow;
    }

    /**
     * 生成建議
     */
    generateRecommendations(results) {
        const recommendations = [];

        // 基於結果分析生成建議
        if (this.statistics.failedTasks > 0) {
            recommendations.push({
                type: 'error_handling',
                priority: 'high',
                message: '部分步驟執行失敗，建議檢查錯誤日誌並優化配置'
            });
        }

        if (this.statistics.completedTasks === this.statistics.totalTasks) {
            recommendations.push({
                type: 'success',
                priority: 'info',
                message: '工作流程執行成功，可以開始下一輪數據處理或進行結果分析'
            });
        }

        const duration = this.statistics.endTime - this.statistics.startTime;
        if (duration > 300000) { // 超過5分鐘
            recommendations.push({
                type: 'performance',
                priority: 'medium',
                message: '執行時間較長，建議優化並發處理或調整批次大小'
            });
        }

        return recommendations;
    }

    /**
     * 獲取Hub狀態
     */
    getStatus() {
        return {
            id: this.id,
            name: this.name,
            status: this.status,
            version: this.version,
            currentWorkflow: this.currentWorkflow,
            agents: Object.fromEntries(
                Object.entries(this.agents).map(([name, agent]) => [
                    name,
                    agent ? agent.getStatus() : { status: 'not_initialized' }
                ])
            ),
            statistics: this.statistics,
            availableWorkflows: Object.keys(this.workflows),
            errors: this.errors.length
        };
    }

    /**
     * 重啟特定Agent
     */
    async restartAgent(agentName) {
        const agent = this.agents[agentName];
        if (!agent) {
            throw new Error(`Agent ${agentName} 不存在`);
        }

        console.log(`🔄 重啟Agent: ${agentName}`);

        try {
            // 停止Agent
            if (agent.stop) {
                await agent.stop();
            }

            // 重新初始化
            await agent.initialize();

            console.log(`✅ Agent ${agentName} 重啟成功`);
        } catch (error) {
            console.error(`❌ Agent ${agentName} 重啟失敗:`, error.message);
            throw error;
        }
    }

    /**
     * 停止Hub和所有Agent
     */
    async stop() {
        console.log('⏹️ 停止Agent Hub...');
        this.status = 'stopping';

        // 停止所有Agent
        const stopPromises = Object.entries(this.agents).map(async ([name, agent]) => {
            if (agent && agent.stop) {
                try {
                    await agent.stop();
                    console.log(`✅ ${name} 已停止`);
                } catch (error) {
                    console.error(`❌ ${name} 停止失敗:`, error.message);
                }
            }
        });

        await Promise.all(stopPromises);

        this.status = 'stopped';
        console.log('✅ Agent Hub 已停止');
        this.emit('stopped');
    }

    /**
     * 創建自定義工作流程
     */
    createCustomWorkflow(name, steps, description = '') {
        // 驗證步驟
        const validSteps = Object.keys(this.agents);
        const invalidSteps = steps.filter(step => !validSteps.includes(step));

        if (invalidSteps.length > 0) {
            throw new Error(`無效的步驟: ${invalidSteps.join(', ')}`);
        }

        this.workflows[name] = steps;
        console.log(`✅ 創建自定義工作流程: ${name} (${steps.join(' → ')})`);

        return {
            name,
            steps,
            description,
            created: new Date().toISOString()
        };
    }
}

module.exports = AgentHub;

// 如果直接運行此文件
if (require.main === module) {
    const hub = new AgentHub();

    hub.on('initialized', async () => {
        console.log('🚀 開始測試工作流程...');

        try {
            // 執行處理現有數據的工作流程
            await hub.executeWorkflow('processExisting', {
                metadataExtractor: {
                    inputSources: ['museums'],
                    includeValidation: true
                },
                classification: {
                    classificationTypes: ['period', 'style', 'medium'],
                    generateReports: true
                },
                summarizationTranslation: {
                    targetLanguages: ['zh-TW', 'en'],
                    generateSummaries: true,
                    generateTranslations: true
                }
            });
        } catch (error) {
            console.error('❌ 工作流程測試失敗:', error.message);
        }

        await hub.stop();
        process.exit(0);
    });

    hub.on('error', (error) => {
        console.error('❌ Hub錯誤:', error);
        process.exit(1);
    });

    hub.on('workflowComplete', (result) => {
        console.log('🎉 工作流程完成事件:', result.workflow);
    });

    hub.initialize();
}