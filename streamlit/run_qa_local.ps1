param([ValidateRange(1024,65535)][int]$Port = 8501)
$ErrorActionPreference = 'Stop'
$env:QA_APP_MODE = 'local'
$env:QA_WEB_ALLOW_LOCAL = '1'
& (Join-Path $PSScriptRoot 'run_qa_web.ps1') -Port $Port
if ($LASTEXITCODE -ne 0) {
    throw "QA compare 로컬 앱이 종료 코드 $LASTEXITCODE 로 종료됐습니다."
}
