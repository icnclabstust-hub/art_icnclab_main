#!/usr/bin/env node
/**
 * Web Crawler Agent - 網路爬取代理
 * 專責爬取藝術史相關資料，支援多源數據採集
 */

const axios = require('axios');
const cheerio = require('cheerio');
const { chromium } = require('playwright');
const fs = require('fs/promises');
const path = require('path');
const EventEmitter = require('events');
const UnifiedErrorHandler = require('../../src/utils/unifiedErrorHandler');
const ConfigManager = require('../../src/config/configManager');
const PerformanceOptimizer = require('../../src/utils/performanceOptimizer');
const ParallelCrawler = require('../../src/utils/parallelCrawler');
const RateLimitManager = require('../../src/utils/rateLimitManager');
const CrawlerPerformanceMonitor = require('../../src/utils/crawlerPerformanceMonitor');

class WebCrawlerAgent extends EventEmitter {
    constructor() {
        super();
        this.id = 'web-crawler-agent';
        this.name = '網路爬取代理';
        this.status = 'initializing';
        this.version = '1.0.0';

        // 統一配置管理
        this.configManager = new ConfigManager();
        this.config = this.configManager.get('agents.webCrawler', {});

        // 爬取目標網站配置
        this.sources = {
            museums: {
                met: {
                    name: '大都會藝術博物館',
                    baseUrl: 'https://collectionapi.metmuseum.org/public/collection/v1',
                    rateLimit: 1000,
                    type: 'api'
                },
                louvre: {
                    name: '羅浮宮',
                    baseUrl: 'https://collections.louvre.fr',
                    rateLimit: 2000,
                    type: 'scraping'
                },
                british: {
                    name: '大英博物館',
                    baseUrl: 'https://www.britishmuseum.org',
                    rateLimit: 1500,
                    type: 'scraping'
                },
                europeana: {
                    name: '歐洲數位圖書館',
                    baseUrl: 'https://api.europeana.eu/record/v2',
                    searchUrl: 'https://api.europeana.eu/record/v2/search.json',
                    apiKey: 'ltureashbo',
                    rateLimit: 1000,
                    type: 'api'
                }
            },
            academic: {
                jstor: {
                    name: 'JSTOR',
                    baseUrl: 'https://www.jstor.org',
                    rateLimit: 3000,
                    type: 'rss'
                },
                academia: {
                    name: 'Academia.edu',
                    baseUrl: 'https://www.academia.edu',
                    rateLimit: 2000,
                    type: 'scraping'
                }
            }
        };

        // 任務隊列和狀態追蹤
        this.taskQueue = [];
        this.activeTasks = new Map();
        this.completedTasks = [];
        this.errors = [];

        // 瀏覽器實例（用於動態內容）
        this.browser = null;
        this.browserPages = [];

        // 數據輸出路徑
        this.outputDir = this.configManager.get('paths.raw', './data/raw');

        // 統一錯誤處理
        this.errorHandler = new UnifiedErrorHandler(this.id, {
            maxRetries: 3,
            retryDelay: 2000,
            circuitBreakerThreshold: 5,
            logPath: './logs/errors'
        });

        // 初始化性能優化器
        this.performanceOptimizer = new PerformanceOptimizer({
            memoryThreshold: 0.7,
            cpuThreshold: 0.6,
            minBatchSize: 5,
            maxBatchSize: 50,
            maxConcurrency: 6
        });

        // 初始化速率限制管理器
        this.rateLimitManager = new RateLimitManager({
            enableTokenBucket: true,
            enableSlidingWindow: true,
            enableAdaptiveRateLimit: true,
            defaultRateLimit: 60, // 每分鐘60個請求
            burstLimit: 10,
            windowSize: 60000, // 1分鐘窗口
            backoffMultiplier: 2,
            maxBackoffTime: 300000 // 最大5分鐘退避
        });

        // 初始化並行爬取系統
        this.parallelCrawler = new ParallelCrawler({
            maxConcurrency: this.config.maxConcurrency || 6,
            maxWorkerThreads: this.config.maxWorkerThreads || 4,
            useCluster: this.config.useCluster || false,
            enablePriority: true,
            enableLoadBalancing: true,
            enableAdaptiveScheduling: true,
            resourceMonitoring: true,
            queueSize: this.config.queueSize || 1000,
            retryAttempts: 3,
            timeoutMs: 60000,
            rateLimitManager: this.rateLimitManager // 整合速率限制管理器
        });

        // 初始化效能監控系統
        this.performanceMonitor = new CrawlerPerformanceMonitor({
            monitoringInterval: 30000, // 30秒
            statisticsInterval: 300000, // 5分鐘
            enableResourceMonitoring: true,
            enableNetworkMonitoring: true,
            enableDetailedLogging: this.config.enableDetailedLogging || false,
            alertThresholds: {
                cpuUsage: 0.8,
                memoryUsage: 0.8,
                errorRate: 0.1,
                responseTime: 10000
            }
        });

        // 監聽錯誤處理事件
        this.errorHandler.on('circuitBreakerOpened', (info) => {
            console.warn(`🚨 [${this.name}] 斷路器開啟: ${info.lastError}`);
            this.emit('circuitBreakerOpened', info);
        });

        this.errorHandler.on('patternDetected', (pattern) => {
            console.log(`🔍 [${this.name}] 錯誤模式檢測: ${pattern.pattern} (${pattern.count}次)`);
            this.emit('errorPatternDetected', pattern);
        });

        console.log(`🕷️ ${this.name} 初始化完成`);
    }

    /**
     * 初始化Agent
     */
    async initialize() {
        return await this.errorHandler.wrapAsync(async () => {
            this.status = 'initializing';
            console.log('🔧 正在初始化Web Crawler Agent...');

            // 確保輸出目錄存在
            await this.errorHandler.wrapAsync(async () => {
                await this.ensureDirectories();
            }, '確保輸出目錄存在');

            // 初始化瀏覽器（用於動態內容爬取）
            await this.errorHandler.wrapAsync(async () => {
                await this.initializeBrowser();
            }, '初始化瀏覽器', { maxRetries: 1 });

            // 初始化速率限制管理器
            await this.errorHandler.wrapAsync(async () => {
                await this.initializeRateLimits();
            }, '初始化速率限制管理器', { maxRetries: 1 });

            // 初始化並行爬取系統
            await this.errorHandler.wrapAsync(async () => {
                await this.parallelCrawler.initialize();
            }, '初始化並行爬取系統', { maxRetries: 1 });

            // 啟動效能監控
            await this.errorHandler.wrapAsync(async () => {
                this.performanceMonitor.start();
            }, '啟動效能監控系統', { maxRetries: 1 });

            // 測試網絡連通性
            await this.errorHandler.wrapAsync(async () => {
                await this.testConnectivity();
            }, '測試網絡連通性', { maxRetries: 2 });

            this.status = 'ready';
            console.log('✅ Web Crawler Agent 初始化完成');
            this.emit('initialized');

        }, 'Agent初始化');
    }

    /**
     * 初始化速率限制
     */
    async initializeRateLimits() {
        // 註冊所有資料源的速率限制配置
        const sourceConfigs = {
            // 博物館API配置
            ...Object.entries(this.sources.museums).map(([name, config]) => [name, {
                rateLimit: Math.floor(60000 / config.rateLimit), // 轉換為每分鐘請求數
                burstLimit: config.burstLimit || 10,
                windowSize: 60000,
                priority: config.priority,
                maxConcurrency: 3,
                respectRetryAfter: true
            }]),

            // 學術資源配置
            ...Object.entries(this.sources.academic).map(([name, config]) => [name, {
                rateLimit: Math.floor(60000 / config.rateLimit),
                burstLimit: config.burstLimit || 5,
                windowSize: 60000,
                priority: config.priority,
                maxConcurrency: 2,
                respectRetryAfter: true
            }])
        };

        // 註冊所有資料源
        for (const [source, config] of Object.entries(sourceConfigs)) {
            this.rateLimitManager.registerSource(source, config);
        }

        // 監聽速率限制事件
        this.rateLimitManager.on('requestDenied', (event) => {
            console.warn(`⏱️ 速率限制觸發: ${event.source} - ${event.reason}, 等待 ${event.waitTime}ms`);
        });

        this.rateLimitManager.on('backoffTriggered', (event) => {
            console.warn(`🔄 退避機制觸發: ${event.source} - ${event.reason}, 等級 ${event.level}, 等待 ${event.backoffTime}ms`);
        });

        console.log('🚦 速率限制管理器初始化完成');
    }

    /**
     * 確保輸出目錄存在
     */
    async ensureDirectories() {
        const dirs = [
            this.outputDir,
            path.join(this.outputDir, 'museums'),
            path.join(this.outputDir, 'academic'),
            path.join(this.outputDir, 'images'),
            path.join(this.outputDir, 'metadata')
        ];

        for (const dir of dirs) {
            await fs.mkdir(dir, { recursive: true });
        }

        console.log('📁 輸出目錄準備完成');
    }

    /**
     * 初始化瀏覽器
     */
    async initializeBrowser() {
        try {
            this.browser = await chromium.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-dev-shm-usage']
            });
            console.log('🌐 瀏覽器初始化完成');
        } catch (error) {
            console.warn('⚠️ 瀏覽器初始化失敗，將使用HTTP請求模式:', error.message);
        }
    }

    /**
     * 測試網絡連通性
     */
    async testConnectivity() {
        const testUrls = [
            'https://collectionapi.metmuseum.org/public/collection/v1/search?q=art',
            'https://www.louvre.fr',
            'https://www.britishmuseum.org',
            'https://api.europeana.eu/record/v2/search.json?wskey=ltureashbo&query=art&rows=1'
        ];

        const results = await Promise.allSettled(
            testUrls.map(url =>
                axios.get(url, {
                    timeout: 5000,
                    headers: { 'User-Agent': this.config.userAgent }
                })
            )
        );

        const successful = results.filter(r => r.status === 'fulfilled').length;
        console.log(`🌐 網絡連通性測試: ${successful}/${testUrls.length} 成功`);

        if (successful === 0) {
            throw new Error('無法連接到任何目標網站');
        }
    }

    /**
     * 開始爬取任務
     * @param {Object} config - 爬取配置
     * @param {Array} config.sources - 要爬取的來源
     * @param {Array} config.keywords - 搜索關鍵字
     * @param {number} config.maxItems - 最大項目數
     */
    async startCrawling(config = {}) {
        try {
            this.status = 'crawling';
            console.log('🚀 開始爬取任務...');

            const {
                sources = ['met', 'louvre'],
                keywords = ['renaissance', 'impressionism', 'baroque'],
                maxItems = 100
            } = config;

            // 生成爬取任務
            const tasks = this.generateCrawlTasks(sources, keywords, maxItems);
            console.log(`📋 生成了 ${tasks.length} 個爬取任務`);

            // 執行任務
            const results = await this.executeTasks(tasks);

            this.status = 'completed';
            console.log(`✅ 爬取完成，共收集 ${results.length} 項數據`);

            this.emit('crawlingComplete', {
                tasksCompleted: results.length,
                errors: this.errors.length,
                outputDir: this.outputDir
            });

            return results;

        } catch (error) {
            this.status = 'error';
            console.error('❌ 爬取任務失敗:', error.message);
            this.emit('error', error);
            throw error;
        }
    }

    /**
     * 生成爬取任務
     */
    generateCrawlTasks(sources, keywords, maxItems) {
        const tasks = [];
        const itemsPerSource = Math.ceil(maxItems / sources.length);

        for (const sourceName of sources) {
            // 找到對應的資料源配置
            let sourceConfig = null;
            let category = null;

            for (const [cat, sources_in_cat] of Object.entries(this.sources)) {
                if (sources_in_cat[sourceName]) {
                    sourceConfig = sources_in_cat[sourceName];
                    category = cat;
                    break;
                }
            }

            if (!sourceConfig) {
                console.warn(`⚠️ 未找到資料源配置: ${sourceName}`);
                continue;
            }

            // 為每個關鍵字生成任務
            for (const keyword of keywords) {
                tasks.push({
                    id: `${sourceName}-${keyword}-${Date.now()}`,
                    source: sourceName,
                    category,
                    config: sourceConfig,
                    keyword,
                    maxItems: Math.ceil(itemsPerSource / keywords.length),
                    status: 'pending'
                });
            }
        }

        return tasks;
    }

    /**
     * 執行爬取任務（使用並行系統）
     */
    async executeTasks(tasks) {
        console.log(`🔄 使用並行爬取系統執行 ${tasks.length} 個任務`);

        // 設置並行爬取事件監聽器
        this.setupParallelCrawlerEvents();

        // 將所有任務轉換為並行爬取任務格式並加入隊列
        const taskConfigs = tasks.map(task => this.convertToParallelTask(task));
        const taskIds = this.parallelCrawler.addTasks(taskConfigs);

        console.log(`📋 已加入 ${taskIds.length} 個任務到並行隊列`);

        // 等待所有任務完成
        const results = await this.waitForTasksCompletion(taskIds);

        console.log(`✅ 並行爬取完成，收集了 ${results.length} 項數據`);
        return results;
    }

    /**
     * 將原始任務轉換為並行任務格式
     */
    convertToParallelTask(task) {
        const sourceConfig = this.sources.museums[task.source] || this.sources.academic[task.source];

        let taskType = 'api';
        let taskConfig = {
            source: task.source,
            url: this.buildTaskUrl(task, sourceConfig),
            type: sourceConfig?.type || 'api',
            method: 'GET',
            params: this.buildTaskParams(task),
            headers: {
                'User-Agent': this.config.userAgent || 'ArtHistoryDatabase/1.0'
            },
            maxItems: task.maxItems || 50
        };

        // 針對不同源的特殊處理
        if (task.source === 'met') {
            taskConfig.processor = 'metMuseum';
        } else if (task.source === 'europeana') {
            taskConfig.processor = 'europeana';
            taskConfig.params.wskey = sourceConfig.apiKey;
        } else if (task.source === 'louvre') {
            taskConfig.type = 'scraping';
            taskConfig.selectors = {
                container: '.search-result-item',
                fields: {
                    title: 'h3',
                    artist: '.artist',
                    date: '.date'
                },
                image: 'img',
                link: 'a'
            };
        }

        return {
            ...taskConfig,
            priority: this.getTaskPriority(task.source),
            metadata: {
                originalTask: task,
                category: task.category,
                keyword: task.keyword
            }
        };
    }

    /**
     * 構建任務URL
     */
    buildTaskUrl(task, sourceConfig) {
        const baseUrl = sourceConfig.baseUrl;

        switch (task.source) {
            case 'met':
                return `${baseUrl}/search`;
            case 'europeana':
                return sourceConfig.searchUrl;
            case 'louvre':
                return `${baseUrl}/en/explore/search`;
            default:
                return baseUrl;
        }
    }

    /**
     * 構建任務參數
     */
    buildTaskParams(task) {
        const params = {};

        switch (task.source) {
            case 'met':
                params.q = task.keyword;
                params.hasImages = 'true';
                break;
            case 'europeana':
                params.query = task.keyword;
                params.rows = task.maxItems || 50;
                params.qf = 'TYPE:IMAGE';
                params.profile = 'rich';
                break;
            case 'louvre':
                params.q = task.keyword;
                break;
            default:
                params.q = task.keyword;
        }

        return params;
    }

    /**
     * 獲取任務優先級
     */
    getTaskPriority(source) {
        const priorityMap = {
            'met': 'high',
            'europeana': 'high',
            'louvre': 'medium',
            'british': 'medium',
            'jstor': 'low',
            'academia': 'low'
        };

        return priorityMap[source] || 'medium';
    }

    /**
     * 設置並行爬取事件監聽器
     */
    setupParallelCrawlerEvents() {
        if (this.parallelEventsSetup) return;

        this.parallelCrawler.on('taskCompleted', (task, result) => {
            console.log(`✅ 並行任務完成: ${task.config.source} - ${task.config.metadata?.keyword}`);
        });

        this.parallelCrawler.on('taskFailed', (task, error) => {
            console.error(`❌ 並行任務失敗: ${task.config.source} - ${error}`);
            this.errors.push({
                task: task.id,
                error: error,
                timestamp: new Date()
            });
        });

        this.parallelCrawler.on('taskStarted', (task) => {
            console.log(`🎯 開始並行任務: ${task.config.source} - ${task.config.metadata?.keyword}`);
        });

        this.parallelEventsSetup = true;
    }

    /**
     * 等待所有任務完成
     */
    async waitForTasksCompletion(taskIds, timeoutMs = 300000) {
        return new Promise((resolve) => {
            const results = [];
            const completedTaskIds = new Set();
            const failedTaskIds = new Set();

            const taskCompletedHandler = (task, result) => {
                if (taskIds.includes(task.id)) {
                    completedTaskIds.add(task.id);

                    // 處理結果數據
                    if (result && result.items) {
                        results.push(...result.items);
                    }

                    this.completedTasks.push(task.config.metadata?.originalTask || task);

                    checkCompletion();
                }
            };

            const taskFailedHandler = (task, error) => {
                if (taskIds.includes(task.id)) {
                    failedTaskIds.add(task.id);

                    const originalTask = task.config.metadata?.originalTask || task;
                    originalTask.status = 'failed';
                    originalTask.error = error;

                    checkCompletion();
                }
            };

            const checkCompletion = () => {
                const totalCompleted = completedTaskIds.size + failedTaskIds.size;
                if (totalCompleted >= taskIds.length) {
                    this.parallelCrawler.off('taskCompleted', taskCompletedHandler);
                    this.parallelCrawler.off('taskFailed', taskFailedHandler);

                    console.log(`📊 任務完成統計: 成功 ${completedTaskIds.size}, 失敗 ${failedTaskIds.size}`);
                    resolve(results);
                }
            };

            // 註冊事件監聽器
            this.parallelCrawler.on('taskCompleted', taskCompletedHandler);
            this.parallelCrawler.on('taskFailed', taskFailedHandler);

            // 設置超時
            setTimeout(() => {
                this.parallelCrawler.off('taskCompleted', taskCompletedHandler);
                this.parallelCrawler.off('taskFailed', taskFailedHandler);

                console.warn(`⏰ 任務執行超時，已完成 ${completedTaskIds.size}/${taskIds.length} 個任務`);
                resolve(results);
            }, timeoutMs);
        });
    }

    /**
     * 執行單個爬取任務
     */
    async executeTask(task) {
        console.log(`🎯 執行任務: ${task.source} - ${task.keyword}`);

        switch (task.source) {
            case 'met':
                return await this.crawlMetMuseum(task);
            case 'louvre':
                return await this.crawlLouvre(task);
            case 'british':
                return await this.crawlBritishMuseum(task);
            case 'europeana':
                return await this.crawlEuropeana(task);
            case 'jstor':
                return await this.crawlJSTOR(task);
            default:
                throw new Error(`不支持的資料源: ${task.source}`);
        }
    }

    /**
     * 爬取大都會博物館API
     */
    async crawlMetMuseum(task) {
        try {
            // 搜索藝術品
            const searchUrl = `${task.config.baseUrl}/search?q=${encodeURIComponent(task.keyword)}&hasImages=true`;
            const searchResponse = await axios.get(searchUrl, {
                headers: { 'User-Agent': this.config.userAgent },
                timeout: this.config.timeout
            });

            const objectIDs = searchResponse.data.objectIDs || [];
            const limitedIDs = objectIDs.slice(0, task.maxItems);

            const artworks = [];

            // 獲取每個藝術品的詳細信息
            for (const objectID of limitedIDs) {
                try {
                    const detailUrl = `${task.config.baseUrl}/objects/${objectID}`;
                    const detailResponse = await axios.get(detailUrl, {
                        headers: { 'User-Agent': this.config.userAgent },
                        timeout: this.config.timeout
                    });

                    const artwork = this.processMetArtwork(detailResponse.data);
                    if (artwork) {
                        artworks.push(artwork);

                        // 下載圖片（如果有）
                        if (artwork.primaryImage) {
                            await this.downloadImage(artwork.primaryImage, artwork.objectID, 'met');
                        }
                    }

                    await this.delay(task.config.rateLimit);
                } catch (error) {
                    console.warn(`⚠️ 獲取作品詳情失敗 ${objectID}:`, error.message);
                }
            }

            // 保存數據
            await this.saveData(artworks, `met_${task.keyword}`, 'museums');

            console.log(`✅ Met Museum ${task.keyword}: 收集了 ${artworks.length} 件作品`);
            return artworks;

        } catch (error) {
            console.error(`❌ Met Museum 爬取失敗:`, error.message);
            throw error;
        }
    }

    /**
     * 處理Met Museum藝術品數據
     */
    processMetArtwork(data) {
        if (!data || !data.title) return null;

        return {
            source: 'met',
            objectID: data.objectID,
            title: data.title,
            artist: data.artistDisplayName || 'Unknown',
            date: data.objectDate || '',
            medium: data.medium || '',
            dimensions: data.dimensions || '',
            culture: data.culture || '',
            period: data.period || '',
            dynasty: data.dynasty || '',
            classification: data.classification || '',
            department: data.department || '',
            primaryImage: data.primaryImage || '',
            additionalImages: data.additionalImages || [],
            description: data.metadataDate || '',
            url: `https://www.metmuseum.org/art/collection/search/${data.objectID}`,
            crawledAt: new Date().toISOString(),
            metadata: {
                isHighlight: data.isHighlight,
                accessionYear: data.accessionYear,
                repository: data.repository,
                tags: data.tags || []
            }
        };
    }

    /**
     * 爬取羅浮宮（使用網頁爬取）
     */
    async crawlLouvre(task) {
        if (!this.browser) {
            console.warn('⚠️ 瀏覽器未可用，跳過Louvre爬取');
            return [];
        }

        try {
            const page = await this.browser.newPage();
            await page.setUserAgent(this.config.userAgent);

            // 導航到搜索頁面
            const searchUrl = `${task.config.baseUrl}/en/explore/search?q=${encodeURIComponent(task.keyword)}`;
            await page.goto(searchUrl, { waitUntil: 'networkidle' });

            // 等待內容加載
            await page.waitForSelector('.search-results', { timeout: 10000 });

            // 提取搜索結果
            const artworks = await page.evaluate(() => {
                const results = [];
                // eslint-disable-next-line no-undef -- page.evaluate 在瀏覽器語境執行，document 存在
                const items = document.querySelectorAll('.search-result-item');

                items.forEach(item => {
                    const title = item.querySelector('h3')?.textContent?.trim();
                    const artist = item.querySelector('.artist')?.textContent?.trim();
                    const image = item.querySelector('img')?.src;
                    const link = item.querySelector('a')?.href;

                    if (title) {
                        results.push({
                            source: 'louvre',
                            title,
                            artist: artist || 'Unknown',
                            primaryImage: image,
                            url: link,
                            crawledAt: new Date().toISOString()
                        });
                    }
                });

                return results.slice(0, 20); // 限制結果數量
            });

            await page.close();

            // 保存數據
            await this.saveData(artworks, `louvre_${task.keyword}`, 'museums');

            console.log(`✅ Louvre ${task.keyword}: 收集了 ${artworks.length} 件作品`);
            return artworks;

        } catch (error) {
            console.error(`❌ Louvre 爬取失敗:`, error.message);
            throw error;
        }
    }

    /**
     * 爬取歐洲數位圖書館 (Europeana API)
     */
    async crawlEuropeana(task) {
        try {
            console.log(`🇪🇺 開始爬取 Europeana - ${task.keyword}`);

            // 建構搜索查詢
            const searchParams = new URLSearchParams({
                wskey: task.config.apiKey,
                query: task.keyword,
                rows: Math.min(task.maxItems, 100), // Europeana 單次最大100筆
                qf: 'TYPE:IMAGE', // 只搜索圖片類型
                profile: 'rich', // 獲取豐富的元數據
                sort: 'score desc' // 按相關性排序
            });

            const searchUrl = `${task.config.searchUrl}?${searchParams.toString()}`;

            const response = await axios.get(searchUrl, {
                headers: {
                    'User-Agent': this.config.userAgent || 'ArtHistoryDatabase/1.0'
                },
                timeout: this.config.timeout || 10000
            });

            if (!response.data.success) {
                throw new Error(`Europeana API 回應錯誤: ${response.data.error}`);
            }

            const items = response.data.items || [];
            const artworks = [];

            console.log(`📦 Europeana 返回 ${items.length} 項結果`);

            // 處理每個項目
            for (const item of items) {
                try {
                    const artwork = this.processEuropeanaArtwork(item, task.keyword);
                    if (artwork) {
                        artworks.push(artwork);

                        // 下載縮略圖（如果有）
                        if (artwork.thumbnail) {
                            await this.downloadImage(
                                artwork.thumbnail,
                                artwork.id.replace(/[^a-zA-Z0-9]/g, '_'),
                                'europeana'
                            );
                        }
                    }

                    // 避免過於頻繁的請求
                    await this.delay(100);
                } catch (error) {
                    console.warn(`⚠️ 處理 Europeana 項目失敗:`, error.message);
                }
            }

            // 保存數據
            await this.saveData(artworks, `europeana_${task.keyword}`, 'museums');

            console.log(`✅ Europeana ${task.keyword}: 收集了 ${artworks.length} 件作品`);
            return artworks;

        } catch (error) {
            console.error(`❌ Europeana 爬取失敗:`, error.message);

            // 如果是API配額問題，記錄特殊錯誤
            if (error.response?.status === 429) {
                console.error('🚨 Europeana API 配額已耗盡，請稍後再試');
            } else if (error.response?.status === 401) {
                console.error('🔑 Europeana API Key 無效，請檢查配置');
            }

            throw error;
        }
    }

    /**
     * 處理 Europeana 藝術品數據
     */
    processEuropeanaArtwork(item, searchKeyword) {
        if (!item || !item.title) return null;

        // 提取圖片URLs
        const getImageUrl = (item) => {
            if (item.edmPreview && item.edmPreview.length > 0) {
                return item.edmPreview[0];
            }
            if (item.edmIsShownBy && item.edmIsShownBy.length > 0) {
                return item.edmIsShownBy[0];
            }
            return null;
        };

        // 處理多語言標題
        const getLocalizedText = (textObj) => {
            if (!textObj) return '';
            if (typeof textObj === 'string') return textObj;
            if (Array.isArray(textObj)) return textObj[0] || '';

            // 優先順序：英文 > 任何其他語言
            return textObj.en?.[0] ||
                   textObj.de?.[0] ||
                   textObj.fr?.[0] ||
                   textObj.it?.[0] ||
                   Object.values(textObj)[0]?.[0] || '';
        };

        return {
            source: 'europeana',
            id: item.id || '',
            europeanaId: item.id,
            title: getLocalizedText(item.title),
            creator: getLocalizedText(item.dcCreator) ||
                    getLocalizedText(item.dcContributor) || 'Unknown',
            date: getLocalizedText(item.dcDate) ||
                  getLocalizedText(item.year) || '',
            type: getLocalizedText(item.type) ||
                  getLocalizedText(item.dcType) || '',
            description: getLocalizedText(item.dcDescription) || '',
            subject: getLocalizedText(item.dcSubject) || '',
            format: getLocalizedText(item.dcFormat) || '',
            language: getLocalizedText(item.dcLanguage) || '',
            coverage: getLocalizedText(item.dcCoverage) || '',

            // 圖片資料
            thumbnail: getImageUrl(item),
            edmPreview: item.edmPreview || [],
            edmIsShownBy: item.edmIsShownBy || [],
            edmIsShownAt: item.edmIsShownAt || [],

            // 權利和來源資訊
            rights: getLocalizedText(item.rights) || '',
            dataProvider: getLocalizedText(item.dataProvider) || '',
            provider: getLocalizedText(item.provider) || '',
            country: item.country || '',

            // 分類和標籤
            dctermsMedial: item.dctermsMedial || [],
            edmConceptPrefLabel: item.edmConceptPrefLabel || [],
            edmTimespanLabel: item.edmTimespanLabel || [],
            edmPlaceLabel: item.edmPlaceLabel || [],

            // 搜索元數據
            searchKeyword: searchKeyword,
            completeness: item.completeness || 0,

            // URLs
            europeanaUrl: `https://www.europeana.eu/item${item.id}`,
            originalUrl: item.edmIsShownAt?.[0] || '',

            // 爬取時間戳
            crawledAt: new Date().toISOString(),

            // 額外元數據
            metadata: {
                score: item.score || 0,
                edmDatasetName: item.edmDatasetName || [],
                edmHasView: item.edmHasView || [],
                edmUgc: item.edmUgc || false,
                europeanaCollectionName: item.europeanaCollectionName || [],
                timestamp_created: item.timestamp_created,
                timestamp_update: item.timestamp_update
            }
        };
    }

    /**
     * 爬取大英博物館
     */
    async crawlBritishMuseum(task) {
        // 大英博物館爬取實現
        console.log(`🏛️ British Museum 爬取 - ${task.keyword} (待實現)`);
        return [];
    }

    /**
     * 爬取JSTOR學術資源
     */
    async crawlJSTOR(task) {
        // JSTOR爬取實現
        console.log(`📚 JSTOR 爬取 - ${task.keyword} (待實現)`);
        return [];
    }

    /**
     * 下載圖片
     */
    async downloadImage(imageUrl, objectID, source) {
        if (!imageUrl) return;

        try {
            const response = await axios.get(imageUrl, {
                responseType: 'stream',
                timeout: this.config.timeout,
                headers: { 'User-Agent': this.config.userAgent }
            });

            const extension = path.extname(imageUrl) || '.jpg';
            const filename = `${source}_${objectID}${extension}`;
            const filepath = path.join(this.outputDir, 'images', filename);

            const writer = fs.createWriteStream(filepath);
            response.data.pipe(writer);

            return new Promise((resolve, reject) => {
                writer.on('finish', resolve);
                writer.on('error', reject);
            });

        } catch (error) {
            console.warn(`⚠️ 圖片下載失敗 ${imageUrl}:`, error.message);
        }
    }

    /**
     * 保存數據到文件
     */
    async saveData(data, filename, category) {
        if (!data || data.length === 0) return;

        const filepath = path.join(this.outputDir, category, `${filename}_${Date.now()}.json`);
        await fs.writeFile(filepath, JSON.stringify(data, null, 2), 'utf8');

        console.log(`💾 數據已保存到: ${filepath}`);
    }

    /**
     * 延遲函數
     */
    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 停止Agent
     */
    async stop() {
        console.log('⏹️ 停止Web Crawler Agent...');
        this.status = 'stopping';

        // 關閉瀏覽器
        if (this.browser) {
            await this.browser.close();
            console.log('🌐 瀏覽器已關閉');
        }

        this.status = 'stopped';
        console.log('✅ Web Crawler Agent 已停止');
        this.emit('stopped');
    }

    /**
     * 獲取Agent狀態
     */
    getStatus() {
        return {
            id: this.id,
            name: this.name,
            status: this.status,
            version: this.version,
            statistics: {
                taskQueue: this.taskQueue.length,
                activeTasks: this.activeTasks.size,
                completedTasks: this.completedTasks.length,
                errors: this.errors.length
            },
            config: this.config
        };
    }
}

module.exports = WebCrawlerAgent;

// 如果直接運行此文件
if (require.main === module) {
    const agent = new WebCrawlerAgent();

    agent.on('initialized', async () => {
        console.log('🚀 開始測試爬取...');
        await agent.startCrawling({
            sources: ['met'],
            keywords: ['renaissance'],
            maxItems: 5
        });
        await agent.stop();
        process.exit(0);
    });

    agent.on('error', (error) => {
        console.error('❌ Agent錯誤:', error);
        process.exit(1);
    });

    agent.initialize();
}