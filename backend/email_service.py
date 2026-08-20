"""
Radiology PC Tracker v1 - Email Service (SMTP & HTTP API Mailer)
Sends HTML verification emails via Resend HTTP API (Port 443 - Never Blocked) or SMTP with Dual-Port fallback.
"""

import os
import smtplib
import logging
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("email_service")

def send_via_resend_api(api_key: str, to_email: str, subject: str, html_content: str) -> bool:
    """Sends email via Resend HTTP API over standard HTTPS Port 443 (Bypasses all cloud SMTP port blocks)."""
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": "RadTracker <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code in [200, 201]:
                logger.info(f"Resend HTTP API email successfully sent to {to_email}!")
                return True
            else:
                logger.warning(f"Resend HTTP API returned status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Resend HTTP API exception: {e}")
        return False

def debug_send_email(to_email: str, code: str = "123456") -> dict:
    """Detailed diagnostic email sender for debugging on cloud platforms."""
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "587").strip()
    try:
        smtp_port = int(smtp_port_raw)
    except Exception:
        smtp_port = 587
        
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@radtracker.org").strip()

    logs = []
    logs.append(f"Resend API Key: {'[SET]' if resend_api_key else '[NOT SET]'}")
    logs.append(f"SMTP Server: {smtp_server}")
    logs.append(f"SMTP Port (env): {smtp_port}")
    logs.append(f"SMTP User: {'[SET: ' + smtp_user + ']' if smtp_user else '[NOT SET]'}")
    logs.append(f"SMTP Pass: {'[SET (length ' + str(len(smtp_password)) + ')]' if smtp_password else '[NOT SET]'}")

    subject = "🏥 RadTracker - 6 Haneli E-Posta Doğrulama Kodunuz"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
      <div style="max-width: 500px; margin: 0 auto; background-color: #1e293b; border-radius: 16px; padding: 24px; border: 1px solid #334155;">
        <div style="text-align: center; margin-bottom: 20px;">
          <h1 style="color: #38bdf8; margin: 0; font-size: 24px;">🏥 RadTracker</h1>
          <p style="color: #94a3b8; font-size: 14px; margin-top: 4px;">Radyoloji PC & Asistan Takip Sistemi</p>
        </div>
        <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
        <p style="font-size: 15px; color: #e2e8f0;">Merhaba,</p>
        <p style="font-size: 14px; color: #cbd5e1;">RadTracker hesabınızı doğrulamak için kullanacağınız 6 haneli güvenlik kodunuz:</p>
        <div style="text-align: center; margin: 25px 0;">
          <span style="font-family: monospace; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #38bdf8; background-color: #0f172a; padding: 12px 24px; border-radius: 12px; border: 1px dashed #0284c7; display: inline-block;">
            {code}
          </span>
        </div>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">Bu kod 15 dakika geçerlidir.</p>
      </div>
    </body>
    </html>
    """

    # 1. Try Resend HTTP API if configured (Port 443 - Guaranteed to work on cloud)
    if resend_api_key:
        logs.append("Attempting Resend HTTP API (Port 443)...")
        if send_via_resend_api(resend_api_key, to_email, subject, html_content):
            logs.append(f"SUCCESS: Email sent to {to_email} via Resend HTTP API!")
            return {"success": True, "method": "Resend HTTP API", "logs": logs}
        else:
            logs.append("Resend HTTP API attempt failed. Falling back to SMTP...")

    # 2. Try SMTP fallback
    if not smtp_user or not smtp_password:
        return {
            "success": False,
            "reason": "Neither RESEND_API_KEY nor (SMTP_USER + SMTP_PASSWORD) are set in Environment Variables.",
            "logs": logs
        }

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"RadTracker <{smtp_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    ports_to_try = [smtp_port, 465 if smtp_port != 465 else 587]
    for port in ports_to_try:
        try:
            logs.append(f"Trying SMTP connection to {smtp_server}:{port}...")
            if port == 465:
                with smtplib.SMTP_SSL(smtp_server, port, timeout=10) as server:
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_from, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_from, [to_email], msg.as_string())

            logs.append(f"SUCCESS: Email sent to {to_email} via SMTP port {port}!")
            return {"success": True, "method": f"SMTP port {port}", "logs": logs}
        except Exception as err:
            err_str = f"Port {port} error: {type(err).__name__} - {str(err)}"
            logs.append(err_str)

    return {"success": False, "reason": "All email sending attempts failed (Cloud socket port blocked).", "logs": logs}


def send_verification_email(to_email: str, code: str) -> bool:
    """Wrapper function used by main.py."""
    res = debug_send_email(to_email, code)
    return res.get("success", False)
