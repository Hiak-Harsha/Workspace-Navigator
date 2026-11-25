# Workspace Navigator

A lightweight, zero-dependency Python + vanilla JS desktop organizer, workspace dashboard, and redundant-file auditor for Windows.

## Quick Start (Any Windows Machine)

1. Ensure **Python 3.8+** is installed (`python --version`).
2. Double-click **`setup.bat`** (or run `.\setup.ps1 -Launch` in PowerShell).
   - Auto-detects your active **Desktop** (including OneDrive-redirected Desktops via Windows Registry / Shell Folders).
   - Initializes your **Workspace** category folders (`00_Archives_Storage` through `06_Career_Personal`).
   - Writes your local `organizer_config.json` (Auto-Organizer starts **PAUSED** by default so nothing moves without your consent).
   - Creates a **Workspace Navigator** shortcut on your Desktop and opens the dashboard at `http://127.0.0.1:8585`.

## Key Features

- **Universal Path Resolution:** No hardcoded usernames or install paths. Dynamically resolves Desktop, Workspace, and VS Code locations (`%LOCALAPPDATA%`, `%ProgramFiles%`, `PATH`).
- **Token-Safe Classification:** Organizes Desktop items on word/token boundaries (avoiding false matches like `"ai"` inside `"mail"` or `"ml"` inside `"html"`), and skips freshly created items (`min_age_seconds`, default 20s) so active downloads or new folders are never swept mid-edit.
- **Consistent Duplicate & Redundancy Engine (`♻️ Redundant`):**
  - **Preventative deduplication:** Before moving a file or folder from Desktop, checks SHA-256 content hashes (or folder file-hash manifests). Identical copies are recycled instead of generating `Folder (1)`, `Folder (2)`... clones.
  - **Workspace audit:** Scans Workspace (and optionally Desktop) while skipping `node_modules`, `.venv`, `.git`, `__pycache__`, etc. Flags exact SHA-256 duplicate files, numbered collision folders (`identical` / `subset` / `different`), empty directories, 0-byte files, and `~$` / `.tmp` artifacts.
  - **Safe cleanup:** Moves selected redundant items to the **Windows Recycle Bin** (`SHFileOperationW`), strictly constrained to paths inside Workspace or Desktop.
- **Git Repo Awareness:** Detects both top-level and nested `.git` repositories (up to depth 2), showing active branch, uncommitted changes, unpushed commits, and repos without a GitHub remote.
- **Quick Launchers:** Open any item in **File Explorer**, **VS Code**, or **PowerShell Terminal** with one click.

## CLI Usage

```powershell
# Initialize workspace folders & config on a new machine
python server.py --init

# Preview what Desktop organization would do (dry-run)
python server.py --migrate-dry-run

# Execute Desktop organization now
python server.py --migrate-execute

# Run redundant-file audit and print JSON report
python server.py --scan-duplicates
```

Or use the PowerShell wrappers:
```powershell
.\migrate_desktop.ps1           # Dry-run
.\migrate_desktop.ps1 -Execute  # Move & deduplicate
.\rollback_desktop.ps1          # Restore moved items from migration_manifest.json
```
