-- 藝術史資料庫效能優化索引
-- 根據查詢模式分析結果，添加缺少的索引以提升查詢效能

-- ========================================
-- 檢查現有索引狀況
-- ========================================

-- 查看所有現有索引
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ========================================
-- 新增效能優化索引
-- ========================================

-- 1. 藝術家表 (artists) 優化索引
-- 國籍與時期復合索引 - 支持國籍和出生年份組合查詢
CREATE INDEX IF NOT EXISTS idx_artists_nationality_birth_year
ON artists(nationality, birth_year)
WHERE nationality IS NOT NULL AND birth_year IS NOT NULL;

-- 藝術運動索引 - 快速查找特定藝術運動的藝術家
CREATE INDEX IF NOT EXISTS idx_artists_art_movement
ON artists(art_movement)
WHERE art_movement IS NOT NULL;

-- 生卒年範圍索引 - 支持時期查詢
CREATE INDEX IF NOT EXISTS idx_artists_birth_death_year
ON artists(birth_year, death_year)
WHERE birth_year IS NOT NULL;

-- 2. 藝術作品表 (artworks) 效能索引
-- 風格索引 - 快速按風格查詢
CREATE INDEX IF NOT EXISTS idx_artworks_style
ON artworks(style)
WHERE style IS NOT NULL;

-- 媒材索引 - 支持媒材分類查詢
CREATE INDEX IF NOT EXISTS idx_artworks_medium
ON artworks(medium)
WHERE medium IS NOT NULL;

-- 創作年份範圍索引 - 優化時期查詢
CREATE INDEX IF NOT EXISTS idx_artworks_creation_year_desc
ON artworks(creation_year DESC)
WHERE creation_year IS NOT NULL;

-- 藝術家與創作年份復合索引 - 優化藝術家作品時序查詢
CREATE INDEX IF NOT EXISTS idx_artworks_artist_creation_year
ON artworks(artist_id, creation_year DESC);

-- 風格與創作年份復合索引 - 支持風格時期組合查詢
CREATE INDEX IF NOT EXISTS idx_artworks_style_year
ON artworks(style, creation_year DESC)
WHERE style IS NOT NULL AND creation_year IS NOT NULL;

-- 3. 全文搜索優化索引
-- 藝術作品標題全文索引（三元組）
CREATE INDEX IF NOT EXISTS idx_artworks_title_fulltext
ON artworks USING gin(to_tsvector('english', title));

-- 藝術作品描述全文索引
CREATE INDEX IF NOT EXISTS idx_artworks_description_fulltext
ON artworks USING gin(to_tsvector('english', description))
WHERE description IS NOT NULL;

-- 藝術家姓名全文索引
CREATE INDEX IF NOT EXISTS idx_artists_name_fulltext
ON artists USING gin(to_tsvector('english', name));

-- 藝術家傳記全文索引
CREATE INDEX IF NOT EXISTS idx_artists_biography_fulltext
ON artists USING gin(to_tsvector('english', biography))
WHERE biography IS NOT NULL;

-- 4. 館藏相關索引
-- 館藏狀態索引 - 快速查找活躍館藏
CREATE INDEX IF NOT EXISTS idx_collections_status
ON collections(status);

-- 收藏編號索引 - 支持編號查找
CREATE INDEX IF NOT EXISTS idx_collections_accession_number
ON collections(accession_number)
WHERE accession_number IS NOT NULL;

-- 收藏日期索引 - 支持時序查詢
CREATE INDEX IF NOT EXISTS idx_collections_acquisition_date
ON collections(acquisition_date DESC)
WHERE acquisition_date IS NOT NULL;

-- 機構國家索引
CREATE INDEX IF NOT EXISTS idx_institutions_country
ON institutions(country)
WHERE country IS NOT NULL;

-- 機構類型索引
CREATE INDEX IF NOT EXISTS idx_institutions_type
ON institutions(type)
WHERE type IS NOT NULL;

-- 5. 標籤系統索引
-- 標籤分類索引
CREATE INDEX IF NOT EXISTS idx_tags_category
ON tags(category)
WHERE category IS NOT NULL;

-- 藝術作品標籤關聯優化
CREATE INDEX IF NOT EXISTS idx_artwork_tags_relevance
ON artwork_tags(artwork_id, relevance_score DESC);

-- 標籤使用統計索引
CREATE INDEX IF NOT EXISTS idx_artwork_tags_tag_artwork
ON artwork_tags(tag_id, artwork_id);

-- 6. RAG系統相關索引
-- 文檔向量內容類型索引
CREATE INDEX IF NOT EXISTS idx_document_vectors_content_type
ON document_vectors(content_type);

-- 文檔向量內容ID與類型復合索引
CREATE INDEX IF NOT EXISTS idx_document_vectors_content_id_type
ON document_vectors(content_id, content_type);

-- 搜索查詢記錄時間索引
CREATE INDEX IF NOT EXISTS idx_search_queries_created_at
ON search_queries(created_at DESC);

-- 搜索查詢類型索引
CREATE INDEX IF NOT EXISTS idx_search_queries_type
ON search_queries(query_type)
WHERE query_type IS NOT NULL;

-- 7. 爬蟲任務索引
-- 任務狀態與優先級復合索引（已存在，但確保存在）
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status_priority_v2
ON crawl_tasks(status, priority, created_at)
WHERE status IN ('pending', 'processing');

-- 任務來源索引
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_source_name
ON crawl_tasks(source_name)
WHERE source_name IS NOT NULL;

-- 完成時間索引
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_completed_at
ON crawl_tasks(completed_at DESC)
WHERE completed_at IS NOT NULL;

-- ========================================
-- 部分索引優化（針對常見查詢條件）
-- ========================================

-- 活躍藝術作品索引（排除沒有基本信息的記錄）
CREATE INDEX IF NOT EXISTS idx_artworks_active
ON artworks(created_at DESC)
WHERE title IS NOT NULL AND artist_id IS NOT NULL;

-- 完整藝術家資料索引
CREATE INDEX IF NOT EXISTS idx_artists_complete
ON artists(name, nationality, birth_year)
WHERE name IS NOT NULL;

-- ========================================
-- 索引使用統計和監控
-- ========================================

-- 查看索引使用統計的查詢（僅用於監控，不執行）
/*
SELECT
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
*/

-- 查看表掃描統計
/*
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY seq_scan DESC;
*/

-- ========================================
-- 完成提示
-- ========================================

DO $$
BEGIN
    RAISE NOTICE '==============================================';
    RAISE NOTICE '效能優化索引創建完成';
    RAISE NOTICE '新增索引數量: 約25個針對性索引';
    RAISE NOTICE '優化範圍: 搜索、過濾、JOIN、排序操作';
    RAISE NOTICE '==============================================';
END $$;