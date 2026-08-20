"""
Radiology PC Tracker v1 - Email Service (SMTP & Verification Mailer)
Sends HTML verification emails via SMTP (Gmail, Outlook, Custom Hospital Mail, Sendgrid).
"""

import os
import smtplib
import logging
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("email_service")

def debug_send_email(to_email: str, code: str = "123456") -> dict:
    """Detailed diagnostic email sender for debugging SMTP issues on cloud platforms."""
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
    logs.append(f"SMTP Server: {smtp_server}")
    logs.append(f"SMTP Port (env): {smtp_port}")
    logs.append(f"SMTP User: {'[SET: ' + smtp_user + ']' if smtp_user else '[NOT SET]'}")
    logs.append(f"SMTP Pass: {'[SET (length ' + str(len(smtp_password)) + ')]' if smtp_password else '[NOT SET]'}")

    if not smtp_user or not smtp_password:
        return {
            "success": False,
            "reason": "SMTP_USER or SMTP_PASSWORD is missing in Environment Variables.",
            "logs": logs
        }

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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"RadTracker <{smtp_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # Try configured port, then alternate port (587 vs 465 vs 25)
    ports_to_try = [smtp_port]
    if 465 not in ports_to_try:
        ports_to_try.append(465)
    if 587 not in ports_to_try:
        ports_to_try.append(587)

    for port in ports_to_try:
        try:
            logs.append(f"Trying connection to {smtp_server}:{port}...")
            if port == 465:
                with smtplib.SMTP_SSL(smtp_server, port, timeout=12) as server:
                    logs.append(f"SSL Connected to {smtp_server}:{port}. Logging in...")
                    server.login(smtp_user, smtp_password)
                    logs.append("Login successful! Sending mail...")
                    server.sendmail(smtp_from, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, port, timeout=12) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    logs.append(f"TLS Started on {smtp_server}:{port}. Logging in...")
                    server.login(smtp_user, smtp_password)
                    logs.append("Login successful! Sending mail...")
                    server.sendmail(smtp_from, [to_email], msg.as_string())

            logs.append(f"SUCCESS: Email sent to {to_email} via port {port}!")
            return {"success": True, "port_used": port, "logs": logs}
        except Exception as err:
            err_str = f"Port {port} error: {type(err).__name__} - {str(err)}"
            logs.append(err_str)
            logger.warning(err_str)

    return {"success": False, "reason": "All SMTP connection attempts failed.", "logs": logs}


def send_verification_email(to_email: str, code: str) -> bool:
    """Wrapper function used by main.py."""
    res = debug_send_email(to_email, code)
    return res.get("success", False)
