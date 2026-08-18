/**
 * 藝術史資料庫 - 資料模型層
 * 提供統一的資料存取介面，支援RAG系統集成
 */

const { Pool } = require('pg');
const { v4: uuidv4 } = require('uuid');
const { globalTimeoutHandler } = require('../utils/timeoutHandler');
require('dotenv').config();

// 資料庫連接池
const pool = new Pool({
    user: process.env.DB_USER || 'postgres',
    host: process.env.DB_HOST || 'localhost',
    database: process.env.DB_NAME || 'art_history_db',
    password: process.env.DB_PASSWORD || 'password',
    port: process.env.DB_PORT || 5432,
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
});

// 基礎模型類
class BaseModel {
    constructor(tableName) {
        this.tableName = tableName;
        this.pool = pool;
    }

    async query(text, params, timeout = null) {
        const operationName = `Query: ${this.tableName}`;
        const queryPromise = (async () => {
            const client = await this.pool.connect();
            try {
                const result = await client.query(text, params);
                return result;
            } finally {
                client.release();
            }
        })();

        // 使用全域超時處理器包裝查詢
        return globalTimeoutHandler.withDatabaseTimeout(
            queryPromise,
            operationName,
            timeout
        );
    }

    async findById(id) {
        const query = `SELECT * FROM ${this.tableName} WHERE id = $1`;
        const result = await this.query(query, [id]);
        return result.rows[0] || null;
    }

    async findAll(limit = 100, offset = 0) {
        const query = `SELECT * FROM ${this.tableName} ORDER BY created_at DESC LIMIT $1 OFFSET $2`;
        const result = await this.query(query, [limit, offset]);
        return result.rows;
    }

    async create(data) {
        const fields = Object.keys(data);
        const values = Object.values(data);
        const placeholders = fields.map((_, index) => `$${index + 1}`);

        const query = `
            INSERT INTO ${this.tableName} (${fields.join(', ')})
            VALUES (${placeholders.join(', ')})
            RETURNING *
        `;

        const result = await this.query(query, values);
        return result.rows[0];
    }

    async update(id, data) {
        const fields = Object.keys(data);
        const values = Object.values(data);
        const setClause = fields.map((field, index) => `${field} = $${index + 2}`);

        const query = `
            UPDATE ${this.tableName}
            SET ${setClause.join(', ')}, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING *
        `;

        const result = await this.query(query, [id, ...values]);
        return result.rows[0];
    }

    async delete(id) {
        const query = `DELETE FROM ${this.tableName} WHERE id = $1 RETURNING *`;
        const result = await this.query(query, [id]);
        return result.rows[0];
    }

    // 基礎搜索方法 - 子類應該重寫此方法以適應不同的表結構
    async search(searchText, limit = 50) {
        // 預設簡單的名稱搜索，適用於大多數表
        const query = `SELECT * FROM ${this.tableName} WHERE name ILIKE $1 LIMIT $2`;
        const result = await this.query(query, [`%${searchText}%`, limit]);
        return result.rows;
    }
}

// 藝術家模型
class Artist extends BaseModel {
    constructor() {
        super('artists');
    }

    async createArtist(artistData) {
        const data = {
            id: uuidv4(),
            name: artistData.name,
            name_variants: JSON.stringify(artistData.name_variants || []),
            birth_year: artistData.birth_year,
            death_year: artistData.death_year,
            nationality: artistData.nationality,
            art_movement: artistData.art_movement,
            biography: artistData.biography,
            source_urls: artistData.source_urls || [],
            metadata: JSON.stringify(artistData.metadata || {})
        };
        return await this.create(data);
    }

    async findByName(name) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE name ILIKE $1 OR name_variants::text ILIKE $1
            ORDER BY similarity(name, $1) DESC
        `;
        const result = await this.query(query, [`%${name}%`]);
        return result.rows;
    }

    async getArtistWithArtworks(artistId) {
        const query = `
            SELECT
                ar.*,
                json_agg(
                    json_build_object(
                        'id', a.id,
                        'title', a.title,
                        'creation_year', a.creation_year,
                        'medium', a.medium,
                        'description', a.description
                    )
                ) as artworks
            FROM artists ar
            LEFT JOIN artworks a ON ar.id = a.artist_id
            WHERE ar.id = $1
            GROUP BY ar.id
        `;
        const result = await this.query(query, [artistId]);
        return result.rows[0];
    }

    async getByMovement(movement) {
        const query = `SELECT * FROM ${this.tableName} WHERE art_movement = $1 ORDER BY name`;
        const result = await this.query(query, [movement]);
        return result.rows;
    }

    // 重寫搜索方法以適應artists表結構
    async search(searchText, limit = 50) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE name ILIKE $1
                OR biography ILIKE $1
                OR nationality ILIKE $1
                OR art_movement ILIKE $1
            ORDER BY name
            LIMIT $2
        `;
        const result = await this.query(query, [`%${searchText}%`, limit]);
        return result.rows;
    }
}

// 藝術作品模型
class Artwork extends BaseModel {
    constructor() {
        super('artworks');
    }

    // 簡化查詢 - 暫時使用基礎查詢進行測試
    async findAll(limit = 100, offset = 0) {
        const query = `SELECT * FROM ${this.tableName} ORDER BY created_at DESC LIMIT $1 OFFSET $2`;
        const result = await this.query(query, [limit, offset]);
        return result.rows;
    }

    async createArtwork(artworkData) {
        const data = {
            id: uuidv4(),
            title: artworkData.title,
            title_variants: JSON.stringify(artworkData.title_variants || []),
            artist_id: artworkData.artist_id,
            creation_year: artworkData.creation_year,
            medium: artworkData.medium,
            dimensions: artworkData.dimensions,
            description: artworkData.description,
            style: artworkData.style,
            subject_matter: artworkData.subject_matter,
            location: artworkData.location,
            current_location: artworkData.current_location,
            provenance: artworkData.provenance,
            significance: artworkData.significance,
            source_urls: artworkData.source_urls || [],
            image_urls: artworkData.image_urls || [],
            metadata: JSON.stringify(artworkData.metadata || {})
        };
        return await this.create(data);
    }

    async getArtworkDetails(artworkId) {
        const query = `
            SELECT * FROM artwork_details WHERE id = $1
        `;
        const result = await this.query(query, [artworkId]);
        return result.rows[0];
    }

    async findByArtist(artistId, limit = 50) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE artist_id = $1
            ORDER BY creation_year DESC
            LIMIT $2
        `;
        const result = await this.query(query, [artistId, limit]);
        return result.rows;
    }

    async findByPeriod(startYear, endYear, limit = 100) {
        const query = `
            SELECT a.*, ar.name as artist_name
            FROM ${this.tableName} a
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE creation_year BETWEEN $1 AND $2
            ORDER BY creation_year ASC
            LIMIT $3
        `;
        const result = await this.query(query, [startYear, endYear, limit]);
        return result.rows;
    }

    async findByStyle(style, limit = 50) {
        const query = `
            SELECT a.*, ar.name as artist_name
            FROM ${this.tableName} a
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE style ILIKE $1
            ORDER BY creation_year DESC
            LIMIT $2
        `;
        const result = await this.query(query, [`%${style}%`, limit]);
        return result.rows;
    }

    async addTags(artworkId, tagIds, assignedBy = 'system') {
        const values = tagIds.map(tagId => [uuidv4(), artworkId, tagId, 1.0, assignedBy]);
        const placeholders = values.map((_, index) => {
            const base = index * 5;
            return `($${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5})`;
        }).join(', ');

        const query = `
            INSERT INTO artwork_tags (id, artwork_id, tag_id, relevance_score, assigned_by)
            VALUES ${placeholders}
            ON CONFLICT (artwork_id, tag_id) DO UPDATE SET
                relevance_score = EXCLUDED.relevance_score,
                assigned_by = EXCLUDED.assigned_by
            RETURNING *
        `;

        const flatValues = values.flat();
        const result = await this.query(query, flatValues);
        return result.rows;
    }

    // 重寫搜索方法以適應artworks表結構
    async search(searchText, limit = 50) {
        const query = `
            SELECT a.*, ar.name as artist_name
            FROM ${this.tableName} a
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE a.title ILIKE $1
                OR a.description ILIKE $1
                OR a.style ILIKE $1
                OR a.medium ILIKE $1
                OR ar.name ILIKE $1
            ORDER BY a.creation_year DESC
            LIMIT $2
        `;
        const result = await this.query(query, [`%${searchText}%`, limit]);
        return result.rows;
    }
}

// 機構模型
class Institution extends BaseModel {
    constructor() {
        super('institutions');
    }

    async createInstitution(institutionData) {
        const data = {
            id: uuidv4(),
            name: institutionData.name,
            type: institutionData.type,
            country: institutionData.country,
            city: institutionData.city,
            address: institutionData.address,
            website: institutionData.website,
            description: institutionData.description,
            collection_focus: institutionData.collection_focus,
            metadata: JSON.stringify(institutionData.metadata || {})
        };
        return await this.create(data);
    }

    async getInstitutionWithCollection(institutionId) {
        const query = `
            SELECT
                i.*,
                json_agg(
                    json_build_object(
                        'artwork_id', c.artwork_id,
                        'artwork_title', a.title,
                        'artist_name', ar.name,
                        'accession_number', c.accession_number,
                        'acquisition_date', c.acquisition_date
                    )
                ) as collection
            FROM institutions i
            LEFT JOIN collections c ON i.id = c.institution_id
            LEFT JOIN artworks a ON c.artwork_id = a.id
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE i.id = $1
            GROUP BY i.id
        `;
        const result = await this.query(query, [institutionId]);
        return result.rows[0];
    }

    async findByCountry(country, limit = 20) {
        const query = `SELECT * FROM ${this.tableName} WHERE country ILIKE $1 ORDER BY name LIMIT $2`;
        const result = await this.query(query, [`%${country}%`, limit]);
        return result.rows;
    }
}

// 館藏記錄模型（作品收藏記錄）
class Collection extends BaseModel {
    constructor() {
        super('collections');
    }

    async createCollection(collectionData) {
        const data = {
            id: uuidv4(),
            artwork_id: collectionData.artwork_id,
            institution_id: collectionData.institution_id,
            accession_number: collectionData.accession_number,
            acquisition_date: collectionData.acquisition_date,
            acquisition_method: collectionData.acquisition_method,
            status: collectionData.status || 'active',
            notes: collectionData.notes,
            metadata: JSON.stringify(collectionData.metadata || {})
        };
        return await this.create(data);
    }

    async findByInstitution(institutionId, limit = 50) {
        const query = `
            SELECT c.*, i.name as institution_name, a.title as artwork_title, ar.name as artist_name
            FROM ${this.tableName} c
            LEFT JOIN institutions i ON c.institution_id = i.id
            LEFT JOIN artworks a ON c.artwork_id = a.id
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE c.institution_id = $1
            ORDER BY c.acquisition_date DESC LIMIT $2
        `;
        const result = await this.query(query, [institutionId, limit]);
        return result.rows;
    }

    async search(searchText, limit = 20) {
        const query = `
            SELECT c.*, i.name as institution_name, a.title as artwork_title, ar.name as artist_name
            FROM ${this.tableName} c
            LEFT JOIN institutions i ON c.institution_id = i.id
            LEFT JOIN artworks a ON c.artwork_id = a.id
            LEFT JOIN artists ar ON a.artist_id = ar.id
            WHERE c.accession_number ILIKE $1 OR c.notes ILIKE $1
                  OR i.name ILIKE $1 OR a.title ILIKE $1 OR ar.name ILIKE $1
            ORDER BY c.acquisition_date DESC
            LIMIT $2
        `;
        const result = await this.query(query, [`%${searchText}%`, limit]);
        return result.rows;
    }
}

// 向量文檔模型（RAG支援）
class DocumentVector extends BaseModel {
    constructor() {
        super('document_vectors');
    }

    async createDocument(documentData) {
        const data = {
            id: uuidv4(),
            content_id: documentData.content_id,
            content_type: documentData.content_type,
            title: documentData.title,
            content: documentData.content,
            content_summary: documentData.content_summary,
            chunk_index: documentData.chunk_index || 0,
            chunk_count: documentData.chunk_count || 1,
            source_url: documentData.source_url,
            metadata: JSON.stringify(documentData.metadata || {})
        };

        // 如果提供了embedding，則加入
        if (documentData.embedding) {
            data.embedding = `[${documentData.embedding.join(',')}]`;
        }

        return await this.create(data);
    }

    async findByContentId(contentId, contentType) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE content_id = $1 AND content_type = $2
            ORDER BY chunk_index ASC
        `;
        const result = await this.query(query, [contentId, contentType]);
        return result.rows;
    }

    async semanticSearch(queryEmbedding, contentType = null, limit = 10) {
        let query = `
            SELECT *,
                   1 - (embedding <=> $1::vector) as similarity
            FROM ${this.tableName}
        `;

        const params = [`[${queryEmbedding.join(',')}]`];

        if (contentType) {
            query += ` WHERE content_type = $2`;
            params.push(contentType);
        }

        query += ` ORDER BY similarity DESC LIMIT $${params.length + 1}`;
        params.push(limit);

        const result = await this.query(query, params);
        return result.rows;
    }

    async bulkInsertDocuments(documents) {
        if (documents.length === 0) return [];

        const fields = Object.keys(documents[0]);
        const placeholderRows = documents.map((_, index) => {
            const offset = index * fields.length;
            return `(${fields.map((_, fieldIndex) => `$${offset + fieldIndex + 1}`).join(', ')})`;
        }).join(', ');

        const query = `
            INSERT INTO ${this.tableName} (${fields.join(', ')})
            VALUES ${placeholderRows}
            RETURNING *
        `;

        const values = documents.flatMap(doc => fields.map(field => doc[field]));
        const result = await this.query(query, values);
        return result.rows;
    }
}

// 標籤模型
class Tag extends BaseModel {
    constructor() {
        super('tags');
    }

    async createTag(tagData) {
        const data = {
            id: uuidv4(),
            name: tagData.name,
            category: tagData.category,
            description: tagData.description,
            parent_tag_id: tagData.parent_tag_id,
            metadata: JSON.stringify(tagData.metadata || {})
        };
        return await this.create(data);
    }

    async findByCategory(category) {
        const query = `SELECT * FROM ${this.tableName} WHERE category = $1 ORDER BY name`;
        const result = await this.query(query, [category]);
        return result.rows;
    }

    async getTagHierarchy() {
        const query = `
            WITH RECURSIVE tag_hierarchy AS (
                SELECT id, name, category, description, parent_tag_id, 0 as level
                FROM tags
                WHERE parent_tag_id IS NULL

                UNION ALL

                SELECT t.id, t.name, t.category, t.description, t.parent_tag_id, th.level + 1
                FROM tags t
                INNER JOIN tag_hierarchy th ON t.parent_tag_id = th.id
            )
            SELECT * FROM tag_hierarchy ORDER BY level, name
        `;
        const result = await this.query(query);
        return result.rows;
    }
}

// 爬蟲任務模型
class CrawlTask extends BaseModel {
    constructor() {
        super('crawl_tasks');
    }

    async createTask(taskData) {
        const data = {
            id: uuidv4(),
            url: taskData.url,
            source_name: taskData.source_name,
            status: taskData.status || 'pending',
            task_type: taskData.task_type,
            priority: taskData.priority || 5,
            agent_name: taskData.agent_name,
            metadata: JSON.stringify(taskData.metadata || {})
        };
        return await this.create(data);
    }

    async getPendingTasks(limit = 10) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE status = 'pending' AND retry_count < max_retries
            ORDER BY priority ASC, created_at ASC
            LIMIT $1
        `;
        const result = await this.query(query, [limit]);
        return result.rows;
    }

    async updateTaskStatus(taskId, status, errorMessage = null, resultsSummary = null) {
        const updateData = { status };

        if (errorMessage) updateData.error_message = errorMessage;
        if (resultsSummary) updateData.results_summary = JSON.stringify(resultsSummary);
        if (status === 'completed') updateData.completed_at = new Date();
        if (status === 'failed') updateData.retry_count = 'retry_count + 1';

        return await this.update(taskId, updateData);
    }

    async getTasksByStatus(status, limit = 50) {
        const query = `
            SELECT * FROM ${this.tableName}
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2
        `;
        const result = await this.query(query, [status, limit]);
        return result.rows;
    }
}

// 統計和分析查詢
class Analytics {
    constructor() {
        this.pool = pool;
    }

    async query(text, params) {
        const client = await this.pool.connect();
        try {
            const result = await client.query(text, params);
            return result;
        } finally {
            client.release();
        }
    }

    async getDatabaseStats() {
        const query = `
            SELECT
                'artists' as table_name, COUNT(*) as count FROM artists
            UNION ALL
            SELECT 'artworks', COUNT(*) FROM artworks
            UNION ALL
            SELECT 'institutions', COUNT(*) FROM institutions
            UNION ALL
            SELECT 'document_vectors', COUNT(*) FROM document_vectors
            UNION ALL
            SELECT 'crawl_tasks', COUNT(*) FROM crawl_tasks
        `;
        const result = await this.query(query);
        return result.rows;
    }

    async getPopularTags(limit = 20) {
        const query = `
            SELECT t.name, t.category, COUNT(at.artwork_id) as usage_count
            FROM tags t
            LEFT JOIN artwork_tags at ON t.id = at.tag_id
            GROUP BY t.id, t.name, t.category
            ORDER BY usage_count DESC
            LIMIT $1
        `;
        const result = await this.query(query, [limit]);
        return result.rows;
    }

    async getArtworksByPeriod() {
        // 簡化查詢 - 使用更簡單的分組邏輯
        const query = `
            SELECT
                CASE
                    WHEN creation_year < 1500 THEN 'Before 1500'
                    WHEN creation_year < 1800 THEN '1500-1800'
                    WHEN creation_year < 1900 THEN '1800-1900'
                    WHEN creation_year < 2000 THEN '1900-2000'
                    ELSE '2000+'
                END as period,
                COUNT(*) as artwork_count
            FROM artworks
            WHERE creation_year IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(creation_year)
        `;
        const result = await this.query(query);
        return result.rows;
    }

    async getCrawlTaskStats() {
        const query = `
            SELECT status, COUNT(*) as count,
                   AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration_seconds
            FROM crawl_tasks
            GROUP BY status
        `;
        const result = await this.query(query);
        return result.rows;
    }
}

// 導出所有模型
module.exports = {
    BaseModel,
    Artist,
    Artwork,
    Collection,
    Institution,
    DocumentVector,
    Tag,
    CrawlTask,
    Analytics,
    pool
};