@echo off
if "%~1"=="--help" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" -Help
    exit /b %ERRORLEVEL%
)
if "%~1"=="-h" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" -Help
    exit /b %ERRORLEVEL%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" %*
