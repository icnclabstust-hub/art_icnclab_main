"""pytest 共用設定：把 langchain-rag 加進 import 路徑，並提供拋棄式 PostgreSQL 資料庫。

DB 測試每個 session 建立一個 ``zz_ingest_test_<pid>`` 資料庫並在結束時刪除，絕不碰
``art_history_db``。連不上 PostgreSQL（例如在沒有資料庫的機器上）時，DB 測試自動略過。
執行方式見 tests/python/README.md。
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "langchain-rag"))

MIGRATIONS = [
    REPO_ROOT / "context" / "database" / "04-catalog-biz-eval-schema.sql",
    REPO_ROOT / "context" / "database" / "05-catalog-external-id-and-grants.sql",
]

PREREQUISITES = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END; $$ language 'plpgsql';
"""

TRUNCATE_ALL = (
    "TRUNCATE catalog.sync_events, catalog.sync_cursor, catalog.chunks, catalog.documents"
    " RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session")
def scratch_db_name():
    """建立並在結束時刪除拋棄式資料庫，回傳其名稱。"""
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql  # noqa: PLC0415

    name = f"zz_ingest_test_{os.getpid()}"
    try:
        admin = psycopg.connect(dbname="postgres", autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.skip(f"連不上 PostgreSQL（需以 postgres 使用者執行）：{exc}")
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with psycopg.connect(dbname=name, autocommit=True) as setup:
        setup.execute(PREREQUISITES)
        for migration in MIGRATIONS:
            setup.execute(migration.read_text(encoding="utf-8"))
    yield name
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    admin.close()


@pytest.fixture
def conn(scratch_db_name):
    """每個測試一條乾淨的連線（表已清空）。"""
    import psycopg  # noqa: PLC0415

    with psycopg.connect(dbname=scratch_db_name, autocommit=True) as connection:
        connection.execute(TRUNCATE_ALL)
        yield connection


def make_artwork(external_id: str = "harvard_1", **overrides) -> dict:
    """產生一筆與 normalize_* 輸出同形狀的作品 dict。"""
    artwork = {
        "id": external_id,
        "title": "Water Lilies",
        "artist": "Claude Monet",
        "date": "1906",
        "medium": "Oil on canvas",
        "culture": "French",
        "period": "Impressionism",
        "department": "Paintings",
        "description": "A view of the water garden at Giverny.",
        "url": f"https://example.org/{external_id}",
    }
    artwork.update(overrides)
    return artwork


def simple_document_text(artwork: dict) -> str:
    """測試用的文件文字組合（規則與正式版相同：Title/Creator/... 逐行）。"""
    parts = [f"Title: {artwork['title']}"]
    for label, key in (
        ("Creator", "artist"),
        ("Date", "date"),
        ("Medium", "medium"),
        ("Culture", "culture"),
        ("Period", "period"),
        ("Department", "department"),
        ("Description", "description"),
    ):
        if artwork.get(key):
            parts.append(f"{label}: {artwork[key]}")
    return "\n".join(parts)
