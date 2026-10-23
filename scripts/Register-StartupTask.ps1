# 註冊「登入時啟動服務」的 Windows 工作排程（目前使用者、一般權限，不需系統管理員）。
# 用法：.\scripts\Register-StartupTask.ps1 [-EnvFile F:\art_icnclab-main\art_icnclab-main\.env]
# .env 現放專案根目錄（2026-09-28 起，見 docs/decision-log.md），不帶 -EnvFile 也會讀到
# 移除：Unregister-ScheduledTask -TaskName ArtHistoryDB-StartServices -Confirm:$false
param([string]$EnvFile = "")

$ErrorActionPreference = "Stop"
$startScript = Join-Path $PSScriptRoot "Start-NativeServices.ps1"
$envAssign = if ($EnvFile) { "`$env:ART_ENV_FILE='$EnvFile'; " } else { "" }
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$envAssign& '$startScript'`""

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName "ArtHistoryDB-StartServices" -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "Start Neo4j, ChromaDB, RAG backend and Open WebUI at logon (Start-NativeServices.ps1)" | Out-Null
Write-Host "已註冊工作排程 ArtHistoryDB-StartServices（登入時執行 $startScript）"
