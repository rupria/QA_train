param([ValidateRange(1024,65535)][int]$Port = 8501)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '먼저 streamlit 폴더에서 uv sync를 실행하세요.'
}
Push-Location -LiteralPath $PSScriptRoot
try {
    & $pythonPath -X utf8 -m streamlit run (Join-Path $PSScriptRoot 'streamlit_app.py') --server.address 127.0.0.1 --server.port $Port --server.headless true --browser.gatherUsageStats false
    if ($LASTEXITCODE -ne 0) { throw "Streamlit이 종료 코드 $LASTEXITCODE 로 종료됐습니다." }
} finally {
    Pop-Location
}
