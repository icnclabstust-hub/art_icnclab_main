-- Phase 3 量測：黃金集標註欄位、量測 run、measurements 補 run_id／k
-- 對應規格：docs/2026-09-23-system-spec-srs.md EVL-03～08、NFR-06
-- 設計：docs/designs/2026-09-21-phase3-biz-logging-and-recall-eval.md §5.2（只取 eval 部分；biz 部分隨
-- BIZ_LOGGING 鎖定暫緩）
--
-- 全部為新增，不改既有欄位語意；可重複執行（IF NOT EXISTS）。

-- 黃金集：文件層級標註（EVL-05）＋答案要點、標註者、標註時間（EVL-03）
ALTER TABLE eval.golden_queries
    ADD COLUMN IF NOT EXISTS golden_key         TEXT,          -- 例：2026-10-07-baroque#1，重新匯入時據此更新
    ADD COLUMN IF NOT EXISTS query_type         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS relevant_doc_ids   UUID[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS gold_answer_points TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS annotator          TEXT,
    ADD COLUMN IF NOT EXISTS annotated_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS status             VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE eval.golden_queries ALTER COLUMN relevant_chunk_ids SET DEFAULT '{}';
CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_golden_queries_key ON eval.golden_queries(golden_key);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'golden_queries_query_type_check') THEN
        ALTER TABLE eval.golden_queries ADD CONSTRAINT golden_queries_query_type_check
            CHECK (query_type IN ('fact', 'relation', 'refuse'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'golden_queries_status_check') THEN
        -- stale：標註的文件被撤出或隔離，排除於指標之外並提示人工複審（設計 §5.5）
        ALTER TABLE eval.golden_queries ADD CONSTRAINT golden_queries_status_check
            CHECK (status IN ('active', 'stale', 'retired'));
    END IF;
END $$;

-- 量測 run：每次執行一筆，含 commit_sha 與設定快照（EVL-07、NFR-06）
CREATE TABLE IF NOT EXISTS eval.runs (
    run_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    trigger         VARCHAR(20) NOT NULL
        CHECK (trigger IN ('nightly', 'pre_deploy', 'manual')),
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'done', 'failed')),
    is_baseline     BOOLEAN NOT NULL DEFAULT FALSE,   -- 人工設定的基準 run（EVL-08）
    commit_sha      TEXT,
    config_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    corpus_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb -- 量測當下的語料指紋，與凍結快照比較漂移
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_runs_one_baseline ON eval.runs(is_baseline) WHERE is_baseline;

ALTER TABLE eval.measurements
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES eval.runs(run_id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS k      INT;
CREATE INDEX IF NOT EXISTS idx_eval_measurements_run ON eval.measurements(run_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'art_user') THEN
        GRANT SELECT, INSERT, UPDATE ON eval.golden_queries, eval.runs, eval.measurements TO art_user;
    END IF;
END $$;
