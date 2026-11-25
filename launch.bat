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
    :: Wait up to 3s for port to listen without using timeout.exe (which fails if stdin is redirected)
    powershell -NoProfile -Command "for($i=0;$i -lt 15;$i++){ try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%);$c.Close();break}catch{Start-Sleep -Milliseconds 200} }" >nul 2>&1
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

:: Fallback to Google Chrome App Mode (x64, x86, or LocalAppData)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    start "" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)

:: Fallback to Brave App Mode
if exist "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe" (
    start "" "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)
if exist "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" (
    start "" "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" --app="http://127.0.0.1:%PORT%" --window-size=1280,840
    goto end
)

:: Generic default browser fallback
start "" "http://127.0.0.1:%PORT%"

:end
endlocal
