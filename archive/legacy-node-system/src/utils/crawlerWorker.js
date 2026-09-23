/**
 * 爬蟲工作執行緒
 * 在獨立的執行緒中執行爬取任務，提供資源隔離和錯誤恢復
 */

const { parentPort, workerData } = require('worker_threads');
const axios = require('axios');
const cheerio = require('cheerio');
const { logger } = require('./logger');
const UnifiedErrorHandler = require('./unifiedErrorHandler');

class CrawlerWorker {
    constructor(workerId, options = {}) {
        this.workerId = workerId;
        this.options = {
            timeout: options.timeout || 30000,
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 1000,
            userAgent: options.userAgent || 'ArtHistoryDatabase/1.0',
            ...options
        };

        // 任務執行狀態
        this.currentTask = null;
        this.isProcessing = false;
        this.tasksCompleted = 0;

        // 錯誤處理
        this.errorHandler = new UnifiedErrorHandler(`CrawlerWorker-${workerId}`, {
            maxRetries: this.options.maxRetries,
            retryDelay: this.options.retryDelay,
            enableCircuitBreaker: true
        });

        // HTTP客戶端配置
        this.httpClient = axios.create({
            timeout: this.options.timeout,
            headers: {
                'User-Agent': this.options.userAgent
            },
            maxRedirects: 5
        });

        this.setupMessageHandling();

        logger.info('爬蟲工作執行緒初始化', { workerId });
    }

    /**
     * 設置消息處理
     */
    setupMessageHandling() {
        if (parentPort) {
            parentPort.on('message', async (message) => {
                try {
                    await this.handleMessage(message);
                } catch (error) {
                    logger.error('處理消息失敗', {
                        workerId: this.workerId,
                        error: error.message
                    });

                    this.sendMessage({
                        type: 'error',
                        error: error.message
                    });
                }
            });

            // 通知主執行緒工作執行緒已準備就緒
            this.sendMessage({
                type: 'workerReady',
                workerId: this.workerId
            });
        }
    }

    /**
     * 處理來自主執行緒的消息
     */
    async handleMessage(message) {
        const { type, task } = message;

        switch (type) {
            case 'executeTask':
                await this.executeTask(task);
                break;

            case 'cancelTask':
                await this.cancelCurrentTask(message.taskId);
                break;

            case 'ping':
                this.sendMessage({
                    type: 'pong',
                    workerId: this.workerId,
                    isProcessing: this.isProcessing
                });
                break;

            default:
                logger.warn('未知消息類型', { type, workerId: this.workerId });
        }
    }

    /**
     * 執行爬取任務
     */
    async executeTask(task) {
        if (this.isProcessing) {
            logger.warn('工作執行緒忙碌中，無法執行新任務', {
                workerId: this.workerId,
                currentTask: this.currentTask?.id
            });
            return;
        }

        this.currentTask = task;
        this.isProcessing = true;

        const startTime = Date.now();

        try {
            logger.info('開始執行任務', {
                workerId: this.workerId,
                taskId: task.id,
                type: task.config.type
            });

            // 根據任務類型執行不同的爬取策略
            let result;
            switch (task.config.type) {
                case 'api':
                    result = await this.executeApiTask(task);
                    break;
                case 'scraping':
                    result = await this.executeScrapingTask(task);
                    break;
                case 'rss':
                    result = await this.executeRssTask(task);
                    break;
                default:
                    throw new Error(`不支持的任務類型: ${task.config.type}`);
            }

            const executionTime = Date.now() - startTime;

            this.sendMessage({
                type: 'taskCompleted',
                taskId: task.id,
                result: result,
                executionTime: executionTime,
                workerId: this.workerId
            });

            this.tasksCompleted++;

            logger.info('任務執行完成', {
                workerId: this.workerId,
                taskId: task.id,
                executionTime: executionTime,
                resultCount: result?.items?.length || 0
            });

        } catch (error) {
            const executionTime = Date.now() - startTime;

            logger.error('任務執行失敗', {
                workerId: this.workerId,
                taskId: task.id,
                error: error.message,
                executionTime: executionTime
            });

            this.sendMessage({
                type: 'taskFailed',
                taskId: task.id,
                error: error.message,
                workerId: this.workerId
            });

        } finally {
            this.currentTask = null;
            this.isProcessing = false;

            // 通知主執行緒工作執行緒已準備處理下一個任務
            this.sendMessage({
                type: 'workerReady',
                workerId: this.workerId
            });
        }
    }

    /**
     * 執行API類型任務
     */
    async executeApiTask(task) {
        return await this.errorHandler.wrapAsync(async () => {
            const { config } = task;
            const { url, method = 'GET', params = {}, headers = {} } = config;

            // 發送進度更新
            this.sendProgress(task.id, 0, '開始API請求');

            const response = await this.httpClient({
                method,
                url,
                params,
                headers: {
                    ...this.httpClient.defaults.headers,
                    ...headers
                }
            });

            this.sendProgress(task.id, 50, '處理API響應');

            // 處理API響應數據
            const processedData = await this.processApiResponse(response.data, config);

            this.sendProgress(task.id, 100, '完成API請求');

            return {
                source: config.source,
                type: 'api',
                items: processedData,
                metadata: {
                    url,
                    responseStatus: response.status,
                    responseHeaders: response.headers,
                    crawledAt: new Date().toISOString()
                }
            };

        }, '執行API任務');
    }

    /**
     * 執行網頁爬取任務
     */
    async executeScrapingTask(task) {
        return await this.errorHandler.wrapAsync(async () => {
            const { config } = task;
            const { url, selectors } = config;

            this.sendProgress(task.id, 0, '開始網頁爬取');

            const response = await this.httpClient.get(url);
            const $ = cheerio.load(response.data);

            this.sendProgress(task.id, 30, '解析HTML內容');

            const items = [];

            // 根據選擇器提取數據
            $(selectors.container || 'body').each((index, element) => {
                const item = {};

                for (const [field, selector] of Object.entries(selectors.fields || {})) {
                    const value = $(element).find(selector).text().trim();
                    if (value) {
                        item[field] = value;
                    }
                }

                // 提取圖片URL
                if (selectors.image) {
                    const imageUrl = $(element).find(selectors.image).attr('src') ||
                                   $(element).find(selectors.image).attr('data-src');
                    if (imageUrl) {
                        item.imageUrl = this.resolveUrl(imageUrl, url);
                    }
                }

                // 提取連結URL
                if (selectors.link) {
                    const linkUrl = $(element).find(selectors.link).attr('href');
                    if (linkUrl) {
                        item.linkUrl = this.resolveUrl(linkUrl, url);
                    }
                }

                if (Object.keys(item).length > 0) {
                    items.push({
                        ...item,
                        extractedAt: new Date().toISOString()
                    });
                }
            });

            this.sendProgress(task.id, 80, '處理提取數據');

            // 後處理數據
            const processedItems = await this.postProcessItems(items, config);

            this.sendProgress(task.id, 100, '完成網頁爬取');

            return {
                source: config.source,
                type: 'scraping',
                items: processedItems,
                metadata: {
                    url,
                    responseStatus: response.status,
                    itemsExtracted: processedItems.length,
                    crawledAt: new Date().toISOString()
                }
            };

        }, '執行爬取任務');
    }

    /**
     * 執行RSS任務
     */
    async executeRssTask(task) {
        return await this.errorHandler.wrapAsync(async () => {
            const { config } = task;
            const { url } = config;

            this.sendProgress(task.id, 0, '開始RSS爬取');

            const response = await this.httpClient.get(url);
            const $ = cheerio.load(response.data, { xmlMode: true });

            this.sendProgress(task.id, 50, '解析RSS內容');

            const items = [];

            $('item, entry').each((index, element) => {
                const $item = $(element);

                const item = {
                    title: $item.find('title').text().trim(),
                    description: $item.find('description, content, summary').text().trim(),
                    link: $item.find('link').text().trim() || $item.find('link').attr('href'),
                    pubDate: $item.find('pubDate, published, updated').text().trim(),
                    author: $item.find('author, creator').text().trim(),
                    category: $item.find('category').text().trim(),
                    guid: $item.find('guid, id').text().trim(),
                    extractedAt: new Date().toISOString()
                };

                if (item.title) {
                    items.push(item);
                }
            });

            this.sendProgress(task.id, 100, '完成RSS爬取');

            return {
                source: config.source,
                type: 'rss',
                items: items,
                metadata: {
                    url,
                    responseStatus: response.status,
                    itemsExtracted: items.length,
                    crawledAt: new Date().toISOString()
                }
            };

        }, '執行RSS任務');
    }

    /**
     * 處理API響應
     */
    async processApiResponse(data, config) {
        try {
            // 根據不同的API源處理數據
            switch (config.source) {
                case 'met':
                    return this.processMetMuseumApi(data, config);
                case 'europeana':
                    return this.processEuropeanaApi(data, config);
                default:
                    return Array.isArray(data) ? data : [data];
            }
        } catch (error) {
            logger.error('處理API響應失敗', {
                source: config.source,
                error: error.message
            });
            return [];
        }
    }

    /**
     * 處理Met Museum API數據
     */
    processMetMuseumApi(data, config) {
        const items = [];

        if (data.objectIDs && Array.isArray(data.objectIDs)) {
            // 搜索結果
            data.objectIDs.slice(0, config.maxItems || 50).forEach(objectID => {
                items.push({
                    objectID,
                    source: 'met',
                    type: 'artwork_reference',
                    needsDetailFetch: true
                });
            });
        } else if (data.objectID) {
            // 詳細信息
            items.push({
                objectID: data.objectID,
                title: data.title,
                artist: data.artistDisplayName || 'Unknown',
                date: data.objectDate || '',
                medium: data.medium || '',
                dimensions: data.dimensions || '',
                culture: data.culture || '',
                classification: data.classification || '',
                department: data.department || '',
                primaryImage: data.primaryImage || '',
                additionalImages: data.additionalImages || [],
                url: `https://www.metmuseum.org/art/collection/search/${data.objectID}`,
                source: 'met',
                type: 'artwork_detail'
            });
        }

        return items;
    }

    /**
     * 處理Europeana API數據
     */
    processEuropeanaApi(data, config) {
        const items = [];

        if (data.items && Array.isArray(data.items)) {
            data.items.forEach(item => {
                const processedItem = {
                    id: item.id,
                    title: this.getLocalizedText(item.title),
                    creator: this.getLocalizedText(item.dcCreator) ||
                            this.getLocalizedText(item.dcContributor) || 'Unknown',
                    date: this.getLocalizedText(item.dcDate) ||
                          this.getLocalizedText(item.year) || '',
                    type: this.getLocalizedText(item.type) ||
                          this.getLocalizedText(item.dcType) || '',
                    description: this.getLocalizedText(item.dcDescription) || '',
                    rights: this.getLocalizedText(item.rights) || '',
                    dataProvider: this.getLocalizedText(item.dataProvider) || '',
                    provider: this.getLocalizedText(item.provider) || '',
                    country: item.country || '',
                    thumbnail: item.edmPreview?.[0] || '',
                    url: `https://www.europeana.eu/item${item.id}`,
                    source: 'europeana'
                };

                items.push(processedItem);
            });
        }

        return items;
    }

    /**
     * 獲取本地化文本
     */
    getLocalizedText(textObj) {
        if (!textObj) return '';
        if (typeof textObj === 'string') return textObj;
        if (Array.isArray(textObj)) return textObj[0] || '';

        return textObj.en?.[0] ||
               textObj.de?.[0] ||
               textObj.fr?.[0] ||
               textObj.it?.[0] ||
               Object.values(textObj)[0]?.[0] || '';
    }

    /**
     * 後處理項目
     */
    async postProcessItems(items, config) {
        // 清理和標準化數據
        return items.map(item => {
            // 清理HTML標籤
            Object.keys(item).forEach(key => {
                if (typeof item[key] === 'string') {
                    item[key] = this.cleanHtml(item[key]);
                }
            });

            // 添加額外元數據
            item.source = config.source;
            item.crawlTimestamp = Date.now();

            return item;
        });
    }

    /**
     * 清理HTML標籤
     */
    cleanHtml(text) {
        if (!text) return '';
        return text
            .replace(/<[^>]*>/g, '') // 移除HTML標籤
            .replace(/\s+/g, ' ')    // 合併多個空白字符
            .trim();                 // 移除前後空白
    }

    /**
     * 解析相對URL為絕對URL
     */
    resolveUrl(relativeUrl, baseUrl) {
        if (!relativeUrl) return '';
        if (relativeUrl.startsWith('http')) return relativeUrl;

        try {
            return new URL(relativeUrl, baseUrl).href;
        } catch (error) {
            logger.warn('URL解析失敗', { relativeUrl, baseUrl });
            return relativeUrl;
        }
    }

    /**
     * 取消當前任務
     */
    async cancelCurrentTask(taskId) {
        if (this.currentTask && this.currentTask.id === taskId) {
            logger.info('取消任務', {
                workerId: this.workerId,
                taskId: taskId
            });

            this.currentTask = null;
            this.isProcessing = false;

            this.sendMessage({
                type: 'taskCancelled',
                taskId: taskId,
                workerId: this.workerId
            });
        }
    }

    /**
     * 發送進度更新
     */
    sendProgress(taskId, progress, message) {
        this.sendMessage({
            type: 'progress',
            taskId: taskId,
            progress: {
                percentage: progress,
                message: message,
                timestamp: Date.now()
            },
            workerId: this.workerId
        });
    }

    /**
     * 發送消息到主執行緒
     */
    sendMessage(message) {
        if (parentPort) {
            parentPort.postMessage(message);
        }
    }

    /**
     * 獲取工作執行緒狀態
     */
    getStatus() {
        return {
            workerId: this.workerId,
            isProcessing: this.isProcessing,
            currentTask: this.currentTask?.id || null,
            tasksCompleted: this.tasksCompleted
        };
    }
}

// 初始化工作執行緒
if (workerData) {
    const worker = new CrawlerWorker(workerData.workerId, workerData.options);

    // 處理未捕獲的異常
    process.on('uncaughtException', (error) => {
        logger.error('工作執行緒未捕獲異常', {
            workerId: workerData.workerId,
            error: error.message
        });

        if (parentPort) {
            parentPort.postMessage({
                type: 'uncaughtException',
                error: error.message,
                workerId: workerData.workerId
            });
        }

        process.exit(1);
    });

    process.on('unhandledRejection', (reason, promise) => {
        logger.error('工作執行緒未處理的Promise拒絕', {
            workerId: workerData.workerId,
            reason: reason
        });

        if (parentPort) {
            parentPort.postMessage({
                type: 'unhandledRejection',
                reason: reason,
                workerId: workerData.workerId
            });
        }
    });
}

module.exports = CrawlerWorker;