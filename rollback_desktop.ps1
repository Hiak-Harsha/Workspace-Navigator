# Universal Desktop Restructuring Rollback Script
$NavigatorDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $NavigatorDir "organizer_config.json"

$Desktop = [Environment]::GetFolderPath("Desktop")
$Workspace = Join-Path $HOME "Workspace"

if (Test-Path $ConfigPath) {
    try {
        $Cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($Cfg.desktop_dir) { $Desktop = $Cfg.desktop_dir }
        if ($Cfg.workspace_dir) { $Workspace = $Cfg.workspace_dir }
    } catch {}
}

$ManifestPath = Join-Path $Workspace "migration_manifest.json"
if (!(Test-Path $ManifestPath)) {
    Write-Host "No migration manifest found at $ManifestPath" -ForegroundColor Red
    exit 1
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
Write-Host "=== Rolling back desktop migration ($($Manifest.Count) items) -> $Desktop ===" -ForegroundColor Yellow

$Remaining = @()
foreach ($entry in $Manifest) {
    $destPath = $entry.To
    if ($destPath -and (Test-Path -LiteralPath $destPath)) {
        $targetOnDesktop = Join-Path $Desktop $entry.Item
        if (Test-Path -LiteralPath $targetOnDesktop) {
            Write-Host "[SKIP] Already exists on Desktop: $($entry.Item)" -ForegroundColor DarkYellow
            $Remaining += $entry
            continue
        }
        try {
            Move-Item -LiteralPath $destPath -Destination $targetOnDesktop
            Write-Host "[RESTORED] $($entry.Item) -> $Desktop" -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Could not restore $($entry.Item): $_" -ForegroundColor Red
            $Remaining += $entry
        }
    } else {
        Write-Host "[SKIP] Item no longer at $destPath" -ForegroundColor Gray
    }
}

$Remaining | ConvertTo-Json -Depth 4 | Set-Content -Path $ManifestPath -Encoding UTF8
Write-Host "`nRollback complete." -ForegroundColor Cyan
