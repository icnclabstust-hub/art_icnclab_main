/**
 * 資料品質監控系統
 * 建立comprehensive資料品質評分機制與監控告警系統
 */

const EventEmitter = require('events');
const { logger } = require('./logger');
const { DataQualityChecker } = require('./dataCleaner');

class DataQualityMonitor extends EventEmitter {
    constructor(options = {}) {
        super();

        this.options = {
            evaluationInterval: options.evaluationInterval || 300000, // 5分鐘評估一次
            alertThresholds: {
                overall: options.overallThreshold || 0.7,        // 整體品質閾值
                completeness: options.completenessThreshold || 0.8, // 完整性閾值
                accuracy: options.accuracyThreshold || 0.85,     // 準確性閾值
                consistency: options.consistencyThreshold || 0.9, // 一致性閾值
                freshness: options.freshnessThreshold || 0.75,   // 時效性閾值
                validity: options.validityThreshold || 0.8       // 有效性閾值
            },
            sampleSize: options.sampleSize || 1000,
            retentionDays: options.retentionDays || 30,
            enableAlerts: options.enableAlerts !== false,
            ...options
        };

        // 品質指標記錄
        this.qualityMetrics = {
            overall: [],
            completeness: [],
            accuracy: [],
            consistency: [],
            freshness: [],
            validity: [],
            trends: new Map()
        };

        // 品質規則定義
        this.qualityRules = new Map([
            ['required_fields', {
                name: '必填欄位檢查',
                weight: 0.3,
                evaluate: this.evaluateCompleteness.bind(this)
            }],
            ['data_format', {
                name: '資料格式驗證',
                weight: 0.2,
                evaluate: this.evaluateValidity.bind(this)
            }],
            ['consistency_check', {
                name: '一致性檢查',
                weight: 0.2,
                evaluate: this.evaluateConsistency.bind(this)
            }],
            ['freshness_check', {
                name: '時效性檢查',
                weight: 0.15,
                evaluate: this.evaluateFreshness.bind(this)
            }],
            ['accuracy_check', {
                name: '準確性檢查',
                weight: 0.15,
                evaluate: this.evaluateAccuracy.bind(this)
            }]
        ]);

        // 監控狀態
        this.isMonitoring = false;
        this.monitoringInterval = null;
        this.lastEvaluation = null;

        // 告警歷史記錄
        this.alertHistory = [];

        logger.info('資料品質監控系統初始化完成');
    }

    /**
     * 啟動監控
     */
    async startMonitoring() {
        if (this.isMonitoring) {
            logger.warn('品質監控系統已在運行中');
            return;
        }

        try {
            logger.info('啟動資料品質監控系統...');

            // 執行初始評估
            await this.performQualityEvaluation();

            // 設定定期評估
            this.monitoringInterval = setInterval(() => {
                this.performQualityEvaluation().catch(error => {
                    logger.error('品質評估失敗', { error: error.message });
                });
            }, this.options.evaluationInterval);

            this.isMonitoring = true;
            this.emit('monitoringStarted');

            logger.info('資料品質監控系統已啟動', {
                evaluationInterval: this.options.evaluationInterval,
                alertsEnabled: this.options.enableAlerts
            });

        } catch (error) {
            logger.error('啟動品質監控失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 停止監控
     */
    async stopMonitoring() {
        if (!this.isMonitoring) {
            logger.warn('品質監控系統未在運行');
            return;
        }

        try {
            if (this.monitoringInterval) {
                clearInterval(this.monitoringInterval);
                this.monitoringInterval = null;
            }

            this.isMonitoring = false;
            this.emit('monitoringStopped');

            logger.info('資料品質監控系統已停止');

        } catch (error) {
            logger.error('停止品質監控失敗', { error: error.message });
        }
    }

    /**
     * 執行品質評估
     */
    async performQualityEvaluation() {
        try {
            const timestamp = new Date();
            logger.info('開始執行資料品質評估', { timestamp });

            // 獲取評估樣本
            const samples = await this.collectDataSamples();

            if (samples.length === 0) {
                logger.warn('沒有可評估的資料樣本');
                return null;
            }

            // 計算各項品質指標
            const qualityScores = {
                timestamp,
                sampleSize: samples.length
            };

            for (const [ruleKey, rule] of this.qualityRules) {
                try {
                    const score = await rule.evaluate(samples);
                    qualityScores[ruleKey] = {
                        score: score,
                        weight: rule.weight,
                        name: rule.name
                    };
                } catch (error) {
                    logger.error(`品質規則評估失敗: ${rule.name}`, { error: error.message });
                    qualityScores[ruleKey] = {
                        score: 0,
                        weight: rule.weight,
                        name: rule.name,
                        error: error.message
                    };
                }
            }

            // 計算加權總分
            qualityScores.overallScore = this.calculateOverallScore(qualityScores);

            // 記錄品質指標
            this.recordQualityMetrics(qualityScores);

            // 檢查告警條件
            await this.checkQualityAlerts(qualityScores);

            this.lastEvaluation = qualityScores;
            this.emit('qualityEvaluated', qualityScores);

            logger.info('資料品質評估完成', {
                overallScore: qualityScores.overallScore,
                sampleSize: qualityScores.sampleSize
            });

            return qualityScores;

        } catch (error) {
            logger.error('品質評估執行失敗', { error: error.message });
            throw error;
        }
    }

    /**
     * 收集資料樣本
     */
    async collectDataSamples() {
        try {
            // 這裡需要從資料庫獲取樣本資料
            // 現在返回模擬資料用於測試
            const mockSamples = [];

            for (let i = 0; i < this.options.sampleSize; i++) {
                mockSamples.push({
                    id: `sample_${i}`,
                    type: Math.random() > 0.5 ? 'artwork' : 'artist',
                    title: Math.random() > 0.9 ? null : `Sample Title ${i}`,
                    description: Math.random() > 0.8 ? null : `Sample Description ${i}`,
                    created_at: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000),
                    updated_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000),
                    source_urls: Math.random() > 0.7 ? [] : [`https://example.com/source${i}`],
                    year: Math.random() > 0.8 ? null : Math.floor(Math.random() * 2000) + 1000
                });
            }

            return mockSamples;

        } catch (error) {
            logger.error('收集資料樣本失敗', { error: error.message });
            return [];
        }
    }

    /**
     * 評估完整性
     */
    async evaluateCompleteness(samples) {
        const requiredFields = ['title', 'description', 'created_at'];
        let totalScore = 0;

        for (const sample of samples) {
            const completeness = DataQualityChecker.checkCompleteness(sample, requiredFields);
            totalScore += completeness.score;
        }

        const averageScore = samples.length > 0 ? totalScore / samples.length : 0;

        logger.debug('完整性評估完成', {
            sampleSize: samples.length,
            averageScore: averageScore
        });

        return averageScore;
    }

    /**
     * 評估有效性
     */
    async evaluateValidity(samples) {
        let validCount = 0;

        for (const sample of samples) {
            let isValid = true;

            // 檢查年份格式
            if (sample.year !== null && sample.year !== undefined) {
                const year = Number(sample.year);
                if (isNaN(year) || year < -3000 || year > new Date().getFullYear() + 10) {
                    isValid = false;
                }
            }

            // 檢查URL格式
            if (sample.source_urls && Array.isArray(sample.source_urls)) {
                for (const url of sample.source_urls) {
                    try {
                        new URL(url);
                    } catch {
                        isValid = false;
                        break;
                    }
                }
            }

            if (isValid) validCount++;
        }

        const validityScore = samples.length > 0 ? validCount / samples.length : 0;

        logger.debug('有效性評估完成', {
            sampleSize: samples.length,
            validCount: validCount,
            validityScore: validityScore
        });

        return validityScore;
    }

    /**
     * 評估一致性
     */
    async evaluateConsistency(samples) {
        let consistentCount = 0;

        for (const sample of samples) {
            const consistency = DataQualityChecker.checkConsistency(sample);
            if (consistency.isConsistent) {
                consistentCount++;
            }
        }

        const consistencyScore = samples.length > 0 ? consistentCount / samples.length : 0;

        logger.debug('一致性評估完成', {
            sampleSize: samples.length,
            consistentCount: consistentCount,
            consistencyScore: consistencyScore
        });

        return consistencyScore;
    }

    /**
     * 評估時效性
     */
    async evaluateFreshness(samples) {
        const now = new Date();
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        let freshCount = 0;

        for (const sample of samples) {
            if (sample.updated_at && new Date(sample.updated_at) > thirtyDaysAgo) {
                freshCount++;
            }
        }

        const freshnessScore = samples.length > 0 ? freshCount / samples.length : 0;

        logger.debug('時效性評估完成', {
            sampleSize: samples.length,
            freshCount: freshCount,
            freshnessScore: freshnessScore
        });

        return freshnessScore;
    }

    /**
     * 評估準確性
     */
    async evaluateAccuracy(samples) {
        // 準確性評估需要參考資料或外部驗證
        // 這裡使用簡化的邏輯：檢查資料的合理性
        let accurateCount = 0;

        for (const sample of samples) {
            let isAccurate = true;

            // 檢查標題長度合理性
            if (sample.title && sample.title.length > 500) {
                isAccurate = false;
            }

            // 檢查年份合理性
            if (sample.year && (sample.year < -3000 || sample.year > new Date().getFullYear())) {
                isAccurate = false;
            }

            if (isAccurate) accurateCount++;
        }

        const accuracyScore = samples.length > 0 ? accurateCount / samples.length : 0;

        logger.debug('準確性評估完成', {
            sampleSize: samples.length,
            accurateCount: accurateCount,
            accuracyScore: accuracyScore
        });

        return accuracyScore;
    }

    /**
     * 計算總體品質評分
     */
    calculateOverallScore(qualityScores) {
        let weightedSum = 0;
        let totalWeight = 0;

        for (const [key, rule] of this.qualityRules) {
            if (qualityScores[key] && qualityScores[key].score !== undefined) {
                weightedSum += qualityScores[key].score * rule.weight;
                totalWeight += rule.weight;
            }
        }

        return totalWeight > 0 ? weightedSum / totalWeight : 0;
    }

    /**
     * 記錄品質指標
     */
    recordQualityMetrics(qualityScores) {
        const timestamp = qualityScores.timestamp;

        // 記錄總體評分
        this.qualityMetrics.overall.push({
            timestamp,
            value: qualityScores.overallScore
        });

        // 記錄各項指標
        for (const [key, rule] of this.qualityRules) {
            if (qualityScores[key]) {
                if (!this.qualityMetrics[key.replace('_check', '')]) {
                    this.qualityMetrics[key.replace('_check', '')] = [];
                }

                this.qualityMetrics[key.replace('_check', '')].push({
                    timestamp,
                    value: qualityScores[key].score
                });
            }
        }

        // 限制歷史記錄長度
        this.limitMetricsHistory();
    }

    /**
     * 限制指標歷史記錄長度
     */
    limitMetricsHistory() {
        const maxRecords = Math.floor(this.options.retentionDays * 24 * 60 * 60 * 1000 / this.options.evaluationInterval);

        for (const key in this.qualityMetrics) {
            if (Array.isArray(this.qualityMetrics[key]) && this.qualityMetrics[key].length > maxRecords) {
                this.qualityMetrics[key] = this.qualityMetrics[key].slice(-maxRecords);
            }
        }
    }

    /**
     * 檢查品質告警
     */
    async checkQualityAlerts(qualityScores) {
        if (!this.options.enableAlerts) return;

        const alerts = [];

        // 檢查總體品質
        if (qualityScores.overallScore < this.options.alertThresholds.overall) {
            alerts.push({
                type: 'overall_quality',
                severity: 'warning',
                message: `整體資料品質低於閾值: ${(qualityScores.overallScore * 100).toFixed(1)}%`,
                value: qualityScores.overallScore,
                threshold: this.options.alertThresholds.overall,
                timestamp: qualityScores.timestamp
            });
        }

        // 檢查各項指標
        for (const [key, rule] of this.qualityRules) {
            if (qualityScores[key]) {
                const metricName = key.replace('_check', '');
                const threshold = this.options.alertThresholds[metricName];

                if (threshold && qualityScores[key].score < threshold) {
                    alerts.push({
                        type: metricName,
                        severity: 'warning',
                        message: `${rule.name}品質低於閾值: ${(qualityScores[key].score * 100).toFixed(1)}%`,
                        value: qualityScores[key].score,
                        threshold: threshold,
                        timestamp: qualityScores.timestamp
                    });
                }
            }
        }

        // 處理告警
        for (const alert of alerts) {
            await this.handleQualityAlert(alert);
        }
    }

    /**
     * 處理品質告警
     */
    async handleQualityAlert(alert) {
        // 記錄告警到歷史
        this.alertHistory.push(alert);

        // 限制告警歷史長度
        if (this.alertHistory.length > 500) {
            this.alertHistory = this.alertHistory.slice(-500);
        }

        logger.warn('資料品質告警', {
            type: alert.type,
            message: alert.message,
            value: alert.value,
            threshold: alert.threshold,
            severity: alert.severity
        });

        this.emit('qualityAlert', alert);
    }

    /**
     * 獲取品質報告
     */
    getQualityReport(timeRange = 24 * 60 * 60 * 1000) {
        const cutoffTime = Date.now() - timeRange;
        const report = {
            timestamp: new Date(),
            timeRange,
            current: this.lastEvaluation,
            trends: {},
            summary: {}
        };

        // 計算趋势
        for (const [key, metrics] of Object.entries(this.qualityMetrics)) {
            if (Array.isArray(metrics)) {
                const recentMetrics = metrics.filter(m => m.timestamp.getTime() > cutoffTime);

                if (recentMetrics.length > 0) {
                    const values = recentMetrics.map(m => m.value);
                    report.trends[key] = {
                        average: values.reduce((sum, v) => sum + v, 0) / values.length,
                        min: Math.min(...values),
                        max: Math.max(...values),
                        latest: values[values.length - 1],
                        dataPoints: values.length,
                        trend: this.calculateTrend(recentMetrics)
                    };
                }
            }
        }

        // 生成摘要
        if (report.current) {
            report.summary = {
                overallQuality: report.current.overallScore,
                qualityGrade: this.getQualityGrade(report.current.overallScore),
                topIssues: this.getTopQualityIssues(report.current),
                recommendations: this.generateQualityRecommendations(report.current)
            };
        }

        return report;
    }

    /**
     * 計算趋势
     */
    calculateTrend(metrics) {
        if (metrics.length < 2) return 'stable';

        const firstHalf = metrics.slice(0, Math.floor(metrics.length / 2));
        const secondHalf = metrics.slice(Math.floor(metrics.length / 2));

        if (firstHalf.length === 0 || secondHalf.length === 0) return 'stable';

        const firstAvg = firstHalf.reduce((sum, m) => sum + m.value, 0) / firstHalf.length;
        const secondAvg = secondHalf.reduce((sum, m) => sum + m.value, 0) / secondHalf.length;

        const changePercent = ((secondAvg - firstAvg) / firstAvg) * 100;

        if (changePercent > 5) return 'improving';
        if (changePercent < -5) return 'declining';
        return 'stable';
    }

    /**
     * 獲取品質等級
     */
    getQualityGrade(score) {
        if (score >= 0.9) return 'A';
        if (score >= 0.8) return 'B';
        if (score >= 0.7) return 'C';
        if (score >= 0.6) return 'D';
        return 'F';
    }

    /**
     * 獲取主要品質問題
     */
    getTopQualityIssues(qualityScores) {
        const issues = [];

        for (const [key, rule] of this.qualityRules) {
            if (qualityScores[key] && qualityScores[key].score < 0.8) {
                issues.push({
                    metric: rule.name,
                    score: qualityScores[key].score,
                    impact: rule.weight
                });
            }
        }

        return issues.sort((a, b) => (b.impact * (1 - b.score)) - (a.impact * (1 - a.score)));
    }

    /**
     * 生成品質改善建議
     */
    generateQualityRecommendations(qualityScores) {
        const recommendations = [];

        for (const [key, rule] of this.qualityRules) {
            if (qualityScores[key] && qualityScores[key].score < 0.8) {
                switch (key) {
                    case 'required_fields':
                        recommendations.push('加強資料收集流程，確保必填欄位的完整性');
                        break;
                    case 'data_format':
                        recommendations.push('建立資料驗證規則，確保資料格式正確性');
                        break;
                    case 'consistency_check':
                        recommendations.push('實施資料一致性檢查，修復衝突資料');
                        break;
                    case 'freshness_check':
                        recommendations.push('增加資料更新頻率，保持資料時效性');
                        break;
                    case 'accuracy_check':
                        recommendations.push('建立資料準確性驗證機制');
                        break;
                }
            }
        }

        return recommendations;
    }

    /**
     * 獲取監控狀態
     */
    getMonitoringStatus() {
        return {
            isMonitoring: this.isMonitoring,
            lastEvaluation: this.lastEvaluation,
            evaluationInterval: this.options.evaluationInterval,
            qualityRules: Array.from(this.qualityRules.entries()).map(([key, rule]) => ({
                key,
                name: rule.name,
                weight: rule.weight
            })),
            alertThresholds: this.options.alertThresholds,
            metricsCount: Object.keys(this.qualityMetrics).reduce((sum, key) => {
                return sum + (Array.isArray(this.qualityMetrics[key]) ? this.qualityMetrics[key].length : 0);
            }, 0)
        };
    }

    /**
     * 關機清理
     */
    async shutdown() {
        logger.info('資料品質監控系統開始關機清理');

        await this.stopMonitoring();

        // 清理資料
        this.qualityMetrics = {
            overall: [],
            completeness: [],
            accuracy: [],
            consistency: [],
            freshness: [],
            validity: [],
            trends: new Map()
        };

        logger.info('資料品質監控系統關機完成');
    }
}

module.exports = DataQualityMonitor;