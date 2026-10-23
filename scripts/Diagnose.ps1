# 系統診斷：檢查服務健康狀態 + 掃描 log 比對已知錯誤知識庫，直接給出處/原因/解法
# 用法:
#   .\Diagnose.ps1                下述健康檢查 + 掃描各服務 log
#   .\Diagnose.ps1 "錯誤訊息內容"   額外比對貼上的錯誤訊息

param(
    [string]$ErrorText = ""
)

# 由本腳本位置推算 WSL 路徑（同 Start-NativeServices.ps1），專案搬家不必改這裡
$WslScript = "/mnt/" + $PSScriptRoot.Substring(0, 1).ToLower() + ($PSScriptRoot.Substring(2) -replace "\\", "/") + "/diagnose.py"

if ($ErrorText) {
    $ErrorText | wsl -d Ubuntu-22.04 -- python3 $WslScript
} else {
    wsl -d Ubuntu-22.04 -- python3 $WslScript
}

