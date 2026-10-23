-- Phase 0（GD 通過項目）：新增 catalog / biz / eval 三個 schema
-- 對應設計文件：docs/designs/2026-09-11-target-architecture-consistency-eval-faithfulness.md 第 5.1、5.2 節
--
-- 範圍聲明（Phase 0）：僅建立 schema 與資料表結構，不搬移既有 public schema 的任何資料，
-- 不變更現行爬蟲/RAG 服務的寫入路徑。三個檢索庫（ChromaDB/Elasticsearch/Neo4j）尚未訂閱
-- catalog.sync_events，屬於 Phase 2 才會啟用的行為，此檔案不建立訂閱器相關物件。

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS biz;
CREATE SCHEMA IF NOT EXISTS eval;

-- ========================================
-- catalog：三檢索庫的單一事實來源（Phase 1 起才開始寫入）
-- ========================================

CREATE TABLE catalog.documents (
    doc_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source             VARCHAR(200) NOT NULL,
    content_hash       VARCHAR(64) NOT NULL,
    version            INTEGER NOT NULL DEFAULT 1,
    is_deleted         BOOLEAN NOT NULL DEFAULT FALSE,
    quarantine_status  VARCHAR(20) NOT NULL DEFAULT 'clean'
        CHECK (quarantine_status IN ('clean', 'quarantined', 'reviewed')),
    metadata           JSONB DEFAULT '{}',
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_catalog_documents_content_hash ON catalog.documents(content_hash);
CREATE INDEX idx_catalog_documents_quarantine_status ON catalog.documents(quarantine_status);

CREATE TABLE catalog.chunks (
    chunk_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id         UUID NOT NULL REFERENCES catalog.documents(doc_id) ON DELETE CASCADE,
    content_hash   VARCHAR(64) NOT NULL,
    chunk_index    INTEGER NOT NULL,
    version        INTEGER NOT NULL DEFAULT 1,
    is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX idx_catalog_chunks_doc_id ON catalog.chunks(doc_id);
CREATE INDEX idx_catalog_chunks_content_hash ON catalog.chunks(content_hash);

-- outbox：任何 documents/chunks 的異動都應在同一交易內寫入一筆事件（Phase 2 起由訂閱器消費）
CREATE TABLE catalog.sync_events (
    event_id     BIGSERIAL PRIMARY KEY,
    entity_type  VARCHAR(20) NOT NULL CHECK (entity_type IN ('document', 'chunk')),
    entity_id    UUID NOT NULL,
    op           VARCHAR(20) NOT NULL CHECK (op IN ('upsert', 'soft_delete')),
    payload      JSONB NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_catalog_sync_events_created_at ON catalog.sync_events(created_at);

-- 各訂閱者（chromadb/elasticsearch/neo4j/redis）各自的消費進度
CREATE TABLE catalog.sync_cursor (
    subscriber     VARCHAR(50) PRIMARY KEY
        CHECK (subscriber IN ('chromadb', 'elasticsearch', 'neo4j', 'redis')),
    last_event_id  BIGINT NOT NULL DEFAULT 0,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- biz：對話與生產查詢紀錄（cited_chunk_ids 供子系統2抽樣建立 golden set）
-- ========================================

CREATE TABLE biz.users (
    user_id      VARCHAR(100) PRIMARY KEY, -- 對應 Open WebUI 既有使用者 id，不新建認證機制
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE biz.conversations (
    conversation_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          VARCHAR(100) NOT NULL REFERENCES biz.users(user_id) ON DELETE CASCADE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_biz_conversations_user_id ON biz.conversations(user_id);

CREATE TABLE biz.messages (
    message_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id  UUID NOT NULL REFERENCES biz.conversations(conversation_id) ON DELETE CASCADE,
    role             VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    route_id         VARCHAR(50),         -- 本次回答使用的策略路由（子系統3實驗層分組鍵）
    cited_chunk_ids  UUID[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_biz_messages_conversation_id ON biz.messages(conversation_id);
CREATE INDEX idx_biz_messages_route_id ON biz.messages(route_id);

-- ========================================
-- eval：召回率量測與回饋迴路
-- ========================================

CREATE TABLE eval.golden_queries (
    query_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text          TEXT NOT NULL,
    relevant_chunk_ids  UUID[] NOT NULL,
    source              VARCHAR(30) NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'sampled_from_production')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE eval.measurements (
    measurement_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id        UUID NOT NULL REFERENCES eval.golden_queries(query_id) ON DELETE CASCADE,
    route_id        VARCHAR(50) NOT NULL,
    stage           VARCHAR(20) NOT NULL
        CHECK (stage IN ('pre_fusion', 'post_rrf', 'post_rerank', 'post_generation')),
    metric_name     VARCHAR(50) NOT NULL, -- recall / ndcg / faithfulness / answer_relevance ...
    metric_value    NUMERIC NOT NULL,
    run_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_eval_measurements_route_stage ON eval.measurements(route_id, stage);
CREATE INDEX idx_eval_measurements_run_at ON eval.measurements(run_at);

CREATE TABLE eval.alerts (
    alert_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name   VARCHAR(50) NOT NULL,
    route_id      VARCHAR(50),
    delta_pct     NUMERIC NOT NULL,
    triggered_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP
);

CREATE INDEX idx_eval_alerts_resolved_at ON eval.alerts(resolved_at);

-- ========================================
-- 更新時間戳觸發器（沿用 01-init-schema.sql 定義的 update_updated_at_column()）
-- ========================================

CREATE TRIGGER update_catalog_documents_updated_at BEFORE UPDATE ON catalog.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_catalog_chunks_updated_at BEFORE UPDATE ON catalog.chunks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_catalog_sync_cursor_updated_at BEFORE UPDATE ON catalog.sync_cursor
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
