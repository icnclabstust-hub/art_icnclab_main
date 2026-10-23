"""PostgreSQL 連線：參數只從環境變數讀取（.env 的 DB_*），不寫死、不印出。"""

import os

import psycopg

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5432
DEFAULT_DBNAME = "art_history_db"


def connect() -> psycopg.Connection:
    """以環境變數建立連線（autocommit，交易由呼叫端用 ``conn.transaction()`` 控制）。

    讀取 ``DB_HOST``／``DB_PORT``／``DB_NAME``／``DB_USER``／``DB_PASSWORD``。

    Returns:
        已連線的 psycopg 連線。
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST", DEFAULT_HOST),
        port=int(os.getenv("DB_PORT", str(DEFAULT_PORT))),
        dbname=os.getenv("DB_NAME", DEFAULT_DBNAME),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        autocommit=True,
    )
