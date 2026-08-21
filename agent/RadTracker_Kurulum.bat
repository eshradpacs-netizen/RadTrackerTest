@echo off
chcp 65001 >nul
title RadTracker PACS - Ajan Kurulumu
color 0B

echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - 100%% SESSIZ AJAN KURULUMU (USB)
echo ============================================================================
echo.
echo [1/3] Ajan dosyalari kalici sisteme kopyalaniyor (C:\ProgramData\RadTracker)...

if not exist "C:\ProgramData\RadTracker" mkdir "C:\ProgramData\RadTracker"

copy /Y "%~dp0agent.ps1" "C:\ProgramData\RadTracker\agent.ps1" >nul
if exist "%~dp0install.ps1" copy /Y "%~dp0install.ps1" "C:\ProgramData\RadTracker\install.ps1" >nul

echo [2/3] Oda ve Masa Secimi Baslatiliyor...
echo.

powershell.exe -ExecutionPolicy Bypass -NoProfile -File "C:\ProgramData\RadTracker\install.ps1"

echo.
echo [3/3] 100%% Gorunmez Arka Plan Baslaticisi Ayarlaniyor...

set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs
echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_VBS%"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""C:\ProgramData\RadTracker\agent.ps1""", 0, False >> "%STARTUP_VBS%"

echo Set WshShell = CreateObject("WScript.Shell") > "C:\ProgramData\RadTracker\launcher.vbs"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""C:\ProgramData\RadTracker\agent.ps1""", 0, False >> "C:\ProgramData\RadTracker\launcher.vbs"

wscript.exe "C:\ProgramData\RadTracker\launcher.vbs"

echo ============================================================================
echo  [BASARILI] Kurulum tamamlandi!
echo  - Ajan bilgisayar her acildiginda HICBIR PENCERE ACMADAN arkada calisacaktir.
echo  - USB belleginizi artik bilgisayardan cikarabilirsiniz.
echo ============================================================================
echo.
pause
