@echo off
title RadTracker Agent Kaldirici
color 0C

echo.
echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - AJAN KALDIRICI (UNINSTALLER)
echo ============================================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c %~s0' -Verb RunAs"
    exit /b
)

set TASK_NAME=RadTrackerAgentTask
set TARGET_DIR=C:\ProgramData\RadTracker

echo [1/3] Calisan ajan gorevi durduruluyor...
schtasks /End /TN "%TASK_NAME%" >nul 2>&1

echo [2/3] Windows Zamanlanmis Gorevi siliniyor...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

echo [3/3] Ajan dosyalari temizleniyor...
if exist "%TARGET_DIR%" rmdir /S /Q "%TARGET_DIR%" >nul 2>&1

echo.
echo ============================================================================
echo   [BASARILI] RadTracker Ajani bu bilgisayardan tamamen kaldirildi!
echo ============================================================================
echo.
pause
