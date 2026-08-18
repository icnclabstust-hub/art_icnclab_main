/**
 * 藝術家路由
 * 處理藝術家相關的API路由
 */

const express = require('express');
const artistController = require('../controllers/artistController');
const { artistValidationMiddleware, bulkArtistValidationMiddleware } = require('../middleware/validationMiddleware');
const { validateArtistSearchMiddleware } = require('../validators/artistValidator');
const { rateLimitMiddleware } = require('../middleware/rateLimiter');

const router = express.Router();

// 應用優化後的速率限制
router.use(rateLimitMiddleware());

// 基本CRUD操作
router.get('/', artistController.getAllArtists.bind(artistController));
router.get('/stats', artistController.getArtistStatistics.bind(artistController));
router.get('/search', validateArtistSearchMiddleware(), artistController.searchArtists.bind(artistController));
router.get('/period', artistController.getArtistsByPeriod.bind(artistController));
router.get('/nationality/:nationality', artistController.getArtistsByNationality.bind(artistController));
router.get('/:id', artistController.getArtistById.bind(artistController));

// 創建和修改操作
router.post('/', artistValidationMiddleware(false), artistController.createArtist.bind(artistController));
router.put('/:id', artistValidationMiddleware(true), artistController.updateArtist.bind(artistController));
router.delete('/:id', artistController.deleteArtist.bind(artistController));

// 批量操作
router.post('/bulk', bulkArtistValidationMiddleware(), artistController.bulkCreateArtists ? artistController.bulkCreateArtists.bind(artistController) : (req, res) => {
    res.status(501).json({
        success: false,
        message: '批量創建功能尚未實現',
        hint: '請使用單個創建接口'
    });
});

module.exports = router;