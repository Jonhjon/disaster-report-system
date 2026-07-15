# 智慧災害通報系統 - 測試 DB 重置腳本
# 用途：TRUNCATE 所有 data table，保留 users（admin）與 alembic_version（schema 版本）
# 安全機制：硬編碼只連 disaster_report_test，不可能誤刪生產 DB

$DockerPath = 'C:\Program Files\Docker\Docker\resources\bin'
$DockerExe = Join-Path $DockerPath 'docker.exe'

$TestDbName = 'disaster_report_test'

Write-Host '=== 重置測試 DB ===' -ForegroundColor Cyan
Write-Host "目標 database：$TestDbName" -ForegroundColor Gray
Write-Host ''

# 確認 container
$dockerRunning = & $DockerExe ps --filter 'name=disaster_db' --format '{{.Names}}' 2>$null
if (-not $dockerRunning) {
    Write-Host '[錯誤] disaster_db container 未啟動' -ForegroundColor Red
    exit 1
}

# 確認測試 DB 存在
$dbExists = & $DockerExe exec disaster_db psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$TestDbName'" 2>$null
if (-not ($dbExists -match '^1')) {
    Write-Host "[錯誤] 測試 DB ($TestDbName) 不存在" -ForegroundColor Red
    Write-Host '請先執行 .\scripts\setup-test-db.ps1' -ForegroundColor Yellow
    exit 1
}

# 動態 TRUNCATE：列舉 public schema 所有 table，排除 users 與 alembic_version
$truncateSql = @'
DO $$
DECLARE
  t text;
  cnt int := 0;
BEGIN
  FOR t IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename NOT IN ('users', 'alembic_version')
  LOOP
    EXECUTE format('TRUNCATE TABLE %I RESTART IDENTITY CASCADE', t);
    cnt := cnt + 1;
    RAISE NOTICE '  TRUNCATE %', t;
  END LOOP;
  RAISE NOTICE '已重置 % 個 table', cnt;
END $$;
'@

Write-Host 'TRUNCATE 中...' -ForegroundColor Yellow
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c $truncateSql
if ($LASTEXITCODE -ne 0) {
    Write-Host '[錯誤] TRUNCATE 失敗' -ForegroundColor Red
    exit 1
}

# 驗證 admin 還在
Write-Host ''
Write-Host '驗證 admin user 仍存在：' -ForegroundColor White
& $DockerExe exec disaster_db psql -U postgres -d $TestDbName -c 'SELECT username FROM users'

Write-Host ''
Write-Host '=== 重置完成 ===' -ForegroundColor Green
Write-Host ''
