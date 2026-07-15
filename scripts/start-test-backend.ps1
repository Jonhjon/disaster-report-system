# 智慧災害通報系統 - 測試後端啟動腳本
# 用途：在 port 8001 啟動 uvicorn，DATABASE_URL 指向 disaster_report_test
#       與生產後端（port 8000）並存互不影響

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir 'backend'
$VenvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'

$TestPort = 8001
$TestDbUrl = 'postgresql://postgres:Cm3023203@127.0.0.1:5432/disaster_report_test'

Write-Host '=== 啟動測試後端 ===' -ForegroundColor Cyan
Write-Host "  Port:        $TestPort" -ForegroundColor Gray
Write-Host "  DATABASE:    disaster_report_test" -ForegroundColor Gray
Write-Host ''

# 檢查 venv 是否存在
if (-not (Test-Path $VenvPython)) {
    Write-Host "[錯誤] 找不到 $VenvPython" -ForegroundColor Red
    Write-Host '請先建立 backend venv 並安裝相依套件' -ForegroundColor Yellow
    exit 1
}

# 清空 port 8001 上的舊 process（複用 start.ps1 的 cleanup 邏輯）
Write-Host "清除 port $TestPort 上的舊程序..." -ForegroundColor DarkGray

function Stop-DescendantProcesses {
    param([int]$ParentId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue
    foreach ($c in $children) {
        Stop-DescendantProcesses -ParentId ([int]$c.ProcessId)
        Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$pidsToKill = New-Object System.Collections.Generic.HashSet[int]

# 抓 port 8001 owner + parent + siblings
Get-NetTCPConnection -LocalPort $TestPort -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $owner = $_.OwningProcess
        if ($owner) {
            [void]$pidsToKill.Add([int]$owner)
            $info = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
            if ($info -and $info.ParentProcessId) {
                [void]$pidsToKill.Add([int]$info.ParentProcessId)
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$($info.ParentProcessId)" -ErrorAction SilentlyContinue |
                    ForEach-Object { [void]$pidsToKill.Add([int]$_.ProcessId) }
            }
        }
    }

foreach ($pidToKill in $pidsToKill) {
    Stop-DescendantProcesses -ParentId $pidToKill
    Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

# 終端標題提示，避免誤操作生產
$Host.UI.RawUI.WindowTitle = "TEST BACKEND :$TestPort | DB=disaster_report_test"

# 啟動 uvicorn
Push-Location $BackendDir
try {
    $env:DATABASE_URL = $TestDbUrl
    Write-Host ''
    Write-Host "啟動中... http://localhost:$TestPort/docs" -ForegroundColor Green
    Write-Host '按 Ctrl+C 停止' -ForegroundColor Gray
    Write-Host ''
    & $VenvPython -m uvicorn app.main:app --reload --port $TestPort
} finally {
    Pop-Location
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
}
