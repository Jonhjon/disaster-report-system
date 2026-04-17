# 智慧災害通報系統 - 一鍵啟動腳本
# 重開機後，以系統管理員身分執行此腳本

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir 'backend'
$PublicDir = Join-Path $ProjectDir 'frontend-public'
$AdminDir = Join-Path $ProjectDir 'frontend-admin'
$NodePath = 'C:\Program Files\nodejs'
$DockerPath = 'C:\Program Files\Docker\Docker\resources\bin'

Write-Host '=== 智慧災害通報系統啟動中 ===' -ForegroundColor Cyan

# 1. 檢查 .env 設定
$EnvFile = Join-Path $BackendDir '.env'
if (Test-Path $EnvFile) {
    $EnvContent = Get-Content $EnvFile -Raw
    if ($EnvContent -match 'your-api-key-here' -or $EnvContent -notmatch 'ANTHROPIC_API_KEY=sk-ant-') {
        Write-Host ''
        Write-Host '[錯誤] 請先設定 ANTHROPIC_API_KEY！' -ForegroundColor Red
        Write-Host '請編輯此檔案並填入 Anthropic API Key (sk-ant-...)：' -ForegroundColor Yellow
        Write-Host "  $EnvFile" -ForegroundColor Yellow
        Write-Host ''
        Read-Host '設定完成後按 Enter 繼續'
    }
} else {
    Write-Host '[警告] 找不到 .env 檔案，請先複製 .env.example 為 .env' -ForegroundColor Yellow
}

# 2. 啟動 Docker Desktop（若未執行）
$dockerProcess = Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Write-Host ''
    Write-Host '[1/5] 啟動 Docker Desktop...' -ForegroundColor Yellow
    Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    Write-Host '      等待 Docker 啟動（約 30 秒）...'
    Start-Sleep -Seconds 30
} else {
    Write-Host '[1/5] Docker Desktop 已在執行中' -ForegroundColor Green
}

# 等待 Docker daemon
Write-Host '      確認 Docker daemon 就緒...'
$maxWait = 60
$waited = 0
do {
    $result = & "$DockerPath\docker.exe" info 2>&1
    if ($result -match 'Server Version') { break }
    Start-Sleep -Seconds 5
    $waited += 5
    if ($waited -ge $maxWait) {
        Write-Host '[錯誤] Docker daemon 未啟動，請手動開啟 Docker Desktop 後重新執行此腳本' -ForegroundColor Red
        exit 1
    }
} while ($true)
Write-Host '      Docker 就緒！' -ForegroundColor Green

# 3. 啟動 PostgreSQL + PostGIS
Write-Host ''
Write-Host '[2/5] 啟動資料庫 (PostgreSQL + PostGIS)...' -ForegroundColor Yellow
Set-Location $ProjectDir
& "$DockerPath\docker.exe" compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host '[錯誤] 資料庫啟動失敗' -ForegroundColor Red
    exit 1
}
Write-Host '      等待資料庫初始化（10 秒）...'
Start-Sleep -Seconds 10

# 重設資料庫密碼（確保密碼始終與 .env 一致）
Write-Host '      確認資料庫認證...' -ForegroundColor DarkGray
& "$DockerPath\docker.exe" exec disaster_db psql -U postgres -c "ALTER USER postgres PASSWORD 'Cm3023203';" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host '      資料庫認證確認完成' -ForegroundColor Green
} else {
    Write-Host '      [!] 資料庫認證設定失敗，請手動檢查 Docker 容器狀態' -ForegroundColor Red
}

# 4. 執行 Alembic 遷移（建立資料表）
Write-Host ''
Write-Host '[3/5] 建立資料庫資料表...' -ForegroundColor Yellow
Set-Location $BackendDir
$VenvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
$VenvAlembic = Join-Path $BackendDir 'venv\Scripts\alembic.exe'
& $VenvAlembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host '[警告] 資料庫遷移失敗（資料表可能已存在，繼續啟動）' -ForegroundColor Yellow
}

# 5. 啟動後端（新視窗）
Write-Host ''
Write-Host '[4/5] 啟動後端服務...' -ForegroundColor Yellow

# 先清除佔用 port 的舊程序
Write-Host '      清除舊程序...' -ForegroundColor DarkGray
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$backendScript = "Set-Location '" + $BackendDir + "'; & '" + $VenvPython + "' -m uvicorn app.main:app --reload"
$backendProc = Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendScript -PassThru

Start-Sleep -Seconds 3

# 6. 啟動民眾端前端（新視窗，port 5173）
Write-Host ''
Write-Host '[5/5] 啟動前端服務...' -ForegroundColor Yellow

$publicScript = "Set-Location '" + $PublicDir + "'; npm run dev"
$publicProc = Start-Process powershell -ArgumentList '-NoExit', '-Command', $publicScript -PassThru

# 7. 啟動管理中心端前端（新視窗，port 5174）
$adminScript = "Set-Location '" + $AdminDir + "'; npm run dev"
$adminProc = Start-Process powershell -ArgumentList '-NoExit', '-Command', $adminScript -PassThru

# 儲存視窗 PID 供 stop.ps1 使用
$pidFile = Join-Path $ProjectDir '.running_pids'
@{
    BackendPID = $backendProc.Id
    PublicPID  = $publicProc.Id
    AdminPID   = $adminProc.Id
} | ConvertTo-Json | Set-Content $pidFile

Write-Host ''
Write-Host '=== 系統啟動完成！===' -ForegroundColor Green
Write-Host ''
Write-Host '請稍候約 5 秒，然後在瀏覽器開啟：' -ForegroundColor White
Write-Host '  民眾端：    http://localhost:5173' -ForegroundColor Cyan
Write-Host '  管理中心端：http://localhost:5174' -ForegroundColor Cyan
Write-Host '  API 文件：  http://localhost:8000/docs' -ForegroundColor Cyan
Write-Host ''
Write-Host '管理中心預設帳號：admin / admin123' -ForegroundColor Yellow
Write-Host ''

Start-Sleep -Seconds 5
Start-Process 'http://localhost:5173'
Start-Process 'http://localhost:5174'

Set-Location $ProjectDir
