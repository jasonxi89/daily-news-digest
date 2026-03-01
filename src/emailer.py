"""Email sender module - converts Markdown to HTML and sends via Gmail SMTP."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    margin: 0;
    padding: 0;
    background-color: #f4f4f7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
    color: #333;
    line-height: 1.6;
  }}
  .wrapper {{
    max-width: 600px;
    margin: 24px auto;
    background: #ffffff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }}
  .header {{
    background: #1a73e8;
    color: #ffffff;
    padding: 20px 28px;
    font-size: 20px;
    font-weight: 600;
  }}
  .content {{
    padding: 24px 28px;
  }}
  .content h1, .content h2, .content h3 {{
    margin-top: 24px;
    margin-bottom: 8px;
    color: #1a1a1a;
  }}
  .content h1 {{ font-size: 22px; }}
  .content h2 {{ font-size: 18px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
  .content h3 {{ font-size: 16px; }}
  .content p {{ margin: 8px 0; }}
  .content a {{ color: #1a73e8; text-decoration: none; }}
  .content a:hover {{ text-decoration: underline; }}
  .content ul, .content ol {{ padding-left: 20px; }}
  .content li {{ margin: 4px 0; }}
  .content blockquote {{
    margin: 12px 0;
    padding: 8px 16px;
    border-left: 4px solid #1a73e8;
    background: #f8f9fa;
    color: #555;
  }}
  .content hr {{
    border: none;
    border-top: 1px solid #eee;
    margin: 20px 0;
  }}
  .footer {{
    padding: 16px 28px;
    text-align: center;
    font-size: 12px;
    color: #999;
    border-top: 1px solid #eee;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">{subject}</div>
  <div class="content">{content}</div>
  <div class="footer">由 Daily News Digest 自动生成</div>
</div>
</body>
</html>
"""


def send_email(markdown_content: str) -> None:
    """Convert Markdown to HTML and send as an email via Gmail SMTP.

    Reads GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL from
    environment variables.

    Raises:
        ValueError: If required environment variables are missing.
        smtplib.SMTPException: If the email fails to send.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL")

    missing = []
    if not gmail_address:
        missing.append("GMAIL_ADDRESS")
    if not gmail_app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if not recipient_email:
        missing.append("RECIPIENT_EMAIL")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"每日新闻摘要 - {today}"

    html_body = markdown.markdown(
        markdown_content,
        extensions=["extra", "nl2br", "sane_lists"],
    )

    html = HTML_TEMPLATE.format(subject=subject, content=html_body)

    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_address
    msg["To"] = recipient_email
    msg["Subject"] = subject

    msg.attach(MIMEText(markdown_content, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, recipient_email, msg.as_string())
        logger.info("Email sent to %s", recipient_email)
    except smtplib.SMTPException:
        logger.exception("Failed to send email to %s", recipient_email)
        raise
