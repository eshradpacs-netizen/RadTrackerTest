"""
Radiology PC Tracker v1 - Email Service (SMTP & Verification Mailer)
Sends HTML verification emails via SMTP (Gmail, Outlook, Custom Hospital Mail, Sendgrid).
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("email_service")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@radtracker.org")

def send_verification_email(to_email: str, code: str) -> bool:
    """Sends a 6-digit verification code to the target email address via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP_USER or SMTP_PASSWORD not set. Email notification skipped (demo code logged).")
        return False

    subject = "🏥 RadTracker - 6 Haneli E-Posta Doğrulama Kodunuz"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
      <div style="max-width: 500px; margin: 0 auto; background-color: #1e293b; border-radius: 16px; padding: 24px; border: 1px solid #334155;">
        <div style="text-align: center; margin-bottom: 20px;">
          <h1 style="color: #38bdf8; margin: 0; font-size: 24px;">🏥 RadTracker</h1>
          <p style="color: #94a3b8; font-size: 14px; margin-top: 4px;">Radyoloji PC & Asistan Takip Sistemi</p>
        </div>
        <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
        <p style="font-size: 15px; color: #e2e8f0;">Merhaba,</p>
        <p style="font-size: 14px; color: #cbd5e1;">RadTracker hesabınızı doğrulamak ve canlı takip yetkisi almak için kullanacağınız 6 haneli güvenlik kodunuz aşağıdadır:</p>
        <div style="text-align: center; margin: 25px 0;">
          <span style="font-family: monospace; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #38bdf8; background-color: #0f172a; padding: 12px 24px; border-radius: 12px; border: 1px dashed #0284c7; display: inline-block;">
            {code}
          </span>
        </div>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">Bu kod 15 dakika boyunca geçerlidir. Güvenliğiniz için lütfen başkalarıyla paylaşmayın.</p>
        <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
        <p style="font-size: 11px; color: #64748b; text-align: center;">Bu e-posta otomatik olarak gönderilmiştir. Lütfen yanıtlamayınız.</p>
      </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"RadTracker <{SMTP_FROM}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
            
        logger.info(f"Verification email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        return False
