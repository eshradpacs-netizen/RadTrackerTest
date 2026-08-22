@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title RadTracker PACS - Ajan Kurulumu

:: 1. Yonetici Yetkisi Kontrolu ve Otomatik Yetki Yukseltme (UAC)
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
echo   RADYOLOJI PACS TAKIP SISTEMI - 100%% SESSIZ VE TEMIZLEYICI KURULUM (USB)
echo ============================================================================
echo.

set TARGET_DIR=C:\ProgramData\RadTracker
set SERVER_URL=https://esh-radtracker.onrender.com

echo [1/4] Bilgisayardaki eski/cakisan tum ajanlar temizleniyor...

:: Eski calisan processleri durdur
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*RadTracker*' -or $_.CommandLine -like '*agent.ps1*' -or $_.CommandLine -like '*radtrack*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Eski baslangic dosyalarini temizle
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" >nul 2>&1
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.bat" >nul 2>&1
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" >nul 2>&1
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.bat" >nul 2>&1
schtasks /Delete /TN "RadTrackerAgent" /F >nul 2>&1
schtasks /Delete /TN "RadTrackerAgentTask" /F >nul 2>&1

:: Hedef klasoru hazirla
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1

echo [TAMAMLANDI] Eski ajan kalintilari temizlendi.
echo.

echo [2/4] Ajan dosyalari kalici sisteme aktariliyor (%TARGET_DIR%)...

:: USB'den kopyala veya Sunucudan indir
if exist "%~dp0agent.ps1" (
    copy /Y "%~dp0agent.ps1" "%TARGET_DIR%\agent.ps1" >nul
) else (
    echo [BILGI] agent.ps1 sunucudan indiriliyor...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%SERVER_URL%/agent/agent.ps1', '%TARGET_DIR%\agent.ps1')"
)

if exist "%~dp0install.ps1" (
    copy /Y "%~dp0install.ps1" "%TARGET_DIR%\install.ps1" >nul
) else (
    echo [BILGI] install.ps1 sunucudan indiriliyor...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%SERVER_URL%/agent/install.ps1', '%TARGET_DIR%\install.ps1')"
)

echo.
echo [3/4] Oda ve Masa Secimi Baslatiliyor...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TARGET_DIR%\install.ps1"

echo.
echo [4/4] 100%% Gorunmez Arka Plan Baslaticisi Kuruluyor...

set STARTUP_VBS=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs
echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_VBS%"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""%TARGET_DIR%\agent.ps1""", 0, False >> "%STARTUP_VBS%"

echo Set WshShell = CreateObject("WScript.Shell") > "%TARGET_DIR%\launcher.vbs"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""%TARGET_DIR%\agent.ps1""", 0, False >> "%TARGET_DIR%\launcher.vbs"

wscript.exe "%TARGET_DIR%\launcher.vbs"

echo.
echo ============================================================================
echo  [BASARILI] Temiz kurulum 100%% tamamlandi!
echo  - Ajan bilgisayar her acildiginda HICBIR PENCERE ACMADAN arkada calisacaktir.
echo  - Yanlislikla kapatilamaz veya durdurulamaz.
echo  - USB belleginizi artik bilgisayardan cikarabilirsiniz.
echo ============================================================================
echo.
pause
