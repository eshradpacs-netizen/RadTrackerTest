@echo off
title RadTracker Canli Ajan Testi
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0test.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Test araci calistirilirken bir sorun olustu.
    pause
)
