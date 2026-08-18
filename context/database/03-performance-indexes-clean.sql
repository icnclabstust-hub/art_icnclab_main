-- 藝術史資料庫效能優化索引（簡化版）
-- 根據查詢模式分析結果，添加缺少的索引以提升查詢效能

-- 1. 藝術家表 (artists) 優化索引
CREATE INDEX IF NOT EXISTS idx_artists_nationality_birth_year
ON artists(nationality, birth_year)
WHERE nationality IS NOT NULL AND birth_year IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artists_art_movement
ON artists(art_movement)
WHERE art_movement IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artists_birth_death_year
ON artists(birth_year, death_year)
WHERE birth_year IS NOT NULL;

-- 2. 藝術作品表 (artworks) 效能索引
CREATE INDEX IF NOT EXISTS idx_artworks_style
ON artworks(style)
WHERE style IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artworks_medium
ON artworks(medium)
WHERE medium IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artworks_creation_year_desc
ON artworks(creation_year DESC)
WHERE creation_year IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artworks_artist_creation_year
ON artworks(artist_id, creation_year DESC);

CREATE INDEX IF NOT EXISTS idx_artworks_style_year
ON artworks(style, creation_year DESC)
WHERE style IS NOT NULL AND creation_year IS NOT NULL;

-- 3. 全文搜索優化索引
CREATE INDEX IF NOT EXISTS idx_artworks_title_fulltext
ON artworks USING gin(to_tsvector('english', title));

CREATE INDEX IF NOT EXISTS idx_artworks_description_fulltext
ON artworks USING gin(to_tsvector('english', description))
WHERE description IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artists_name_fulltext
ON artists USING gin(to_tsvector('english', name));

CREATE INDEX IF NOT EXISTS idx_artists_biography_fulltext
ON artists USING gin(to_tsvector('english', biography))
WHERE biography IS NOT NULL;

-- 4. 館藏相關索引
CREATE INDEX IF NOT EXISTS idx_collections_status
ON collections(status);

CREATE INDEX IF NOT EXISTS idx_collections_accession_number
ON collections(accession_number)
WHERE accession_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_collections_acquisition_date
ON collections(acquisition_date DESC)
WHERE acquisition_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_institutions_country
ON institutions(country)
WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_institutions_type
ON institutions(type)
WHERE type IS NOT NULL;

-- 5. 標籤系統索引
CREATE INDEX IF NOT EXISTS idx_tags_category
ON tags(category)
WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artwork_tags_relevance
ON artwork_tags(artwork_id, relevance_score DESC);

CREATE INDEX IF NOT EXISTS idx_artwork_tags_tag_artwork
ON artwork_tags(tag_id, artwork_id);

-- 6. RAG系統相關索引
CREATE INDEX IF NOT EXISTS idx_document_vectors_content_type_updated
ON document_vectors(content_type);

CREATE INDEX IF NOT EXISTS idx_document_vectors_content_id_type_updated
ON document_vectors(content_id, content_type);

CREATE INDEX IF NOT EXISTS idx_search_queries_created_at
ON search_queries(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_queries_type
ON search_queries(query_type)
WHERE query_type IS NOT NULL;

-- 7. 爬蟲任務索引
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status_priority_v2
ON crawl_tasks(status, priority, created_at)
WHERE status IN ('pending', 'processing');

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_source_name
ON crawl_tasks(source_name)
WHERE source_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_completed_at
ON crawl_tasks(completed_at DESC)
WHERE completed_at IS NOT NULL;

-- 8. 部分索引優化（針對常見查詢條件）
CREATE INDEX IF NOT EXISTS idx_artworks_active
ON artworks(created_at DESC)
WHERE title IS NOT NULL AND artist_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artists_complete
ON artists(name, nationality, birth_year)
WHERE name IS NOT NULL;