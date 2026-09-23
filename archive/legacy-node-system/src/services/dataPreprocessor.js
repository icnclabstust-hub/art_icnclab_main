const { dbManager } = require('../database/connection');
const logger = require('../utils/logger').logger;
const mlConfig = require('../config/mlConfig');
const fs = require('fs').promises;
const path = require('path');

class ArtDataPreprocessor {
  constructor() {
    this.qualityThreshold = mlConfig.preprocessing.quality_threshold;
    this.minTextLength = mlConfig.preprocessing.min_text_length;
    this.maxTextLength = mlConfig.preprocessing.max_text_length;
    this.textCleaning = mlConfig.preprocessing.text_cleaning;
    this.dataSplit = mlConfig.preprocessing.data_split;
    this.augmentation = mlConfig.preprocessing.augmentation;
  }

  // 準備分類訓練資料集
  async prepareClassificationDataset(filters = {}) {
    try {
      logger.info('開始準備分類訓練資料集...');

      // 1. 提取高品質資料
      const rawData = await this.extractQualityData('classification', filters);
      logger.info(`提取到 ${rawData.length} 條原始資料`);

      if (rawData.length < 100) {
        throw new Error('訓練資料不足，至少需要100條高品質資料');
      }

      // 2. 文本清理和標準化
      const cleanData = this.cleanTextData(rawData);
      logger.info('完成文本清理和標準化');

      // 3. 標籤編碼
      const encodedData = this.encodeLabels(cleanData);
      logger.info('完成標籤編碼');

      // 4. 資料增強（如果啟用）
      let augmentedData = encodedData;
      if (this.augmentation.enabled) {
        augmentedData = await this.augmentData(encodedData);
        logger.info(`資料增強完成，資料量從 ${encodedData.length} 增加到 ${augmentedData.length}`);
      }

      // 5. 資料分割
      const dataset = this.splitDataset(augmentedData, this.dataSplit);
      logger.info(`資料分割完成: 訓練集 ${dataset.train.length}, 驗證集 ${dataset.validation.length}, 測試集 ${dataset.test.length}`);

      // 6. 統計資訊
      const stats = this.generateDatasetStats(dataset);

      return {
        dataset,
        stats,
        metadata: {
          total_samples: augmentedData.length,
          preprocessing_config: {
            quality_threshold: this.qualityThreshold,
            min_text_length: this.minTextLength,
            augmentation_enabled: this.augmentation.enabled
          },
          created_at: new Date().toISOString()
        }
      };

    } catch (error) {
      logger.error('準備分類資料集失敗:', error);
      throw error;
    }
  }

  // 準備嵌入訓練資料集
  async prepareEmbeddingDataset(filters = {}) {
    try {
      logger.info('開始準備嵌入訓練資料集...');

      // 1. 提取資料
      const rawData = await this.extractQualityData('embedding', filters);
      logger.info(`提取到 ${rawData.length} 條原始資料`);

      // 2. 清理文本
      const cleanData = this.cleanTextData(rawData);

      // 3. 生成相似性對
      const similarityPairs = await this.generateSimilarityPairs(cleanData);
      logger.info(`生成 ${similarityPairs.positive.length} 個正樣本對，${similarityPairs.negative.length} 個負樣本對`);

      // 4. 準備對比學習資料
      const contrastiveData = this.prepareContrastiveData(cleanData, similarityPairs);

      return {
        texts: cleanData.map(item => item.text),
        metadata: cleanData.map(item => ({
          id: item.id,
          period: item.period,
          style: item.style,
          region: item.region
        })),
        similarity_pairs: similarityPairs,
        contrastive_data: contrastiveData,
        stats: {
          total_texts: cleanData.length,
          positive_pairs: similarityPairs.positive.length,
          negative_pairs: similarityPairs.negative.length,
          unique_periods: new Set(cleanData.map(d => d.period)).size,
          unique_styles: new Set(cleanData.map(d => d.style)).size
        }
      };

    } catch (error) {
      logger.error('準備嵌入資料集失敗:', error);
      throw error;
    }
  }

  // 提取高品質資料
  async extractQualityData(dataType, filters = {}) {
    const qualityThreshold = filters.quality_threshold || this.qualityThreshold;
    const minTextLength = filters.min_text_length || this.minTextLength;

    let query = mlConfig.database.queries[`${dataType}_data`];
    let params = [qualityThreshold, minTextLength];

    // 添加額外過濾條件
    if (filters.period) {
      query += ' AND c.period = ?';
      params.push(filters.period);
    }

    if (filters.style) {
      query += ' AND c.style = ?';
      params.push(filters.style);
    }

    if (filters.date_from) {
      query += ' AND a.created_at >= ?';
      params.push(filters.date_from);
    }

    if (filters.date_to) {
      query += ' AND a.created_at <= ?';
      params.push(filters.date_to);
    }

    if (filters.limit) {
      query += ' LIMIT ?';
      params.push(filters.limit);
    }

    const results = await dbManager.query(query, params);
    return results;
  }

  // 清理文本資料
  cleanTextData(data) {
    return data.map(item => {
      let text = `${item.title || ''} ${item.description || ''} ${item.artist_name || ''}`;

      // 應用清理規則
      if (this.textCleaning.remove_special_chars) {
        if (this.textCleaning.preserve_chinese) {
          text = text.replace(/[^\w\s\u4e00-\u9fff]/gi, ' ');
        } else {
          text = text.replace(/[^\w\s]/gi, ' ');
        }
      }

      if (this.textCleaning.normalize_unicode) {
        text = text.normalize('NFKC');
      }

      text = text.replace(/\s+/g, ' ').trim();

      if (this.textCleaning.lowercase) {
        text = text.toLowerCase();
      }

      // 截斷過長文本
      if (text.length > this.maxTextLength) {
        text = text.substring(0, this.maxTextLength);
      }

      return {
        ...item,
        text,
        original_length: `${item.title || ''} ${item.description || ''} ${item.artist_name || ''}`.length,
        cleaned_length: text.length,
        language: this.detectLanguage(item.title || item.description || '')
      };
    });
  }

  // 編碼標籤
  encodeLabels(data) {
    // 建立標籤映射
    const labelMaps = {
      period: this.createLabelMap(data, 'period'),
      style: this.createLabelMap(data, 'style'),
      region: this.createLabelMap(data, 'region'),
      medium: this.createLabelMap(data, 'medium')
    };

    return data.map(item => ({
      ...item,
      labels: {
        period: labelMaps.period[item.period] || 0,
        style: labelMaps.style[item.style] || 0,
        region: labelMaps.region[item.region] || 0,
        medium: labelMaps.medium[item.medium] || 0
      },
      label_names: {
        period: item.period,
        style: item.style,
        region: item.region,
        medium: item.medium
      }
    }));
  }

  // 建立標籤映射
  createLabelMap(data, labelType) {
    const uniqueLabels = [...new Set(data.map(item => item[labelType]).filter(Boolean))];
    const labelMap = {};

    uniqueLabels.forEach((label, index) => {
      labelMap[label] = index;
    });

    logger.info(`${labelType} 標籤映射:`, labelMap);
    return labelMap;
  }

  // 資料增強
  async augmentData(data) {
    if (!this.augmentation.enabled) {
      return data;
    }

    const augmentedData = [...data];

    for (const item of data) {
      // 只對較短的文本進行增強
      if (item.text.length < 200) {
        // 同義詞替換
        if (Math.random() < this.augmentation.synonym_replacement) {
          const augmented = await this.applySynonymReplacement(item);
          if (augmented) augmentedData.push(augmented);
        }

        // 隨機插入
        if (Math.random() < this.augmentation.random_insertion) {
          const augmented = this.applyRandomInsertion(item);
          if (augmented) augmentedData.push(augmented);
        }

        // 隨機交換
        if (Math.random() < this.augmentation.random_swap) {
          const augmented = this.applyRandomSwap(item);
          if (augmented) augmentedData.push(augmented);
        }

        // 隨機刪除
        if (Math.random() < this.augmentation.random_deletion) {
          const augmented = this.applyRandomDeletion(item);
          if (augmented) augmentedData.push(augmented);
        }
      }
    }

    return augmentedData;
  }

  // 同義詞替換
  async applySynonymReplacement(item) {
    // 簡化版本：隨機替換一些常見詞彙
    const synonymMap = {
      '畫': ['繪畫', '作品', '圖畫'],
      '藝術': ['美術', '創作', '作品'],
      '風格': ['手法', '技法', '特色'],
      '作者': ['藝術家', '畫家', '創作者']
    };

    let text = item.text;
    for (const [word, synonyms] of Object.entries(synonymMap)) {
      if (text.includes(word) && Math.random() < 0.3) {
        const synonym = synonyms[Math.floor(Math.random() * synonyms.length)];
        text = text.replace(word, synonym);
      }
    }

    return text !== item.text ? { ...item, text } : null;
  }

  // 隨機插入
  applyRandomInsertion(item) {
    const words = item.text.split(' ');
    if (words.length < 3) return null;

    const insertWords = ['精美的', '經典的', '著名的', '重要的'];
    const insertWord = insertWords[Math.floor(Math.random() * insertWords.length)];
    const position = Math.floor(Math.random() * words.length);

    words.splice(position, 0, insertWord);
    return { ...item, text: words.join(' ') };
  }

  // 隨機交換
  applyRandomSwap(item) {
    const words = item.text.split(' ');
    if (words.length < 4) return null;

    const idx1 = Math.floor(Math.random() * words.length);
    const idx2 = Math.floor(Math.random() * words.length);

    if (idx1 !== idx2) {
      [words[idx1], words[idx2]] = [words[idx2], words[idx1]];
      return { ...item, text: words.join(' ') };
    }

    return null;
  }

  // 隨機刪除
  applyRandomDeletion(item) {
    const words = item.text.split(' ');
    if (words.length < 5) return null;

    const numDelete = Math.floor(words.length * 0.1);
    for (let i = 0; i < numDelete; i++) {
      const idx = Math.floor(Math.random() * words.length);
      words.splice(idx, 1);
    }

    return { ...item, text: words.join(' ') };
  }

  // 分割資料集
  splitDataset(data, splitRatio) {
    const shuffled = this.shuffleArray([...data]);
    const trainSize = Math.floor(shuffled.length * splitRatio.train);
    const validSize = Math.floor(shuffled.length * splitRatio.validation);

    return {
      train: shuffled.slice(0, trainSize),
      validation: shuffled.slice(trainSize, trainSize + validSize),
      test: shuffled.slice(trainSize + validSize)
    };
  }

  // 生成相似性對
  async generateSimilarityPairs(data) {
    const positivePairs = [];
    const negativePairs = [];

    // 按類別分組
    const groupedData = this.groupByAttributes(data);

    // 生成正樣本對
    for (const [key, items] of Object.entries(groupedData)) {
      if (items.length > 1) {
        for (let i = 0; i < items.length; i++) {
          for (let j = i + 1; j < Math.min(items.length, i + 6); j++) {
            positivePairs.push({
              text1: items[i].text,
              text2: items[j].text,
              similarity: 1.0,
              reason: key
            });
          }
        }
      }
    }

    // 生成負樣本對
    const allItems = Object.values(groupedData).flat();
    for (let i = 0; i < Math.min(positivePairs.length * 2, 5000); i++) {
      const item1 = allItems[Math.floor(Math.random() * allItems.length)];
      const item2 = allItems[Math.floor(Math.random() * allItems.length)];

      // 確保是不同類別
      if (item1.period !== item2.period || item1.style !== item2.style) {
        negativePairs.push({
          text1: item1.text,
          text2: item2.text,
          similarity: 0.0,
          reason: 'different_category'
        });
      }
    }

    return {
      positive: positivePairs,
      negative: negativePairs
    };
  }

  // 按屬性分組
  groupByAttributes(data) {
    const grouped = {};

    data.forEach(item => {
      const key = `${item.period}_${item.style}_${item.region}`;
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(item);
    });

    return grouped;
  }

  // 準備對比學習資料
  prepareContrastiveData(data, similarityPairs) {
    const contrastiveData = [];

    // 從正負樣本對中準備三元組
    similarityPairs.positive.forEach((pair, index) => {
      if (index < similarityPairs.negative.length) {
        contrastiveData.push({
          anchor: pair.text1,
          positive: pair.text2,
          negative: similarityPairs.negative[index].text2
        });
      }
    });

    return contrastiveData;
  }

  // 生成資料集統計
  generateDatasetStats(dataset) {
    const allData = [...dataset.train, ...dataset.validation, ...dataset.test];

    return {
      total_samples: allData.length,
      train_samples: dataset.train.length,
      validation_samples: dataset.validation.length,
      test_samples: dataset.test.length,

      label_distribution: {
        period: this.getLabelDistribution(allData, 'period'),
        style: this.getLabelDistribution(allData, 'style'),
        region: this.getLabelDistribution(allData, 'region'),
        medium: this.getLabelDistribution(allData, 'medium')
      },

      text_stats: {
        avg_length: allData.reduce((sum, item) => sum + item.text.length, 0) / allData.length,
        min_length: Math.min(...allData.map(item => item.text.length)),
        max_length: Math.max(...allData.map(item => item.text.length))
      },

      language_distribution: this.getLabelDistribution(allData, 'language')
    };
  }

  // 獲取標籤分布
  getLabelDistribution(data, labelType) {
    const distribution = {};
    data.forEach(item => {
      const label = item[labelType] || 'unknown';
      distribution[label] = (distribution[label] || 0) + 1;
    });
    return distribution;
  }

  // 偵測語言
  detectLanguage(text) {
    if (!text) return 'unknown';

    // 簡單的語言偵測
    const chineseRatio = (text.match(/[\u4e00-\u9fff]/g) || []).length / text.length;
    const englishRatio = (text.match(/[a-zA-Z]/g) || []).length / text.length;

    if (chineseRatio > 0.3) return 'zh';
    if (englishRatio > 0.7) return 'en';
    return 'mixed';
  }

  // 隨機打亂陣列
  shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  }

  // 匯出資料到檔案
  async exportToFile(data, filename, format = 'json') {
    try {
      const exportDir = path.join(process.cwd(), 'ml-data');

      // 確保目錄存在
      try {
        await fs.access(exportDir);
      } catch {
        await fs.mkdir(exportDir, { recursive: true });
      }

      const filepath = path.join(exportDir, `${filename}.${format}`);

      switch (format) {
        case 'json':
          await fs.writeFile(filepath, JSON.stringify(data, null, 2));
          break;
        case 'jsonl': {
          const lines = data.map(item => JSON.stringify(item)).join('\n');
          await fs.writeFile(filepath, lines);
          break;
        }
        default:
          throw new Error(`不支援的格式: ${format}`);
      }

      logger.info(`資料已匯出到: ${filepath}`);
      return filepath;
    } catch (error) {
      logger.error('資料匯出失敗:', error);
      throw error;
    }
  }
}

module.exports = ArtDataPreprocessor;