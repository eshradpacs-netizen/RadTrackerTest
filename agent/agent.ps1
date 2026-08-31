<#
.SYNOPSIS
    Radiology PC Tracker v1 - Production Enterprise Silent Agent (Windows)
    100% Crash-Resistant, Zero-Footprint Background Telemetry Agent.
#>

param (
    [string]$ServerUrl = "https://esh-radtracker.onrender.com",
    [int]$Interval = 10,
    [string]$AgentId = ""
)

# 0. Instantly and completely hide console window via Win32 API if any window exists
$Win32HideSource = @'
using System;
using System.Runtime.InteropServices;
public class Win32Window {
    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();
}
'@
try {
    if (-not ([System.Management.Automation.PSTypeName]'Win32Window').Type) {
        Add-Type -TypeDefinition $Win32HideSource -ErrorAction SilentlyContinue
    }
    $consolePtr = [Win32Window]::GetConsoleWindow()
    if ($consolePtr -ne [IntPtr]::Zero) {
        [Win32Window]::ShowWindowAsync($consolePtr, 0) | Out-Null
    }
} catch { }

# Enforce TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls

# 1. Multi-Path Config Resolver (PSScriptRoot, ProgramData, AppData)
$configPaths = @(
    "$PSScriptRoot\config.json",
    "C:\ProgramData\RadTracker\config.json",
    "$env:APPDATA\RadTracker\config.json",
    "$env:LOCALAPPDATA\RadTracker\config.json"
)

foreach ($cp in $configPaths) {
    if (Test-Path $cp) {
        try {
            $cfg = Get-Content $cp -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($cfg.agentId) { $AgentId = $cfg.agentId.Trim() }
            if ($cfg.serverUrl) { $ServerUrl = $cfg.serverUrl.Trim().TrimEnd('/') }
            if ($AgentId) { break }
        } catch { }
    }
}

# 2. Win32 GetLastInputInfo API for accurate idle time monitoring
$Win32InputSource = @'
using System;
using System.Runtime.InteropServices;
public class Win32Input {
    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }
}
'@
try {
    if (-not ([System.Management.Automation.PSTypeName]'Win32Input').Type) {
        Add-Type -TypeDefinition $Win32InputSource -ErrorAction SilentlyContinue
    }
} catch { }

$script:LastIdleTime = 0
$script:ConsecutiveFailures = 0

function Get-SystemIdleSeconds {
    try {
        $lastInput = New-Object Win32Input+LASTINPUTINFO
        $lastInput.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($lastInput)
        if ([Win32Input]::GetLastInputInfo([ref]$lastInput)) {
            $tickCount = [Environment]::TickCount
            $uintTickCount = if ($tickCount -lt 0) { [uint32]($tickCount + 4294967296) } else { [uint32]$tickCount }
            $idleMs = $uintTickCount - $lastInput.dwTime
            $script:LastIdleTime = [Math]::Max(0, [Math]::Round($idleMs / 1000))
            return $script:LastIdleTime
        }
    } catch { }
    $script:LastIdleTime = $script:LastIdleTime + $Interval
    return $script:LastIdleTime
}

function Get-PrimaryIPAddress {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { 
            $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox|VMware|Pseudo|Teredo|isatap' -and 
            $_.IPAddress -notlike '169.254.*' -and 
            $_.IPAddress -notlike '127.*'
        } | Select-Object -First 1).IPAddress
        
        if (-not $ip) {
            $ip = ([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object { 
                $_.AddressFamily -eq 'InterNetwork' -and $_.IPAddressToString -notlike '127.*' 
            } | Select-Object -First 1).IPAddressToString
        }
    } catch {
        $ip = "127.0.0.1"
    }
    if (-not $ip) { $ip = "127.0.0.1" }
    return $ip
}

function Check-SuspiciousActivity {
    $suspiciousList = @("autoclicker", "jiggler", "movemouse", "caffeine", "autohotkey", "tinytask", "pyautogui", "mousemove", "automouse")
    try {
        $procNames = (Get-Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName)
        foreach ($p in $procNames) {
            $lp = $p.ToLower()
            foreach ($s in $suspiciousList) {
                if ($lp -like "*$s*") { return 1 }
            }
        }
    } catch { }
    return 0
}

# Main Execution Loop (100% Unbreakable Infinite Loop)
$hostname = $env:COMPUTERNAME
$username = $env:USERNAME

while ($true) {
    try {
        $idleSec = Get-SystemIdleSeconds
        $ip = Get-PrimaryIPAddress
        $isSuspicious = Check-SuspiciousActivity

        $encAgentId = [uri]::EscapeDataString($AgentId)
        $encHostname = [uri]::EscapeDataString($hostname)
        $encIp = [uri]::EscapeDataString($ip)
        $encUsername = [uri]::EscapeDataString($username)
        
        $endpoint = "$ServerUrl/api/heartbeat?id=$encAgentId&hostname=$encHostname&ip=$encIp&username=$encUsername&idleTimeSeconds=$idleSec&suspicious=$isSuspicious"
        
        $response = Invoke-RestMethod -Uri $endpoint -Method Get -TimeoutSec 8 -Headers @{ "User-Agent" = "RadTrackerAgent-v1/Enterprise" }
        $script:ConsecutiveFailures = 0
    } catch {
        $script:ConsecutiveFailures++
    }

    $sleepDuration = if ($script:ConsecutiveFailures -gt 5) { [Math]::Min(30, $Interval * 2) } else { $Interval }
    Start-Sleep -Seconds $sleepDuration
}
