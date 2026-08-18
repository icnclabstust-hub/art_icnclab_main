/**
 * 生產環境配置
 * 優化性能、安全和穩定性的生產配置
 */

module.exports = {
  // 應用程式配置
  app: {
    port: 8080,
    host: '127.0.0.1'
  },

  // 資料庫配置 - 生產環境
  database: {
    database: 'art_history_prod',
    poolSize: 20, // 增加連接池
    connectionTimeout: 30000,
    queryTimeout: 10000,
    logging: false, // 關閉SQL日誌
    ssl: true, // 啟用SSL
    retryAttempts: 3,
    retryDelay: 5000
  },

  // Agent配置 - 生產優化
  agents: {
    webCrawler: {
      maxConcurrentRequests: 10,
      requestDelay: 500,
      timeout: 60000,
      maxPages: 10000, // 生產環境可處理更多頁面
      respectRobotsTxt: true,
      enableCaching: true,
      sources: {
        met: {
          enabled: true,
          rateLimit: 500 // 更積極的爬取
        },
        louvre: {
          enabled: true,
          rateLimit: 1000
        },
        british: {
          enabled: true,
          rateLimit: 800
        }
      }
    },

    metadataExtractor: {
      batchSize: 100, // 大批次處理
      maxFileSize: 524288000, // 500MB
      enableImageMetadata: true,
      parallelProcessing: true,
      qualityChecks: {
        enableValidation: true,
        requireTitle: true,
        requireCreator: true,
        requireDate: true, // 生產環境嚴格要求
        minDescriptionLength: 20
      }
    },

    classification: {
      enableMLClassification: true, // 生產環境啟用ML
      confidenceThreshold: 0.8, // 提高信心閾值
      maxClassifications: 15,
      enableCaching: true
    },

    summarizationTranslation: {
      enableTranslation: true,
      targetLanguages: ['zh-TW', 'zh-CN', 'en', 'fr', 'de', 'it', 'es', 'ja'],
      apiServices: {
        openai: {
          enabled: true,
          model: 'gpt-4',
          maxTokens: 2000,
          temperature: 0.2 // 更保守的生成
        },
        deepl: {
          enabled: true,
          formality: 'more',
          preserveFormatting: true
        }
      }
    }
  },

  // 日誌配置 - 生產環境
  logging: {
    level: 'warn',
    enableConsole: false, // 關閉控制台輸出
    enableFile: true,
    maxFileSize: 52428800, // 50MB
    maxFiles: 10,
    compress: true,
    categories: {
      app: { level: 'info', enabled: true },
      agents: { level: 'warn', enabled: true },
      database: { level: 'error', enabled: true },
      api: { level: 'info', enabled: true },
      errors: { level: 'error', enabled: true }
    }
  },

  // 快取配置 - Redis生產配置
  cache: {
    enabled: true,
    type: 'redis',
    ttl: 7200, // 2小時
    maxSize: 1073741824, // 1GB
    redis: {
      host: 'redis-cluster',
      port: 6379,
      password: '${REDIS_PASSWORD}',
      database: 0,
      retryAttempts: 3,
      retryDelay: 1000,
      enableClustering: true,
      enableReadonly: true
    }
  },

  // 安全配置 - 生產環境加強
  security: {
    enableCors: true,
    corsOptions: {
      origin: ['https://arthistory.example.com', 'https://admin.arthistory.example.com'],
      methods: ['GET', 'POST', 'PUT', 'DELETE'],
      allowedHeaders: ['Content-Type', 'Authorization'],
      credentials: true
    },
    enableRateLimit: true,
    rateLimit: {
      windowMs: 900000, // 15分鐘
      maxRequests: 50, // 嚴格限制
      enableStoreIpInRedis: true,
      skipSuccessfulRequests: false
    },
    enableHelmet: true,
    helmetOptions: {
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"]
        }
      }
    },
    jwt: {
      secret: '${JWT_SECRET}',
      expiresIn: '2h', // 短期有效
      algorithm: 'RS256' // 更安全的算法
    },
    enableHttps: true,
    httpsOptions: {
      key: '${SSL_KEY_PATH}',
      cert: '${SSL_CERT_PATH}',
      ca: '${SSL_CA_PATH}'
    }
  },

  // API配置
  api: {
    enableSwagger: false, // 生產環境關閉API文檔
    timeout: 30000,
    maxRequestSize: 10485760, // 10MB限制
    enableCompression: true,
    compression: {
      level: 6,
      threshold: 1024
    },
    pagination: {
      defaultLimit: 20,
      maxLimit: 100
    }
  },

  // 錯誤處理配置 - 生產優化
  errorHandling: {
    enabled: true,
    maxRetries: 5,
    retryDelay: 2000,
    exponentialBackoff: true,
    maxRetryDelay: 30000,
    circuitBreakerThreshold: 10,
    circuitBreakerTimeout: 60000,
    logErrors: true,
    enableRecovery: true,
    enableAlerts: true,
    alertThreshold: 20
  },

  // 監控配置 - 生產監控
  monitoring: {
    enabled: true,
    metricsEnabled: true,
    healthCheck: {
      enabled: true,
      path: '/health',
      interval: 60000,
      timeout: 5000
    },
    prometheus: {
      enabled: true,
      path: '/metrics',
      collectDefaultMetrics: true,
      enableGCMetrics: true,
      enableProcessMetrics: true
    },
    alerts: {
      enabled: true,
      webhookUrl: '${ALERT_WEBHOOK_URL}',
      channels: ['slack', 'email'],
      thresholds: {
        errorRate: 0.05, // 5%
        responseTime: 2000, // 2秒
        memoryUsage: 0.9, // 90%
        cpuUsage: 0.8 // 80%
      }
    }
  },

  // 開發工具配置 - 生產環境關閉
  development: {
    enableHotReload: false,
    debugMode: false,
    mockData: false,
    seedDatabase: false,
    enableProfiler: false
  },

  // 性能優化配置
  performance: {
    enableClustering: true,
    clusterWorkers: 0, // 使用所有CPU核心
    enableGzip: true,
    enableETag: true,
    enableKeepAlive: true,
    keepAliveTimeout: 65000,
    headersTimeout: 66000,
    maxHeadersCount: 1000
  },

  // 備份配置
  backup: {
    enabled: true,
    schedule: '0 2 * * *', // 每天凌晨2點
    retention: 30, // 保留30天
    compression: true,
    destinations: [
      {
        type: 's3',
        bucket: '${BACKUP_S3_BUCKET}',
        region: '${AWS_REGION}',
        accessKeyId: '${AWS_ACCESS_KEY_ID}',
        secretAccessKey: '${AWS_SECRET_ACCESS_KEY}'
      }
    ]
  }
};