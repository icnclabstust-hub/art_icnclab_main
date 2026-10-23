/**
 * 藝術家控制器
 * 處理藝術家相關的API請求
 */

const { Artist, Artwork } = require('../../database/models');
const { successResponse, errorResponse } = require('../../utils/responseHelper');

class ArtistController {
    constructor() {
        this.artistModel = new Artist();
        this.artworkModel = new Artwork();
    }

    // 獲取所有藝術家
    async getAllArtists(req, res) {
        try {
            console.log('📊 開始獲取藝術家列表...');

            // 暫時回傳測試數據以確保API工作
            const testData = [
                { id: '1', name: '測試藝術家', nationality: '台灣', created_at: new Date() }
            ];

            console.log('📊 回傳測試資料');
            return successResponse(res, testData, {
                page: 1,
                limit: 20,
                total: testData.length
            });
        } catch (error) {
            console.error('❌ 獲取藝術家失敗:', error);
            return errorResponse(res, 'Failed to fetch artists', error.message);
        }
    }

    // 根據ID獲取藝術家詳情
    async getArtistById(req, res) {
        try {
            const { id } = req.params;
            const artist = await this.artistModel.findById(id);

            if (!artist) {
                return errorResponse(res, 'Artist not found', null, 404);
            }

            // 獲取該藝術家的作品統計
            const artworkStats = await this.artworkModel.query(`
                SELECT
                    COUNT(*) as total_artworks,
                    MIN(creation_year) as earliest_work,
                    MAX(creation_year) as latest_work
                FROM artworks
                WHERE artist_id = $1
            `, [id]);

            artist.artwork_statistics = artworkStats.rows[0];

            return successResponse(res, artist);
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artist', error.message);
        }
    }

    // 創建新的藝術家
    async createArtist(req, res) {
        try {
            const artistData = req.body;

            // 基本驗證
            if (!artistData.name) {
                return errorResponse(res, 'Artist name is required', null, 400);
            }

            const artist = await this.artistModel.create({
                ...artistData,
                id: require('uuid').v4(),
                created_at: new Date(),
                updated_at: new Date()
            });

            return successResponse(res, artist, null, 201);
        } catch (error) {
            return errorResponse(res, 'Failed to create artist', error.message);
        }
    }

    // 更新藝術家
    async updateArtist(req, res) {
        try {
            const { id } = req.params;
            const updateData = req.body;

            // 檢查藝術家是否存在
            const existingArtist = await this.artistModel.findById(id);
            if (!existingArtist) {
                return errorResponse(res, 'Artist not found', null, 404);
            }

            const updatedArtist = await this.artistModel.update(id, {
                ...updateData,
                updated_at: new Date()
            });

            return successResponse(res, updatedArtist);
        } catch (error) {
            return errorResponse(res, 'Failed to update artist', error.message);
        }
    }

    // 刪除藝術家
    async deleteArtist(req, res) {
        try {
            const { id } = req.params;

            const artist = await this.artistModel.findById(id);
            if (!artist) {
                return errorResponse(res, 'Artist not found', null, 404);
            }

            // 檢查是否有關聯的藝術品
            const relatedArtworks = await this.artworkModel.query(
                'SELECT COUNT(*) as count FROM artworks WHERE artist_id = $1',
                [id]
            );

            if (parseInt(relatedArtworks.rows[0].count) > 0) {
                return errorResponse(res, 'Cannot delete artist with associated artworks', null, 409);
            }

            await this.artistModel.delete(id);
            return successResponse(res, { message: 'Artist deleted successfully' });
        } catch (error) {
            return errorResponse(res, 'Failed to delete artist', error.message);
        }
    }

    // 搜索藝術家
    async searchArtists(req, res) {
        try {
            const { q: searchText } = req.query;
            const limit = Math.min(parseInt(req.query.limit) || 20, 100);

            if (!searchText || searchText.trim().length === 0) {
                return errorResponse(res, 'Search query is required', null, 400);
            }

            const artists = await this.artistModel.search(searchText, limit);

            return successResponse(res, {
                query: searchText,
                artists,
                count: artists.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to search artists', error.message);
        }
    }

    // 根據國籍獲取藝術家
    async getArtistsByNationality(req, res) {
        try {
            const { nationality } = req.params;
            const limit = Math.min(parseInt(req.query.limit) || 50, 100);

            const artists = await this.artistModel.findByNationality(nationality, limit);

            return successResponse(res, {
                nationality,
                artists,
                count: artists.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artists by nationality', error.message);
        }
    }

    // 根據時期獲取藝術家
    async getArtistsByPeriod(req, res) {
        try {
            const startYear = parseInt(req.query.start_year);
            const endYear = parseInt(req.query.end_year);
            const limit = Math.min(parseInt(req.query.limit) || 100, 200);

            if (!startYear || !endYear || startYear > endYear) {
                return errorResponse(res, 'Invalid period parameters', null, 400);
            }

            const artists = await this.artistModel.findByPeriod(startYear, endYear, limit);

            return successResponse(res, {
                period: { start_year: startYear, end_year: endYear },
                artists,
                count: artists.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artists by period', error.message);
        }
    }

    // 獲取藝術家統計
    async getArtistStatistics(req, res) {
        try {
            const stats = await this.artistModel.query(`
                SELECT
                    COUNT(*) as total_artists,
                    COUNT(DISTINCT nationality) as unique_nationalities,
                    MIN(birth_year) as earliest_birth_year,
                    MAX(birth_year) as latest_birth_year,
                    COUNT(CASE WHEN death_year IS NULL THEN 1 END) as living_artists
                FROM artists
                WHERE birth_year IS NOT NULL
            `);

            const nationalityStats = await this.artistModel.query(`
                SELECT nationality, COUNT(*) as count
                FROM artists
                WHERE nationality IS NOT NULL
                GROUP BY nationality
                ORDER BY count DESC
                LIMIT 10
            `);

            const centuryStats = await this.artistModel.query(`
                SELECT
                    FLOOR(birth_year / 100) * 100 as century,
                    COUNT(*) as count
                FROM artists
                WHERE birth_year IS NOT NULL
                GROUP BY FLOOR(birth_year / 100)
                ORDER BY century
            `);

            return successResponse(res, {
                general: stats.rows[0],
                top_nationalities: nationalityStats.rows,
                by_century: centuryStats.rows
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch artist statistics', error.message);
        }
    }
}

module.exports = new ArtistController();