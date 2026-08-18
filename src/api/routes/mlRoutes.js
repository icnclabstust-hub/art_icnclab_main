const express = require('express');
const router = express.Router();
const axios = require('axios');
const { dbManager } = require('../../database/connection');
const logger = require('../../utils/logger').logger;

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://cuda-ml-service:8080';
const ML_SERVICE_TIMEOUT = 300000; // 5分鐘超時

// ML服務健康檢查
router.get('/health', async (req, res) => {
  try {
    const response = await axios.get(`${ML_SERVICE_URL}/health`, {
      timeout: 5000
    });

    res.json({
      success: true,
      ml_service_status: 'healthy',
      gpu_available: response.data.gpu_available,
      cuda_version: response.data.cuda_version,
      memory_usage: response.data.memory_usage
    });
  } catch (error) {
    logger.warn('ML服務連接失敗:', error.message);
    res.status(503).json({
      success: false,
      ml_service_status: 'unhealthy',
      error: error.message
    });
  }
});

// 模型訓練端點
router.post('/train', async (req, res) => {
  try {
    const { model_type = 'classification', config = {} } = req.body;

    logger.info(`開始準備${model_type}模型訓練資料`);

    // 準備訓練資料
    const trainingData = await prepareTrainingData(model_type);

    if (!trainingData || trainingData.length === 0) {
      return res.status(400).json({
        success: false,
        message: '沒有足夠的訓練資料'
      });
    }

    // 默認訓練配置
    const defaultConfig = {
      epochs: 10,
      batch_size: 32,
      learning_rate: 2e-5,
      validation_split: 0.1,
      early_stopping: true
    };

    const mergedConfig = { ...defaultConfig, ...config };

    // 調用CUDA服務開始訓練
    const response = await axios.post(`${ML_SERVICE_URL}/train`, {
      model_type,
      data: trainingData,
      config: mergedConfig
    }, {
      timeout: ML_SERVICE_TIMEOUT
    });

    logger.info(`${model_type}模型訓練已啟動:`, response.data.job_id);

    res.json({
      success: true,
      training_job_id: response.data.job_id,
      model_type,
      data_size: trainingData.length,
      estimated_time: response.data.eta,
      config: mergedConfig,
      message: '模型訓練已成功啟動'
    });

  } catch (error) {
    logger.error('模型訓練啟動失敗:', error);
    res.status(500).json({
      success: false,
      message: '模型訓練啟動失敗',
      error: error.message
    });
  }
});

// 訓練進度查詢
router.get('/train/:job_id/progress', async (req, res) => {
  try {
    const { job_id } = req.params;

    const response = await axios.get(`${ML_SERVICE_URL}/train/${job_id}/progress`);

    res.json({
      success: true,
      job_id,
      status: response.data.status,
      progress: response.data.progress,
      current_epoch: response.data.current_epoch,
      total_epochs: response.data.total_epochs,
      loss: response.data.current_loss,
      accuracy: response.data.current_accuracy,
      estimated_remaining_time: response.data.eta
    });

  } catch (error) {
    res.status(500).json({
      success: false,
      message: '無法獲取訓練進度',
      error: error.message
    });
  }
});

// 推理端點
router.post('/inference', async (req, res) => {
  try {
    const { text, tasks = ['classification'], model_version = 'latest' } = req.body;

    if (!text) {
      return res.status(400).json({
        success: false,
        message: '請提供要分析的文本'
      });
    }

    const texts = Array.isArray(text) ? text : [text];

    // 批量推理加速
    const response = await axios.post(`${ML_SERVICE_URL}/inference`, {
      texts,
      tasks,
      model_version,
      batch_size: Math.min(texts.length, 64)
    });

    res.json({
      success: true,
      results: response.data.results,
      processing_time: response.data.processing_time,
      model_version: response.data.model_version,
      gpu_time: response.data.gpu_time
    });

  } catch (error) {
    logger.error('推理請求失敗:', error);
    res.status(500).json({
      success: false,
      message: '推理請求失敗',
      error: error.message
    });
  }
});

// 批量生成嵌入向量
router.post('/embeddings/batch', async (req, res) => {
  try {
    const { texts, embedding_model = 'multilingual-bert' } = req.body;

    if (!texts || !Array.isArray(texts)) {
      return res.status(400).json({
        success: false,
        message: '請提供文本陣列'
      });
    }

    // 分批處理大量文本
    const batchSize = 100;
    const batches = [];

    for (let i = 0; i < texts.length; i += batchSize) {
      batches.push(texts.slice(i, i + batchSize));
    }

    const allEmbeddings = [];

    for (const batch of batches) {
      const response = await axios.post(`${ML_SERVICE_URL}/embeddings`, {
        texts: batch,
        model: embedding_model
      });

      allEmbeddings.push(...response.data.embeddings);
    }

    res.json({
      success: true,
      embeddings: allEmbeddings,
      total_texts: texts.length,
      embedding_dim: allEmbeddings[0]?.length || 0,
      model_used: embedding_model
    });

  } catch (error) {
    logger.error('嵌入向量生成失敗:', error);
    res.status(500).json({
      success: false,
      message: '嵌入向量生成失敗',
      error: error.message
    });
  }
});

// 模型狀態查詢
router.get('/models/status', async (req, res) => {
  try {
    const response = await axios.get(`${ML_SERVICE_URL}/models/status`);

    res.json({
      success: true,
      models: response.data.models,
      gpu_stats: response.data.gpu_stats,
      system_info: {
        cuda_version: response.data.cuda_version,
        cudnn_version: response.data.cudnn_version,
        gpu_name: response.data.gpu_name,
        total_memory: response.data.total_memory,
        available_memory: response.data.available_memory
      }
    });

  } catch (error) {
    res.status(500).json({
      success: false,
      message: '無法獲取模型狀態',
      error: error.message
    });
  }
});

// 藝術品分類專用端點
router.post('/classify/artwork', async (req, res) => {
  try {
    const { artwork_id, title, description, artist_name } = req.body;

    if (!title && !description) {
      return res.status(400).json({
        success: false,
        message: '請提供藝術品標題或描述'
      });
    }

    const text = `${title || ''} ${description || ''} ${artist_name || ''}`.trim();

    const response = await axios.post(`${ML_SERVICE_URL}/classify/artwork`, {
      text,
      tasks: ['period', 'style', 'region', 'medium']
    });

    // 如果提供artwork_id，更新資料庫
    if (artwork_id) {
      await updateArtworkClassification(artwork_id, response.data.classification);
    }

    res.json({
      success: true,
      artwork_id,
      classification: response.data.classification,
      confidence_scores: response.data.confidence_scores
    });

  } catch (error) {
    logger.error('藝術品分類失敗:', error);
    res.status(500).json({
      success: false,
      message: '藝術品分類失敗',
      error: error.message
    });
  }
});

// 相似作品推薦
router.post('/similarity/recommend', async (req, res) => {
  try {
    const { artwork_id, text, top_k = 10 } = req.body;

    let queryText = text;

    if (artwork_id && !text) {
      // 根據artwork_id獲取描述文本
      const artwork = await dbManager.query(
        'SELECT title, description, artist_name FROM artworks WHERE id = ?',
        [artwork_id]
      );

      if (artwork.length === 0) {
        return res.status(404).json({
          success: false,
          message: '找不到指定的藝術品'
        });
      }

      queryText = `${artwork[0].title} ${artwork[0].description} ${artwork[0].artist_name}`;
    }

    const response = await axios.post(`${ML_SERVICE_URL}/similarity/search`, {
      query_text: queryText,
      top_k,
      include_embeddings: false
    });

    res.json({
      success: true,
      query_artwork_id: artwork_id,
      recommendations: response.data.similar_items,
      similarity_scores: response.data.scores
    });

  } catch (error) {
    logger.error('相似作品推薦失敗:', error);
    res.status(500).json({
      success: false,
      message: '相似作品推薦失敗',
      error: error.message
    });
  }
});

// 資料預處理端點
router.post('/preprocess/dataset', async (req, res) => {
  try {
    const { data_type = 'classification', filters = {} } = req.body;

    logger.info(`開始準備${data_type}資料集...`);

    const dataset = await prepareTrainingData(data_type, filters);

    res.json({
      success: true,
      data_type,
      dataset_size: dataset.length,
      filters_applied: filters,
      preprocessing_completed: true
    });

  } catch (error) {
    logger.error('資料預處理失敗:', error);
    res.status(500).json({
      success: false,
      message: '資料預處理失敗',
      error: error.message
    });
  }
});

// 輔助函數：準備訓練資料
async function prepareTrainingData(modelType, filters = {}) {
  const qualityThreshold = filters.quality_threshold || 0.8;
  const minTextLength = filters.min_text_length || 50;

  let query;
  let params = [qualityThreshold, minTextLength];

  switch (modelType) {
    case 'classification':
      query = `
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
      `;
      break;

    case 'embedding':
      query = `
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
      `;
      break;

    default:
      throw new Error(`不支援的模型類型: ${modelType}`);
  }

  const results = await dbManager.query(query, params);

  return results.map(row => ({
    id: row.id,
    text: cleanText(`${row.title || ''} ${row.description || ''} ${row.artist_name || ''}`),
    labels: {
      period: row.period,
      style: row.style,
      region: row.region,
      medium: row.medium
    },
    confidence: row.confidence_score
  }));
}

// 輔助函數：清理文本
function cleanText(text) {
  return text
    .replace(/[^\w\s\u4e00-\u9fff]/gi, ' ') // 保留中文字符
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

// 輔助函數：更新藝術品分類
async function updateArtworkClassification(artworkId, classification) {
  try {
    await dbManager.query(`
      UPDATE classifications
      SET
        period = ?,
        style = ?,
        region = ?,
        medium = ?,
        confidence_score = ?,
        updated_at = NOW()
      WHERE artwork_id = ?
    `, [
      classification.period,
      classification.style,
      classification.region,
      classification.medium,
      classification.confidence || 0.9,
      artworkId
    ]);

    logger.info(`更新藝術品${artworkId}的分類資料`);
  } catch (error) {
    logger.error(`更新藝術品${artworkId}分類失敗:`, error);
  }
}

module.exports = router;