/**
 * 測試資料生成器
 * 為測試提供一致的測試資料
 */

const { v4: uuidv4 } = require('uuid');

class TestDataGenerator {
    constructor() {
        this.createdIds = [];
    }

    // 生成測試藝術家資料
    generateArtistData(overrides = {}) {
        const baseData = {
            name: 'Test Artist ' + Date.now(),
            name_variants: ['Artist Variant 1', 'Artist Variant 2'],
            birth_year: 1800 + Math.floor(Math.random() * 200),
            death_year: null,
            nationality: 'Test Nationality',
            art_movement: 'Test Movement',
            biography: 'This is a test artist biography for testing purposes.',
            source_urls: ['https://test.example.com/artist'],
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        // 隨機決定是否有死亡年份
        if (Math.random() > 0.5 && baseData.birth_year) {
            baseData.death_year = baseData.birth_year + Math.floor(Math.random() * 80) + 20;
        }

        return { ...baseData, ...overrides };
    }

    // 生成測試藝術作品資料
    generateArtworkData(artistId = null, overrides = {}) {
        const baseData = {
            title: 'Test Artwork ' + Date.now(),
            title_variants: ['Artwork Variant 1', 'Artwork Variant 2'],
            artist_id: artistId || uuidv4(),
            creation_year: 1400 + Math.floor(Math.random() * 600),
            medium: 'Oil on canvas',
            dimensions: '100 cm × 80 cm',
            description: 'This is a test artwork description for testing purposes.',
            style: 'Test Style',
            subject_matter: 'Test Subject',
            location: 'Test Location',
            current_location: 'Test Museum',
            provenance: 'Test provenance information',
            significance: 'This artwork is significant for testing purposes.',
            source_urls: ['https://test.example.com/artwork'],
            image_urls: ['https://test.example.com/image1.jpg', 'https://test.example.com/image2.jpg'],
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成測試機構資料
    generateInstitutionData(overrides = {}) {
        const baseData = {
            name: 'Test Institution ' + Date.now(),
            type: 'museum',
            country: 'Test Country',
            city: 'Test City',
            address: '123 Test Street, Test City, Test Country',
            website: 'https://test-institution.example.com',
            description: 'This is a test institution for testing purposes.',
            collection_focus: 'Test collection focus',
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成測試標籤資料
    generateTagData(overrides = {}) {
        const categories = ['subject', 'style', 'technique', 'period', 'location'];
        const baseData = {
            name: 'Test Tag ' + Date.now(),
            category: categories[Math.floor(Math.random() * categories.length)],
            description: 'This is a test tag for testing purposes.',
            parent_tag_id: null,
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成測試文檔向量資料
    generateDocumentVectorData(overrides = {}) {
        const baseData = {
            content_id: uuidv4(),
            content_type: 'test',
            title: 'Test Document ' + Date.now(),
            content: 'This is test content for vector search testing. It contains various keywords and phrases that can be used to test search functionality.',
            content_summary: 'Test content summary for vector search.',
            chunk_index: 0,
            chunk_count: 1,
            source_url: 'https://test.example.com/document',
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成測試爬蟲任務資料
    generateCrawlTaskData(overrides = {}) {
        const taskTypes = ['artist', 'artwork', 'institution', 'collection'];
        const baseData = {
            url: 'https://test.example.com/' + Date.now(),
            source_name: 'Test Source',
            task_type: taskTypes[Math.floor(Math.random() * taskTypes.length)],
            priority: Math.floor(Math.random() * 10) + 1,
            agent_name: 'TestAgent',
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成測試館藏關係資料
    generateCollectionData(artworkId, institutionId, overrides = {}) {
        const baseData = {
            artwork_id: artworkId,
            institution_id: institutionId,
            accession_number: 'TEST-' + Date.now(),
            acquisition_date: new Date().toISOString().split('T')[0],
            acquisition_method: 'Test acquisition',
            status: 'active',
            notes: 'Test collection notes',
            metadata: {
                test: true,
                generated_at: new Date().toISOString()
            }
        };

        return { ...baseData, ...overrides };
    }

    // 生成批量測試資料
    generateBulkArtistData(count = 5) {
        return Array.from({ length: count }, () => this.generateArtistData());
    }

    generateBulkArtworkData(artistIds = [], count = 5) {
        return Array.from({ length: count }, (_, index) => {
            const artistId = artistIds.length > 0
                ? artistIds[index % artistIds.length]
                : null;
            return this.generateArtworkData(artistId);
        });
    }

    generateBulkInstitutionData(count = 3) {
        return Array.from({ length: count }, () => this.generateInstitutionData());
    }

    generateBulkTagData(count = 10) {
        return Array.from({ length: count }, () => this.generateTagData());
    }

    // 生成完整的測試場景資料
    generateCompleteTestScenario() {
        const artists = this.generateBulkArtistData(3);
        const institutions = this.generateBulkInstitutionData(2);
        const tags = this.generateBulkTagData(5);

        return {
            artists,
            artworks: [], // 將在藝術家創建後填充
            institutions,
            tags,
            collections: [] // 將在作品和機構創建後填充
        };
    }

    // 記錄創建的ID（用於清理）
    trackId(id) {
        this.createdIds.push(id);
    }

    // 獲取所有創建的ID
    getCreatedIds() {
        return [...this.createdIds];
    }

    // 清空ID記錄
    clearTrackedIds() {
        this.createdIds = [];
    }

    // 生成隨機字符串
    generateRandomString(length = 10) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }

    // 生成隨機日期
    generateRandomDate(startYear = 1800, endYear = 2023) {
        const start = new Date(startYear, 0, 1);
        const end = new Date(endYear, 11, 31);
        return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()));
    }

    // 生成測試嵌入向量（模擬）
    generateMockEmbedding(dimensions = 1536) {
        return Array.from({ length: dimensions }, () => Math.random() * 2 - 1);
    }

    // 生成用於搜索測試的資料
    generateSearchTestData() {
        return {
            artists: [
                this.generateArtistData({ name: 'Leonardo da Vinci', nationality: 'Italian', art_movement: 'Renaissance' }),
                this.generateArtistData({ name: 'Pablo Picasso', nationality: 'Spanish', art_movement: 'Cubism' }),
                this.generateArtistData({ name: 'Vincent van Gogh', nationality: 'Dutch', art_movement: 'Post-Impressionism' })
            ],
            artworks: [
                this.generateArtworkData(null, { title: 'Mona Lisa', style: 'Renaissance', subject_matter: 'Portrait' }),
                this.generateArtworkData(null, { title: 'Guernica', style: 'Cubism', subject_matter: 'War' }),
                this.generateArtworkData(null, { title: 'Starry Night', style: 'Post-Impressionism', subject_matter: 'Landscape' })
            ],
            tags: [
                this.generateTagData({ name: 'Portrait', category: 'subject' }),
                this.generateTagData({ name: 'Landscape', category: 'subject' }),
                this.generateTagData({ name: 'Renaissance', category: 'period' }),
                this.generateTagData({ name: 'Cubism', category: 'style' })
            ]
        };
    }
}

// 創建單例實例
const testDataGenerator = new TestDataGenerator();

// 測試資料清理助手
class TestDataCleaner {
    constructor() {
        this.cleanupCallbacks = [];
    }

    // 註冊清理回調
    registerCleanup(callback) {
        this.cleanupCallbacks.push(callback);
    }

    // 執行所有清理操作
    async cleanup() {
        for (const callback of this.cleanupCallbacks.reverse()) {
            try {
                await callback();
            } catch (error) {
                console.error('清理測試資料時出錯:', error);
            }
        }
        this.cleanupCallbacks = [];
    }

    // 清理特定模型的測試資料
    async cleanupModel(model, condition = { metadata: { test: true } }) {
        try {
            const query = `
                DELETE FROM ${model.tableName}
                WHERE metadata->>'test' = 'true'
                RETURNING id
            `;
            const result = await model.query(query);
            console.log(`已清理 ${result.rows.length} 條 ${model.tableName} 測試資料`);
        } catch (error) {
            console.error(`清理 ${model.tableName} 測試資料失敗:`, error);
        }
    }
}

// 創建清理器實例
const testDataCleaner = new TestDataCleaner();

module.exports = {
    TestDataGenerator,
    TestDataCleaner,
    testDataGenerator,
    testDataCleaner
};