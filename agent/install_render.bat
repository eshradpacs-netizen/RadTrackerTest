@echo off
title RadTracker Agent Installer - Render Cloud
echo ==================================================
echo  Radiology PC Tracker v1 - Render Cloud Installer
echo ==================================================
echo.

set SERVER_URL=https://esh-radtracker.onrender.com

set AGENT_DIR=%~dp0
set AGENT_PS1=%AGENT_DIR%agent.ps1
set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs

echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_VBS%"
echo WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%AGENT_PS1%"" -ServerUrl ""%SERVER_URL%""", 0, False >> "%STARTUP_VBS%"

echo [BASARILI] Ajan Render Bulut adresine baglandi: %SERVER_URL%
echo Ajan Windows Baslangicina (Startup) eklendi ve sessizce calisacak.
echo.
wscript.exe "%STARTUP_VBS%"
echo [CANLI] Ajan arka planda baslatildi!
pause
