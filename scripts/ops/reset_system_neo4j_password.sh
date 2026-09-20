#!/usr/bin/env bash
# throwaway：一次性維運腳本，用於找回 WSL 系統自帶 neo4j.service 的密碼；不排程、不進 src/。
#
# 用途：系統實例（/var/lib/neo4j/data，埠 7687）密碼遺失時，暫時關閉認證，
#       盤點資料量並把密碼重設為隨機值。
# 使用：由使用者親自執行，需要 root。
#         wsl -d Ubuntu-22.04 -u root -- bash /mnt/f/art_icnclab-main/art_icnclab-main/scripts/ops/reset_system_neo4j_password.sh
# 風險：執行期間（通常 < 2 分鐘）該實例認證關閉，因此同時把 bolt/http 限制為只聽 127.0.0.1；
#       結束時無論成功或失敗都會還原原始設定並重啟。新密碼只寫入權限 600 的檔案，不印到螢幕。
# 不會做：不動專案原生實例（7688）、不刪除任何資料。

set -u

CONF=/etc/neo4j/neo4j.conf
BACKUP="${CONF}.bak-$(date +%Y%m%d-%H%M%S)"
PASSWORD_FILE=/home/user/.neo4j-system-password
BOLT=bolt://127.0.0.1:7687
WAIT_ATTEMPTS=40
WAIT_INTERVAL_SECONDS=3

if [ "$(id -u)" -ne 0 ]; then
    echo "需要 root 執行（wsl -d Ubuntu-22.04 -u root -- bash ...）" >&2
    exit 1
fi
if ! systemctl cat neo4j.service >/dev/null 2>&1; then
    echo "找不到 neo4j.service，中止" >&2
    exit 1
fi

echo "即將對『系統 Neo4j（7687）』做以下事情："
echo "  1. 備份 $CONF -> $BACKUP"
echo "  2. 暫時關閉認證並只聽 127.0.0.1，重啟該服務"
echo "  3. 唯讀盤點節點數，並把密碼重設為隨機值（存到 $PASSWORD_FILE）"
echo "  4. 還原設定、重啟、驗證認證已恢復"
printf '確認請輸入 YES：'
read -r answer
if [ "$answer" != "YES" ]; then
    echo "已取消，未做任何變更"
    exit 0
fi

# 若上次中斷留下暫時設定，此時備份會把「已被改過」的設定當成原始版本，還原就等於沒還原
if grep -q "^# TEMP：密碼重設期間" "$CONF"; then
    echo "$CONF 仍含上次遺留的暫時設定，請先用最早的 .bak-* 備份還原後再執行" >&2
    exit 1
fi

cp -a "$CONF" "$BACKUP" || { echo "備份失敗，中止" >&2; exit 1; }
echo "已備份：$BACKUP"

restore_config() {
    cp -a "$BACKUP" "$CONF"
    systemctl restart neo4j
    echo "已還原原始設定並重啟（備份保留在 $BACKUP）"
}
trap restore_config EXIT

cat >>"$CONF" <<'EOF'

# TEMP：密碼重設期間的暫時設定，腳本結束時會還原
dbms.security.auth_enabled=false
server.bolt.listen_address=127.0.0.1:7687
server.http.listen_address=127.0.0.1:7474
EOF

systemctl restart neo4j

ready=false
last_error=""
for _ in $(seq 1 "$WAIT_ATTEMPTS"); do
    # system 資料庫只接受管理指令，不能用 RETURN 1 探測
    if last_error="$(cypher-shell -a "$BOLT" -u neo4j -p x -d system "SHOW DATABASES;" 2>&1)"; then
        ready=true
        break
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
done
if [ "$ready" != true ]; then
    echo "服務未在時限內就緒，放棄（將自動還原設定）。最後一次錯誤：" >&2
    echo "$last_error" >&2
    echo "--- 目前監聽的 7687 ---" >&2
    ss -tln 2>/dev/null | grep ":7687" >&2
    journalctl -u neo4j --no-pager -n 8 2>/dev/null | cut -c1-160 >&2
    exit 1
fi

echo "== 節點數（唯讀）=="
cypher-shell -a "$BOLT" -u neo4j -p x --format plain "MATCH (n) RETURN count(n) AS nodes;"
echo "== 標籤分布（前 10）=="
cypher-shell -a "$BOLT" -u neo4j -p x --format plain \
    "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC LIMIT 10;"

new_password="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
if cypher-shell -a "$BOLT" -u neo4j -p x -d system \
    "ALTER USER neo4j SET PASSWORD '${new_password}' CHANGE NOT REQUIRED;" >/dev/null; then
    ( umask 077 && printf '%s\n' "$new_password" >"$PASSWORD_FILE" )
    chown user:user "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    echo "密碼已重設，新密碼存於 $PASSWORD_FILE（權限 600）"
else
    echo "密碼重設失敗，未做變更" >&2
fi
unset new_password

# 驗證（在 EXIT trap 還原之前，先手動還原一次以便檢查認證是否確實恢復）
trap - EXIT
restore_config
sleep 10
if cypher-shell -a "$BOLT" -u neo4j -p x "RETURN 1;" >/dev/null 2>&1; then
    echo "警告：以錯誤密碼仍能連線，認證可能沒有恢復，請檢查 $CONF" >&2
    exit 2
fi
echo "驗證通過：認證已恢復（錯誤密碼被拒絕）"
