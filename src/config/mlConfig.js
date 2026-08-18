const mlConfig = {
  // ML服務連接配置
  service: {
    url: process.env.ML_SERVICE_URL || 'http://cuda-ml-service:8080',
    timeout: parseInt(process.env.ML_SERVICE_TIMEOUT) || 300000, // 5分鐘
    retries: 3,
    retryDelay: 2000
  },

  // CUDA/GPU配置
  cuda: {
    enabled: process.env.CUDA_ENABLED === 'true',
    device_id: parseInt(process.env.CUDA_DEVICE_ID) || 0,
    memory_fraction: parseFloat(process.env.CUDA_MEMORY_FRACTION) || 0.8,
    mixed_precision: process.env.CUDA_MIXED_PRECISION === 'true'
  },

  // 模型配置
  models: {
    classification: {
      name: 'art-classification',
      version: 'v1.0',
      max_sequence_length: 512,
      num_labels: {
        period: 6,    // 古代、中世紀、文藝復興、巴洛克、現代、當代
        style: 20,    // 各種藝術風格
        region: 5,    // 歐洲、亞洲、美洲、非洲、大洋洲
        medium: 10    // 繪畫、雕塑、建築等
      },
      confidence_threshold: 0.7
    },

    embedding: {
      name: 'multilingual-bert',
      version: 'v1.0',
      embedding_dim: 768,
      max_sequence_length: 512,
      batch_size: 32
    },

    similarity: {
      name: 'art-similarity',
      version: 'v1.0',
      similarity_threshold: 0.75,
      top_k_default: 10,
      max_top_k: 100
    }
  },

  // 訓練配置
  training: {
    default_config: {
      epochs: 10,
      batch_size: 32,
      learning_rate: 2e-5,
      validation_split: 0.1,
      early_stopping: true,
      patience: 3,
      min_delta: 0.001
    },

    classification_config: {
      epochs: 15,
      batch_size: 16,
      learning_rate: 1e-5,
      warmup_steps: 500,
      weight_decay: 0.01,
      gradient_accumulation_steps: 2
    },

    embedding_config: {
      epochs: 20,
      batch_size: 64,
      learning_rate: 3e-5,
      negative_sampling_ratio: 5,
      margin: 0.3
    }
  },

  // 資料預處理配置
  preprocessing: {
    quality_threshold: 0.8,
    min_text_length: 50,
    max_text_length: 2048,

    text_cleaning: {
      remove_special_chars: true,
      preserve_chinese: true,
      normalize_unicode: true,
      lowercase: true
    },

    data_split: {
      train: 0.8,
      validation: 0.1,
      test: 0.1
    },

    augmentation: {
      enabled: true,
      synonym_replacement: 0.1,
      random_insertion: 0.1,
      random_swap: 0.1,
      random_deletion: 0.1
    }
  },

  // 推理配置
  inference: {
    batch_size: 64,
    max_concurrent_requests: 10,
    cache_predictions: true,
    cache_ttl: 3600, // 1小時

    // 結果後處理
    postprocessing: {
      apply_softmax: true,
      temperature: 1.0,
      top_k_filtering: false,
      confidence_calibration: true
    }
  },

  // 快取配置
  cache: {
    embeddings: {
      enabled: true,
      max_size: 10000,
      ttl: 86400 // 24小時
    },

    predictions: {
      enabled: true,
      max_size: 5000,
      ttl: 3600 // 1小時
    },

    training_data: {
      enabled: true,
      max_size: 1000,
      ttl: 7200 // 2小時
    }
  },

  // 監控配置
  monitoring: {
    enabled: true,
    metrics: {
      gpu_utilization: true,
      memory_usage: true,
      inference_latency: true,
      throughput: true,
      error_rate: true
    },

    alerts: {
      gpu_memory_threshold: 0.9,
      inference_latency_threshold: 5000, // ms
      error_rate_threshold: 0.05
    },

    logging: {
      level: process.env.ML_LOG_LEVEL || 'info',
      include_predictions: process.env.NODE_ENV === 'development',
      include_embeddings: false
    }
  },

  // 資料庫查詢配置
  database: {
    queries: {
      classification_data: `
        SELECT
          a.id,
          a.title,
          a.description,
          a.artist_name,
          c.period,
          c.style,
          c.region,
          c.medium,
          c.confidence_score
        FROM artworks a
        JOIN classifications c ON a.id = c.artwork_id
        WHERE
          c.confidence_score > ?
          AND LENGTH(CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.description, ''))) > ?
          AND a.status = 'verified'
        ORDER BY c.confidence_score DESC
      `,

      embedding_data: `
        SELECT
          a.id,
          CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.description, ''), ' ', COALESCE(a.artist_name, '')) as text,
          c.period,
          c.style,
          c.region
        FROM artworks a
        JOIN classifications c ON a.id = c.artwork_id
        WHERE
          c.confidence_score > ?
          AND LENGTH(CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.description, ''))) > ?
        ORDER BY a.created_at DESC
      `,

      similarity_candidates: `
        SELECT
          a.id,
          a.title,
          a.description,
          a.artist_name,
          c.period,
          c.style,
          c.region
        FROM artworks a
        JOIN classifications c ON a.id = c.artwork_id
        WHERE a.id != ?
        ORDER BY c.confidence_score DESC
        LIMIT ?
      `
    }
  },

  // API端點配置
  api: {
    rate_limiting: {
      inference: {
        points: 100,
        duration: 60 // 每分鐘100次請求
      },
      training: {
        points: 5,
        duration: 3600 // 每小時5次訓練請求
      },
      embeddings: {
        points: 50,
        duration: 60 // 每分鐘50次嵌入請求
      }
    },

    validation: {
      max_text_length: 5000,
      max_batch_size: 100,
      required_fields: {
        classification: ['text'],
        embedding: ['texts'],
        similarity: ['query_text']
      }
    }
  },

  // 任務排程配置
  scheduling: {
    model_retraining: {
      enabled: true,
      cron: '0 2 * * 0', // 每週日凌晨2點
      min_new_data_threshold: 100
    },

    data_preprocessing: {
      enabled: true,
      cron: '0 1 * * 1', // 每週一凌晨1點
      cleanup_old_cache: true
    },

    model_evaluation: {
      enabled: true,
      cron: '0 3 * * 1', // 每週一凌晨3點
      metrics: ['accuracy', 'precision', 'recall', 'f1_score']
    }
  }
};

module.exports = mlConfig;