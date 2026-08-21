@echo off
:: ============================================================================
::  Radiology PC Tracker v1 - 1-Click Silent Agent Enterprise Installer
:: ============================================================================
title RadTracker Agent Kurulumu
color 0B

echo.
echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - 1-TIK AJAN KURULUMU (WINDOWS)
echo ============================================================================
echo.

:: 1. Admin yetkisi kontrolü
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [BILGI] Yonetici haklari istendi...
    powershell -Command "Start-Process cmd -ArgumentList '/c %~s0' -Verb RunAs"
    exit /b
)

set SERVER_URL=https://radtrackertest.onrender.com
set TARGET_DIR=C:\ProgramData\RadTracker
set TARGET_PS1=%TARGET_DIR%\agent.ps1
set TASK_NAME=RadTrackerAgentTask

echo [1/4] Kurulum dizini olusturuluyor: %TARGET_DIR%
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [2/4] Ajan dosyasi kopyalaniyor...
copy /Y "%~dp0agent.ps1" "%TARGET_PS1%" >nul

echo [3/4] Windows Zamanlanmis Gorev (Scheduled Task) tanimlaniyor...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
schtasks /Create /F /TN "%TASK_NAME%" /SC ONLOGON /RL HIGHEST /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File \"%TARGET_PS1%\" -ServerUrl \"%SERVER_URL%\"" >nul

echo [4/4] Ajan arka planda hemen baslatiliyor ve test ediliyor...
powershell -ExecutionPolicy Bypass -NoProfile -Command "& {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
    $hostn = $env:COMPUTERNAME
    $user = $env:USERNAME
    Write-Host ''
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host '  CANLI SISTEM BILGILERI:' -ForegroundColor Cyan
    Write-Host \"  Bilgisayar Adi : $hostn\" -ForegroundColor White
    Write-Host \"  IP Adresi      : $ip\" -ForegroundColor White
    Write-Host \"  Kullanici      : $user\" -ForegroundColor White
    Write-Host \"  Sunucu Adresi  : %SERVER_URL%\" -ForegroundColor White
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    
    try {
        $url = \"%SERVER_URL%/api/heartbeat?hostname=$hostn&ip=$ip&username=$user&idleTimeSeconds=0&suspicious=0\"
        $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 6
        Write-Host '  [OK] Sunucuya Ilk Sinyal Basariyla Gonderildi (200 OK)!' -ForegroundColor Green
        Write-Host \"  [OK] Sisteme Kaydedildi: $($resp.pc.friendlyName) - $($resp.pc.room)\" -ForegroundColor Yellow
    } catch {
        Write-Host '  [UYARI] Sunucu uyku modundan uyaniyor veya baglanti bekliyor...' -ForegroundColor DarkYellow
    }
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
}"

schtasks /Run /TN "%TASK_NAME%" >nul 2>&1

echo.
echo ============================================================================
echo   [TEBRIKLER] KURULUM BASARIYLA TAMAMLANDI!
echo ============================================================================
echo   - Ajan artik bilgisayar her acildiginda tamamen sessizce calisacak.
echo   - Doktorun ekraninda hicbir pencere veya bildirim acilmayacaktir.
echo.
echo Cikmak icin herhangi bir tusa basin...
pause >nul
