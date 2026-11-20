@echo off
setlocal
cd /d "%~dp0"

:: Check for pythonw to launch silently without console window
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw main.py %*
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        start "" python main.py %*
    ) else (
        echo [ERROR] Python was not found in your system PATH.
        echo Please install Python 3.10+ and make sure it is added to PATH.
        pause
    )
)
