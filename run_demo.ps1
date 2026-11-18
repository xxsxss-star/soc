$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到 .venv。请先创建虚拟环境并执行：.\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

$env:PYTHONPATH = $projectRoot
if (-not $env:API_BASE_URL) {
    $env:API_BASE_URL = "http://127.0.0.1:8000/api/v1"
}

$backend = $null
try {
    $backend = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            Invoke-RestMethod -Uri "$env:API_BASE_URL/health" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw "FastAPI 后端未能在 http://127.0.0.1:8000 启动"
    }

    Write-Host "后端已启动：http://127.0.0.1:8000/docs"
    Write-Host "前端即将启动：http://127.0.0.1:8501"
    & $pythonPath -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
    }
}
