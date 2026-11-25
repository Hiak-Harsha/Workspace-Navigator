# Universal Desktop Migration Script (uses navigator_core classification + SHA-256 deduplication)
param(
    [switch]$Execute = $false
)

$NavigatorDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerPy = Join-Path $NavigatorDir "server.py"

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Host "Python 3 is required to run Workspace Navigator migration." -ForegroundColor Red
    exit 1
}

$ModeFlag = if ($Execute) { "--migrate-execute" } else { "--migrate-dry-run" }
Write-Host "=== Universal Desktop Organization ($ModeFlag) ===" -ForegroundColor Cyan

if ($PythonCmd.Name -eq "py.exe" -or $PythonCmd.Name -eq "py") {
    & $PythonCmd.Source -3 $ServerPy $ModeFlag
} else {
    & $PythonCmd.Source $ServerPy $ModeFlag
}
