/**
 * 開發環境配置
 * 覆蓋預設配置以適應開發需求
 */

module.exports = {
  // 應用程式配置
  app: {
    port: 3000,
    host: '127.0.0.1' // 僅本機；需外部訪問時再放開
  },

  // 資料庫配置 - 開發環境
  database: {
    database: 'art_history_dev',
    logging: true, // 開啟SQL日誌
    poolSize: 5,
    connectionTimeout: 5000
  },

  // Agent配置 - 開發模式
  agents: {
    webCrawler: {
      maxConcurrentRequests: 2, // 降低並發數避免被封
      requestDelay: 2000, // 增加延遲
      timeout: 10000,
      maxPages: 10, // 限制頁面數量
      sources: {
        met: {
          enabled: true,
          rateLimit: 2000 // 更保守的速率限制
        },
        louvre: {
          enabled: false // 開發時關閉
        },
        british: {
          enabled: false // 開發時關閉
        }
      }
    },

    metadataExtractor: {
      batchSize: 10, // 小批次處理
      maxFileSize: 10485760, // 10MB限制
      qualityChecks: {
        requireDate: false, // 放寬要求
        minDescriptionLength: 5
      }
    },

    classification: {
      enableMLClassification: false, // 開發時關閉ML
      maxClassifications: 5
    },

    summarizationTranslation: {
      enableTranslation: false, // 開發時關閉翻譯
      apiServices: {
        openai: {
          enabled: false // 節省API費用
        },
        deepl: {
          enabled: false
        }
      }
    }
  },

  // 日誌配置 - 詳細日誌
  logging: {
    level: 'debug',
    enableConsole: true,
    enableFile: true,
    categories: {
      app: { level: 'debug', enabled: true },
      agents: { level: 'debug', enabled: true },
      database: { level: 'debug', enabled: true },
      api: { level: 'debug', enabled: true },
      errors: { level: 'error', enabled: true }
    }
  },

  // 快取配置 - 開發環境
  cache: {
    enabled: true,
    type: 'memory',
    ttl: 300, // 5分鐘快速過期
    maxSize: 10485760 // 10MB
  },

  // 安全配置 - 開發環境放寬
  security: {
    corsOptions: {
      origin: true, // 允許所有來源
      credentials: true
    },
    rateLimit: {
      windowMs: 60000, // 1分鐘
      maxRequests: 1000 // 高限制
    },
    jwt: {
      expiresIn: '7d' // 長期有效
    }
  },

  // API配置
  api: {
    enableSwagger: true,
    timeout: 10000,
    pagination: {
      defaultLimit: 10,
      maxLimit: 50
    }
  },

  // 錯誤處理配置 - 開發模式
  errorHandling: {
    maxRetries: 1, // 快速失敗
    retryDelay: 500,
    circuitBreakerThreshold: 3,
    logErrors: true,
    enableRecovery: true
  },

  // 監控配置
  monitoring: {
    enabled: true,
    healthCheck: {
      enabled: true,
      interval: 10000 // 10秒檢查
    }
  },

  // 開發工具配置
  development: {
    enableHotReload: true,
    debugMode: true,
    mockData: true,
    seedDatabase: true,
    enableProfiler: true
  }
};