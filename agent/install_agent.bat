@echo off
:: Radiology PC Tracker v1 - 1-Click Silent Agent Installer for Windows
title RadTracker Agent Installer

echo ==================================================
echo  Radiology PC Tracker v1 - Silent Agent Installer
echo ==================================================
echo.

set /p SERVER_URL="Lutfen Sunucu Adresini Girin (Varsayilan: https://radtrackertest.onrender.com): "
if "%SERVER_URL%"=="" set SERVER_URL=https://radtrackertest.onrender.com

set AGENT_DIR=%~dp0
set AGENT_PS1=%AGENT_DIR%agent.ps1
set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs

echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_VBS%"
echo WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%AGENT_PS1%"" -ServerUrl ""%SERVER_URL%""", 0, False >> "%STARTUP_VBS%"

echo.
echo [BASARILI] Ajan Windows Baslangicina (Startup) eklendi!
echo Ajan artik bilgisayar her acildiginda arka planda sessizce calisacak.
echo.
echo Simdi ajani hemen baslatmak icin bir tusa basin...
pause > nul

wscript.exe "%STARTUP_VBS%"
echo [CANLI] Ajan arka planda baslatildi!
pause
