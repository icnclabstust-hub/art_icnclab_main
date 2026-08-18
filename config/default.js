/**
 * 預設配置 - 所有環境的基礎配置
 */

module.exports = {
  // 應用程式基本配置
  app: {
    name: '藝術史資料庫',
    version: '1.0.0',
    description: 'AI-powered Art History Database with RAG integration',
    port: 3000,
    host: 'localhost',
    timezone: 'Asia/Taipei',
    language: 'zh-TW'
  },

  // 資料庫配置
  database: {
    type: 'postgresql',
    host: 'localhost',
    port: 5432,
    database: 'art_history_db',
    username: 'postgres',
    password: 'password',
    poolSize: 10,
    connectionTimeout: 10000,
    queryTimeout: 5000,
    logging: false,
    ssl: false
  },

  // Web爬蟲代理配置
  agents: {
    webCrawler: {
      userAgent: 'Art History Database Crawler 1.0',
      maxConcurrentRequests: 5,
      requestDelay: 1000,
      retryAttempts: 3,
      timeout: 30000,
      respectRobotsTxt: true,
      maxDepth: 3,
      maxPages: 1000,
      sources: {
        met: {
          name: '大都會藝術博物館',
          baseUrl: 'https://collectionapi.metmuseum.org/public/collection/v1',
          rateLimit: 1000,
          enabled: true
        },
        louvre: {
          name: '羅浮宮',
          baseUrl: 'https://collections.louvre.fr',
          rateLimit: 2000,
          enabled: false
        },
        british: {
          name: '大英博物館',
          baseUrl: 'https://www.britishmuseum.org',
          rateLimit: 1500,
          enabled: false
        }
      }
    },

    metadataExtractor: {
      confidenceThreshold: 0.85,
      dublinCoreValidation: true,
      batchSize: 50,
      maxFileSize: 104857600, // 100MB
      outputFormat: 'json',
      enableImageMetadata: true,
      languages: ['en', 'zh-TW', 'zh-CN', 'fr', 'de', 'it', 'es', 'ja'],
      qualityChecks: {
        enableValidation: true,
        requireTitle: true,
        requireCreator: true,
        requireDate: false,
        minDescriptionLength: 10
      }
    },

    classification: {
      classificationTypes: ['period', 'style', 'medium', 'subject', 'region'],
      confidenceThreshold: 0.7,
      maxClassifications: 10,
      enableMLClassification: false,
      taxonomies: {
        period: ['古代', '中世紀', '文藝復興', '巴洛克', '新古典主義', '浪漫主義', '現代', '當代'],
        style: ['寫實主義', '印象派', '立體主義', '超現實主義', '抽象表現主義', '極簡主義'],
        medium: ['油畫', '水彩', '雕塑', '版畫', '攝影', '數位藝術', '裝置藝術'],
        subject: ['肖像', '風景', '靜物', '宗教', '神話', '歷史', '日常生活'],
        region: ['歐洲', '亞洲', '美洲', '非洲', '大洋洲']
      }
    },

    summarizationTranslation: {
      defaultLanguage: 'en',
      targetLanguages: ['zh-TW', 'zh-CN', 'en', 'fr', 'de', 'it', 'es', 'ja'],
      enableSummarization: true,
      enableTranslation: true,
      summaryLength: {
        short: 100,
        medium: 300,
        long: 500
      },
      apiServices: {
        openai: {
          enabled: false,
          model: 'gpt-3.5-turbo',
          maxTokens: 1000,
          temperature: 0.3
        },
        deepl: {
          enabled: false,
          formality: 'default',
          preserveFormatting: true
        },
        google: {
          enabled: false,
          model: 'nmt'
        }
      }
    }
  },

  // 資料路徑配置
  paths: {
    data: './data',
    raw: './data/raw',
    processed: './data/processed',
    output: './data/output',
    temp: './temp',
    logs: './logs',
    cache: './cache',
    backups: './backups',
    uploads: './uploads',
    static: './public'
  },

  // 日誌配置
  logging: {
    level: 'info',
    format: 'combined',
    enableFile: true,
    enableConsole: true,
    maxFileSize: 10485760, // 10MB
    maxFiles: 5,
    dateFormat: 'YYYY-MM-DD HH:mm:ss',
    categories: {
      app: { level: 'info', enabled: true },
      agents: { level: 'debug', enabled: true },
      database: { level: 'warn', enabled: true },
      api: { level: 'info', enabled: true },
      errors: { level: 'error', enabled: true }
    }
  },

  // 快取配置
  cache: {
    enabled: true,
    type: 'memory', // memory, redis, file
    ttl: 3600, // 1 hour
    maxSize: 104857600, // 100MB
    prefix: 'art_history_',
    redis: {
      host: 'localhost',
      port: 6379,
      password: null,
      database: 0
    }
  },

  // 安全配置
  security: {
    enableCors: true,
    corsOptions: {
      origin: ['http://localhost:3000', 'http://localhost:8080'],
      methods: ['GET', 'POST', 'PUT', 'DELETE'],
      allowedHeaders: ['Content-Type', 'Authorization'],
      credentials: true
    },
    enableRateLimit: true,
    rateLimit: {
      windowMs: 900000, // 15 minutes
      maxRequests: 100,
      message: 'Too many requests, please try again later'
    },
    enableHelmet: true,
    jwt: {
      secret: process.env.JWT_SECRET || 'art-history-database-super-secret-jwt-key-2024-ml-integration',
      expiresIn: process.env.JWT_EXPIRES_IN || '24h',
      algorithm: 'HS256'
    }
  },

  // API配置
  api: {
    prefix: '/api',
    version: 'v1',
    timeout: 30000,
    maxRequestSize: 52428800, // 50MB
    enableSwagger: true,
    swaggerPath: '/docs',
    pagination: {
      defaultLimit: 20,
      maxLimit: 100
    }
  },

  // 錯誤處理配置
  errorHandling: {
    enabled: true,
    maxRetries: 3,
    retryDelay: 1000,
    exponentialBackoff: true,
    circuitBreakerThreshold: 5,
    circuitBreakerTimeout: 30000,
    logErrors: true,
    enableRecovery: true
  },

  // 監控配置
  monitoring: {
    enabled: true,
    metricsEnabled: true,
    healthCheck: {
      enabled: true,
      path: '/health',
      interval: 30000
    },
    prometheus: {
      enabled: false,
      path: '/metrics',
      collectDefaultMetrics: true
    }
  },

  // 開發工具配置
  development: {
    enableHotReload: false,
    debugMode: false,
    mockData: false,
    seedDatabase: false,
    enableProfiler: false
  }
};