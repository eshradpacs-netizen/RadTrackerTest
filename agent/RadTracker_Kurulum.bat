@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title RadTracker PACS - Ajan Kurulumu

:: 1. Yonetici Yetkisi Kontrolu
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================================
    echo   [BILGI] Yonetici yetkileri aliniyor, lutfen EVET butonuna basiniz...
    echo ============================================================================
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/k ""%~f0""' -Verb RunAs"
    exit /b
)

color 0B
cls
echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - GUCLENDIRILMIS KURULUM
echo ============================================================================
echo.

set TARGET_DIR=C:\ProgramData\RadTracker
set SERVER_URL=https://esh-radtracker.onrender.com

echo [1/3] Bilgisayardaki eski calisan ajanlar durduruluyor...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*agent.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*pc_agent*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
taskkill /F /IM wscript.exe >nul 2>&1

:: Eski gecici dosyalari temizle
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" >nul 2>&1
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" >nul 2>&1
schtasks /Delete /TN "RadTrackerAgent" /F >nul 2>&1
schtasks /Delete /TN "RadTrackerAgentTask" /F >nul 2>&1

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1

echo [2/3] Ajan dosyalari aktariliyor (%TARGET_DIR%)...
if exist "%~dp0agent.ps1" (
    copy /Y "%~dp0agent.ps1" "%TARGET_DIR%\agent.ps1" >nul
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%SERVER_URL%/agent/agent.ps1', '%TARGET_DIR%\agent.ps1')"
)

if exist "%~dp0install.ps1" (
    copy /Y "%~dp0install.ps1" "%TARGET_DIR%\install.ps1" >nul
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%SERVER_URL%/agent/install.ps1', '%TARGET_DIR%\install.ps1')"
)

echo.
echo [3/3] Oda ve Masa Secimi Baslatiliyor...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TARGET_DIR%\install.ps1"

echo.
pause
