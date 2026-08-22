@echo off
chcp 65001 >nul
title RadTracker PACS - Otomatik Temizlemeli Ajan Kurulumu
color 0B

echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - 100%% SESSIZ VE TEMIZLEYICI KURULUM (USB)
echo ============================================================================
echo.
echo [1/4] Bilgisayardaki eski/cakisan tum ajanlar temizleniyor...

:: 1. Calisan eski PowerShell ve Python ajan sureclerini zorla durdur
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*RadTracker*' -or $_.CommandLine -like '*agent.ps1*' -or $_.CommandLine -like '*radtrack*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

:: 2. Eski Baslangic (Startup) VBS ve BAT kisayollarini sil
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs" 2>nul
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" 2>nul
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.bat" 2>nul
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.vbs" 2>nul
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTracker*.bat" 2>nul

:: 3. Eski Gorev Zamanlayici gorevlerini sil
schtasks /Delete /TN "RadTrackerAgent" /F 2>nul
schtasks /Delete /TN "RadTrackerAgentTask" /F 2>nul
schtasks /Delete /TN "RadiologyTracker" /F 2>nul

:: 4. Eski dosya dizinini temizle ve sifirdan olustur
rmdir /S /Q "C:\ProgramData\RadTracker" 2>nul
mkdir "C:\ProgramData\RadTracker" 2>nul

echo [TAMAMLANDI] Eski ajan kalintilari basariyla temizlendi!
echo.
echo [2/4] Yeni guncel ajan dosyalari kopyalaniyor...
copy /Y "%~dp0agent.ps1" "C:\ProgramData\RadTracker\agent.ps1" >nul
if exist "%~dp0install.ps1" copy /Y "%~dp0install.ps1" "C:\ProgramData\RadTracker\install.ps1" >nul

echo.
echo [3/4] Oda ve Masa Secimi Baslatiliyor...
echo.
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "C:\ProgramData\RadTracker\install.ps1"

echo.
echo [4/4] 100%% Gorunmez Arka Plan Baslaticisi Kuruluyor...

set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs
echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_VBS%"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""C:\ProgramData\RadTracker\agent.ps1""", 0, False >> "%STARTUP_VBS%"

echo Set WshShell = CreateObject("WScript.Shell") > "C:\ProgramData\RadTracker\launcher.vbs"
echo WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File ""C:\ProgramData\RadTracker\agent.ps1""", 0, False >> "C:\ProgramData\RadTracker\launcher.vbs"

wscript.exe "C:\ProgramData\RadTracker\launcher.vbs"

echo ============================================================================
echo  [BASARILI] Temiz kurulum tamamlandi!
echo  - Bilgisayar her acildiginda HICBIR PENCERE ACMADAN arkada calisacaktir.
echo  - Yanlislikla kapatilamaz veya durdurulamaz.
echo  - USB belleginizi artik cikarabilirsiniz.
echo ============================================================================
echo.
pause
