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

if (-not $AnalyzerArguments -or $AnalyzerArguments.Count -eq 0) {
    Write-Host 'Usage: .\run_ast_analyzer_Tree.ps1 "C:\path\to\source.py"'
    exit 1
}

& $python -B $analyzer tree @AnalyzerArguments
exit $LASTEXITCODE
