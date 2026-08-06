# 智慧災害通報系統 - 測試 DB 建立腳本（一次性）
# 用途：在現有 disaster_db container 內建立 disaster_report_test database
#       並套用 alembic migration（含 admin user seed）

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir 'backend'
$DockerPath = 'C:\Program Files\Docker\Docker\resources\bin'
$DockerExe = Join-Path $DockerPath 'docker.exe'

$TestDbName = 'disaster_report_test'

# 從 backend/.env.test 讀取測試 DATABASE_URL（避免在腳本硬寫 DB 密碼）
$TestEnvFile = Join-Path $BackendDir '.env.test'
if (-not (Test-Path $TestEnvFile)) {
    Write-Host "[錯誤] 找不到 $TestEnvFile" -ForegroundColor Red
    exit 1
}
$TestEnvContent = Get-Content $TestEnvFile -Raw
if ($TestEnvContent -match '(?m)^\s*DATABASE_URL\s*=\s*["'']?([^"''\r\n]+)["'']?\s*$') {
    $TestDbUrl = $Matches[1].Trim()
} else {
    Write-Host "[錯誤] $TestEnvFile 內找不到 DATABASE_URL" -ForegroundColor Red
    exit 1
}

Write-Host '=== 測試 DB 建立中 ===' -ForegroundColor Cyan

# 1. 確認 disaster_db container 已啟動
Write-Host ''
Write-Host '[1/5] 確認 disaster_db container...' -ForegroundColor Yellow
$dockerRunning = & $DockerExe ps --filter 'name=disaster_db' --format '{{.Names}}' 2>$null
if (-not $dockerRunning) {
    Write-Host '[錯誤] disaster_db container 未啟動！' -ForegroundColor Red
    Write-Host '請先執行 .\start.ps1 啟動主系統，再來建立測試 DB。' -ForegroundColor Yellow
    exit 1
}
Write-Host '      disaster_db container 已就緒' -ForegroundColor Green

# 2. 建立 disaster_report_test database（已存在則跳過）
Write-Host ''
Write-Host "[2/5] 建立 $TestDbName database..." -ForegroundColor Yellow
$dbExists = & $DockerExe exec disaster_db psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$TestDbName'" 2>$null
if ($dbExists -match '^1') {
    Write-Host '      測試 DB 已存在，跳過建立' -ForegroundColor Gray
} else {
    & $DockerExe exec disaster_db psql -U postgres -c "CREATE DATABASE $TestDbName" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[錯誤] CREATE DATABASE 失敗' -ForegroundColor Red
        exit 1
    }
    Write-Host '      測試 DB 建立成功' -ForegroundColor Green
}

# 3. 啟用 PostGIS extension
Write-Host ''
Write-Host '[3/5] 啟用 PostGIS extension...' -ForegroundColor Yellow
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c 'CREATE EXTENSION IF NOT EXISTS postgis' 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[錯誤] PostGIS extension 啟用失敗' -ForegroundColor Red
    exit 1
}
Write-Host '      PostGIS extension 已啟用' -ForegroundColor Green

# 4. 授權 app_user（複製自 docker/init-db.sh 邏輯）
Write-Host ''
Write-Host '[4/5] 授權 app_user...' -ForegroundColor Yellow
$grantSql = @"
GRANT ALL PRIVILEGES ON DATABASE $TestDbName TO app_user;
GRANT ALL ON SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO app_user;
"@
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c $grantSql 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host '      [!] 部分授權失敗（app_user 可能未建立），可忽略' -ForegroundColor Yellow
} else {
    Write-Host '      app_user 授權完成' -ForegroundColor Green
}

# 5. 跑 alembic upgrade head（env var 覆蓋 DATABASE_URL）
# 用 python -m alembic 而非 alembic.exe wrapper，後者在某些 Windows 環境會吞掉輸出
Write-Host ''
Write-Host '[5/5] 套用 Alembic migration...' -ForegroundColor Yellow
$VenvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host "[錯誤] 找不到 $VenvPython" -ForegroundColor Red
    Write-Host '請先建立 backend venv 並安裝相依套件' -ForegroundColor Yellow
    exit 1
}

Push-Location $BackendDir
try {
    $env:DATABASE_URL = $TestDbUrl
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[錯誤] Alembic upgrade 失敗' -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
}
Write-Host '      Migration 套用完成（admin user 由 migration 007 自動 seed）' -ForegroundColor Green

# 驗證輸出
Write-Host ''
Write-Host '=== 驗證 ===' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Tables：' -ForegroundColor White
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c '\dt'

Write-Host ''
Write-Host 'Admin user：' -ForegroundColor White
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c 'SELECT username, display_name FROM users'

Write-Host ''
Write-Host 'PostGIS：' -ForegroundColor White
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c 'SELECT PostGIS_Version()'

Write-Host ''
Write-Host '=== 測試 DB 已就緒！===' -ForegroundColor Green
Write-Host ''
Write-Host '下一步：' -ForegroundColor White
Write-Host '  - 啟動測試後端：.\scripts\start-test-backend.ps1（port 8001）' -ForegroundColor Cyan
Write-Host '  - 清空測試資料：.\scripts\reset-test-db.ps1' -ForegroundColor Cyan
Write-Host ''
