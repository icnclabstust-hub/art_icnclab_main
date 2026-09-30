-- Phase 3：eval.alerts 補上等級與明細欄位，並開放應用角色寫入 eval
-- 對應規格：docs/2026-09-23-system-spec-srs.md EVL-10～12、DAT-05（一致性稽核須寫入 eval.alerts）
-- 上位設計：docs/designs/2026-09-21-phase3-biz-logging-and-recall-eval.md（schema 以新增欄位補足，不改既有欄位）
--
-- severity：規格的告警等級（DAT-17 容量 warning／critical、GRD-10 gate_error critical 等共用）
-- detail：各告警來源自己的明細（一致性稽核放各檢索庫差異數與範例 id）
-- 可重複執行（IF NOT EXISTS）。

ALTER TABLE eval.alerts ADD COLUMN IF NOT EXISTS severity VARCHAR(10) NOT NULL DEFAULT 'warning';
ALTER TABLE eval.alerts ADD COLUMN IF NOT EXISTS detail JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'alerts_severity_check') THEN
        ALTER TABLE eval.alerts ADD CONSTRAINT alerts_severity_check
            CHECK (severity IN ('info', 'warning', 'critical'));
    END IF;
END $$;

-- 同一指標、同一路由（來源）同時只保留一筆未處理告警；重複偵測到時更新明細而非新增
CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_alerts_open
    ON eval.alerts(metric_name, COALESCE(route_id, '')) WHERE resolved_at IS NULL;

-- 應用程式角色（.env 的 DB_USER）需要寫入 eval（告警、之後的量測）；同樣不給 DDL 權限
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'art_user') THEN
        GRANT USAGE ON SCHEMA eval TO art_user;
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA eval TO art_user;
    END IF;
END $$;
