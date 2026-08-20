@echo off
title RadTracker v1 - Server and Cloudflare Tunnel Starter
echo ==================================================
echo  Radiology PC Tracker v1 - Server & Tunnel Starter
echo ==================================================
echo.

set /p BOT_TOKEN="Lutfen Telegram Bot Tokeninizi Girin (BotFather'dan aldiginiz): "
if "%BOT_TOKEN%"=="" (
    echo [HATA] Bot Token girmediniz. Lutfen BotFather tokeninizi hazirlayin.
    pause
    exit /b
)

set TELEGRAM_BOT_TOKEN=%BOT_TOKEN%

echo.
echo [1/2] FastAPI Sunucusu Port 8000'de Baslatiliyor...
start "RadTracker Backend Server" cmd /k "cd /d %~dp0backend && C:\Users\abdul\miniconda3\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 3 > nul

echo [2/2] Sifresiz Cloudflare Tunel Aciliyor...
echo ==================================================
echo Ekrana cikan "https://xxxx.trycloudflare.com" adresini kopyalayip
echo Telegram @BotFather'a /setmenubutton ile tanimlayin!
echo ==================================================
echo.

npx cloudflared tunnel --url http://127.0.0.1:8000

pause
