@echo off
chcp 65001 >nul
title RadTracker PACS - Ajan Kurulumu
color 0B

echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - 1-TIK AJAN KURULUMU
echo ============================================================================
echo.

set TARGET_DIR=C:\ProgramData\RadTracker
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1
if not exist "%TARGET_DIR%" set TARGET_DIR=%APPDATA%\RadTracker
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1

copy /Y "%~dp0agent.ps1" "%TARGET_DIR%\agent.ps1" >nul 2>&1
copy /Y "%~dp0install.ps1" "%TARGET_DIR%\install.ps1" >nul 2>&1

powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%TARGET_DIR%\install.ps1"

echo.
