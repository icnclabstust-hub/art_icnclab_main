# Python 測試（catalog 攝取與訂閱器）

## 執行

DB 測試會建立並刪除拋棄式資料庫 `zz_ingest_test_<pid>`，**不會碰 `art_history_db`**。
需以 `postgres` 作業系統使用者執行（peer 認證）；連不上資料庫時 DB 測試自動略過。

```bash
# 一次性：安裝測試依賴到所有使用者可讀的目錄
pip3 install --target /var/tmp/art-ingest-libs "psycopg[binary]==3.3.6" pytest
chmod -R a+rX /var/tmp/art-ingest-libs

# DB 測試（WSL 內）
sudo -u postgres env PYTHONPATH=/var/tmp/art-ingest-libs python3 -m pytest tests/python -q -p no:cacheprovider

# 與既有 ChromaBatchWriter 的相容性測試（需 chromadb，用一般使用者）
python3 -m pytest tests/python/test_scanner_and_ids.py -q -p no:cacheprovider
```
