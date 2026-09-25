param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AnalyzerArguments
)

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$analyzer = Join-Path $PSScriptRoot 'ast_analyzer.py'

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "AST 전용 환경을 찾을 수 없습니다: $python"
    exit 1
}

& $python -B $analyzer @AnalyzerArguments
exit $LASTEXITCODE
