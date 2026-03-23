# 智慧災害通報系統 - 一鍵關閉腳本

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerPath = 'C:\Program Files\Docker\Docker\resources\bin'

Write-Host '=== 智慧災害通報系統關閉中 ===' -ForegroundColor Cyan

# 1. 停止後端（uvicorn）
Write-Host ''
Write-Host '[1/3] 停止後端服務...' -ForegroundColor Yellow
$uvicornProcs = Get-Process -Name 'python' -ErrorAction SilentlyContinue |
    Where-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -match 'uvicorn'
        } catch { $false }
    }
if ($uvicornProcs) {
    $uvicornProcs | Stop-Process -Force
    Write-Host '      後端已停止' -ForegroundColor Green
} else {
    Write-Host '      後端未在執行中（略過）' -ForegroundColor Gray
}

# 2. 停止前端（node / vite）
Write-Host ''
Write-Host '[2/3] 停止前端服務...' -ForegroundColor Yellow
$nodeProcs = Get-Process -Name 'node' -ErrorAction SilentlyContinue |
    Where-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -match 'vite'
        } catch { $false }
    }
if ($nodeProcs) {
    $nodeProcs | Stop-Process -Force
    Write-Host '      前端已停止' -ForegroundColor Green
} else {
    Write-Host '      前端未在執行中（略過）' -ForegroundColor Gray
}

# 3. 停止 Docker 容器（PostgreSQL + PostGIS）
Write-Host ''
Write-Host '[3/3] 停止資料庫容器...' -ForegroundColor Yellow
Set-Location $ProjectDir
$dockerExe = "$DockerPath\docker.exe"
if (Test-Path $dockerExe) {
    & $dockerExe compose stop
    if ($LASTEXITCODE -eq 0) {
        Write-Host '      資料庫容器已暫停（資料保留）' -ForegroundColor Green
    } else {
        Write-Host '      資料庫容器停止失敗（可能已停止）' -ForegroundColor Gray
    }
} else {
    Write-Host '      找不到 Docker，略過' -ForegroundColor Gray
}
# 4. 關閉後端/前端 PowerShell 視窗
$pidFile = Join-Path $ProjectDir '.running_pids'
if (Test-Path $pidFile) {
    Write-Host ''
    Write-Host '[4/4] 關閉服務視窗...' -ForegroundColor Yellow
    $savedPids = Get-Content $pidFile | ConvertFrom-Json
    Stop-Process -Id $savedPids.BackendPID  -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $savedPids.FrontendPID -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile
    Write-Host '      服務視窗已關閉' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== 系統已完全關閉 ===' -ForegroundColor Green
Write-Host ''
