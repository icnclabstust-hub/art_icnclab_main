-- 修復資料庫結構 - 處理向量類型問題

-- 刪除有問題的表
DROP TABLE IF EXISTS document_vectors;

-- 重新創建文檔向量表（暫時不使用VECTOR類型）
CREATE TABLE document_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_summary TEXT,
    embedding TEXT, -- 暫時用TEXT存儲向量，之後可以改為JSONB或安裝pgvector
    chunk_index INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 1,
    source_url VARCHAR(1000),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 創建相關索引
CREATE INDEX idx_document_vectors_content_id ON document_vectors(content_id, content_type);
CREATE INDEX idx_document_vectors_content_type ON document_vectors(content_type);
CREATE INDEX idx_document_vectors_metadata ON document_vectors USING gin(metadata);

-- 添加觸發器
CREATE TRIGGER update_document_vectors_updated_at BEFORE UPDATE ON document_vectors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 註釋向量索引（需要pgvector擴展）
-- CREATE INDEX idx_document_vectors_embedding ON document_vectors USING ivfflat (embedding vector_cosine_ops);

-- 確保所有其他表都正確創建
-- 檢查表結構
DO $$
BEGIN
    -- 打印創建的表信息
    RAISE NOTICE '資料庫結構修復完成';
    RAISE NOTICE '已創建的表: %', (
        SELECT STRING_AGG(tablename, ', ')
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename NOT LIKE 'pg_%'
    );
END $$;