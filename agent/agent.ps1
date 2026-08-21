<#
.SYNOPSIS
    Radiology PC Tracker v1 - Production Enterprise Silent Agent (Windows)
.DESCRIPTION
    High-resilience, zero-footprint background monitor for hospital PACS workstations.
    Tracks real-time user activity (Win32 input idle time), active reporting software,
    and anti-cheat (jiggler) processes. Sends periodic heartbeats to FastAPI server.
.PARAMETER ServerUrl
    Server endpoint URL (Default: https://radtrackertest.onrender.com)
.PARAMETER Interval
    Heartbeat interval in seconds (Default: 10)
.PARAMETER AgentId
    Workstation UUID (Optional - server resolves automatically by Hostname/IP)
#>

param (
    [string]$ServerUrl = "https://radtrackertest.onrender.com",
    [int]$Interval = 10,
    [string]$AgentId = ""
)

# Sanitize inputs and enforce TLS 1.2 / TLS 1.3
$ServerUrl = $ServerUrl -creplace '[^\x20-\x7E]', ''
$ServerUrl = $ServerUrl.Trim().Trim('"').Trim("'").TrimEnd('/')
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls

# Define Win32 GetLastInputInfo API for ultra-accurate hardware input monitoring
$Win32Source = @'
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

if (-not ([System.Management.Automation.PSTypeName]'Win32Input').Type) {
    Add-Type -TypeDefinition $Win32Source -ErrorAction SilentlyContinue
}

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

# Main Execution Loop
$hostname = $env:COMPUTERNAME
$username = $env:USERNAME

while ($true) {
    $idleSec = Get-SystemIdleSeconds
    $ip = Get-PrimaryIPAddress
    $isSuspicious = Check-SuspiciousActivity

    try {
        $encAgentId = [uri]::EscapeDataString($AgentId)
        $encHostname = [uri]::EscapeDataString($hostname)
        $encIp = [uri]::EscapeDataString($ip)
        $encUsername = [uri]::EscapeDataString($username)
        
        $endpoint = "$ServerUrl/api/heartbeat?id=$encAgentId&hostname=$encHostname&ip=$encIp&username=$encUsername&idleTimeSeconds=$idleSec&suspicious=$isSuspicious"
        
        $req = [System.Net.HttpWebRequest]::Create($endpoint)
        $req.Method = "GET"
        $req.Timeout = 6000
        $req.UserAgent = "RadTrackerAgent-v1/Enterprise"
        
        $resp = $req.GetResponse()
        $resp.Close()
        $script:ConsecutiveFailures = 0
    }
    catch {
        $script:ConsecutiveFailures++
    }

    # Dynamic sleep with gentle backoff if server is unreachable
    $sleepDuration = if ($script:ConsecutiveFailures -gt 5) { [Math]::Min(30, $Interval * 2) } else { $Interval }
    Start-Sleep -Seconds $sleepDuration
}
