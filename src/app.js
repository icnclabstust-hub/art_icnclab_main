const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
require('dotenv').config();

// 導入資料庫和工具
const { dbManager } = require('./database/connection');
const { httpLoggerMiddleware, errorLoggerMiddleware } = require('./utils/logger');
const { createErrorHandlingMiddleware, createHealthCheckMiddleware, createErrorStatsMiddleware } = require('./api/middleware/errorHandlingMiddleware');
const artworkRoutes = require('./api/routes/artworkRoutes');
const artistRoutes = require('./api/routes/artistRoutes');
const collectionRoutes = require('./api/routes/collectionRoutes');
const searchRoutes = require('./api/routes/searchRoutes');
const n8nIntegrationRoutes = require('./api/routes/n8nIntegrationRoutes');
const duplicateDetectionRoutes = require('./api/routes/duplicateDetectionRoutes');
const mlRoutes = require('./api/routes/mlRoutes');
const { globalRateLimitMiddleware } = require('./api/middleware/rateLimiter');
const { timeoutMiddleware, getTimeoutStats } = require('./api/middleware/timeoutMiddleware');
const { router: agentRoutes, cleanup: agentCleanup, setupWebSocketEvents } = require('./routes/agents');
const CronScheduler = require('./utils/cronScheduler');
const CrawlIntervalManager = require('./utils/crawlIntervalManager');
const SchedulerMonitor = require('./utils/schedulerMonitor');
const DataQualityMonitor = require('./utils/dataQualityMonitor');
const { cacheManager } = require('./utils/cacheManager');
const { cachePreloader } = require('./utils/cachePreloader');
const { cacheAnalytics } = require('./utils/cacheAnalytics');
const { memoryMonitor } = require('./utils/memoryMonitor');
const { objectPoolManager } = require('./utils/objectPoolManager');
const { gcOptimizer } = require('./utils/gcOptimizer');
const { memoryPressureManager } = require('./utils/memoryPressureManager');

const app = express();
const PORT = process.env.API_PORT || 3000;

// 初始化 Cron 排程系統
const cronScheduler = new CronScheduler({
  timezone: 'Asia/Taipei',
  enablePersistence: true,
  maxConcurrentCronJobs: 20,
  healthCheckInterval: 300000 // 5 minutes
});

// 初始化爬取間隔管理系統
const crawlIntervalManager = new CrawlIntervalManager({
  enablePersistence: true,
  performanceAnalysisInterval: 300000, // 5 minutes
  adaptiveAdjustmentEnabled: true,
  configPath: './config/crawl-intervals.json'
});

// 初始化排程監控系統
const schedulerMonitor = new SchedulerMonitor(cronScheduler, {
  monitoringInterval: 30000, // 30 seconds
  enableRealTimeAlerts: true,
  alertThresholds: {
    consecutiveFailures: 3,
    successRate: 0.8,
    avgExecutionTime: 300000, // 5 minutes
    memoryUsage: 500 * 1024 * 1024 // 500MB
  }
});

// 初始化資料品質監控系統
const dataQualityMonitor = new DataQualityMonitor({
  evaluationInterval: 300000, // 5分鐘評估一次
  alertThresholds: {
    overall: 0.7,
    completeness: 0.8,
    accuracy: 0.85,
    consistency: 0.9,
    freshness: 0.75,
    validity: 0.8
  },
  sampleSize: 1000,
  retentionDays: 30,
  enableAlerts: true
});

// 動態載入路由
const schedulerRoutes = require('./api/routes/schedulerRoutes')(cronScheduler);
const crawlIntervalRoutes = require('./api/routes/crawlIntervalRoutes')(crawlIntervalManager);
const schedulerMonitorRoutes = require('./api/routes/schedulerMonitorRoutes')(schedulerMonitor);
const dataQualityRoutes = require('./api/routes/dataQualityRoutes')(dataQualityMonitor);

// 中間件設定
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));
app.use(httpLoggerMiddleware);
app.use(globalRateLimitMiddleware); // 重新啟用優化後的速率限制
app.use(timeoutMiddleware.standard); // 添加標準超時處理
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// 靜態文件服務（用於監控儀表板）
app.use(express.static('public'));

// 健康檢查端點
app.get('/health', async (req, res) => {
  try {
    if (res.headersSent) {
      return;
    }
    const dbStatus = await dbManager.checkConnections();
    res.status(200).json({
      status: 'healthy',
      message: '藝術史資料庫系統運行正常',
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
      environment: process.env.NODE_ENV || 'development',
      database: dbStatus
    });
  } catch (error) {
    if (!res.headersSent) {
      res.status(503).json({
        status: 'unhealthy',
        message: '系統健康檢查失敗',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }
});

// 根路徑
app.get('/', (req, res) => {
  res.json({
    name: '藝術史資料庫爬蟲系統',
    description: '專注於RAG集成的藝術史資料庫爬蟲系統',
    version: '1.0.0',
    endpoints: {
      health: '/health',
      api: '/api/v1',
      docs: '/api/docs'
    },
    agents: {
      webCrawler: 'WebCrawlerAgent',
      metadataExtractor: 'MetadataExtractorAgent',
      classification: 'ClassificationAgent',
      summarizationTranslation: 'SummarizationTranslationAgent'
    }
  });
});

// API v1 路由
app.use('/api/v1/artworks', artworkRoutes);
app.use('/api/v1/artists', artistRoutes);
app.use('/api/v1/collections', collectionRoutes);
app.use('/api/v1/search', searchRoutes);
app.use('/api/v1/agents', agentRoutes);
app.use('/api/v1/n8n', n8nIntegrationRoutes);
app.use('/api/v1/duplicate-detection', duplicateDetectionRoutes);
app.use('/api/v1/scheduler', schedulerRoutes);
app.use('/api/v1/crawl-intervals', crawlIntervalRoutes);
app.use('/api/v1/scheduler-monitor', schedulerMonitorRoutes);
app.use('/api/v1/data-quality', dataQualityRoutes);
app.use('/api/v1/ml', mlRoutes);

// 監控儀表板路由
app.get('/dashboard', (req, res) => {
  res.sendFile('dashboard.html', { root: './public' });
});

// 資料品質儀表板路由
app.get('/data-quality', (req, res) => {
  res.sendFile('data-quality-dashboard.html', { root: './public' });
});

// 重複檢測儀表板路由
app.get('/duplicate-detection', (req, res) => {
  res.sendFile('duplicate-detection-dashboard.html', { root: './public' });
});

// 錯誤處理監控端點
app.get('/api/v1/health', createHealthCheckMiddleware());
app.get('/api/v1/error-stats', createErrorStatsMiddleware());

// 快取管理端點
app.get('/api/v1/cache/stats', async (req, res) => {
  try {
    const stats = cacheManager.getStats();
    const healthCheck = await cacheManager.healthCheck();
    const analyticsReport = cacheAnalytics.getAnalyticsReport();
    const preloaderStats = cachePreloader.getStats();

    res.json({
      success: true,
      data: {
        stats,
        health: healthCheck,
        analytics: analyticsReport,
        preloader: preloaderStats
      }
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to get cache stats',
      error: error.message
    });
  }
});

app.post('/api/v1/cache/clear/:category?', async (req, res) => {
  try {
    const { category } = req.params;

    if (category) {
      await cacheManager.clearCategory(category);
      res.json({
        success: true,
        message: `Cache category '${category}' cleared successfully`
      });
    } else {
      // 清空所有快取類別
      const categories = ['artwork', 'artist', 'search', 'collection', 'metadata', 'user_data'];
      await Promise.all(categories.map(cat => cacheManager.clearCategory(cat)));

      res.json({
        success: true,
        message: 'All cache categories cleared successfully'
      });
    }
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to clear cache',
      error: error.message
    });
  }
});

// 快取預載端點
app.post('/api/v1/cache/preload', async (req, res) => {
  try {
    await cachePreloader.startPreloading();
    res.json({
      success: true,
      message: 'Cache preloading started successfully'
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to start cache preloading',
      error: error.message
    });
  }
});

// 快取分析端點
app.get('/api/v1/cache/analytics', (req, res) => {
  try {
    const report = cacheAnalytics.getAnalyticsReport();
    res.json({
      success: true,
      data: report
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to get cache analytics',
      error: error.message
    });
  }
});

// 重置快取分析
app.post('/api/v1/cache/analytics/reset', (req, res) => {
  try {
    cacheAnalytics.resetAnalytics();
    res.json({
      success: true,
      message: 'Cache analytics reset successfully'
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to reset cache analytics',
      error: error.message
    });
  }
});

// 記憶體監控端點
app.get('/api/v1/memory/stats', (req, res) => {
  try {
    const memoryReport = memoryMonitor.getMemoryReport();
    const poolStats = objectPoolManager.getStats();
    const gcReport = gcOptimizer.getGCReport();
    const pressureReport = memoryPressureManager.getPressureReport();

    res.json({
      success: true,
      data: {
        memory: memoryReport,
        pools: poolStats,
        gc: gcReport,
        pressure: pressureReport
      }
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to get memory stats',
      error: error.message
    });
  }
});

// 強制垃圾回收
app.post('/api/v1/memory/gc/:type?', (req, res) => {
  try {
    const gcType = req.params.type || 'major';
    const result = gcOptimizer.forceGC(gcType);

    if (result) {
      res.json({
        success: true,
        message: `${gcType.toUpperCase()} GC executed successfully`,
        data: {
          duration: `${result.duration}ms`,
          memoryFreed: `${Math.round(result.memoryFreed / 1024 / 1024)}MB`,
          efficiency: `${result.efficiency}%`
        }
      });
    } else {
      res.status(503).json({
        success: false,
        message: 'GC not available, start Node.js with --expose-gc flag'
      });
    }
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to execute GC',
      error: error.message
    });
  }
});

// 物件池統計
app.get('/api/v1/memory/pools', (req, res) => {
  try {
    const stats = objectPoolManager.getStats();
    res.json({
      success: true,
      data: stats
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to get pool stats',
      error: error.message
    });
  }
});

// 清理物件池
app.post('/api/v1/memory/pools/cleanup', (req, res) => {
  try {
    objectPoolManager.cleanup();
    res.json({
      success: true,
      message: 'Object pools cleaned up successfully'
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to cleanup object pools',
      error: error.message
    });
  }
});

// 緊急記憶體動作
app.post('/api/v1/memory/emergency/:action', async (req, res) => {
  try {
    const action = req.params.action;
    const result = await memoryPressureManager.triggerEmergencyAction(action);

    res.json({
      success: true,
      message: `Emergency action '${action}' executed`,
      data: result
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: 'Failed to execute emergency action',
      error: error.message
    });
  }
});

app.get('/api/v1', (req, res) => {
  res.json({
    message: 'Art History Database API v1',
    version: '1.0.0',
    endpoints: {
      artworks: '/api/v1/artworks',
      artists: '/api/v1/artists',
      collections: '/api/v1/collections',
      search: '/api/v1/search',
      agents: '/api/v1/agents',
      n8n: '/api/v1/n8n',
      duplicateDetection: '/api/v1/duplicate-detection',
      scheduler: '/api/v1/scheduler',
      crawlIntervals: '/api/v1/crawl-intervals',
      schedulerMonitor: '/api/v1/scheduler-monitor',
      dataQuality: '/api/v1/data-quality',
      ml: '/api/v1/ml',
      health: '/api/v1/health',
      status: '/api/v1/status',
      timeouts: '/api/v1/timeouts',
      errorStats: '/api/v1/error-stats',
      cacheStats: '/api/v1/cache/stats',
      clearCache: '/api/v1/cache/clear',
      cachePreload: '/api/v1/cache/preload',
      cacheAnalytics: '/api/v1/cache/analytics',
      memoryStats: '/api/v1/memory/stats',
      memoryGC: '/api/v1/memory/gc',
      memoryPools: '/api/v1/memory/pools',
      memoryEmergency: '/api/v1/memory/emergency',
      dashboard: '/dashboard',
      dataQualityDashboard: '/data-quality',
      duplicateDetectionDashboard: '/duplicate-detection'
    },
    documentation: 'https://docs.your-domain.com/api/v1'
  });
});

// 超時統計端點
app.get('/api/v1/timeouts', getTimeoutStats);

// 環境檢查端點
app.get('/api/v1/status', async (req, res) => {
  try {
    if (res.headersSent) {
      return;
    }
    const dbStatus = await dbManager.checkConnections();
    const status = {
      server: 'running',
      timestamp: new Date().toISOString(),
      database: dbStatus,
      agents: {
        webCrawler: 'available',
        metadataExtractor: 'available',
        classification: 'available',
        summarizationTranslation: 'available'
      }
    };

    res.json(status);
  } catch (error) {
    if (!res.headersSent) {
      res.status(500).json({
        server: 'error',
        message: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }
});

// 錯誤處理中間件
app.use(errorLoggerMiddleware);
app.use(createErrorHandlingMiddleware({
  enableRetry: true,
  enableCircuitBreaker: true,
  logErrors: true,
  exposeStackTrace: process.env.NODE_ENV === 'development'
}));

// 404 處理
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Route ${req.originalUrl} not found`,
    availableRoutes: ['/', '/health', '/api/v1', '/api/v1/status']
  });
});

// 啟動服務器
async function startServer() {
  try {
    // 初始化資料庫連接
    console.log('🔗 初始化資料庫連接...');
    await dbManager.connectAll();

    // 初始化快取管理器
    console.log('💾 初始化快取管理器...');
    await cacheManager.init();

    // 初始化快取分析系統
    console.log('📊 初始化快取分析系統...');
    cacheAnalytics.startMonitoring();

    // 註冊並啟動快取預載
    console.log('🔄 設置快取預載系統...');
    cachePreloader.registerCommonTasks();
    await cachePreloader.startPreloading();
    cachePreloader.startPeriodicPreloading();

    // 初始化記憶體監控系統
    console.log('🔍 初始化記憶體監控系統...');
    memoryMonitor.startMonitoring();

    // 初始化物件池管理器
    console.log('📦 初始化物件池管理器...');
    objectPoolManager.initializeCommonPools();
    objectPoolManager.initializeBufferPools();
    objectPoolManager.startMaintenance();

    // 啟動GC最佳化
    console.log('🗜️ 啟動GC最佳化器...');
    gcOptimizer.startOptimization();

    // 啟動記憶體壓力管理
    console.log('📊 啟動記憶體壓力管理...');
    memoryPressureManager.startMonitoring();

    // 初始化 Cron 排程系統
    console.log('📅 初始化 Cron 排程系統...');
    await cronScheduler.initialize();

    // 初始化爬取間隔管理系統
    console.log('⏱️ 初始化爬取間隔管理系統...');
    await crawlIntervalManager.initialize();

    // 初始化排程監控系統
    console.log('📊 初始化排程監控系統...');
    await schedulerMonitor.startMonitoring();

    // 初始化資料品質監控系統
    console.log('📈 初始化資料品質監控系統...');
    await dataQualityMonitor.startMonitoring();

    // 啟動HTTP服務器
    app.listen(PORT, () => {
      console.log(`🚀 藝術史資料庫系統啟動成功!`);
      console.log(`📍 服務地址: http://localhost:${PORT}`);
      console.log(`🏥 健康檢查: http://localhost:${PORT}/health`);
      console.log(`📚 API文檔: http://localhost:${PORT}/api/v1`);
      console.log(`🎨 藝術作品API: http://localhost:${PORT}/api/v1/artworks`);
      console.log(`📊 監控儀表板: http://localhost:${PORT}/dashboard`);
      console.log(`📈 品質監控: http://localhost:${PORT}/data-quality`);
      console.log(`🌍 環境: ${process.env.NODE_ENV || 'development'}`);
      console.log(`⏰ 啟動時間: ${new Date().toLocaleString()}`);
    });
  } catch (error) {
    console.error('❌ 服務器啟動失敗:', error);
    process.exit(1);
  }
}

startServer();

// 優雅關機
process.on('SIGTERM', async () => {
  console.log('👋 接收到SIGTERM信號，正在優雅關機...');
  await dataQualityMonitor.stopMonitoring();
  await schedulerMonitor.stopMonitoring();
  await cronScheduler.shutdown();
  await crawlIntervalManager.shutdown();
  await agentCleanup();
  cacheAnalytics.stopMonitoring();
  memoryMonitor.stopMonitoring();
  gcOptimizer.stopOptimization();
  memoryPressureManager.stopMonitoring();
  objectPoolManager.shutdown();
  await cacheManager.shutdown();
  await dbManager.closeAll();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('👋 接收到SIGINT信號，正在優雅關機...');
  await dataQualityMonitor.stopMonitoring();
  await schedulerMonitor.stopMonitoring();
  await cronScheduler.shutdown();
  await crawlIntervalManager.shutdown();
  await agentCleanup();
  cacheAnalytics.stopMonitoring();
  memoryMonitor.stopMonitoring();
  gcOptimizer.stopOptimization();
  memoryPressureManager.stopMonitoring();
  objectPoolManager.shutdown();
  await cacheManager.shutdown();
  await dbManager.closeAll();
  process.exit(0);
});

module.exports = app;