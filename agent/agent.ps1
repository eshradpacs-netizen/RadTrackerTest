<#
.SYNOPSIS
    Radiology PC Tracker v1 - Silent Client Agent (Windows PowerShell)
.DESCRIPTION
    Monitors Windows system idle time and suspicious processes, sending periodic 10s heartbeats to FastAPI / Telegram-DB backend.
.PARAMETER ServerUrl
    The URL of the server (e.g., https://radtracker.koyeb.app or http://10.86.144.210:8000).
.PARAMETER AgentId
    The UUID of the workstation (Optional - auto-resolved if omitted).
#>

param (
    [string]$ServerUrl = "https://radtrackertest.onrender.com",
    [int]$Interval = 10,
    [string]$AgentId = ""
)

$ServerUrl = $ServerUrl -creplace '[^\x20-\x7E]', ''
$ServerUrl = $ServerUrl.Trim().Trim('"').Trim("'").Trim()
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Win32Source = @'
using System;
using System.Runtime.InteropServices;

public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }
}
'@

if (-not ([System.Management.Automation.PSTypeName]'Win32').Type) {
    Add-Type -TypeDefinition $Win32Source
}

$script:LastIdleTime = 0

function Get-SystemIdleTime {
    $lastInput = New-Object Win32+LASTINPUTINFO
    $lastInput.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($lastInput)
    
    if ([Win32]::GetLastInputInfo([ref]$lastInput)) {
        $tickCount = [Environment]::TickCount
        $uintTickCount = if ($tickCount -lt 0) { [uint32]($tickCount + 4294967296) } else { [uint32]$tickCount }
        $idleMs = $uintTickCount - $lastInput.dwTime
        $script:LastIdleTime = [Math]::Round($idleMs / 1000)
        return $script:LastIdleTime
    }
    $script:LastIdleTime = $script:LastIdleTime + $Interval
    return $script:LastIdleTime
}

function Get-LocalIPAddress {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
            $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox|VMware|Pseudo' -and $_.IPAddress -notlike '169.254.*'
        } | Select-Object -First 1).IPAddress
        
        if (-not $ip) {
            $ip = ([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1).IPAddressToString
        }
    }
    catch {
        $ip = "127.0.0.1"
    }
    return $ip
}

$hostname = $env:COMPUTERNAME

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Radiology PC Tracker v1 Agent Started" -ForegroundColor Green
Write-Host " Hostname:   $hostname"
Write-Host " Server URL: $ServerUrl"
Write-Host " Interval:   $Interval seconds"
Write-Host "=================================================="

while ($true) {
    $idleSec = Get-SystemIdleTime
    $ip = Get-LocalIPAddress
    $username = $env:USERNAME

    $suspiciousKeywords = @("autoclicker", "jiggler", "movemouse", "caffeine", "autohotkey", "tinytask", "pyautogui")
    $isSuspicious = 0
    $procs = Get-Process -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        $name = $p.ProcessName.ToLower()
        foreach ($kw in $suspiciousKeywords) {
            if ($name -like "*$kw*") { $isSuspicious = 1; break }
        }
        if ($isSuspicious -eq 1) { break }
    }

    try {
        $encAgentId = [uri]::EscapeDataString($AgentId)
        $encHostname = [uri]::EscapeDataString($hostname)
        $encIp = [uri]::EscapeDataString($ip)
        $encUsername = [uri]::EscapeDataString($username)
        
        $endpoint = "$($ServerUrl)/api/heartbeat?id=$($encAgentId)&hostname=$($encHostname)&ip=$($encIp)&username=$($encUsername)&idleTimeSeconds=$($idleSec)&suspicious=$($isSuspicious)"
        $response = Invoke-RestMethod -Uri $endpoint -Method Get -TimeoutSec 8
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Heartbeat Sent OK. Idle: $idleSec s. Suspicious: $isSuspicious" -ForegroundColor Green
    }
    catch {
        Write-Warning "[$(Get-Date -Format 'HH:mm:ss')] Heartbeat failed: $_"
    }

    Start-Sleep -Seconds $Interval
}
