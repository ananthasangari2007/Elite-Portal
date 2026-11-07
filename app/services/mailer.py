"""SMTP mail delivery (password reset). Configured via MAIL_* environment variables."""
from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config


def send_reset_email(user, reset_url: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Elite Portal — Password Reset"
    msg["From"] = Config.MAIL_DEFAULT_SENDER or Config.MAIL_USERNAME
    msg["To"] = user.email
    body = f"""
    <html><body>
    <p>Hi {html.escape(user.name or '')},</p>
    <p>Click the link below to reset your Elite Portal password.
       This link expires in 1 hour and can only be used once.</p>
    <p><a href="{html.escape(reset_url, quote=True)}">Reset Password</a></p>
    <p>If you did not request this, ignore this email.</p>
    <p>— Elite Portal Team</p>
    </body></html>
    """
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=15) as smtp:
        if Config.MAIL_USE_TLS:
            smtp.starttls()
        if Config.MAIL_USERNAME:
            smtp.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        smtp.send_message(msg)
