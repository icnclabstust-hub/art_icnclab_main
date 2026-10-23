/**
 * 藝術作品控制器測試
 * 測試API控制器功能
 */

const request = require('supertest');
const app = require('../../src/app');
const { Artist, Artwork } = require('../../src/database/models');
const { dbManager } = require('../../src/database/connection');

describe('Artwork Controller', () => {
    let testArtist;
    let testArtwork;

    beforeAll(async () => {
        await dbManager.connectPostgres();
    });

    afterAll(async () => {
        await dbManager.closeAll();
    });

    beforeEach(async () => {
        // 創建測試藝術家
        const artistModel = new Artist();
        testArtist = await artistModel.createArtist({
            name: 'Test Artist for API',
            nationality: 'Test',
            metadata: { test: true }
        });

        // 創建測試藝術作品
        const artworkModel = new Artwork();
        testArtwork = await artworkModel.createArtwork({
            title: 'Test Artwork for API',
            artist_id: testArtist.id,
            creation_year: 2023,
            description: 'A test artwork for API testing',
            metadata: { test: true }
        });
    });

    afterEach(async () => {
        // 清理測試資料
        const artworkModel = new Artwork();
        const artistModel = new Artist();

        try {
            if (testArtwork && testArtwork.id) {
                await artworkModel.delete(testArtwork.id);
            }
            if (testArtist && testArtist.id) {
                await artistModel.delete(testArtist.id);
            }
        } catch (error) {
            console.error('清理測試資料失敗:', error);
        }
    });

    describe('GET /api/v1/artworks', () => {
        test('應該返回藝術作品列表', async () => {
            const response = await request(app)
                .get('/api/v1/artworks')
                .expect(200);

            expect(response.body).toHaveProperty('success', true);
            expect(response.body).toHaveProperty('data');
            expect(Array.isArray(response.body.data)).toBe(true);
        });

        test('應該支持分頁參數', async () => {
            const response = await request(app)
                .get('/api/v1/artworks?page=1&limit=5')
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body).toHaveProperty('meta');
            expect(response.body.meta).toHaveProperty('page', 1);
            expect(response.body.meta).toHaveProperty('limit', 5);
        });
    });

    describe('GET /api/v1/artworks/:id', () => {
        test('應該返回指定ID的藝術作品', async () => {
            const response = await request(app)
                .get(`/api/v1/artworks/${testArtwork.id}`)
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('id', testArtwork.id);
            expect(response.body.data).toHaveProperty('title', testArtwork.title);
        });

        test('當作品不存在時應該返回404', async () => {
            const fakeId = '00000000-0000-0000-0000-000000000000';
            const response = await request(app)
                .get(`/api/v1/artworks/${fakeId}`)
                .expect(404);

            expect(response.body.success).toBe(false);
            expect(response.body.error.message).toContain('not found');
        });
    });

    describe('POST /api/v1/artworks', () => {
        test('應該能夠創建新的藝術作品', async () => {
            const artworkData = {
                title: 'New Test Artwork',
                artist_id: testArtist.id,
                creation_year: 2023,
                medium: 'Oil on canvas',
                description: 'A newly created test artwork'
            };

            const response = await request(app)
                .post('/api/v1/artworks')
                .send(artworkData)
                .expect(201);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('title', artworkData.title);
            expect(response.body.data).toHaveProperty('artist_id', artworkData.artist_id);

            // 清理創建的資料
            const artworkModel = new Artwork();
            await artworkModel.delete(response.body.data.id);
        });

        test('當資料驗證失敗時應該返回400', async () => {
            const invalidData = {
                // 缺少必需的 title 字段
                artist_id: testArtist.id,
                creation_year: 'invalid_year' // 無效的年份格式
            };

            const response = await request(app)
                .post('/api/v1/artworks')
                .send(invalidData)
                .expect(400);

            expect(response.body.success).toBe(false);
            expect(response.body.error.message).toContain('validation');
        });
    });

    describe('PUT /api/v1/artworks/:id', () => {
        test('應該能夠更新藝術作品', async () => {
            const updateData = {
                description: 'Updated description for test artwork',
                medium: 'Updated medium'
            };

            const response = await request(app)
                .put(`/api/v1/artworks/${testArtwork.id}`)
                .send(updateData)
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('description', updateData.description);
            expect(response.body.data).toHaveProperty('medium', updateData.medium);
        });

        test('當作品不存在時應該返回404', async () => {
            const fakeId = '00000000-0000-0000-0000-000000000000';
            const updateData = { description: 'Updated description' };

            const response = await request(app)
                .put(`/api/v1/artworks/${fakeId}`)
                .send(updateData)
                .expect(404);

            expect(response.body.success).toBe(false);
        });
    });

    describe('DELETE /api/v1/artworks/:id', () => {
        test('應該能夠刪除藝術作品', async () => {
            // 創建一個專門用於刪除測試的作品
            const artworkModel = new Artwork();
            const deletableArtwork = await artworkModel.createArtwork({
                title: 'Deletable Test Artwork',
                artist_id: testArtist.id,
                metadata: { test: true }
            });

            const response = await request(app)
                .delete(`/api/v1/artworks/${deletableArtwork.id}`)
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data.message).toContain('deleted successfully');

            // 驗證作品已被刪除
            const deletedArtwork = await artworkModel.findById(deletableArtwork.id);
            expect(deletedArtwork).toBeNull();
        });
    });

    describe('GET /api/v1/artworks/search', () => {
        test('應該能夠搜索藝術作品', async () => {
            const response = await request(app)
                .get('/api/v1/artworks/search?q=test')
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('query', 'test');
            expect(Array.isArray(response.body.data.artworks)).toBe(true);
        });

        test('當搜索查詢為空時應該返回400', async () => {
            const response = await request(app)
                .get('/api/v1/artworks/search')
                .expect(400);

            expect(response.body.success).toBe(false);
        });
    });

    describe('GET /api/v1/artworks/artist/:artistId', () => {
        test('應該返回指定藝術家的作品', async () => {
            const response = await request(app)
                .get(`/api/v1/artworks/artist/${testArtist.id}`)
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('artist');
            expect(response.body.data.artist).toHaveProperty('id', testArtist.id);
            expect(Array.isArray(response.body.data.artworks)).toBe(true);
        });

        test('當藝術家不存在時應該返回404', async () => {
            const fakeId = '00000000-0000-0000-0000-000000000000';
            const response = await request(app)
                .get(`/api/v1/artworks/artist/${fakeId}`)
                .expect(404);

            expect(response.body.success).toBe(false);
        });
    });

    describe('GET /api/v1/artworks/period', () => {
        test('應該返回指定時期的作品', async () => {
            const response = await request(app)
                .get('/api/v1/artworks/period?start_year=2000&end_year=2025')
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('period');
            expect(response.body.data.period).toHaveProperty('start_year', 2000);
            expect(response.body.data.period).toHaveProperty('end_year', 2025);
            expect(Array.isArray(response.body.data.artworks)).toBe(true);
        });

        test('當時期參數無效時應該返回400', async () => {
            const response = await request(app)
                .get('/api/v1/artworks/period?start_year=invalid&end_year=2025')
                .expect(400);

            expect(response.body.success).toBe(false);
        });
    });

    describe('GET /api/v1/artworks/stats', () => {
        test('應該返回藝術作品統計信息', async () => {
            const response = await request(app)
                .get('/api/v1/artworks/stats')
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(response.body.data).toHaveProperty('general');
            expect(response.body.data).toHaveProperty('top_styles');
            expect(response.body.data).toHaveProperty('by_century');
        });
    });

    describe('POST /api/v1/artworks/:id/tags', () => {
        test('應該能夠為作品添加標籤', async () => {
            // 首先需要創建測試標籤
            const { Tag } = require('../../src/database/models');
            const tagModel = new Tag();

            const testTag = await tagModel.createTag({
                name: 'Test Tag for Artwork',
                category: 'test',
                metadata: { test: true }
            });

            const response = await request(app)
                .post(`/api/v1/artworks/${testArtwork.id}/tags`)
                .send({
                    tag_ids: [testTag.id],
                    assigned_by: 'test'
                })
                .expect(200);

            expect(response.body.success).toBe(true);
            expect(Array.isArray(response.body.data)).toBe(true);

            // 清理測試標籤
            await tagModel.delete(testTag.id);
        });

        test('當作品不存在時應該返回404', async () => {
            const fakeId = '00000000-0000-0000-0000-000000000000';
            const response = await request(app)
                .post(`/api/v1/artworks/${fakeId}/tags`)
                .send({
                    tag_ids: ['00000000-0000-0000-0000-000000000001']
                })
                .expect(404);

            expect(response.body.success).toBe(false);
        });
    });
});