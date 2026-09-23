/**
 * 館藏控制器
 * 處理館藏相關的API請求
 */

const { Collection, Artwork, Institution } = require('../../database/models');
const { successResponse, errorResponse } = require('../../utils/responseHelper');

class CollectionController {
    constructor() {
        this.collectionModel = new Collection();
        this.artworkModel = new Artwork();
        this.institutionModel = new Institution();
    }

    // 獲取所有館藏
    async getAllCollections(req, res) {
        try {
            const page = parseInt(req.query.page) || 1;
            const limit = Math.min(parseInt(req.query.limit) || 20, 100);
            const offset = (page - 1) * limit;

            const collections = await this.collectionModel.findAll(limit, offset);

            // 獲取每個館藏的機構資訊和作品統計
            const collectionsWithDetails = await Promise.all(
                collections.map(async (collection) => {
                    if (collection.institution_id) {
                        const institution = await this.institutionModel.findById(collection.institution_id);
                        collection.institution = institution;
                    }

                    // 獲取館藏中的作品數量
                    const artworkCount = await this.artworkModel.query(`
                        SELECT COUNT(*) as count FROM artworks WHERE collection_id = $1
                    `, [collection.id]);
                    collection.artwork_count = parseInt(artworkCount.rows[0].count);

                    return collection;
                })
            );

            return successResponse(res, collectionsWithDetails, {
                page,
                limit,
                total: collectionsWithDetails.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch collections', error.message);
        }
    }

    // 根據ID獲取館藏詳情
    async getCollectionById(req, res) {
        try {
            const { id } = req.params;
            const collection = await this.collectionModel.findById(id);

            if (!collection) {
                return errorResponse(res, 'Collection not found', null, 404);
            }

            // 獲取機構資訊
            if (collection.institution_id) {
                const institution = await this.institutionModel.findById(collection.institution_id);
                collection.institution = institution;
            }

            // 獲取館藏記錄相關統計
            const stats = await this.collectionModel.query(`
                SELECT
                    c.accession_number,
                    c.acquisition_date,
                    c.acquisition_method,
                    c.status,
                    a.creation_year,
                    a.style,
                    a.medium
                FROM collections c
                LEFT JOIN artworks a ON c.artwork_id = a.id
                WHERE c.id = $1
            `, [id]);

            collection.statistics = stats.rows[0];

            return successResponse(res, collection);
        } catch (error) {
            return errorResponse(res, 'Failed to fetch collection', error.message);
        }
    }

    // 獲取館藏記錄的詳細資訊（包含作品資訊）
    async getCollectionArtworks(req, res) {
        try {
            const { id } = req.params;

            // 檢查館藏記錄是否存在
            const collection = await this.collectionModel.findById(id);
            if (!collection) {
                return errorResponse(res, 'Collection record not found', null, 404);
            }

            // 獲取關聯的作品詳細資訊
            const artwork = await this.artworkModel.findById(collection.artwork_id);
            const institution = collection.institution_id ?
                await this.institutionModel.findById(collection.institution_id) : null;

            return successResponse(res, {
                collection_record: collection,
                artwork: artwork,
                institution: institution
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch collection details', error.message);
        }
    }

    // 創建新的館藏記錄
    async createCollection(req, res) {
        try {
            const collectionData = req.body;

            // 基本驗證
            if (!collectionData.artwork_id) {
                return errorResponse(res, 'Artwork ID is required', null, 400);
            }
            if (!collectionData.institution_id) {
                return errorResponse(res, 'Institution ID is required', null, 400);
            }

            // 檢查作品是否存在
            const artwork = await this.artworkModel.findById(collectionData.artwork_id);
            if (!artwork) {
                return errorResponse(res, 'Artwork not found', null, 404);
            }

            // 檢查機構是否存在
            const institution = await this.institutionModel.findById(collectionData.institution_id);
            if (!institution) {
                return errorResponse(res, 'Institution not found', null, 404);
            }

            const collection = await this.collectionModel.create({
                ...collectionData,
                id: require('uuid').v4(),
                created_at: new Date(),
                updated_at: new Date()
            });

            return successResponse(res, collection, null, 201);
        } catch (error) {
            return errorResponse(res, 'Failed to create collection record', error.message);
        }
    }

    // 更新館藏
    async updateCollection(req, res) {
        try {
            const { id } = req.params;
            const updateData = req.body;

            // 檢查館藏是否存在
            const existingCollection = await this.collectionModel.findById(id);
            if (!existingCollection) {
                return errorResponse(res, 'Collection not found', null, 404);
            }

            // 如果更新機構ID，檢查機構是否存在
            if (updateData.institution_id && updateData.institution_id !== existingCollection.institution_id) {
                const institution = await this.institutionModel.findById(updateData.institution_id);
                if (!institution) {
                    return errorResponse(res, 'Institution not found', null, 404);
                }
            }

            const updatedCollection = await this.collectionModel.update(id, {
                ...updateData,
                updated_at: new Date()
            });

            return successResponse(res, updatedCollection);
        } catch (error) {
            return errorResponse(res, 'Failed to update collection', error.message);
        }
    }

    // 刪除館藏
    async deleteCollection(req, res) {
        try {
            const { id } = req.params;

            const collection = await this.collectionModel.findById(id);
            if (!collection) {
                return errorResponse(res, 'Collection not found', null, 404);
            }

            // 檢查是否有關聯的藝術品
            const relatedArtworks = await this.artworkModel.query(
                'SELECT COUNT(*) as count FROM artworks WHERE collection_id = $1',
                [id]
            );

            if (parseInt(relatedArtworks.rows[0].count) > 0) {
                return errorResponse(res, 'Cannot delete collection with associated artworks', null, 409);
            }

            await this.collectionModel.delete(id);
            return successResponse(res, { message: 'Collection deleted successfully' });
        } catch (error) {
            return errorResponse(res, 'Failed to delete collection', error.message);
        }
    }

    // 搜索館藏
    async searchCollections(req, res) {
        try {
            const { q: searchText } = req.query;
            const limit = Math.min(parseInt(req.query.limit) || 20, 100);

            if (!searchText || searchText.trim().length === 0) {
                return errorResponse(res, 'Search query is required', null, 400);
            }

            const collections = await this.collectionModel.search(searchText, limit);

            return successResponse(res, {
                query: searchText,
                collections,
                count: collections.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to search collections', error.message);
        }
    }

    // 根據機構獲取館藏
    async getCollectionsByInstitution(req, res) {
        try {
            const { institutionId } = req.params;
            const limit = Math.min(parseInt(req.query.limit) || 50, 100);

            // 檢查機構是否存在
            const institution = await this.institutionModel.findById(institutionId);
            if (!institution) {
                return errorResponse(res, 'Institution not found', null, 404);
            }

            const collections = await this.collectionModel.findByInstitution(institutionId, limit);

            return successResponse(res, {
                institution,
                collections,
                count: collections.length
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch collections by institution', error.message);
        }
    }

    // 獲取館藏統計
    async getCollectionStatistics(req, res) {
        try {
            const stats = await this.collectionModel.query(`
                SELECT
                    COUNT(*) as total_collections,
                    COUNT(DISTINCT institution_id) as unique_institutions,
                    AVG(total_artworks) as avg_artworks_per_collection
                FROM (
                    SELECT
                        c.id,
                        c.institution_id,
                        COUNT(a.id) as total_artworks
                    FROM collections c
                    LEFT JOIN artworks a ON c.id = a.collection_id
                    GROUP BY c.id, c.institution_id
                ) as collection_stats
            `);

            const institutionStats = await this.collectionModel.query(`
                SELECT
                    i.name as institution_name,
                    COUNT(c.id) as collection_count,
                    COUNT(a.id) as total_artworks
                FROM institutions i
                LEFT JOIN collections c ON i.id = c.institution_id
                LEFT JOIN artworks a ON c.id = a.collection_id
                GROUP BY i.id, i.name
                ORDER BY collection_count DESC
                LIMIT 10
            `);

            return successResponse(res, {
                general: stats.rows[0],
                top_institutions: institutionStats.rows
            });
        } catch (error) {
            return errorResponse(res, 'Failed to fetch collection statistics', error.message);
        }
    }
}

module.exports = new CollectionController();