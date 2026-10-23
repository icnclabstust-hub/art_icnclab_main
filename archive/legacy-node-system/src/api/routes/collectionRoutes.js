/**
 * 館藏路由
 * 處理館藏相關的API路由
 */

const express = require('express');
const collectionController = require('../controllers/collectionController');
const { rateLimitMiddleware } = require('../middleware/rateLimiter');

const router = express.Router();

// 應用速率限制
router.use(rateLimitMiddleware);

// 基本CRUD操作
router.get('/', collectionController.getAllCollections.bind(collectionController));
router.get('/stats', collectionController.getCollectionStatistics.bind(collectionController));
router.get('/search', collectionController.searchCollections.bind(collectionController));
router.get('/:id', collectionController.getCollectionById.bind(collectionController));
router.get('/:id/artworks', collectionController.getCollectionArtworks.bind(collectionController));

// 創建和修改操作
router.post('/', collectionController.createCollection.bind(collectionController));
router.put('/:id', collectionController.updateCollection.bind(collectionController));
router.delete('/:id', collectionController.deleteCollection.bind(collectionController));

// 關聯操作
router.get('/institution/:institutionId', collectionController.getCollectionsByInstitution.bind(collectionController));

module.exports = router;