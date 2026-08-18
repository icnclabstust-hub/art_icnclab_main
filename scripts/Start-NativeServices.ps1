# 一鍵啟動整套系統：全部原生執行於 WSL（Neo4j / ChromaDB / rag-manager-v2 / Open WebUI）
# 系統已完全不使用 Docker（2026-07-28 移除）
# 可重複執行：每個服務都會先檢查是否已經在跑，不會重複啟動

$ErrorActionPreference = "Continue"
$ProjectDir = "c:\Users\user\Desktop\藝術史資料庫\art-history-database"
$LogDir = Join-Path $ProjectDir "logs\startup"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("start_{0}.log" -f (Get-Date -Format "yyyy-MM-ddTHH-mm-ss"))

# 從 .env 讀取密碼，不寫死在腳本裡避免密碼進 git
function Get-EnvValue($key) {
    $envPath = Join-Path $ProjectDir ".env"
    $line = Get-Content $envPath | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1] }
    return $null
}
$Neo4jPassword = Get-EnvValue "NEO4J_PASSWORD"
$EsPassword = Get-EnvValue "ES_PASSWORD"

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Test-TcpConnect($hostname, $port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connectTask = $client.ConnectAsync($hostname, $port)
        $completed = $connectTask.Wait(3000)
        $result = $completed -and $client.Connected
        $client.Close()
        return $result
    } catch {
        return $false
    }
}

function Test-Port($port) {
    # 只要能建立 TCP 連線就算服務有在跑；用 Invoke-WebRequest 檢查 HTTP 狀態碼會誤判
    # （例如 ChromaDB 新版對根目錄 "/" 回應 404，會被 Invoke-WebRequest 當成例外，誤判成「服務沒在跑」）
    # WSL 環境下 Windows 對 127.0.0.1 / localhost（常解析成 ::1）的埠轉發偶爾只有其中一個能通，兩個都測，任一成功就算通過
    return (Test-TcpConnect "127.0.0.1" $port) -or (Test-TcpConnect "localhost" $port)
}

function Start-WslBackground($bashCommand) {
    # 用 Start-Process 讓 wsl.exe 成為獨立的 Windows 背景程序（前景跑 bash 指令，不在 bash 內部用 nohup/disown）
    # 這樣程序的存活期由 Windows 管理，不受 WSL session 中斷影響；用 nohup+disown 的寫法在 WSL 底下並不可靠，服務會悄悄被砍掉
    $wslArgs = "-d Ubuntu-22.04 -- bash -c `"$bashCommand`""
    Start-Process -FilePath "wsl.exe" -ArgumentList $wslArgs -WindowStyle Hidden
}

# 1. Neo4j（原生 WSL，bolt:7688 / http:7475 —— 7687/7474 被 WSL 環境本身的系統 Neo4j 服務佔用，改用替代埠）
Write-Log "檢查 Neo4j (port 7475)..."
if (Test-Port 7475) {
    Write-Log "✅ Neo4j 已在運作"
} else {
    Write-Log "啟動 Neo4j..."
    Start-WslBackground "/home/user/neo4j-community-2026.06.0/bin/neo4j console > /tmp/neo4j-native.log 2>&1"
    Start-Sleep -Seconds 20
    if (Test-Port 7475) { Write-Log "✅ Neo4j 啟動成功" } else { Write-Log "⚠️ Neo4j 啟動後仍無回應，請檢查 /tmp/neo4j-native.log" }
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

# 3. rag-manager-v2（原生 WSL，依賴 Neo4j/ChromaDB，:8007）
Write-Log "檢查 rag-manager-v2 (port 8007)..."
if (Test-Port 8007) {
    Write-Log "✅ rag-manager-v2 已在運作"
} else {
    Write-Log "啟動 rag-manager-v2..."
    $ragCmd = "cd '/mnt/c/Users/user/Desktop/藝術史資料庫/art-history-database/langchain-rag' && NEO4J_URI=bolt://127.0.0.1:7688 NEO4J_PASSWORD=$Neo4jPassword CHROMADB_PORT=8000 ES_PASSWORD=$EsPassword python3 unified_rag_manager_v2.py > /tmp/rag_manager_v2.log 2>&1"
    Start-WslBackground $ragCmd
    Start-Sleep -Seconds 8
    if (Test-Port 8007) { Write-Log "✅ rag-manager-v2 啟動成功" } else { Write-Log "⚠️ rag-manager-v2 啟動後仍無回應，請檢查 /tmp/rag_manager_v2.log" }
}

# 4. Open WebUI（原生 WSL，:8080）
Write-Log "檢查 Open WebUI (port 8080)..."
if (Test-Port 8080) {
    Write-Log "✅ Open WebUI 已在運作"
} else {
    Write-Log "啟動 Open WebUI..."
    $webuiCmd = "cd /home/user && DATA_DIR=/home/user/openwebui-data OLLAMA_BASE_URL=http://localhost:11434 /home/user/openwebui-venv/bin/open-webui serve --port 8080 > /tmp/openwebui.log 2>&1"
    Start-WslBackground $webuiCmd
    Start-Sleep -Seconds 10
    if (Test-Port 8080) { Write-Log "✅ Open WebUI 啟動成功" } else { Write-Log "⚠️ Open WebUI 啟動後仍無回應，請檢查 /tmp/openwebui.log" }
}

Write-Log "=== 啟動流程結束 ==="

# 只保留最近 30 天的 log
Get-ChildItem $LogDir -Filter "start_*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force -ErrorAction SilentlyContinue




