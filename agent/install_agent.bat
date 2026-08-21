@echo off
title RadTracker Agent Kurulumu
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Kurulum sirasinda bir sorun olustu.
    pause
)
