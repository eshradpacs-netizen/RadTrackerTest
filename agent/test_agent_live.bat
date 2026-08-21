@echo off
title RadTracker Canli Ajan Testi
color 0A

echo.
echo ============================================================================
echo   RADYOLOJI PACS TAKIP SISTEMI - CANLI AJAN TEST ARACI
echo ============================================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -Command "& {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls
    $configPath = 'C:\ProgramData\RadTracker\config.json'
    
    if (-not (Test-Path $configPath)) {
        Write-Host '❌ HATA: Bu bilgisayara henuz ajan kurulmamis!' -ForegroundColor Red
        Write-Host 'Lutfen once install_agent.bat calistiriniz.' -ForegroundColor Yellow
        exit
    }

    $cfg = Get-Content $configPath -Raw | ConvertFrom-Json
    $srv = $cfg.serverUrl
    $agentId = $cfg.agentId
    $friendly = $cfg.friendlyName
    $room = $cfg.room
    $hostn = $env:COMPUTERNAME
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
    $user = $env:USERNAME

    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host '  Mevcut Yapilandirma:' -ForegroundColor Cyan
    Write-Host \"  Tanimli Masa  : $friendly ($room)\" -ForegroundColor Yellow
    Write-Host \"  UUID          : $agentId\" -ForegroundColor Gray
    Write-Host \"  Sunucu URL    : $srv\" -ForegroundColor White
    Write-Host \"  Host / IP     : $hostn / $ip\" -ForegroundColor White
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host 'Canli sinyaller gonderiliyor (Durdurmak icin Ctrl+C)...' -ForegroundColor Green
    Write-Host ''

    while ($true) {
        $timeStr = (Get-Date -Format 'HH:mm:ss')
        try {
            $url = \"$srv/api/heartbeat?id=$agentId&hostname=$hostn&ip=$ip&username=$user&idleTimeSeconds=0&suspicious=0\"
            $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 6
            Write-Host \"[$timeStr] [OK 200] Sinyal Ulasti -> $($resp.pc.friendlyName) (Durum: $($resp.pc.status))\" -ForegroundColor Green
        } catch {
            Write-Host \"[$timeStr] [HATA] Baglanti saglanamadi: $_\" -ForegroundColor Red
        }
        Start-Sleep -Seconds 5
    }
}"

pause
