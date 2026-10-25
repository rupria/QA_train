param(
    [ValidateSet("status", "download", "path")]
    [string]$Command = "status",
    [string]$DataDir
)

$arguments = @("run", "qa-model")
if ($DataDir) {
    $arguments += @("--data-dir", $DataDir)
}
$arguments += $Command
& uv @arguments
exit $LASTEXITCODE
