/**
 * Agent API路由
 * 提供Agent Hub和各個Agent的RESTful API接口
 */

const express = require('express');
const fs = require('fs/promises');
const path = require('path');
const router = express.Router();
const AgentHub = require('../agent-hub');

// 全局Agent Hub實例
let agentHub = null;

// 初始化Agent Hub（延遲初始化）
async function initializeAgentHub() {
    if (!agentHub) {
        agentHub = new AgentHub();
        await agentHub.initialize();
    }
    return agentHub;
}

/**
 * @route GET /api/agents/status
 * @desc 獲取Agent Hub和所有Agent的狀態
 * @access Public
 */
router.get('/status', async (req, res) => {
    try {
        const hub = await initializeAgentHub();
        const status = hub.getStatus();

        res.json({
            success: true,
            data: status,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route GET /api/agents/workflows
 * @desc 獲取可用的工作流程列表
 * @access Public
 */
router.get('/workflows', async (req, res) => {
    try {
        const hub = await initializeAgentHub();
        const status = hub.getStatus();

        res.json({
            success: true,
            data: {
                availableWorkflows: status.availableWorkflows,
                descriptions: {
                    fullPipeline: '完整的數據處理管線：爬取 → 元數據提取 → 分類 → 摘要翻譯',
                    processExisting: '處理現有數據：元數據提取 → 分類 → 摘要翻譯',
                    crawlOnly: '僅爬取和基本處理：爬取 → 元數據提取'
                }
            },
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route POST /api/agents/workflows/:workflowName/execute
 * @desc 執行指定的工作流程
 * @access Public
 */
router.post('/workflows/:workflowName/execute', async (req, res) => {
    try {
        const { workflowName } = req.params;
        const config = req.body || {};

        console.log(`🚀 API請求執行工作流程: ${workflowName}`);

        const hub = await initializeAgentHub();

        // 非同步執行工作流程
        const executionPromise = hub.executeWorkflow(workflowName, config);

        // 立即返回執行中狀態
        res.json({
            success: true,
            data: {
                workflow: workflowName,
                status: 'executing',
                message: '工作流程已開始執行',
                estimatedDuration: getEstimatedDuration(workflowName)
            },
            timestamp: new Date().toISOString()
        });

        // 在背景執行工作流程
        executionPromise.catch(error => {
            console.error(`❌ 工作流程 ${workflowName} 執行失敗:`, error.message);
        });

    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route GET /api/agents/:agentName/status
 * @desc 獲取特定Agent的狀態
 * @access Public
 */
router.get('/:agentName/status', async (req, res) => {
    try {
        const { agentName } = req.params;
        const hub = await initializeAgentHub();
        const hubStatus = hub.getStatus();

        const agentStatus = hubStatus.agents[agentName];
        if (!agentStatus) {
            return res.status(404).json({
                success: false,
                error: `Agent ${agentName} 不存在`,
                availableAgents: Object.keys(hubStatus.agents),
                timestamp: new Date().toISOString()
            });
        }

        res.json({
            success: true,
            data: agentStatus,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route POST /api/agents/:agentName/restart
 * @desc 重啟特定的Agent
 * @access Public
 */
router.post('/:agentName/restart', async (req, res) => {
    try {
        const { agentName } = req.params;
        const hub = await initializeAgentHub();

        console.log(`🔄 API請求重啟Agent: ${agentName}`);

        await hub.restartAgent(agentName);

        res.json({
            success: true,
            data: {
                agent: agentName,
                status: 'restarted',
                message: `Agent ${agentName} 重啟成功`
            },
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route POST /api/agents/workflows/custom
 * @desc 創建自定義工作流程
 * @access Public
 */
router.post('/workflows/custom', async (req, res) => {
    try {
        const { name, steps, description } = req.body;

        if (!name || !steps || !Array.isArray(steps)) {
            return res.status(400).json({
                success: false,
                error: '缺少必需參數: name, steps (array)',
                timestamp: new Date().toISOString()
            });
        }

        const hub = await initializeAgentHub();
        const workflow = hub.createCustomWorkflow(name, steps, description);

        res.json({
            success: true,
            data: workflow,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(400).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route GET /api/agents/data/flow
 * @desc 獲取數據處理流程狀態
 * @access Public
 */
router.get('/data/flow', async (req, res) => {
    try {
        const dataFlowStatus = await getDataFlowStatus();

        res.json({
            success: true,
            data: dataFlowStatus,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * @route GET /api/agents/statistics
 * @desc 獲取系統統計信息
 * @access Public
 */
router.get('/statistics', async (req, res) => {
    try {
        const statistics = await getSystemStatistics();

        res.json({
            success: true,
            data: statistics,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

/**
 * WebSocket事件處理（如果需要實時更新）
 */
function setupWebSocketEvents(io) {
    if (!agentHub) return;

    // 監聽工作流程完成事件
    agentHub.on('workflowComplete', (result) => {
        io.emit('workflow:complete', result);
    });

    // 監聽工作流程錯誤事件
    agentHub.on('workflowError', (error) => {
        io.emit('workflow:error', error);
    });

    // 監聽步驟完成事件
    agentHub.on('stepComplete', (result) => {
        io.emit('step:complete', result);
    });
}

// 輔助函數：估算工作流程執行時間
function getEstimatedDuration(workflowName) {
    const estimations = {
        fullPipeline: '15-30分鐘',
        processExisting: '10-20分鐘',
        crawlOnly: '5-15分鐘'
    };

    return estimations[workflowName] || '未知';
}

// 輔助函數：獲取數據流程狀態
async function getDataFlowStatus() {
    const dataDir = process.env.DATA_RAW_DIR || './data';
    const processedDir = process.env.DATA_PROCESSED_DIR || './data/processed';

    try {
        const stages = {
            raw: await getDirectoryStats(path.join(dataDir, 'raw')),
            processed: await getDirectoryStats(path.join(processedDir, 'metadata')),
            classified: await getDirectoryStats(path.join(processedDir, 'classified')),
            final: await getDirectoryStats(path.join(processedDir, 'final'))
        };

        return {
            stages,
            pipeline: {
                stage1: { name: 'Raw Data', files: stages.raw.fileCount },
                stage2: { name: 'Metadata Extracted', files: stages.processed.fileCount },
                stage3: { name: 'Classified', files: stages.classified.fileCount },
                stage4: { name: 'Final Output', files: stages.final.fileCount }
            }
        };
    } catch (error) {
        return {
            error: error.message,
            stages: {}
        };
    }
}

// 輔助函數：獲取目錄統計
async function getDirectoryStats(dirPath) {
    try {
        const files = await fs.readdir(dirPath);
        const jsonFiles = files.filter(f => f.endsWith('.json'));

        let totalSize = 0;
        for (const file of files) {
            try {
                const stat = await fs.stat(path.join(dirPath, file));
                totalSize += stat.size;
            } catch (e) {
                // 忽略單個文件錯誤
            }
        }

        return {
            fileCount: jsonFiles.length,
            totalFiles: files.length,
            totalSize: Math.round(totalSize / 1024) // KB
        };
    } catch (error) {
        return {
            fileCount: 0,
            totalFiles: 0,
            totalSize: 0,
            error: error.message
        };
    }
}

// 輔助函數：獲取系統統計
async function getSystemStatistics() {
    try {
        const hub = agentHub;
        if (!hub) {
            return { error: 'Agent Hub 未初始化' };
        }

        const status = hub.getStatus();
        const dataFlow = await getDataFlowStatus();

        return {
            hub: {
                status: status.status,
                currentWorkflow: status.currentWorkflow,
                errors: status.errors
            },
            agents: Object.fromEntries(
                Object.entries(status.agents).map(([name, agent]) => [
                    name,
                    {
                        status: agent.status,
                        errors: agent.statistics?.errors || 0,
                        completedTasks: agent.statistics?.completedTasks || 0
                    }
                ])
            ),
            dataFlow: dataFlow,
            system: {
                uptime: process.uptime(),
                memory: process.memoryUsage(),
                version: process.version
            }
        };
    } catch (error) {
        return { error: error.message };
    }
}

// 清理函數：關閉Agent Hub
async function cleanup() {
    if (agentHub) {
        console.log('🧹 清理Agent Hub...');
        try {
            await agentHub.stop();
        } catch (error) {
            console.error('❌ Agent Hub清理失敗:', error.message);
        }
    }
}

// 導出路由和輔助函數
module.exports = {
    router,
    setupWebSocketEvents,
    cleanup,
    initializeAgentHub
};