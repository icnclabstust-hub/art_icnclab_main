/**
 * 資料模型測試
 * 測試資料庫模型的基本功能
 */

const { Artist, Artwork, Institution, Tag, DocumentVector, CrawlTask } = require('../../src/database/models');
const { dbManager } = require('../../src/database/connection');

// 測試前設置
beforeAll(async () => {
    await dbManager.connectPostgres();
});

// 測試後清理
afterAll(async () => {
    await dbManager.closeAll();
});

describe('Artist Model', () => {
    let artistModel;
    let testArtist;

    beforeEach(() => {
        artistModel = new Artist();
    });

    test('應該能夠創建藝術家', async () => {
        const artistData = {
            name: 'Leonardo da Vinci',
            name_variants: ['Leonardo di ser Piero da Vinci'],
            birth_year: 1452,
            death_year: 1519,
            nationality: 'Italian',
            art_movement: 'Renaissance',
            biography: 'Italian polymath of the Renaissance period',
            metadata: { test: true }
        };

        testArtist = await artistModel.createArtist(artistData);

        expect(testArtist).toBeTruthy();
        expect(testArtist.id).toBeTruthy();
        expect(testArtist.name).toBe(artistData.name);
        expect(testArtist.birth_year).toBe(artistData.birth_year);
        expect(testArtist.nationality).toBe(artistData.nationality);
    });

    test('應該能夠根據ID查找藝術家', async () => {
        if (!testArtist) {
            testArtist = await artistModel.createArtist({
                name: 'Test Artist',
                nationality: 'Test',
                metadata: { test: true }
            });
        }

        const foundArtist = await artistModel.findById(testArtist.id);
        expect(foundArtist).toBeTruthy();
        expect(foundArtist.id).toBe(testArtist.id);
        expect(foundArtist.name).toBe(testArtist.name);
    });

    test('應該能夠根據名稱搜索藝術家', async () => {
        const artists = await artistModel.findByName('Leonardo');
        expect(Array.isArray(artists)).toBe(true);

        if (artists.length > 0) {
            expect(artists[0].name.toLowerCase()).toContain('leonardo');
        }
    });

    test('應該能夠更新藝術家信息', async () => {
        if (!testArtist) {
            testArtist = await artistModel.createArtist({
                name: 'Test Artist for Update',
                nationality: 'Test',
                metadata: { test: true }
            });
        }

        const updateData = {
            biography: 'Updated biography',
            art_movement: 'Updated Movement'
        };

        const updatedArtist = await artistModel.update(testArtist.id, updateData);
        expect(updatedArtist.biography).toBe(updateData.biography);
        expect(updatedArtist.art_movement).toBe(updateData.art_movement);
    });

    afterEach(async () => {
        // 清理測試資料
        if (testArtist && testArtist.id) {
            try {
                await artistModel.delete(testArtist.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('Artwork Model', () => {
    let artworkModel;
    let artistModel;
    let testArtwork;
    let testArtist;

    beforeEach(async () => {
        artworkModel = new Artwork();
        artistModel = new Artist();

        // 創建測試藝術家
        testArtist = await artistModel.createArtist({
            name: 'Test Artist for Artwork',
            nationality: 'Test',
            metadata: { test: true }
        });
    });

    test('應該能夠創建藝術作品', async () => {
        const artworkData = {
            title: 'Mona Lisa',
            title_variants: ['La Gioconda'],
            artist_id: testArtist.id,
            creation_year: 1503,
            medium: 'Oil on poplar',
            dimensions: '77 cm × 53 cm',
            description: 'Portrait painting by Leonardo da Vinci',
            style: 'Renaissance',
            subject_matter: 'Portrait',
            significance: 'One of the most famous paintings in the world',
            metadata: { test: true }
        };

        testArtwork = await artworkModel.createArtwork(artworkData);

        expect(testArtwork).toBeTruthy();
        expect(testArtwork.id).toBeTruthy();
        expect(testArtwork.title).toBe(artworkData.title);
        expect(testArtwork.artist_id).toBe(testArtist.id);
        expect(testArtwork.creation_year).toBe(artworkData.creation_year);
    });

    test('應該能夠獲取藝術作品詳情', async () => {
        if (!testArtwork) {
            testArtwork = await artworkModel.createArtwork({
                title: 'Test Artwork',
                artist_id: testArtist.id,
                metadata: { test: true }
            });
        }

        const artworkDetails = await artworkModel.getArtworkDetails(testArtwork.id);
        expect(artworkDetails).toBeTruthy();
        expect(artworkDetails.title).toBe(testArtwork.title);
        expect(artworkDetails.artist_name).toBe(testArtist.name);
    });

    test('應該能夠根據藝術家查找作品', async () => {
        const artworks = await artworkModel.findByArtist(testArtist.id);
        expect(Array.isArray(artworks)).toBe(true);

        if (artworks.length > 0) {
            expect(artworks[0].artist_id).toBe(testArtist.id);
        }
    });

    test('應該能夠根據時期查找作品', async () => {
        const artworks = await artworkModel.findByPeriod(1400, 1600);
        expect(Array.isArray(artworks)).toBe(true);
    });

    afterEach(async () => {
        // 清理測試資料
        if (testArtwork && testArtwork.id) {
            try {
                await artworkModel.delete(testArtwork.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }

        if (testArtist && testArtist.id) {
            try {
                await artistModel.delete(testArtist.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('Institution Model', () => {
    let institutionModel;
    let testInstitution;

    beforeEach(() => {
        institutionModel = new Institution();
    });

    test('應該能夠創建機構', async () => {
        const institutionData = {
            name: 'Test Museum',
            type: 'museum',
            country: 'Test Country',
            city: 'Test City',
            description: 'A test museum for unit testing',
            metadata: { test: true }
        };

        testInstitution = await institutionModel.createInstitution(institutionData);

        expect(testInstitution).toBeTruthy();
        expect(testInstitution.id).toBeTruthy();
        expect(testInstitution.name).toBe(institutionData.name);
        expect(testInstitution.type).toBe(institutionData.type);
        expect(testInstitution.country).toBe(institutionData.country);
    });

    test('應該能夠根據國家查找機構', async () => {
        const institutions = await institutionModel.findByCountry('Test');
        expect(Array.isArray(institutions)).toBe(true);
    });

    afterEach(async () => {
        // 清理測試資料
        if (testInstitution && testInstitution.id) {
            try {
                await institutionModel.delete(testInstitution.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('Tag Model', () => {
    let tagModel;
    let testTag;

    beforeEach(() => {
        tagModel = new Tag();
    });

    test('應該能夠創建標籤', async () => {
        const tagData = {
            name: 'Test Tag',
            category: 'test',
            description: 'A test tag for unit testing',
            metadata: { test: true }
        };

        testTag = await tagModel.createTag(tagData);

        expect(testTag).toBeTruthy();
        expect(testTag.id).toBeTruthy();
        expect(testTag.name).toBe(tagData.name);
        expect(testTag.category).toBe(tagData.category);
    });

    test('應該能夠根據分類查找標籤', async () => {
        const tags = await tagModel.findByCategory('test');
        expect(Array.isArray(tags)).toBe(true);
    });

    test('應該能夠獲取標籤層次結構', async () => {
        const hierarchy = await tagModel.getTagHierarchy();
        expect(Array.isArray(hierarchy)).toBe(true);
    });

    afterEach(async () => {
        // 清理測試資料
        if (testTag && testTag.id) {
            try {
                await tagModel.delete(testTag.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('DocumentVector Model', () => {
    let documentVectorModel;
    let testDocument;

    beforeEach(() => {
        documentVectorModel = new DocumentVector();
    });

    test('應該能夠創建文檔向量', async () => {
        const documentData = {
            content_id: 'test-content-id',
            content_type: 'test',
            title: 'Test Document',
            content: 'This is a test document for vector search',
            content_summary: 'Test document summary',
            metadata: { test: true }
        };

        testDocument = await documentVectorModel.createDocument(documentData);

        expect(testDocument).toBeTruthy();
        expect(testDocument.id).toBeTruthy();
        expect(testDocument.content_id).toBe(documentData.content_id);
        expect(testDocument.content_type).toBe(documentData.content_type);
        expect(testDocument.title).toBe(documentData.title);
    });

    test('應該能夠根據內容ID查找文檔', async () => {
        if (!testDocument) {
            testDocument = await documentVectorModel.createDocument({
                content_id: 'test-search-id',
                content_type: 'test',
                title: 'Test Search Document',
                content: 'Test content',
                metadata: { test: true }
            });
        }

        const documents = await documentVectorModel.findByContentId(
            testDocument.content_id,
            testDocument.content_type
        );

        expect(Array.isArray(documents)).toBe(true);
        if (documents.length > 0) {
            expect(documents[0].content_id).toBe(testDocument.content_id);
        }
    });

    afterEach(async () => {
        // 清理測試資料
        if (testDocument && testDocument.id) {
            try {
                await documentVectorModel.delete(testDocument.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('CrawlTask Model', () => {
    let crawlTaskModel;
    let testTask;

    beforeEach(() => {
        crawlTaskModel = new CrawlTask();
    });

    test('應該能夠創建爬蟲任務', async () => {
        const taskData = {
            url: 'https://test.example.com',
            source_name: 'Test Source',
            task_type: 'test',
            agent_name: 'TestAgent',
            metadata: { test: true }
        };

        testTask = await crawlTaskModel.createTask(taskData);

        expect(testTask).toBeTruthy();
        expect(testTask.id).toBeTruthy();
        expect(testTask.url).toBe(taskData.url);
        expect(testTask.status).toBe('pending');
        expect(testTask.task_type).toBe(taskData.task_type);
    });

    test('應該能夠獲取待處理任務', async () => {
        const pendingTasks = await crawlTaskModel.getPendingTasks(5);
        expect(Array.isArray(pendingTasks)).toBe(true);
    });

    test('應該能夠更新任務狀態', async () => {
        if (!testTask) {
            testTask = await crawlTaskModel.createTask({
                url: 'https://test-update.example.com',
                source_name: 'Test Update',
                task_type: 'test',
                agent_name: 'TestAgent',
                metadata: { test: true }
            });
        }

        const updatedTask = await crawlTaskModel.updateTaskStatus(
            testTask.id,
            'completed',
            null,
            { items_processed: 10 }
        );

        expect(updatedTask.status).toBe('completed');
    });

    afterEach(async () => {
        // 清理測試資料
        if (testTask && testTask.id) {
            try {
                await crawlTaskModel.delete(testTask.id);
            } catch (error) {
                // 忽略清理錯誤
            }
        }
    });
});

describe('Database Connection', () => {
    test('應該能夠檢查資料庫連接狀態', async () => {
        const status = await dbManager.checkConnections();
        expect(status).toBeTruthy();
        expect(typeof status.postgres).toBe('boolean');
    });

    test('應該能夠獲取PostgreSQL連接池', () => {
        expect(() => {
            const pool = dbManager.getPostgresPool();
            expect(pool).toBeTruthy();
        }).not.toThrow();
    });
});