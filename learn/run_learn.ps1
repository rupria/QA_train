param(
    [ValidateSet("catalog", "policy", "fetch", "build", "pack", "all")]
    [string]$Command = "all",
    [string[]]$Source = @(),
    [switch]$Force,
    [string]$PackVersion = "0.1.0-draft",
    [string[]]$ReviewStatus = @(),
    [string]$PackOutput = "",
    [string]$Embeddings = ""
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
if ($Command -eq "pack") {
    $Arguments += @("--pack-version", $PackVersion)
    foreach ($Status in $ReviewStatus) {
        $Arguments += @("--review-status", $Status)
    }
    if ($PackOutput) {
        $Arguments += @("--pack-output", $PackOutput)
    }
    if ($Embeddings) {
        $Arguments += @("--embeddings", $Embeddings)
    }
}
$Arguments += $Command
& $PythonPath @Arguments
exit $LASTEXITCODE
