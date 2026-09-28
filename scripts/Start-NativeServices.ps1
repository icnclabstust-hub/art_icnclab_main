# 一鍵啟動整套系統：全部原生執行於 WSL（Neo4j / ChromaDB / rag-manager-v2 / Open WebUI）
# 可重複執行：每個服務都會先檢查是否已經在跑，不會重複啟動

$ErrorActionPreference = "Continue"
# 專案根目錄由腳本位置推算；WSL 內對應路徑為 /mnt/<磁碟機小寫>/...
$ProjectDir = Split-Path -Parent $PSScriptRoot
$WslProjectDir = "/mnt/" + $ProjectDir.Substring(0, 1).ToLower() + ($ProjectDir.Substring(2) -replace "\\", "/")
# .env 預設在專案根目錄（現行位置 F:\art_icnclab-main\art_icnclab-main\.env）；若放在別處，以環境變數 ART_ENV_FILE 指定
$EnvFile = if ($env:ART_ENV_FILE) { $env:ART_ENV_FILE } else { Join-Path $ProjectDir ".env" }
$LogDir = Join-Path $ProjectDir "logs\startup"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("start_{0}.log" -f (Get-Date -Format "yyyy-MM-ddTHH-mm-ss"))

# Open WebUI 對外埠：優先用架構圖的 8080；若 Windows 把它保留給 Hyper-V/WinNAT（瀏覽器的 localhost 連不到），
# 退回 3000。保留範圍會隨系統重開機變動，所以每次啟動時判斷（netsh interface ipv4 show excludedportrange protocol=tcp）。
function Get-WebUiPort {
    $preferred = 8080
    $fallback = 3000
    foreach ($line in (netsh interface ipv4 show excludedportrange protocol=tcp)) {
        if ($line -match '^\s*(\d+)\s+(\d+)') {
            if ($preferred -ge [int]$Matches[1] -and $preferred -le [int]$Matches[2]) { return $fallback }
        }
    }
    return $preferred
}
$WebUiPort = Get-WebUiPort
# 密碼不經過命令列（ps 看得到）：只把 .env 的 WSL 路徑交給後端，由後端自己讀
$WslEnvFile = "/mnt/" + $EnvFile.Substring(0, 1).ToLower() + ($EnvFile.Substring(2) -replace "\\", "/")

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Test-Port($port) {
    # 在 WSL 內檢查（服務都跑在 WSL）。不從 Windows 連 localhost：Windows 把 TCP 7937-8340 等範圍保留給
    # Hyper-V/WinNAT（netsh interface ipv4 show excludedportrange protocol=tcp），8000/8001/8080 落在其中，
    # WSL 無法轉發到 Windows 的 localhost，從 Windows 測永遠失敗，會誤判成服務沒在跑而重複啟動。
    $null = & wsl.exe -d Ubuntu-22.04 -- bash -c "(echo > /dev/tcp/127.0.0.1/$port) 2>/dev/null"
    return ($LASTEXITCODE -eq 0)
}

function Start-WslBackground($bashCommand) {
    # 用 Start-Process 讓 wsl.exe 成為獨立的 Windows 背景程序（前景跑 bash 指令，不在 bash 內部用 nohup/disown）
    # 這樣程序的存活期由 Windows 管理，不受 WSL session 中斷影響；用 nohup+disown 的寫法在 WSL 底下並不可靠，服務會悄悄被砍掉
    $wslArgs = "-d Ubuntu-22.04 -- bash -c `"$bashCommand`""
    Start-Process -FilePath "wsl.exe" -ArgumentList $wslArgs -WindowStyle Hidden
}

# 1. Neo4j（原生 WSL，標準埠 bolt:7687 / http:7474）
#    2026-09-20 起改用標準埠；此前為 7688/7475，因 WSL 系統自帶的 neo4j.service 佔用標準埠。
#    該系統服務已 systemctl disable --now，標準埠歸本專案。
Write-Log "檢查 Neo4j (port 7474)..."
if (Test-Port 7474) {
    Write-Log "✅ Neo4j 已在運作"
} else {
    Write-Log "啟動 Neo4j..."
    Start-WslBackground "/home/user/neo4j-community-2026.06.0/bin/neo4j console > /tmp/neo4j-native.log 2>&1"
    Start-Sleep -Seconds 20
    if (Test-Port 7474) { Write-Log "✅ Neo4j 啟動成功" } else { Write-Log "⚠️ Neo4j 啟動後仍無回應，請檢查 /tmp/neo4j-native.log" }
}

# 2. ChromaDB（原生 WSL，:8000）
Write-Log "檢查 ChromaDB (port 8000)..."
if (Test-Port 8000) {
    Write-Log "✅ ChromaDB 已在運作"
} else {
    Write-Log "啟動 ChromaDB..."
    Start-WslBackground "/home/user/.local/bin/chroma run --path /home/user/native-chromadb/data --port 8000 > /tmp/chromadb.log 2>&1"
    Start-Sleep -Seconds 8
    if (Test-Port 8000) { Write-Log "✅ ChromaDB 啟動成功" } else { Write-Log "⚠️ ChromaDB 啟動後仍無回應，請檢查 /tmp/chromadb.log" }
}

# 3. rag-manager-v2（原生 WSL，依賴 Neo4j/ChromaDB，:8001）
Write-Log "檢查 rag-manager-v2 (port 8001)..."
if (Test-Port 8001) {
    Write-Log "✅ rag-manager-v2 已在運作"
} else {
    Write-Log "啟動 rag-manager-v2..."
    $ragCmd = "cd '$WslProjectDir/langchain-rag' && ENV_FILE='$WslEnvFile' NEO4J_URI=bolt://127.0.0.1:7687 CHROMADB_PORT=8000 python3 unified_rag_manager_v2.py > /tmp/rag_manager_v2.log 2>&1"
    Start-WslBackground $ragCmd
    Start-Sleep -Seconds 8
    if (Test-Port 8001) { Write-Log "✅ rag-manager-v2 啟動成功" } else { Write-Log "⚠️ rag-manager-v2 啟動後仍無回應，請檢查 /tmp/rag_manager_v2.log" }
}

# 4. Open WebUI（原生 WSL），埠由 Get-WebUiPort 決定
Write-Log "Open WebUI 使用埠 $WebUiPort（8080 若被 Windows 保留則退回 3000）"
Write-Log "檢查 Open WebUI (port $WebUiPort)..."
if (Test-Port $WebUiPort) {
    Write-Log "✅ Open WebUI 已在運作"
} else {
    Write-Log "啟動 Open WebUI..."
    $webuiCmd = "cd /home/user && DATA_DIR=/home/user/openwebui-data OLLAMA_BASE_URL=http://localhost:11434 /home/user/openwebui-venv/bin/open-webui serve --port $WebUiPort > /tmp/openwebui.log 2>&1"
    Start-WslBackground $webuiCmd
    Start-Sleep -Seconds 10
    if (Test-Port $WebUiPort) { Write-Log "✅ Open WebUI 啟動成功" } else { Write-Log "⚠️ Open WebUI 啟動後仍無回應，請檢查 /tmp/openwebui.log" }
}

Write-Log "=== 啟動流程結束 ==="

# 只保留最近 30 天的 log
Get-ChildItem $LogDir -Filter "start_*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force -ErrorAction SilentlyContinue




