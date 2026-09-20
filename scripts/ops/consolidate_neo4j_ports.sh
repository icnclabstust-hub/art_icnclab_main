#!/usr/bin/env bash
# throwaway：一次性維運腳本，執行 2026-09-20 埠號整併決定中的 Neo4j 部分；不排程、不進 src/。
#
# 做什麼：
#   1. 停用並停止 WSL 系統自帶的 neo4j.service（只有 6 個設定節點，已於 2026-09-20 確認無藝術史資料），
#      釋放 7687/7474。
#   2. 把專案原生 Neo4j（資料在 /home/user/native-neo4j/data，7,276 節點）的設定
#      由 7688/7475 改為標準埠 7687/7474。
# 不做什麼：不刪任何資料、不強制砍行程（埠仍被佔用時直接中止並列出佔用者）、
#           不啟動專案實例（請用 Start-NativeServices.ps1）、不改 .env。
#
# 使用（需 root，在 WSL Ubuntu-22.04 內）：
#   sudo bash scripts/ops/consolidate_neo4j_ports.sh            # 執行整併（會要求輸入 YES）
#   sudo bash scripts/ops/consolidate_neo4j_ports.sh --rollback # 還原設定並重新啟用 neo4j.service

set -u

PROJECT_CONF=/home/user/neo4j-community-2026.06.0/conf/neo4j.conf
BACKUP_PREFIX="${PROJECT_CONF}.bak-portmerge"
OLD_BOLT="server.bolt.listen_address=0.0.0.0:7688"
NEW_BOLT="server.bolt.listen_address=0.0.0.0:7687"
OLD_HTTP="server.http.listen_address=0.0.0.0:7475"
NEW_HTTP="server.http.listen_address=0.0.0.0:7474"
FREE_WAIT_ATTEMPTS=15
FREE_WAIT_INTERVAL_SECONDS=2

port_in_use() {
    ss -tln 2>/dev/null | grep -qE ":($1)\b"
}

if [ "$(id -u)" -ne 0 ]; then
    echo "需要 root（sudo bash ...）" >&2
    exit 1
fi
if [ ! -f "$PROJECT_CONF" ]; then
    echo "找不到專案設定檔：$PROJECT_CONF" >&2
    exit 1
fi

if [ "${1:-}" = "--rollback" ]; then
    latest_backup="$(ls -t "${BACKUP_PREFIX}"-* 2>/dev/null | head -1)"
    if [ -z "$latest_backup" ]; then
        echo "找不到 ${BACKUP_PREFIX}-* 備份，無法還原" >&2
        exit 1
    fi
    echo "將以 $latest_backup 還原專案設定，並重新啟用 neo4j.service（會佔回 7687/7474）"
    printf '確認請輸入 YES：'
    read -r answer
    [ "$answer" = "YES" ] || { echo "已取消"; exit 0; }
    if pgrep -f neo4j-community >/dev/null; then
        echo "專案 Neo4j 仍在執行，請先停止再還原" >&2
        exit 1
    fi
    cat "$latest_backup" >"$PROJECT_CONF"
    systemctl enable --now neo4j
    echo "已還原專案設定並重新啟用 neo4j.service"
    exit 0
fi

if pgrep -f neo4j-community >/dev/null; then
    echo "專案 Neo4j 正在執行，請先停止它再整併（避免改設定期間資料庫仍在運作）" >&2
    exit 1
fi
if ! grep -qxF "$OLD_BOLT" "$PROJECT_CONF" || ! grep -qxF "$OLD_HTTP" "$PROJECT_CONF"; then
    echo "專案設定檔中找不到預期的舊設定（$OLD_BOLT / $OLD_HTTP），可能已改過，中止" >&2
    grep -nE "^server\.(bolt|http)\.listen_address" "$PROJECT_CONF" >&2
    exit 1
fi

echo "即將執行 Neo4j 埠號整併："
echo "  1. 備份 $PROJECT_CONF -> ${BACKUP_PREFIX}-<時間戳>"
echo "  2. systemctl disable --now neo4j（系統實例，只有 6 個設定節點）"
echo "  3. 確認 7687/7474 已釋放（仍被佔用就中止，不強制砍行程）"
echo "  4. 專案設定 7688/7475 -> 7687/7474"
printf '確認請輸入 YES：'
read -r answer
[ "$answer" = "YES" ] || { echo "已取消，未做任何變更"; exit 0; }

backup="${BACKUP_PREFIX}-$(date +%Y%m%d-%H%M%S)"
cp -a "$PROJECT_CONF" "$backup" || { echo "備份失敗，中止" >&2; exit 1; }
echo "已備份：$backup"

systemctl disable --now neo4j || { echo "停用 neo4j.service 失敗，中止（設定尚未修改）" >&2; exit 1; }

freed=false
for _ in $(seq 1 "$FREE_WAIT_ATTEMPTS"); do
    if ! port_in_use "7687|7474"; then
        freed=true
        break
    fi
    sleep "$FREE_WAIT_INTERVAL_SECONDS"
done
if [ "$freed" != true ]; then
    echo "7687/7474 仍被佔用，中止（專案設定尚未修改）。佔用者：" >&2
    ss -tlnp 2>/dev/null | grep -E ":(7687|7474)\b" >&2
    echo "請確認佔用者身分後再處理；要復原系統實例請執行 sudo systemctl enable --now neo4j" >&2
    exit 1
fi
echo "7687/7474 已釋放"

# 以 cat 覆寫而非 sed -i，保留原檔的擁有者與權限
tmp_conf="$(mktemp)"
sed -e "s|^${OLD_BOLT}\$|${NEW_BOLT}|" -e "s|^${OLD_HTTP}\$|${NEW_HTTP}|" "$PROJECT_CONF" >"$tmp_conf"
cat "$tmp_conf" >"$PROJECT_CONF"
rm -f "$tmp_conf"

echo "== 修改後的設定 =="
grep -nE "^server\.(bolt|http)\.listen_address" "$PROJECT_CONF"
echo
echo "完成。後續（不在本腳本內）："
echo "  - 在 Windows 執行 scripts/Start-NativeServices.ps1 啟動專案 Neo4j"
echo "  - 執行期 .env 的 NEO4J_URI 改為 bolt://127.0.0.1:7687"
echo "  - 驗證 7687 上的是專案資料（節點數應為 7276）、7688/7475 無服務"
echo "  - 需要回退：sudo bash $0 --rollback"
