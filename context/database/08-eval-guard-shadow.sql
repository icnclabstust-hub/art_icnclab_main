-- Phase 4 影子模式：同步粗篩結果（只記錄、不阻擋）
-- 對應規格：docs/2026-09-23-system-spec-srs.md GRD-06、06a、06b、06d、GRD-08
-- 上位設計：docs/designs/2026-09-21-phase4-evidence-refusal-faithfulness-fuzzy.md §5.4（影子模式）
--
-- 只存數值與文件 id：不存提問、答案原文或使用者 id（BIZ-03、EVL-15a：BIZ_LOGGING 關閉期間
-- 不得寫入可連結到個人的內容）。累積的分數分布用於日後以黃金集校準門檻（GRD-05）。
-- 可重複執行（IF NOT EXISTS）。

CREATE TABLE IF NOT EXISTS eval.guard_shadow (
    shadow_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    route_id         VARCHAR(50) NOT NULL,             -- 策略 id（例如 hybrid）
    model            VARCHAR(100),
    gate_status      VARCHAR(10) NOT NULL
        CHECK (gate_status IN ('ok', 'hang', 'crash')), -- GRD-06d：掛住與崩潰須可分辨
    guard_ms         NUMERIC,                           -- GRD-06a：粗篩耗時（觀測目標 300 ms）
    n_sentences      INT,
    n_anchored       INT,                               -- 含錨點（數字、拉丁字母專名）的句子數
    n_supported      INT,                               -- 錨點全部出現在來源
    n_partial        INT,
    n_unsupported    INT,                               -- 錨點全部不在來源
    anchor_hit_rate  NUMERIC,                           -- 全部錨點中出現在來源的比例
    cited_doc_ids    UUID[] NOT NULL DEFAULT '{}',
    cache_hit        BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_eval_guard_shadow_created_at ON eval.guard_shadow(created_at);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'art_user') THEN
        GRANT SELECT, INSERT ON eval.guard_shadow TO art_user;
    END IF;
END $$;
