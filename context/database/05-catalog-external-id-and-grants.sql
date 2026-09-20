-- Phase 1：catalog 攝取所需的補充欄位與應用角色權限
-- 對應設計文件：docs/designs/2026-09-20-phase1-catalog-ingestion.md §3
--
-- external_id：既有系統使用的字串 id（Chroma chunk id、Neo4j clean_id）。catalog 的 UUID 由它
-- 確定性推導，保留原字串是為了讓訂閱器寫回各檢索庫時沿用相同 id，既有資料才能被「認領」。
-- 可重複執行（IF NOT EXISTS）。

ALTER TABLE catalog.documents ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE catalog.chunks ADD COLUMN IF NOT EXISTS external_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_documents_external_id
    ON catalog.documents(external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_chunks_external_id
    ON catalog.chunks(external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_catalog_documents_source ON catalog.documents(source);

-- 應用程式角色（.env 的 DB_USER，目前為 art_user）只需要 catalog 的資料讀寫，不給 DDL 權限。
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'art_user') THEN
        GRANT USAGE ON SCHEMA catalog TO art_user;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalog TO art_user;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA catalog TO art_user;
    END IF;
END $$;
