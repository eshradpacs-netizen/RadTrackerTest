"""
Radiology PC Tracker v1 - Python Client Agent
Cross-platform lightweight agent script to monitor system idle time and send heartbeats.
"""

import time
import socket
import getpass
import urllib.request
import urllib.parse
import json

SERVER_URL = "http://localhost:8000"
INTERVAL = 10

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_agent(server_url=SERVER_URL, interval=INTERVAL):
    hostname = socket.gethostname()
    username = getpass.getuser()
    ip = get_ip()
    
    print(f"=== Radiology PC Tracker v1 Python Agent Started ===")
    print(f"Hostname: {hostname} | IP: {ip} | Server: {server_url}")

    while True:
        try:
            params = urllib.parse.urlencode({
                "hostname": hostname,
                "ip": ip,
                "username": username,
                "idleTimeSeconds": 0,
                "suspicious": 0
            })
            url = f"{server_url}/api/heartbeat?{params}"
            req = urllib.request.Request(url, headers={'User-Agent': 'RadTrackerAgent/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"[{time.strftime('%H:%M:%S')}] Heartbeat sent successfully.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Heartbeat error: {e}")
            
        time.sleep(interval)

if __name__ == "__main__":
    run_agent()
