param(
    [ValidateSet("catalog", "policy", "fetch", "build", "all")]
    [string]$Command = "all",
    [string[]]$Source = @(),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
$env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"

uv sync
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Arguments = @("-X", "utf8", "-B", "-m", "qa_learn.cli")
foreach ($SourceId in $Source) {
    $Arguments += @("--source", $SourceId)
}
if ($Force) {
    $Arguments += "--force"
}
$Arguments += $Command
& $PythonPath @Arguments
exit $LASTEXITCODE
