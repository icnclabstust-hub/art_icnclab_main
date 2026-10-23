/**
 * 搜索控制器
 * 提供統一的跨資源搜索服務
 */

const { Artwork, Artist, Collection, Institution } = require('../../database/models');
const { successResponse, errorResponse } = require('../../utils/responseHelper');
const { cacheManager } = require('../../utils/cacheManager');

class SearchController {
    constructor() {
        this.artworkModel = new Artwork();
        this.artistModel = new Artist();
        this.collectionModel = new Collection();
        this.institutionModel = new Institution();
    }

    // 全局搜索 - 跨所有資源類型
    async globalSearch(req, res) {
        try {
            const { q: searchText, limit = 20, type } = req.query;
            const searchLimit = Math.min(parseInt(limit), 100);

            if (!searchText || searchText.trim().length === 0) {
                return errorResponse(res, 'Search query is required', null, 400);
            }

            // 生成快取鍵
            const searchTypes = type ? [type] : ['artworks', 'artists', 'collections'];
            const cacheKey = `global_${searchText.toLowerCase()}_${searchTypes.join('_')}_${searchLimit}`;

            // 使用快取包裝器
            const results = await cacheManager.wrap(
                'search',
                cacheKey,
                async () => {
                    const searchResults = {
                        query: searchText,
                        results: {}
                    };

                    if (searchTypes.includes('artworks')) {
                        try {
                            const artworks = await this.artworkModel.search(searchText, searchLimit);
                            searchResults.results.artworks = {
                                count: artworks.length,
                                items: artworks
                            };
                        } catch (error) {
                            searchResults.results.artworks = { count: 0, items: [], error: error.message };
                        }
                    }

                    if (searchTypes.includes('artists')) {
                        try {
                            const artists = await this.artistModel.search(searchText, searchLimit);
                            searchResults.results.artists = {
                                count: artists.length,
                                items: artists
                            };
                        } catch (error) {
                            searchResults.results.artists = { count: 0, items: [], error: error.message };
                        }
                    }

                    if (searchTypes.includes('collections')) {
                        try {
                            const collections = await this.collectionModel.search(searchText, searchLimit);
                            searchResults.results.collections = {
                                count: collections.length,
                                items: collections
                            };
                        } catch (error) {
                            searchResults.results.collections = { count: 0, items: [], error: error.message };
                        }
                    }

                    // 計算總結果數
                    searchResults.total_count = Object.values(searchResults.results).reduce((sum, category) => sum + category.count, 0);

                    return searchResults;
                }
            );

            return successResponse(res, results);
        } catch (error) {
            return errorResponse(res, 'Search failed', error.message);
        }
    }

    // 高級搜索 - 支持多個過濾條件
    async advancedSearch(req, res) {
        try {
            const {
                q: searchText,
                type = 'artworks',
                period_start,
                period_end,
                style,
                nationality,
                medium,
                institution_id,
                limit = 50
            } = req.query;

            const searchLimit = Math.min(parseInt(limit), 200);

            if (!searchText || searchText.trim().length === 0) {
                return errorResponse(res, 'Search query is required', null, 400);
            }

            let results = [];
            const filters = {};

            // 構建過濾條件
            if (period_start) filters.period_start = parseInt(period_start);
            if (period_end) filters.period_end = parseInt(period_end);
            if (style) filters.style = style;
            if (nationality) filters.nationality = nationality;
            if (medium) filters.medium = medium;
            if (institution_id) filters.institution_id = institution_id;

            // 根據類型執行搜索
            switch (type) {
                case 'artworks':
                    results = await this.searchArtworksAdvanced(searchText, filters, searchLimit);
                    break;
                case 'artists':
                    results = await this.searchArtistsAdvanced(searchText, filters, searchLimit);
                    break;
                case 'collections':
                    results = await this.searchCollectionsAdvanced(searchText, filters, searchLimit);
                    break;
                default:
                    return errorResponse(res, 'Invalid search type. Must be: artworks, artists, or collections', null, 400);
            }

            return successResponse(res, {
                query: searchText,
                type,
                filters,
                results,
                count: results.length
            });
        } catch (error) {
            return errorResponse(res, 'Advanced search failed', error.message);
        }
    }

    // 搜索建議 - 自動完成功能
    async searchSuggestions(req, res) {
        try {
            const { q: searchText, type = 'all', limit = 10 } = req.query;
            const suggestionLimit = Math.min(parseInt(limit), 50);

            if (!searchText || searchText.trim().length < 2) {
                return errorResponse(res, 'Search query must be at least 2 characters', null, 400);
            }

            // 生成快取鍵
            const cacheKey = `suggestions_${searchText.toLowerCase()}_${type}_${suggestionLimit}`;

            // 使用快取包裝器
            const suggestions = await cacheManager.wrap(
                'search',
                cacheKey,
                async () => {
                    const result = {
                        query: searchText,
                        suggestions: {}
                    };

                    // 基於搜索文字提供建議
                    if (type === 'all' || type === 'titles') {
                        const artworkTitles = await this.artworkModel.query(`
                            SELECT DISTINCT title
                            FROM artworks
                            WHERE title ILIKE $1
                            ORDER BY title
                            LIMIT $2
                        `, [`${searchText}%`, suggestionLimit]);

                        result.suggestions.titles = artworkTitles.rows.map(row => row.title);
                    }

                    if (type === 'all' || type === 'artists') {
                        const artistNames = await this.artistModel.query(`
                            SELECT DISTINCT name
                            FROM artists
                            WHERE name ILIKE $1
                            ORDER BY name
                            LIMIT $2
                        `, [`${searchText}%`, suggestionLimit]);

                        result.suggestions.artists = artistNames.rows.map(row => row.name);
                    }

                    if (type === 'all' || type === 'styles') {
                        const styles = await this.artworkModel.query(`
                            SELECT DISTINCT style
                            FROM artworks
                            WHERE style ILIKE $1 AND style IS NOT NULL
                            ORDER BY style
                            LIMIT $2
                        `, [`${searchText}%`, suggestionLimit]);

                        result.suggestions.styles = styles.rows.map(row => row.style);
                    }

                    return result;
                },
                3600 // 1小時快取，因為建議相對穩定
            );

            return successResponse(res, suggestions);
        } catch (error) {
            return errorResponse(res, 'Failed to get search suggestions', error.message);
        }
    }

    // 輔助方法 - 高級藝術品搜索
    async searchArtworksAdvanced(searchText, filters, limit) {
        let query = `
            SELECT a.*, ar.name as artist_name
            FROM artworks a
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE (a.title ILIKE $1 OR a.description ILIKE $1 OR ar.name ILIKE $1)
        `;

        const params = [`%${searchText}%`];
        let paramCount = 1;

        // 添加過濾條件
        if (filters.period_start) {
            paramCount++;
            query += ` AND a.creation_year >= $${paramCount}`;
            params.push(filters.period_start);
        }

        if (filters.period_end) {
            paramCount++;
            query += ` AND a.creation_year <= $${paramCount}`;
            params.push(filters.period_end);
        }

        if (filters.style) {
            paramCount++;
            query += ` AND a.style ILIKE $${paramCount}`;
            params.push(`%${filters.style}%`);
        }

        if (filters.medium) {
            paramCount++;
            query += ` AND a.medium ILIKE $${paramCount}`;
            params.push(`%${filters.medium}%`);
        }

        paramCount++;
        query += ` ORDER BY a.created_at DESC LIMIT $${paramCount}`;
        params.push(limit);

        const result = await this.artworkModel.query(query, params);
        return result.rows;
    }

    // 輔助方法 - 高級藝術家搜索
    async searchArtistsAdvanced(searchText, filters, limit) {
        let query = `
            SELECT *
            FROM artists
            WHERE (name ILIKE $1 OR biography ILIKE $1)
        `;

        const params = [`%${searchText}%`];
        let paramCount = 1;

        if (filters.nationality) {
            paramCount++;
            query += ` AND nationality ILIKE $${paramCount}`;
            params.push(`%${filters.nationality}%`);
        }

        if (filters.period_start) {
            paramCount++;
            query += ` AND birth_year >= $${paramCount}`;
            params.push(filters.period_start);
        }

        if (filters.period_end) {
            paramCount++;
            query += ` AND birth_year <= $${paramCount}`;
            params.push(filters.period_end);
        }

        paramCount++;
        query += ` ORDER BY name LIMIT $${paramCount}`;
        params.push(limit);

        const result = await this.artistModel.query(query, params);
        return result.rows;
    }

    // 輔助方法 - 高級館藏搜索
    async searchCollectionsAdvanced(searchText, filters, limit) {
        let query = `
            SELECT c.*, i.name as institution_name
            FROM collections c
            LEFT JOIN institutions i ON c.institution_id = i.id
            WHERE (c.name ILIKE $1 OR c.description ILIKE $1 OR i.name ILIKE $1)
        `;

        const params = [`%${searchText}%`];
        let paramCount = 1;

        if (filters.institution_id) {
            paramCount++;
            query += ` AND c.institution_id = $${paramCount}`;
            params.push(filters.institution_id);
        }

        paramCount++;
        query += ` ORDER BY c.name LIMIT $${paramCount}`;
        params.push(limit);

        const result = await this.collectionModel.query(query, params);
        return result.rows;
    }
}

module.exports = new SearchController();