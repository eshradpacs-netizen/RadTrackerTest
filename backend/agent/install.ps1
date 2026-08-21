<#
.SYNOPSIS
    Radiology PC Tracker v1 - 100% Resilient Multi-User Room & Desk Installer
#>

# Enable TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls

Clear-Host
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  RADYOLOJI PACS TAKIP SISTEMI - 1-TIK AJAN KURULUMU (WINDOWS)" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$ServerUrl = "https://esh-radtracker.onrender.com"

# Determine Best Persistent Directory (ProgramData or User AppData)
$TargetDir = "C:\ProgramData\RadTracker"
try {
    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force -ErrorAction Stop | Out-Null
    }
} catch {
    $TargetDir = "$env:APPDATA\RadTracker"
    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    }
}

$TargetPs1 = "$TargetDir\agent.ps1"
$TargetCfg = "$TargetDir\config.json"
$TaskName  = "RadTrackerAgentTask"

$ScriptDir = Split-Path -Parent $PSCommandPath
$SourcePs1 = Join-Path $ScriptDir "agent.ps1"

if (Test-Path $SourcePs1) {
    Copy-Item -Path $SourcePs1 -Destination $TargetPs1 -Force
}

Write-Host "----------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host " BU BILGISAYAR FIZIKSEL OLARAK HANGI ODADA BULUNUYOR?" -ForegroundColor White
Write-Host "----------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host " [1]  Genel PACS Oda 1 (PC 1 - 8)" -ForegroundColor Gray
Write-Host " [2]  Genel PACS Oda 2 (PC 1 - 8)" -ForegroundColor Gray
Write-Host " [3]  Genel PACS Oda 3 (PC 1 - 11)" -ForegroundColor Gray
Write-Host " [4]  Genel PACS Oda 4 (PC 1 - 10)" -ForegroundColor Gray
Write-Host " [5]  Genel PACS Oda 5 (Tek Masa)" -ForegroundColor Gray
Write-Host " [6]  Toplanti Odasi (PC 1 - 3)" -ForegroundColor Gray
Write-Host " [7]  KVC PACS Odasi (PC 1 - 2)" -ForegroundColor Gray
Write-Host " [8]  Kadin Dogum PACS Odasi (PC 1 - 3)" -ForegroundColor Gray
Write-Host " [9]  Kadin Dogum Toplanti Odasi (PC 1)" -ForegroundColor Gray
Write-Host " [10] Onkoloji PACS Odasi (PC 1)" -ForegroundColor Gray
Write-Host " [11] FTR PACS Odasi (PC 1)" -ForegroundColor Gray
Write-Host " [12] Noroloji PACS Odasi (PC 1 - 3)" -ForegroundColor Gray
Write-Host "----------------------------------------------------------------------------" -ForegroundColor DarkCyan

$odaSec = Read-Host "Oda Seciminiz [1-12]"
$masaSek = "1"

if ($odaSec -eq "1") { $masaSek = Read-Host "Genel PACS Oda 1 icindeki Masa Numarasi [1-8]" }
elseif ($odaSec -eq "2") { $masaSek = Read-Host "Genel PACS Oda 2 icindeki Masa Numarasi [1-8]" }
elseif ($odaSec -eq "3") { $masaSek = Read-Host "Genel PACS Oda 3 icindeki Masa Numarasi [1-11]" }
elseif ($odaSec -eq "4") { $masaSek = Read-Host "Genel PACS Oda 4 icindeki Masa Numarasi [1-10]" }
elseif ($odaSec -eq "6") { $masaSek = Read-Host "Toplanti Odasi icindeki Masa Numarasi [1-3]" }
elseif ($odaSec -eq "7") { $masaSek = Read-Host "KVC PACS Odasi icindeki Masa Numarasi [1-2]" }
elseif ($odaSec -eq "8") { $masaSek = Read-Host "Kadin Dogum PACS Odasi icindeki Masa Numarasi [1-3]" }
elseif ($odaSec -eq "12") { $masaSek = Read-Host "Noroloji PACS Odasi icindeki Masa Numarasi [1-3]" }

$uuidMap = @{
    '1_1' = @{ id = 'b94f7242-d702-43fb-8c48-0a757f8e5844'; name = 'Genel PACS Oda 1 PC 1'; room = 'Genel PACS Oda 1' }
    '1_2' = @{ id = 'b9e2ce81-48fc-4da1-aec0-49e9cf917149'; name = 'Genel PACS Oda 1 PC 2'; room = 'Genel PACS Oda 1' }
    '1_3' = @{ id = '54752286-42a1-42f8-956b-166be2534c30'; name = 'Genel PACS Oda 1 PC 3'; room = 'Genel PACS Oda 1' }
    '1_4' = @{ id = '2b24ef48-9b49-4609-85ff-a5d63e03cc07'; name = 'Genel PACS Oda 1 PC 4'; room = 'Genel PACS Oda 1' }
    '1_5' = @{ id = '59a700e4-4579-42c9-8e98-33d7172cb89d'; name = 'Genel PACS Oda 1 PC 5'; room = 'Genel PACS Oda 1' }
    '1_6' = @{ id = '7d395fc7-a5a5-468f-8ff6-177145d7fd9e'; name = 'Genel PACS Oda 1 PC 6'; room = 'Genel PACS Oda 1' }
    '1_7' = @{ id = 'afdafa05-3cf2-4985-8fd1-f3030666ada2'; name = 'Genel PACS Oda 1 PC 7'; room = 'Genel PACS Oda 1' }
    '1_8' = @{ id = 'f37df6f1-8640-481b-aefe-69a050c29244'; name = 'Genel PACS Oda 1 PC 8'; room = 'Genel PACS Oda 1' }

    '2_1' = @{ id = '1307ea69-e2fd-4af6-9a68-3ad45b3a0599'; name = 'Genel PACS Oda 2 PC 1'; room = 'Genel PACS Oda 2' }
    '2_2' = @{ id = '5f40732a-76df-4350-b659-38ee27b1bc3c'; name = 'Genel PACS Oda 2 PC 2'; room = 'Genel PACS Oda 2' }
    '2_3' = @{ id = 'dfb8e384-a294-4c1e-839d-915cda26b7ad'; name = 'Genel PACS Oda 2 PC 3'; room = 'Genel PACS Oda 2' }
    '2_4' = @{ id = '63dacfd7-2785-46d6-84a6-5203201a5eba'; name = 'Genel PACS Oda 2 PC 4'; room = 'Genel PACS Oda 2' }
    '2_5' = @{ id = '893a98c2-03a1-4a07-be92-a12f0db24c4e'; name = 'Genel PACS Oda 2 PC 5'; room = 'Genel PACS Oda 2' }
    '2_6' = @{ id = 'fa3c0301-5067-4b42-b61b-a4fae85e61fa'; name = 'Genel PACS Oda 2 PC 6'; room = 'Genel PACS Oda 2' }
    '2_7' = @{ id = '3fa5738c-2024-491a-a392-3bc980df577d'; name = 'Genel PACS Oda 2 PC 7'; room = 'Genel PACS Oda 2' }
    '2_8' = @{ id = '8d6f236c-d407-4777-a1a4-acb28d1425f8'; name = 'Genel PACS Oda 2 PC 8'; room = 'Genel PACS Oda 2' }

    '3_1' = @{ id = '60677442-626e-4a01-bf3c-7813257a051c'; name = 'Genel PACS Oda 3 PC 1'; room = 'Genel PACS Oda 3' }
    '3_2' = @{ id = '0dc40f21-f20e-46d2-a9dc-4d96225bb95b'; name = 'Genel PACS Oda 3 PC 2'; room = 'Genel PACS Oda 3' }
    '3_3' = @{ id = '1f375a3c-5714-45d5-9815-af77966d233a'; name = 'Genel PACS Oda 3 PC 3'; room = 'Genel PACS Oda 3' }
    '3_4' = @{ id = '8f8a4aa4-02e0-4498-bfc2-a4f84df0d9a0'; name = 'Genel PACS Oda 3 PC 4'; room = 'Genel PACS Oda 3' }
    '3_5' = @{ id = '33e3c64f-9199-4d91-a182-d8be64c9a182'; name = 'Genel PACS Oda 3 PC 5'; room = 'Genel PACS Oda 3' }
    '3_6' = @{ id = '025b8f0c-28c9-40e1-98fb-90e9c53dca46'; name = 'Genel PACS Oda 3 PC 6'; room = 'Genel PACS Oda 3' }
    '3_7' = @{ id = 'e8ec0325-fec6-417b-8383-227074dbc797'; name = 'Genel PACS Oda 3 PC 7'; room = 'Genel PACS Oda 3' }
    '3_8' = @{ id = '62eb1f6f-4fd4-4b6c-8404-eafe846c72ce'; name = 'Genel PACS Oda 3 PC 8'; room = 'Genel PACS Oda 3' }
    '3_9' = @{ id = 'ws-t-09'; name = 'Genel PACS Oda 3 PC 9'; room = 'Genel PACS Oda 3' }
    '3_10' = @{ id = 'ws-t-10'; name = 'Genel PACS Oda 3 PC 10'; room = 'Genel PACS Oda 3' }
    '3_11' = @{ id = 'ws-t-11'; name = 'Genel PACS Oda 3 PC 11'; room = 'Genel PACS Oda 3' }

    '4_1' = @{ id = 'eb5b137e-3cdf-4946-b73c-f36dc927d4ea'; name = 'Genel PACS Oda 4 PC 1'; room = 'Genel PACS Oda 4' }
    '4_2' = @{ id = 'c364e1da-b4c5-4b5b-ad68-3832437ae0ab'; name = 'Genel PACS Oda 4 PC 2'; room = 'Genel PACS Oda 4' }
    '4_3' = @{ id = '58e7e5fb-4fe5-4267-b314-346f6378ee6d'; name = 'Genel PACS Oda 4 PC 3'; room = 'Genel PACS Oda 4' }
    '4_4' = @{ id = '689507ac-5a29-459e-a772-7b9cdee519ab'; name = 'Genel PACS Oda 4 PC 4'; room = 'Genel PACS Oda 4' }
    '4_5' = @{ id = 'beb8c80d-7d8a-46dd-9ce1-2f284084bab7'; name = 'Genel PACS Oda 4 PC 5'; room = 'Genel PACS Oda 4' }
    '4_6' = @{ id = 'fc796cf6-1bc1-4792-822f-5fbb8cabeea8'; name = 'Genel PACS Oda 4 PC 6'; room = 'Genel PACS Oda 4' }
    '4_7' = @{ id = 'a01f0ce3-8377-41bb-8ba7-cf183256a1b7'; name = 'Genel PACS Oda 4 PC 7'; room = 'Genel PACS Oda 4' }
    '4_8' = @{ id = '08573d99-370e-4542-8072-c31f4de8e1b5'; name = 'Genel PACS Oda 4 PC 8'; room = 'Genel PACS Oda 4' }
    '4_9' = @{ id = '523499fe-5bee-4489-90d9-7cbca5388240'; name = 'Genel PACS Oda 4 PC 9'; room = 'Genel PACS Oda 4' }
    '4_10' = @{ id = '3709a075-ffa2-4724-9d78-74684c95882b'; name = 'Genel PACS Oda 4 PC 10'; room = 'Genel PACS Oda 4' }

    '5_1' = @{ id = 'e092e2c2-5348-4724-9a00-5d37a4486176'; name = 'Genel PACS Oda 5 PC 1'; room = 'Genel PACS Oda 5' }
    
    '6_1' = @{ id = '6c5f9782-8754-4d33-a647-b2e4100269ce'; name = 'Toplanti Odasi PC 1'; room = 'Toplanti Odasi' }
    '6_2' = @{ id = 'aa6b1c56-86bd-40be-9f14-417e94791ec9'; name = 'Toplanti Odasi PC 2'; room = 'Toplanti Odasi' }
    '6_3' = @{ id = '62ea8688-2b98-4008-a716-aa454392929e'; name = 'Toplanti Odasi PC 3'; room = 'Toplanti Odasi' }

    '7_1' = @{ id = '3178e41d-97f6-4cdf-b170-503cbf9343bc'; name = 'KVC PACS Oda 1 PC 1'; room = 'KVC PACS Odasi' }
    '7_2' = @{ id = '1259338b-c73d-4629-ae01-115ad7ccecb2'; name = 'KVC PACS Oda 1 PC 2'; room = 'KVC PACS Odasi' }

    '8_1' = @{ id = 'kd-pacs-01-uuid-0001'; name = 'Kadin Dogum PACS Oda 1 PC 1'; room = 'Kadin Dogum PACS Odasi' }
    '8_2' = @{ id = 'kd-pacs-01-uuid-0002'; name = 'Kadin Dogum PACS Oda 1 PC 2'; room = 'Kadin Dogum PACS Odasi' }
    '8_3' = @{ id = 'kd-pacs-01-uuid-0003'; name = 'Kadin Dogum PACS Oda 1 PC 3'; room = 'Kadin Dogum PACS Odasi' }

    '9_1' = @{ id = 'Aquila-α'; name = 'Kadin Dogum Toplanti Odasi PC 1'; room = 'Kadin Dogum Toplanti Odasi' }
    '10_1' = @{ id = 'ws-onkoloji-01'; name = 'Onkoloji PACS Oda 1 PC 1'; room = 'Onkoloji PACS Odasi' }
    '11_1' = @{ id = 'ws-ftr-01'; name = 'FTR PACS Oda 1 PC 1'; room = 'FTR PACS Odasi' }
    '12_1' = @{ id = 'noroloji-pacs-01-uuid-0001'; name = 'Noroloji PACS Oda 1 PC 1'; room = 'Noroloji PACS Odasi' }
    '12_2' = @{ id = 'noroloji-pacs-01-uuid-0002'; name = 'Noroloji PACS Oda 1 PC 2'; room = 'Noroloji PACS Odasi' }
    '12_3' = @{ id = 'noroloji-pacs-01-uuid-0003'; name = 'Noroloji PACS Oda 1 PC 3'; room = 'Noroloji PACS Odasi' }
}

$key = "$($odaSec)_$($masaSek)"
$selected = $uuidMap[$key]

$agentId = if ($selected) { $selected.id } else { '' }
$friendlyName = if ($selected) { $selected.name } else { 'Otomatik' }
$roomName = if ($selected) { $selected.room } else { 'Otomatik' }

$cfgObj = @{
    agentId = $agentId
    friendlyName = $friendlyName
    room = $roomName
    serverUrl = $ServerUrl
}

$cfgJson = $cfgObj | ConvertTo-Json -Compress
Set-Content -Path $TargetCfg -Value $cfgJson -Encoding UTF8

$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
$hostn = $env:COMPUTERNAME
$user = $env:USERNAME

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  BU BILGISAYARA ATANAN KONUM BILGISI:" -ForegroundColor Cyan
Write-Host "  Tanimlanan Konum : $friendlyName ($roomName)" -ForegroundColor Yellow
Write-Host "  Benzersiz UUID   : $agentId" -ForegroundColor Gray
Write-Host "  Bilgisayar Adi   : $hostn" -ForegroundColor White
Write-Host "  Yerel IP         : $ip" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor DarkCyan

try {
    $url = "$ServerUrl/api/heartbeat?id=$agentId&hostname=$hostn&ip=$ip&username=$user&idleTimeSeconds=0&suspicious=0"
    $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 8
    Write-Host "  [OK] Sunucuya Ilk Sinyal Basariyla Gonderildi (200 OK)!" -ForegroundColor Green
    Write-Host "  [OK] Krokideki Masaya Baglandi: $($resp.pc.friendlyName)" -ForegroundColor Green
} catch {
    Write-Host "  [UYARI] Ilk sinyal bekletildi: $_" -ForegroundColor DarkYellow
}
Write-Host "============================================================" -ForegroundColor DarkCyan

# 1. Add to Windows Startup Folder (Works for 100% of standard & admin users)
try {
    $startupVbs = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\RadTrackerAgent.vbs"
    $vbsContent = "Set WshShell = CreateObject(`"WScript.Shell`")`nWshShell.Run `"powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File `"`"$TargetPs1`"`"`", 0, False"
    Set-Content -Path $startupVbs -Value $vbsContent -Encoding ASCII
} catch { }

# 2. Try Scheduled Task (Optional if admin)
try {
    schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
    schtasks /Create /F /TN $TaskName /SC ONLOGON /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File `"$TargetPs1`"" 2>$null | Out-Null
    schtasks /Run /TN $TaskName 2>$null | Out-Null
} catch { }

# 3. Start background runner now
try {
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File `"$TargetPs1`"" -WindowStyle Hidden
} catch { }

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  [TEBRIKLER] KURULUM BASARIYLA TAMAMLANDI!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Bilgisayar artik dogrudan krokideki masaya kilitlendi."
Write-Host "  Ajan arka planda sessizce calismaya basladi."
Write-Host ""
Write-Host "Cikmak icin herhangi bir tusa basin..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
