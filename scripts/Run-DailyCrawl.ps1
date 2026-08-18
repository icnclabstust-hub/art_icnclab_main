# 每日排程呼叫用的精簡包裝：確保原生服務已啟動，再觸發 WSL 內的每日爬蟲流程
& "c:\Users\user\Desktop\藝術史資料庫\art-history-database\scripts\Start-NativeServices.ps1"

wsl -d Ubuntu-22.04 -- bash "/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/scripts/daily_crawl_and_sync.sh"

