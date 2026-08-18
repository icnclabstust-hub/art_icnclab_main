-- 藝術史資料庫基礎架構設計
-- PostgreSQL 資料庫結構定義

-- 創建資料庫
-- CREATE DATABASE art_history_db;
-- \c art_history_db;

-- 啟用必要擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- ========================================
-- 核心資料表結構
-- ========================================

-- 藝術家表
CREATE TABLE artists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    name_variants JSONB DEFAULT '[]', -- 不同語言的名稱變體
    birth_year INTEGER,
    death_year INTEGER,
    nationality VARCHAR(100),
    art_movement VARCHAR(100),
    biography TEXT,
    source_urls TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 藝術作品表
CREATE TABLE artworks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    title_variants JSONB DEFAULT '[]', -- 不同語言的標題變體
    artist_id UUID REFERENCES artists(id) ON DELETE CASCADE,
    creation_year INTEGER,
    medium VARCHAR(200),
    dimensions VARCHAR(200),
    description TEXT,
    style VARCHAR(100),
    subject_matter VARCHAR(200),
    location VARCHAR(300),
    current_location VARCHAR(300),
    provenance TEXT,
    significance TEXT, -- 藝術史意義
    source_urls TEXT[],
    image_urls TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 館藏機構表
CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    type VARCHAR(50), -- museum, gallery, private_collection
    country VARCHAR(100),
    city VARCHAR(100),
    address TEXT,
    website VARCHAR(500),
    description TEXT,
    collection_focus TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 館藏關係表
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artwork_id UUID REFERENCES artworks(id) ON DELETE CASCADE,
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    accession_number VARCHAR(100),
    acquisition_date DATE,
    acquisition_method VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active', -- active, loaned, sold, destroyed
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artwork_id, institution_id)
);

-- 藝術運動/風格表
CREATE TABLE art_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL UNIQUE,
    period_start INTEGER,
    period_end INTEGER,
    origin_country VARCHAR(100),
    description TEXT,
    key_characteristics TEXT,
    influence TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 藝術家與藝術運動關係表
CREATE TABLE artist_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artist_id UUID REFERENCES artists(id) ON DELETE CASCADE,
    movement_id UUID REFERENCES art_movements(id) ON DELETE CASCADE,
    involvement_type VARCHAR(50), -- founder, key_member, influenced_by
    period_start INTEGER,
    period_end INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, movement_id)
);

-- 標籤表（用於分類和檢索）
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50), -- subject, style, technique, period, location
    description TEXT,
    parent_tag_id UUID REFERENCES tags(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 藝術作品標籤關係表
CREATE TABLE artwork_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artwork_id UUID REFERENCES artworks(id) ON DELETE CASCADE,
    tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2) DEFAULT 1.0,
    assigned_by VARCHAR(50), -- human, ai_agent, web_crawler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artwork_id, tag_id)
);

-- ========================================
-- RAG系統支援表
-- ========================================

-- 文檔向量表（用於RAG檢索）
CREATE TABLE document_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL, -- 可以關聯到任何實體的ID
    content_type VARCHAR(50) NOT NULL, -- artwork, artist, institution, etc.
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_summary TEXT,
    embedding VECTOR(1536), -- OpenAI embedding 維度
    chunk_index INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 1,
    source_url VARCHAR(1000),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 搜索查詢記錄表
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    query_type VARCHAR(50), -- semantic, keyword, hybrid
    user_session VARCHAR(100),
    results_count INTEGER,
    response_time_ms INTEGER,
    feedback_score DECIMAL(2,1), -- 用戶反饋評分
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 爬蟲和處理狀態表
-- ========================================

-- 爬蟲任務表
CREATE TABLE crawl_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url VARCHAR(1000) NOT NULL,
    source_name VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    task_type VARCHAR(50), -- artist, artwork, institution, collection
    priority INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    results_summary JSONB,
    agent_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 資料處理日誌表
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50),
    entity_id UUID,
    operation VARCHAR(50), -- extract, classify, translate, summarize
    agent_name VARCHAR(100),
    status VARCHAR(50), -- success, error, warning
    input_data JSONB,
    output_data JSONB,
    error_details TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 索引創建
-- ========================================

-- 基本索引
CREATE INDEX idx_artists_name ON artists(name);
CREATE INDEX idx_artists_nationality ON artists(nationality);
CREATE INDEX idx_artworks_title ON artworks(title);
CREATE INDEX idx_artworks_artist_id ON artworks(artist_id);
CREATE INDEX idx_artworks_creation_year ON artworks(creation_year);
CREATE INDEX idx_collections_artwork_id ON collections(artwork_id);
CREATE INDEX idx_collections_institution_id ON collections(institution_id);

-- 全文搜索索引
CREATE INDEX idx_artists_name_trgm ON artists USING gin(name gin_trgm_ops);
CREATE INDEX idx_artworks_title_trgm ON artworks USING gin(title gin_trgm_ops);
CREATE INDEX idx_artworks_description_trgm ON artworks USING gin(description gin_trgm_ops);

-- JSONB索引
CREATE INDEX idx_artists_metadata ON artists USING gin(metadata);
CREATE INDEX idx_artworks_metadata ON artworks USING gin(metadata);
CREATE INDEX idx_document_vectors_metadata ON document_vectors USING gin(metadata);

-- 向量索引（需要pgvector擴展）
-- CREATE INDEX idx_document_vectors_embedding ON document_vectors USING ivfflat (embedding vector_cosine_ops);

-- 複合索引
CREATE INDEX idx_artworks_artist_year ON artworks(artist_id, creation_year);
CREATE INDEX idx_crawl_tasks_status_priority ON crawl_tasks(status, priority);

-- ========================================
-- 觸發器函數
-- ========================================

-- 更新時間戳觸發器函數
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 為相關表創建更新時間戳觸發器
CREATE TRIGGER update_artists_updated_at BEFORE UPDATE ON artists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_artworks_updated_at BEFORE UPDATE ON artworks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_institutions_updated_at BEFORE UPDATE ON institutions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_collections_updated_at BEFORE UPDATE ON collections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_vectors_updated_at BEFORE UPDATE ON document_vectors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 視圖定義
-- ========================================

-- 完整藝術作品資訊視圖
CREATE VIEW artwork_details AS
SELECT
    a.id,
    a.title,
    a.title_variants,
    a.creation_year,
    a.medium,
    a.dimensions,
    a.description,
    a.style,
    a.subject_matter,
    a.location,
    a.current_location,
    a.significance,
    a.image_urls,
    ar.name as artist_name,
    ar.nationality as artist_nationality,
    ar.art_movement,
    i.name as institution_name,
    i.country as institution_country,
    c.accession_number,
    array_agg(DISTINCT t.name) as tags,
    a.metadata,
    a.created_at,
    a.updated_at
FROM artworks a
LEFT JOIN artists ar ON a.artist_id = ar.id
LEFT JOIN collections c ON a.id = c.artwork_id
LEFT JOIN institutions i ON c.institution_id = i.id
LEFT JOIN artwork_tags at ON a.id = at.artwork_id
LEFT JOIN tags t ON at.tag_id = t.id
GROUP BY a.id, ar.id, i.id, c.id;

-- 藝術家作品統計視圖
CREATE VIEW artist_statistics AS
SELECT
    ar.id,
    ar.name,
    ar.nationality,
    ar.art_movement,
    COUNT(a.id) as artwork_count,
    MIN(a.creation_year) as earliest_work,
    MAX(a.creation_year) as latest_work,
    array_agg(DISTINCT a.style) as styles_used,
    array_agg(DISTINCT i.name) as represented_institutions
FROM artists ar
LEFT JOIN artworks a ON ar.id = a.artist_id
LEFT JOIN collections c ON a.id = c.artwork_id
LEFT JOIN institutions i ON c.institution_id = i.id
GROUP BY ar.id, ar.name, ar.nationality, ar.art_movement;

-- ========================================
-- 初始資料插入
-- ========================================

-- 插入基礎標籤分類
INSERT INTO tags (name, category, description) VALUES
('Renaissance', 'period', '文藝復興時期藝術'),
('Baroque', 'period', '巴洛克時期藝術'),
('Impressionism', 'style', '印象派風格'),
('Oil Painting', 'technique', '油畫技法'),
('Portrait', 'subject', '肖像畫'),
('Landscape', 'subject', '風景畫'),
('Religious', 'subject', '宗教主題'),
('Mythology', 'subject', '神話主題'),
('Europe', 'location', '歐洲'),
('Asia', 'location', '亞洲')
ON CONFLICT (name) DO NOTHING;

-- 插入範例機構
INSERT INTO institutions (name, type, country, city, website, description) VALUES
('Louvre Museum', 'museum', 'France', 'Paris', 'https://www.louvre.fr', '世界最大的藝術博物館之一'),
('Metropolitan Museum of Art', 'museum', 'USA', 'New York', 'https://www.metmuseum.org', '紐約大都會藝術博物館'),
('British Museum', 'museum', 'UK', 'London', 'https://www.britishmuseum.org', '大英博物館'),
('National Palace Museum', 'museum', 'Taiwan', 'Taipei', 'https://www.npm.gov.tw', '國立故宮博物院')
ON CONFLICT DO NOTHING;

-- 提示完成
COMMENT ON DATABASE CURRENT_DATABASE() IS '藝術史資料庫 - 支援RAG系統的完整藝術史資料架構';