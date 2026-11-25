@echo off
setlocal

set "ACTION=%~1"
set "TARGET=%~2"

if not exist "%TARGET%" exit /b 1

if /i "%ACTION%"=="explorer" (
    if exist "%TARGET%\*" (
        start "" explorer.exe "%TARGET%"
    ) else (
        start "" explorer.exe /select,"%TARGET%"
    )
    exit /b 0
)

if /i "%ACTION%"=="vscode" (
    if exist "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" (
        start "" /D "%LOCALAPPDATA%\Programs\Microsoft VS Code" "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" "%TARGET%"
        exit /b 0
    )
    if exist "%ProgramFiles%\Microsoft VS Code\Code.exe" (
        start "" /D "%ProgramFiles%\Microsoft VS Code" "%ProgramFiles%\Microsoft VS Code\Code.exe" "%TARGET%"
        exit /b 0
    )
    if exist "%ProgramFiles(x86)%\Microsoft VS Code\Code.exe" (
        start "" /D "%ProgramFiles(x86)%\Microsoft VS Code" "%ProgramFiles(x86)%\Microsoft VS Code\Code.exe" "%TARGET%"
        exit /b 0
    )
    start "" code "%TARGET%"
    exit /b 0
)

if /i "%ACTION%"=="terminal" (
    if exist "%TARGET%\*" (
        start "PowerShell" powershell.exe -NoExit -Command "Set-Location -LiteralPath '%TARGET%'"
    ) else (
        for %%I in ("%TARGET%") do (
            start "PowerShell" powershell.exe -NoExit -Command "Set-Location -LiteralPath '%%~dpI'"
        )
    )
    exit /b 0
)

exit /b 2
