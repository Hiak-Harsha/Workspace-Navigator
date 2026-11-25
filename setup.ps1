# Universal First-Time Setup for Workspace Navigator
param(
    [switch]$Launch = $false
)

$NavigatorDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerPy = Join-Path $NavigatorDir "server.py"
$LaunchVbs = Join-Path $NavigatorDir "launch.vbs"

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Host "ERROR: Python 3 not found on PATH. Install Python 3.8+ and re-run setup." -ForegroundColor Red
    exit 1
}

Write-Host "Initializing Workspace Navigator from $NavigatorDir ..." -ForegroundColor Cyan
if ($PythonCmd.Name -eq "py.exe" -or $PythonCmd.Name -eq "py") {
    $InitOut = & $PythonCmd.Source -3 $ServerPy --init
} else {
    $InitOut = & $PythonCmd.Source $ServerPy --init
}
Write-Host $InitOut

# Create Desktop shortcut on the current user's Desktop (handles OneDrive redirection)
$DesktopDir = [Environment]::GetFolderPath("Desktop")
try {
    $Info = $InitOut | ConvertFrom-Json
    if ($Info.desktop_dir) { $DesktopDir = $Info.desktop_dir }
} catch {}

if (Test-Path $DesktopDir) {
    $ShortcutPath = Join-Path $DesktopDir "Workspace Navigator.lnk"
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "wscript.exe"
    $Shortcut.Arguments = "`"$LaunchVbs`""
    $Shortcut.WorkingDirectory = $NavigatorDir
    $Shortcut.Description = "Launch Workspace Navigator"
    $Shortcut.Save()
    Write-Host "Desktop shortcut created: $ShortcutPath" -ForegroundColor Green
}

if ($Launch) {
    Start-Process "wscript.exe" -ArgumentList "`"$LaunchVbs`""
}
