-- 例行備份（pg_dump）用：讓應用角色 art_user 能「唯讀」整個資料庫，備份才不必動用超級使用者。
-- 對應：scripts/ops/backup_postgres.sh。只授予 SELECT／USAGE，不含任何寫入或 DDL 權限；可重複執行。

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'art_user') THEN
        GRANT USAGE ON SCHEMA biz, eval TO art_user;
        GRANT SELECT ON ALL TABLES IN SCHEMA biz, eval TO art_user;
        GRANT SELECT ON ALL SEQUENCES IN SCHEMA biz, eval TO art_user;
    END IF;
END $$;
