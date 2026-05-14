# 智慧災害通報系統 - 一鍵啟動腳本
# 重開機後，以系統管理員身分執行此腳本

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir 'backend'
$PublicDir = Join-Path $ProjectDir 'frontend-public'
$AdminDir = Join-Path $ProjectDir 'frontend-admin'
$NodePath = 'C:\Program Files\nodejs'
$DockerPath = 'C:\Program Files\Docker\Docker\resources\bin'

Write-Host '=== 智慧災害通報系統啟動中 ===' -ForegroundColor Cyan

# 0. 偵測系統是否已在執行
$pidFile = Join-Path $ProjectDir '.running_pids'
$alreadyRunning = $false
$statusLines = @()

if (Test-Path $pidFile) {
    try {
        $savedPids = Get-Content $pidFile -Raw | ConvertFrom-Json
        $ports = @{ 8000 = '後端  '; 5173 = '民眾端'; 5174 = '管理端' }
        $pidMap = @{ 8000 = $savedPids.BackendPID; 5173 = $savedPids.PublicPID; 5174 = $savedPids.AdminPID }

        foreach ($port in $ports.Keys) {
            $label   = $ports[$port]
            $pid_    = $pidMap[$port]
            $procAlive = $pid_ -and (Get-Process -Id $pid_ -ErrorAction SilentlyContinue)
            $portUsed  = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) -ne $null

            if ($procAlive -or $portUsed) {
                $alreadyRunning = $true
                $pidStr  = if ($pid_) { "PID: $pid_" } else { 'PID: -' }
                $portStr = if ($portUsed) { '使用中' } else { '未偵測' }
                $statusLines += "  $label  $pidStr  port $port`: $portStr"
            }
        }
    } catch {
        # PID 檔損毀，略過偵測
    }
}

# 無 PID 檔時仍檢查埠是否被佔
if (-not $alreadyRunning) {
    foreach ($port in @(8000, 5173, 5174)) {
        if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
            $alreadyRunning = $true
            $statusLines += "  port $port`: 使用中（無 PID 記錄）"
        }
    }
}

if ($alreadyRunning) {
    Write-Host ''
    Write-Host '[警告] 系統似乎已在執行中！' -ForegroundColor Yellow
    foreach ($line in $statusLines) { Write-Host $line -ForegroundColor DarkYellow }
    Write-Host ''
    Write-Host '請選擇：' -ForegroundColor White
    Write-Host '  [R] 強制重新啟動（關閉現有服務再啟動）' -ForegroundColor Cyan
    Write-Host '  [Q] 取消（離開腳本）' -ForegroundColor Cyan
    Write-Host ''
    $choice = Read-Host '輸入 R 或 Q'
    if ($choice -notmatch '^[Rr]$') {
        Write-Host '已取消。系統繼續在背景執行中。' -ForegroundColor Green
        exit 0
    }
    Write-Host ''
    Write-Host '繼續重新啟動系統...' -ForegroundColor Yellow
}

# 1. 檢查 .env 設定
$EnvFile = Join-Path $BackendDir '.env'
if (Test-Path $EnvFile) {
    $EnvContent = Get-Content $EnvFile -Raw
    # 容許值前後有引號或空白：擷取 ANTHROPIC_API_KEY 的值再判斷
    $apiKey = $null
    if ($EnvContent -match '(?m)^\s*ANTHROPIC_API_KEY\s*=\s*["'']?([^"''\r\n]+)["'']?\s*$') {
        $apiKey = $Matches[1].Trim()
    }
    if (-not $apiKey -or $apiKey -eq 'your-api-key-here') {
        Write-Host ''
        Write-Host '[錯誤] 請先設定 ANTHROPIC_API_KEY！' -ForegroundColor Red
        Write-Host '請編輯此檔案並填入 Anthropic API Key：' -ForegroundColor Yellow
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
    Write-Host ''
    Write-Host '[!!] Alembic 遷移失敗' -ForegroundColor Red
    Write-Host '     後端可能因 schema 不一致而報錯。請依序確認：' -ForegroundColor Yellow
    Write-Host '       1. Docker 容器 disaster_db 是否就緒（docker ps）' -ForegroundColor Yellow
    Write-Host '       2. backend\.env 的 DATABASE_URL 密碼是否與 docker-compose.yml 一致' -ForegroundColor Yellow
    Write-Host '       3. 手動檢查當前版本：venv\Scripts\alembic.exe current' -ForegroundColor Yellow
    Write-Host '       4. 手動套用：venv\Scripts\alembic.exe upgrade head' -ForegroundColor Yellow
    Write-Host '     腳本會繼續啟動服務，但若後端啟動後 API 報 500，請優先排查上述項目。' -ForegroundColor Yellow
    Write-Host ''
}

# 5. 啟動後端（新視窗）
Write-Host ''
Write-Host '[4/5] 啟動後端服務...' -ForegroundColor Yellow

# 先清除佔用 port 8000 的舊 uvicorn / 殭屍 worker
# 三層保險：(1) 抓 cmdline 含 uvicorn 的 python；(2) 抓這些 python 的 child；(3) 抓 port 8000 的 owner
Write-Host '      清除舊 uvicorn 程序與佔用 port 8000 的 worker...' -ForegroundColor DarkGray

function Stop-DescendantProcesses {
    param([int]$ParentId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue
    foreach ($c in $children) {
        Stop-DescendantProcesses -ParentId ([int]$c.ProcessId)
        Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$pidsToKill = New-Object System.Collections.Generic.HashSet[int]

# (1) 直接 cmdline match uvicorn 的 python 主進程
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'uvicorn' } |
    ForEach-Object {
        [void]$pidsToKill.Add([int]$_.ProcessId)
        # (2) 連同 multiprocessing-fork 子 worker 一起清
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($_.ProcessId)" -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$pidsToKill.Add([int]$_.ProcessId) }
    }

# (3) 不論 cmdline，凡是 LISTEN 8000 的 owner + 其 parent / 兄弟 worker 全清
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $owner = $_.OwningProcess
        if ($owner) {
            [void]$pidsToKill.Add([int]$owner)
            $info = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
            if ($info -and $info.ParentProcessId) {
                [void]$pidsToKill.Add([int]$info.ParentProcessId)
                # 兄弟 worker（同一個父程序底下）
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$($info.ParentProcessId)" -ErrorAction SilentlyContinue |
                    ForEach-Object { [void]$pidsToKill.Add([int]$_.ProcessId) }
            }
        }
    }

foreach ($pidToKill in $pidsToKill) {
    Stop-DescendantProcesses -ParentId $pidToKill
    Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
}

# 確認 port 真的釋放
Start-Sleep -Seconds 1
$stillListening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($stillListening) {
    Write-Host '      [警告] port 8000 仍被佔用，5 秒後再嘗試一次...' -ForegroundColor Yellow
    $stillListening.OwningProcess | Sort-Object -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 5
}

# 清除 backend 下已刪除模組殘留的 .pyc（防止 import 載到不存在的舊模組）
Write-Host '      清除 backend __pycache__（避免 stale .pyc）...' -ForegroundColor DarkGray
Get-ChildItem -Path $BackendDir -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\venv\\' -and $_.FullName -notmatch '\\node_modules\\' } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

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
