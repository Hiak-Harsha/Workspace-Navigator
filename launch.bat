@echo off
setlocal
cd /d "%~dp0"

set "PORT=8585"

:: Check if server is already listening on port
netstat -ano | findstr "127.0.0.1:%PORT%" | findstr "LISTENING" >nul
if %ERRORLEVEL% NEQ 0 (
    where pythonw.exe >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        start "" pythonw.exe server.py
    ) else (
        where pyw.exe >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            start "" pyw.exe -3 server.py
        ) else (
            start "" /MIN python.exe server.py
        )
    )
    timeout /t 1 /nobreak >nul
)

:: Open in Microsoft Edge App Mode (x86 or x64)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)

:: Fallback to Google Chrome App Mode (x64 or x86)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)

:: Default browser fallback
start "" "http://127.0.0.1:%PORT%"

:end
endlocal
