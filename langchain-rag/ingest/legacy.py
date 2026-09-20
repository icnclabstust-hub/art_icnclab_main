"""載入既有匯入腳本，沿用其 normalize／組文字邏輯，確保與現有資料的 id 與內容一致。

import_all_museums_to_neo4j.py 在 import 當下要求 NEO4J_PASSWORD 存在，但攝取層完全不連
Neo4j，所以這裡只塞一個佔位值讓它能被 import，實際連線密碼不會經過這條路徑。
"""

import importlib
import os
from types import ModuleType

_PLACEHOLDER_ENV = "NEO4J_PASSWORD"
_PLACEHOLDER_VALUE = "unused-by-ingest"


def load_legacy_module() -> ModuleType:
    """回傳已 import 的 ``import_all_museums_to_neo4j`` 模組。

    Returns:
        提供 ``NORMALIZERS``、``SOURCE_PATTERNS``、``build_document_text`` 等成員的模組。
    """
    os.environ.setdefault(_PLACEHOLDER_ENV, _PLACEHOLDER_VALUE)
    return importlib.import_module("import_all_museums_to_neo4j")
