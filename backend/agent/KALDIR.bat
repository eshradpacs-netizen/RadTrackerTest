@echo off
chcp 65001 >nul
title RadTracker PACS - Ajan Kaldirici
color 0C

echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - AJAN KALDIRICI
echo ============================================================================
echo.

schtasks /Delete /TN "RadTrackerAgent" /F >nul 2>&1
schtasks /Delete /TN "RadTrackerAgentTask" /F >nul 2>&1
powershell.exe -Command "Get-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object { (Get-CimInstance Win32_Process -Filter \"ProcessId = $($_.Id)\").CommandLine -like '*agent.ps1*' } | Stop-Process -Force" >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RadTrackerAgent" /f >nul 2>&1
rmdir /S /Q "C:\ProgramData\RadTracker" >nul 2>&1

echo [TAMAMLANDI] Ajan basariyla kaldirildi.
echo.
pause
