# 每日排程呼叫用的包裝：確保原生服務已啟動，再在 WSL 內執行「新架構」每日流程
# （爬蟲 → catalog 攝取 → ChromaDB／ES／Neo4j 訂閱同步 → 驗證）。
# 用法：.\scripts\Run-DailyCrawl.ps1 [-SkipCrawl]      # -SkipCrawl 只攝取與同步，不重新爬取（測試用）
# .env 位置：預設在專案根目錄；放在別處時以環境變數 ART_ENV_FILE 指定（Windows 路徑）。
param([switch]$SkipCrawl)

$ErrorActionPreference = "Continue"

function ConvertTo-WslPath([string]$winPath) {
    "/mnt/" + $winPath.Substring(0, 1).ToLower() + ($winPath.Substring(2) -replace "\\", "/")
}

$projectDir = Split-Path -Parent $PSScriptRoot
$wslProject = ConvertTo-WslPath $projectDir
$envFile = if ($env:ART_ENV_FILE) { $env:ART_ENV_FILE } else { Join-Path $projectDir ".env" }
$wslEnvFile = ConvertTo-WslPath $envFile

& (Join-Path $PSScriptRoot "Start-NativeServices.ps1")

$skip = if ($SkipCrawl) { "SKIP_CRAWL=1" } else { "SKIP_CRAWL=" }
wsl.exe -d Ubuntu-22.04 -- env "ENV_FILE=$wslEnvFile" $skip bash "$wslProject/scripts/daily_crawl_and_sync_catalog.sh"
exit $LASTEXITCODE
