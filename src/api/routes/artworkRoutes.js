/**
 * 藝術作品路由
 * 處理藝術作品相關的API路由
 */

const express = require('express');
const artworkController = require('../controllers/artworkController');
const { validateSearchMiddleware } = require('../validators/artworkValidator');
const { artworkValidationMiddleware, bulkArtworkValidationMiddleware } = require('../middleware/validationMiddleware');
const { rateLimitMiddleware } = require('../middleware/rateLimiter');

const router = express.Router();

// 應用優化後的速率限制
router.use(rateLimitMiddleware());

// 基本CRUD操作
router.get('/', artworkController.getAllArtworks.bind(artworkController));
router.get('/stats', artworkController.getArtworkStatistics.bind(artworkController));
router.get('/search', validateSearchMiddleware(), artworkController.searchArtworks.bind(artworkController));
router.get('/period', artworkController.getArtworksByPeriod.bind(artworkController));
router.get('/style/:style', artworkController.getArtworksByStyle.bind(artworkController));
router.get('/:id', artworkController.getArtworkById.bind(artworkController));

// 創建和修改操作
router.post('/', artworkValidationMiddleware(false), artworkController.createArtwork.bind(artworkController));
router.put('/:id', artworkValidationMiddleware(true), artworkController.updateArtwork.bind(artworkController));
router.delete('/:id', artworkController.deleteArtwork.bind(artworkController));

// 批量操作
router.post('/bulk', bulkArtworkValidationMiddleware(), artworkController.bulkCreateArtworks ? artworkController.bulkCreateArtworks.bind(artworkController) : (req, res) => {
    res.status(501).json({
        success: false,
        message: '批量創建功能尚未實現',
        hint: '請使用單個創建接口'
    });
});

// 關聯操作
router.get('/artist/:artistId', artworkController.getArtworksByArtist.bind(artworkController));
router.post('/:id/tags', artworkController.addTagsToArtwork.bind(artworkController));

module.exports = router;