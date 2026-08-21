@echo off
chcp 65001 >nul
title RadTracker PACS - Ajan Kaldirici
color 0C

echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - AJAN KALDIRICI
echo ============================================================================
echo.
echo [1/3] Calisan ajan surecleri durduruluyor...
powershell.exe -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*RadTracker*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" 2>nul

echo [2/3] Baslangic (Startup) kisayollari siliniyor...
del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs" 2>nul
del /F /Q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs" 2>nul

echo [3/3] Kalici program dosyalari temizleniyor...
rmdir /S /Q "C:\ProgramData\RadTracker" 2>nul

echo ============================================================================
echo  [BASARILI] RadTracker ajani bu bilgisayardan tamamen kaldirildi.
echo ============================================================================
echo.
pause
