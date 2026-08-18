/**
 * 藝術作品控制器
 * 處理藝術作品相關的API請求
 */

const { Artwork, Artist, Institution, Tag } = require('../../database/models');
const { validateArtwork } = require('../validators/artworkValidator');
const { successResponse, errorResponse } = require('../../utils/responseHelper');
const { cacheManager } = require('../../utils/cacheManager');

class ArtworkController {
    constructor() {
        this.artworkModel = new Artwork();
        this.artistModel = new Artist();
        this.institutionModel = new Institution();
        this.tagModel = new Tag();
    }

    // 獲取所有藝術作品 - 簡化查詢避免 N+1 問題
    async getAllArtworks(req, res) {
        try {
            const page = parseInt(req.query.page) || 1;
            const limit = Math.min(parseInt(req.query.limit) || 20, 100);
            const offset = (page - 1) * limit;

            // 使用改善的 findAll 方法，已包含藝術家資訊
            const artworks = await this.artworkModel.findAll(limit, offset);

            return successResponse(res, artworks, {
                page,
                limit,
                total: artworks.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artworks', error.message);
        }
    }

    // 根據ID獲取藝術作品詳情
    async getArtworkById(req, res) {
        try {
            const { id } = req.params;

            // 使用快取包裝器
            const artwork = await cacheManager.wrap(
                'artwork',
                `details_${id}`,
                async () => {
                    return await this.artworkModel.getArtworkDetails(id);
                }
            );

            if (!artwork) {
                return errorResponse(res, 'Artwork not found', null, 404);
            }

            return successResponse(res, artwork);
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artwork', error.message);
        }
    }

    // 創建新的藝術作品
    async createArtwork(req, res) {
        try {
            // 驗證輸入資料
            const { error, value } = validateArtwork(req.body);
            if (error) {
                return errorResponse(res, 'Validation failed', error.details[0].message, 400);
            }

            // 檢查藝術家是否存在
            if (value.artist_id) {
                const artist = await this.artistModel.findById(value.artist_id);
                if (!artist) {
                    return errorResponse(res, 'Artist not found', null, 404);
                }
            }

            // 創建藝術作品
            const artwork = await this.artworkModel.createArtwork(value);

            // 如果提供了標籤，則添加標籤關聯
            if (value.tag_ids && value.tag_ids.length > 0) {
                await this.artworkModel.addTags(artwork.id, value.tag_ids, 'api');
            }

            // 失效相關快取
            await this.invalidateArtworkCaches(artwork.id, value.artist_id);

            return successResponse(res, artwork, null, 201);
        } catch (error) {
            return errorResponse(res, 'Failed to create artwork', error.message);
        }
    }

    // 更新藝術作品
    async updateArtwork(req, res) {
        try {
            const { id } = req.params;

            // 檢查作品是否存在
            const existingArtwork = await this.artworkModel.findById(id);
            if (!existingArtwork) {
                return errorResponse(res, 'Artwork not found', null, 404);
            }

            // 驗證更新資料
            const { error, value } = validateArtwork(req.body, false);
            if (error) {
                return errorResponse(res, 'Validation failed', error.details[0].message, 400);
            }

            // 如果更新藝術家ID，檢查藝術家是否存在
            if (value.artist_id && value.artist_id !== existingArtwork.artist_id) {
                const artist = await this.artistModel.findById(value.artist_id);
                if (!artist) {
                    return errorResponse(res, 'Artist not found', null, 404);
                }
            }

            const updatedArtwork = await this.artworkModel.update(id, value);

            // 失效相關快取（包含舊藝術家和新藝術家）
            await this.invalidateArtworkCaches(id, existingArtwork.artist_id);
            if (value.artist_id && value.artist_id !== existingArtwork.artist_id) {
                await this.invalidateArtworkCaches(id, value.artist_id);
            }

            return successResponse(res, updatedArtwork);
        } catch (error) {
            return errorResponse(res, 'Failed to update artwork', error.message);
        }
    }

    // 刪除藝術作品
    async deleteArtwork(req, res) {
        try {
            const { id } = req.params;

            const artwork = await this.artworkModel.findById(id);
            if (!artwork) {
                return errorResponse(res, 'Artwork not found', null, 404);
            }

            await this.artworkModel.delete(id);

            // 失效相關快取
            await this.invalidateArtworkCaches(id, artwork.artist_id);

            return successResponse(res, { message: 'Artwork deleted successfully' });
        } catch (error) {
            return errorResponse(res, 'Failed to delete artwork', error.message);
        }
    }

    // 根據藝術家獲取作品
    async getArtworksByArtist(req, res) {
        try {
            const { artistId } = req.params;
            const limit = Math.min(parseInt(req.query.limit) || 50, 100);

            // 使用快取包裝器檢查藝術家
            const artist = await cacheManager.wrap(
                'artist',
                `details_${artistId}`,
                async () => {
                    return await this.artistModel.findById(artistId);
                }
            );

            if (!artist) {
                return errorResponse(res, 'Artist not found', null, 404);
            }

            // 使用快取包裝器獲取作品列表
            const artworks = await cacheManager.wrap(
                'artwork',
                `by_artist_${artistId}_limit_${limit}`,
                async () => {
                    return await this.artworkModel.findByArtist(artistId, limit);
                },
                1800 // 30分鐘快取時間，因為列表可能會更頻繁變動
            );

            return successResponse(res, {
                artist,
                artworks,
                count: artworks.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artworks by artist', error.message);
        }
    }

    // 根據時期獲取作品
    async getArtworksByPeriod(req, res) {
        try {
            const startYear = parseInt(req.query.start_year);
            const endYear = parseInt(req.query.end_year);
            const limit = Math.min(parseInt(req.query.limit) || 100, 200);

            if (!startYear || !endYear || startYear > endYear) {
                return errorResponse(res, 'Invalid period parameters', null, 400);
            }

            const artworks = await this.artworkModel.findByPeriod(startYear, endYear, limit);
            return successResponse(res, {
                period: { start_year: startYear, end_year: endYear },
                artworks,
                count: artworks.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artworks by period', error.message);
        }
    }

    // 根據風格獲取作品
    async getArtworksByStyle(req, res) {
        try {
            const { style } = req.params;
            const limit = Math.min(parseInt(req.query.limit) || 50, 100);

            const artworks = await this.artworkModel.findByStyle(style, limit);
            return successResponse(res, {
                style,
                artworks,
                count: artworks.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artworks by style', error.message);
        }
    }

    // 搜索藝術作品 - 簡化查詢避免 N+1 問題
    async searchArtworks(req, res) {
        try {
            const { q: searchText } = req.query;
            const limit = Math.min(parseInt(req.query.limit) || 20, 100);

            if (!searchText || searchText.trim().length === 0) {
                return errorResponse(res, 'Search query is required', null, 400);
            }

            // search 方法已經包含藝術家資訊的 JOIN
            const artworks = await this.artworkModel.search(searchText, limit);

            return successResponse(res, {
                query: searchText,
                artworks,
                count: artworks.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to search artworks', error.message);
        }
    }

    // 添加標籤到藝術作品
    async addTagsToArtwork(req, res) {
        try {
            const { id } = req.params;
            const { tag_ids, assigned_by = 'api' } = req.body;

            if (!tag_ids || !Array.isArray(tag_ids) || tag_ids.length === 0) {
                return errorResponse(res, 'Tag IDs array is required', null, 400);
            }

            // 檢查作品是否存在
            const artwork = await this.artworkModel.findById(id);
            if (!artwork) {
                return errorResponse(res, 'Artwork not found', null, 404);
            }

            // 檢查所有標籤是否存在
            for (const tagId of tag_ids) {
                const tag = await this.tagModel.findById(tagId);
                if (!tag) {
                    return errorResponse(res, `Tag with ID ${tagId} not found`, null, 404);
                }
            }

            const artworkTags = await this.artworkModel.addTags(id, tag_ids, assigned_by);
            return successResponse(res, artworkTags);
        } catch (error) {
            return errorResponse(res, 'Failed to add tags to artwork', error.message);
        }
    }

    // 獲取藝術作品統計
    async getArtworkStatistics(req, res) {
        try {
            // 使用快取包裝器獲取統計數據
            const statistics = await cacheManager.wrap(
                'artwork',
                'statistics',
                async () => {
                    const stats = await this.artworkModel.query(`
                        SELECT
                            COUNT(*) as total_artworks,
                            COUNT(DISTINCT artist_id) as unique_artists,
                            MIN(creation_year) as earliest_year,
                            MAX(creation_year) as latest_year,
                            COUNT(DISTINCT style) as unique_styles,
                            COUNT(DISTINCT medium) as unique_mediums
                        FROM artworks
                        WHERE creation_year IS NOT NULL
                    `);

                    const styleStats = await this.artworkModel.query(`
                        SELECT style, COUNT(*) as count
                        FROM artworks
                        WHERE style IS NOT NULL
                        GROUP BY style
                        ORDER BY count DESC
                        LIMIT 10
                    `);

                    const periodStats = await this.artworkModel.query(`
                        SELECT
                            FLOOR(creation_year / 100) * 100 as century,
                            COUNT(*) as count
                        FROM artworks
                        WHERE creation_year IS NOT NULL
                        GROUP BY FLOOR(creation_year / 100)
                        ORDER BY century
                    `);

                    return {
                        general: stats.rows[0],
                        top_styles: styleStats.rows,
                        by_century: periodStats.rows
                    };
                },
                3600 // 1小時快取，因為統計數據變化不頻繁
            );

            return successResponse(res, statistics);
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artwork statistics', error.message);
        }
    }

    // 快取失效輔助方法
    async invalidateArtworkCaches(artworkId, artistId = null) {
        try {
            // 失效特定藝術作品的快取
            await cacheManager.delete('artwork', `details_${artworkId}`);

            // 失效統計快取
            await cacheManager.delete('artwork', 'statistics');

            // 如果有藝術家ID，失效相關的藝術家作品列表
            if (artistId) {
                await cacheManager.deleteByPattern('artwork', `by_artist_${artistId}_*`);
            }

            // 失效搜尋快取
            await cacheManager.clearCategory('search');

        } catch (error) {
            console.warn('快取失效失敗:', error.message);
        }
    }
}

module.exports = new ArtworkController();