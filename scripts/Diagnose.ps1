# 系統診斷：檢查服務健康狀態 + 掃描 log 比對已知錯誤知識庫，直接給出處/原因/解法
# 用法:
#   .\Diagnose.ps1                下述健康檢查 + 掃描各服務 log
#   .\Diagnose.ps1 "錯誤訊息內容"   額外比對貼上的錯誤訊息

param(
    [string]$ErrorText = ""
)

if ($ErrorText) {
    $ErrorText | wsl -d Ubuntu-22.04 -- python3 "/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/scripts/diagnose.py"
} else {
    wsl -d Ubuntu-22.04 -- python3 "/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/scripts/diagnose.py"
}

