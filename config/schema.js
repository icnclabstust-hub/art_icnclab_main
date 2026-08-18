/**
 * 配置驗證模式
 * 定義所有配置項的類型、約束和驗證規則
 */

module.exports = {
  // 應用程式配置模式
  app: {
    properties: {
      name: {
        type: 'string',
        required: true,
        minLength: 1,
        maxLength: 100
      },
      version: {
        type: 'string',
        required: true,
        pattern: '^\\d+\\.\\d+\\.\\d+$'
      },
      port: {
        type: 'number',
        required: true,
        min: 1024,
        max: 65535
      },
      host: {
        type: 'string',
        required: true,
        pattern: '^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|localhost|0\\.0\\.0\\.0|[a-zA-Z0-9.-]+)$'
      },
      timezone: {
        type: 'string',
        required: false,
        pattern: '^[A-Z][a-z]+/[A-Z][a-z_]+$'
      },
      language: {
        type: 'enum',
        values: ['zh-TW', 'zh-CN', 'en', 'fr', 'de', 'it', 'es', 'ja'],
        required: false
      }
    }
  },

  // 資料庫配置模式
  database: {
    properties: {
      type: {
        type: 'enum',
        values: ['postgresql', 'mysql', 'sqlite', 'mongodb'],
        required: true
      },
      host: {
        type: 'string',
        required: true
      },
      port: {
        type: 'number',
        required: true,
        min: 1,
        max: 65535
      },
      database: {
        type: 'string',
        required: true,
        minLength: 1
      },
      username: {
        type: 'string',
        required: true,
        minLength: 1
      },
      password: {
        type: 'string',
        required: false
      },
      poolSize: {
        type: 'number',
        required: false,
        min: 1,
        max: 100
      },
      connectionTimeout: {
        type: 'number',
        required: false,
        min: 1000,
        max: 300000
      },
      queryTimeout: {
        type: 'number',
        required: false,
        min: 1000,
        max: 60000
      },
      logging: {
        type: 'boolean',
        required: false
      },
      ssl: {
        type: 'boolean',
        required: false
      }
    }
  },

  // Agent配置模式
  agents: {
    properties: {
      webCrawler: {
        properties: {
          userAgent: {
            type: 'string',
            required: true,
            minLength: 10
          },
          maxConcurrentRequests: {
            type: 'number',
            required: true,
            min: 1,
            max: 50
          },
          requestDelay: {
            type: 'number',
            required: true,
            min: 100,
            max: 10000
          },
          retryAttempts: {
            type: 'number',
            required: true,
            min: 0,
            max: 10
          },
          timeout: {
            type: 'number',
            required: true,
            min: 5000,
            max: 300000
          },
          respectRobotsTxt: {
            type: 'boolean',
            required: false
          },
          maxDepth: {
            type: 'number',
            required: false,
            min: 1,
            max: 10
          },
          maxPages: {
            type: 'number',
            required: false,
            min: 1,
            max: 100000
          }
        }
      },

      metadataExtractor: {
        properties: {
          confidenceThreshold: {
            type: 'number',
            required: true,
            min: 0.0,
            max: 1.0
          },
          dublinCoreValidation: {
            type: 'boolean',
            required: false
          },
          batchSize: {
            type: 'number',
            required: true,
            min: 1,
            max: 1000
          },
          maxFileSize: {
            type: 'number',
            required: true,
            min: 1024,
            max: 1073741824 // 1GB
          },
          outputFormat: {
            type: 'enum',
            values: ['json', 'xml', 'csv', 'yaml'],
            required: false
          },
          enableImageMetadata: {
            type: 'boolean',
            required: false
          },
          languages: {
            type: 'array',
            required: false
          }
        }
      },

      classification: {
        properties: {
          classificationTypes: {
            type: 'array',
            required: true
          },
          confidenceThreshold: {
            type: 'number',
            required: true,
            min: 0.0,
            max: 1.0
          },
          maxClassifications: {
            type: 'number',
            required: false,
            min: 1,
            max: 100
          },
          enableMLClassification: {
            type: 'boolean',
            required: false
          }
        }
      },

      summarizationTranslation: {
        properties: {
          defaultLanguage: {
            type: 'enum',
            values: ['zh-TW', 'zh-CN', 'en', 'fr', 'de', 'it', 'es', 'ja'],
            required: true
          },
          targetLanguages: {
            type: 'array',
            required: true
          },
          enableSummarization: {
            type: 'boolean',
            required: false
          },
          enableTranslation: {
            type: 'boolean',
            required: false
          }
        }
      }
    }
  },

  // 路徑配置模式
  paths: {
    properties: {
      data: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      raw: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      processed: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      output: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      temp: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      logs: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      cache: {
        type: 'path',
        required: true,
        pathType: 'directory'
      },
      backups: {
        type: 'path',
        required: false,
        pathType: 'directory'
      }
    }
  },

  // 日誌配置模式
  logging: {
    properties: {
      level: {
        type: 'enum',
        values: ['error', 'warn', 'info', 'debug', 'trace'],
        required: true
      },
      format: {
        type: 'enum',
        values: ['json', 'combined', 'common', 'dev', 'short', 'tiny'],
        required: false
      },
      enableFile: {
        type: 'boolean',
        required: false
      },
      enableConsole: {
        type: 'boolean',
        required: false
      },
      maxFileSize: {
        type: 'number',
        required: false,
        min: 1024,
        max: 104857600 // 100MB
      },
      maxFiles: {
        type: 'number',
        required: false,
        min: 1,
        max: 100
      }
    }
  },

  // 快取配置模式
  cache: {
    properties: {
      enabled: {
        type: 'boolean',
        required: true
      },
      type: {
        type: 'enum',
        values: ['memory', 'redis', 'file'],
        required: true
      },
      ttl: {
        type: 'number',
        required: true,
        min: 60,
        max: 86400 // 24小時
      },
      maxSize: {
        type: 'number',
        required: true,
        min: 1024,
        max: 1073741824 // 1GB
      },
      prefix: {
        type: 'string',
        required: false,
        pattern: '^[a-zA-Z0-9_-]+$'
      }
    }
  },

  // 安全配置模式
  security: {
    properties: {
      enableCors: {
        type: 'boolean',
        required: false
      },
      enableRateLimit: {
        type: 'boolean',
        required: false
      },
      enableHelmet: {
        type: 'boolean',
        required: false
      },
      rateLimit: {
        properties: {
          windowMs: {
            type: 'number',
            required: true,
            min: 60000, // 1分鐘
            max: 3600000 // 1小時
          },
          maxRequests: {
            type: 'number',
            required: true,
            min: 1,
            max: 10000
          }
        }
      },
      jwt: {
        properties: {
          secret: {
            type: 'string',
            required: true,
            minLength: 32
          },
          expiresIn: {
            type: 'string',
            required: true,
            pattern: '^\\d+[smhd]$'
          },
          algorithm: {
            type: 'enum',
            values: ['HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512'],
            required: false
          }
        }
      }
    }
  },

  // API配置模式
  api: {
    properties: {
      prefix: {
        type: 'string',
        required: true,
        pattern: '^/[a-zA-Z0-9_-]+$'
      },
      version: {
        type: 'string',
        required: true,
        pattern: '^v\\d+$'
      },
      timeout: {
        type: 'number',
        required: true,
        min: 1000,
        max: 300000
      },
      maxRequestSize: {
        type: 'number',
        required: true,
        min: 1024,
        max: 104857600 // 100MB
      },
      enableSwagger: {
        type: 'boolean',
        required: false
      }
    }
  },

  // 錯誤處理配置模式
  errorHandling: {
    properties: {
      enabled: {
        type: 'boolean',
        required: true
      },
      maxRetries: {
        type: 'number',
        required: true,
        min: 0,
        max: 10
      },
      retryDelay: {
        type: 'number',
        required: true,
        min: 100,
        max: 30000
      },
      exponentialBackoff: {
        type: 'boolean',
        required: false
      },
      circuitBreakerThreshold: {
        type: 'number',
        required: false,
        min: 1,
        max: 100
      },
      circuitBreakerTimeout: {
        type: 'number',
        required: false,
        min: 1000,
        max: 300000
      },
      logErrors: {
        type: 'boolean',
        required: false
      },
      enableRecovery: {
        type: 'boolean',
        required: false
      }
    }
  },

  // 監控配置模式
  monitoring: {
    properties: {
      enabled: {
        type: 'boolean',
        required: true
      },
      metricsEnabled: {
        type: 'boolean',
        required: false
      },
      healthCheck: {
        properties: {
          enabled: {
            type: 'boolean',
            required: true
          },
          path: {
            type: 'string',
            required: true,
            pattern: '^/[a-zA-Z0-9_-]+$'
          },
          interval: {
            type: 'number',
            required: true,
            min: 1000,
            max: 300000
          }
        }
      }
    }
  }
};