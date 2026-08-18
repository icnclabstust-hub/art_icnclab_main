const express = require('express');
const router = express.Router();

// N8N API密鑰驗證中間件
const N8N_API_KEY = 'CHANGE_ME_N8N_API_KEY';

const validateN8NKey = (req, res, next) => {
  const apiKey = req.headers['x-n8n-key'];
  if (!apiKey || apiKey !== N8N_API_KEY) {
    return res.status(401).json({
      success: false,
      error: 'Unauthorized',
      message: 'Invalid or missing N8N API key'
    });
  }
  next();
};

// Mock Agent 執行函數 (基本功能版)
const executeAgent = async (agentType, parameters) => {
  // 模擬agent處理延遲
  await new Promise(resolve => setTimeout(resolve, 100));
  
  switch (agentType.toLowerCase()) {
    case 'webcrawler':
      return {
        status: 'completed',
        results: [
          {
            source: parameters.sources?.[0] || 'default',
            title: 'Mock Art Data',
            url: 'https://example.com/art',
            data: { description: 'Mock crawled art data' }
          }
        ],
        totalFound: parameters.maxResults || 10
      };

    case 'metadataextractor':
      return {
        status: 'completed',
        metadata: {
          title: parameters.inputData?.title || 'Unknown Title',
          format: parameters.outputFormat || 'dublin-core',
          extracted: new Date().toISOString()
        }
      };

    case 'classification':
      return {
        status: 'completed',
        classifications: {
          category: 'painting',
          style: 'renaissance',
          confidence: 0.85
        }
      };

    case 'summarizationtranslation':
      return {
        status: 'completed',
        summary: 'Mock summary of art history content',
        translation: 'Mock translation result'
      };

    default:
      throw new Error(`Unknown agent type: ${agentType}`);
  }
};

// N8N健康檢查端點
router.get('/health', validateN8NKey, (req, res) => {
  res.json({
    status: 'healthy',
    message: 'N8N Integration API is operational',
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    agents: {
      webCrawler: 'available',
      metadataExtractor: 'available',
      classification: 'available',
      summarizationTranslation: 'available'
    }
  });
});

// N8N狀態檢查端點
router.get('/status', validateN8NKey, (req, res) => {
  res.json({
    integration: 'active',
    timestamp: new Date().toISOString(),
    apiKey: 'validated',
    agents: {
      webCrawler: { status: 'ready', lastUsed: null },
      metadataExtractor: { status: 'ready', lastUsed: null },
      classification: { status: 'ready', lastUsed: null },
      summarizationTranslation: { status: 'ready', lastUsed: null }
    },
    endpoints: {
      health: '/api/v1/n8n/health',
      status: '/api/v1/n8n/status',
      trigger: '/api/v1/n8n/webhook/trigger',
      batch: '/api/v1/n8n/batch/process'
    }
  });
});

// N8N Webhook觸發端點
router.post('/webhook/trigger', validateN8NKey, async (req, res) => {
  try {
    const { agentType, workflowId, executionId, parameters } = req.body;

    if (!agentType || !parameters) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'agentType and parameters are required'
      });
    }

    const startTime = Date.now();
    const result = await executeAgent(agentType, parameters);
    const executionTime = Date.now() - startTime;

    res.json({
      success: true,
      message: `${agentType} agent executed successfully`,
      data: result,
      metadata: {
        workflowId: workflowId || 'unknown',
        executionId: executionId || 'unknown',
        agentType,
        executionTime: `${executionTime}ms`,
        timestamp: new Date().toISOString(),
        parametersCount: Object.keys(parameters).length
      }
    });

  } catch (error) {
    console.error('N8N Webhook Trigger Error:', error);
    res.status(500).json({
      success: false,
      error: 'Agent Execution Failed',
      message: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// N8N批量處理端點
router.post('/batch/process', validateN8NKey, async (req, res) => {
  try {
    const { workflowId, executionId, tasks } = req.body;

    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'tasks array is required and cannot be empty'
      });
    }

    const results = [];
    const startTime = Date.now();

    for (const task of tasks) {
      const { id, agentType, parameters } = task;

      if (!agentType || !parameters) {
        results.push({
          taskId: id || 'unknown',
          success: false,
          error: 'Missing agentType or parameters',
          timestamp: new Date().toISOString()
        });
        continue;
      }

      try {
        const taskStartTime = Date.now();
        const taskResult = await executeAgent(agentType, parameters);
        const taskExecutionTime = Date.now() - taskStartTime;

        results.push({
          taskId: id || 'unknown',
          success: true,
          agentType,
          data: taskResult,
          executionTime: `${taskExecutionTime}ms`,
          timestamp: new Date().toISOString()
        });

      } catch (taskError) {
        results.push({
          taskId: id || 'unknown',
          success: false,
          agentType,
          error: taskError.message,
          timestamp: new Date().toISOString()
        });
      }
    }

    const totalExecutionTime = Date.now() - startTime;
    const successCount = results.filter(r => r.success).length;
    const failureCount = results.length - successCount;

    res.json({
      success: true,
      message: `Batch processing completed: ${successCount} successful, ${failureCount} failed`,
      data: {
        results,
        summary: {
          total: results.length,
          successful: successCount,
          failed: failureCount,
          totalExecutionTime: `${totalExecutionTime}ms`
        }
      },
      metadata: {
        workflowId: workflowId || 'unknown',
        executionId: executionId || 'unknown',
        timestamp: new Date().toISOString()
      }
    });

  } catch (error) {
    console.error('N8N Batch Process Error:', error);
    res.status(500).json({
      success: false,
      error: 'Batch Processing Failed',
      message: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// N8N工作流程統計端點
router.get('/stats', validateN8NKey, (req, res) => {
  res.json({
    success: true,
    message: 'N8N Integration Statistics',
    data: {
      totalExecutions: 0,
      agentUsage: {
        webCrawler: 0,
        metadataExtractor: 0,
        classification: 0,
        summarizationTranslation: 0
      },
      averageExecutionTime: '0ms',
      lastExecution: null,
      uptime: process.uptime()
    },
    timestamp: new Date().toISOString()
  });
});

module.exports = router;
