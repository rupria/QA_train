param(
    [string[]]$Language,
    [ValidateSet('web','jvm','dotnet','native','data-script','infrastructure','other')]
    [string]$Group,
    [switch]$All,
    [switch]$List,
    [ValidateSet('parse','compare','all')]
    [string]$Check = 'all',
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot 'AST\.venv\Scripts\python.exe'
$runnerPath = Join-Path $PSScriptRoot 'run_language_parser_tests.py'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '먼저 AST 폴더에서 uv sync를 실행하세요.'
}

$runnerArgs = @('-X', 'utf8', '-B', $runnerPath, '--check', $Check)
if ($List) {
    $runnerArgs += '--list'
} elseif ($Language) {
    foreach ($item in $Language) {
        $runnerArgs += @('--language', $item)
    }
} elseif ($Group) {
    $runnerArgs += @('--group', $Group)
} elseif ($All) {
    $runnerArgs += '--all'
} else {
    throw '-Language, -Group, -All, -List 중 하나를 지정하세요.'
}
if ($Json) {
    $runnerArgs += '--json'
}

& $pythonPath @runnerArgs
exit $LASTEXITCODE
