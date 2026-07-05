"""Email sender module - converts Markdown to HTML and sends via Gmail SMTP."""

import logging
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

logger = logging.getLogger(__name__)

# 每次失败后的等待秒数（指数退避）；总尝试次数 = len(RETRY_DELAYS)
RETRY_DELAYS = (5, 30, 120)

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
        smtplib.SMTPException | OSError: If all send attempts fail
            (retries with exponential backoff, see RETRY_DELAYS).
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

    recipients = [r.strip() for r in recipient_email.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_address
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(markdown_content, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_with_retry(gmail_address, gmail_app_password, recipients, msg)


def _send_with_retry(sender: str, password: str, recipients: list, message) -> None:
    """Send via Gmail SMTP with retries (exponential backoff).

    Attempts len(RETRY_DELAYS) times; waits RETRY_DELAYS[i] seconds after
    the i-th failure. Raises the last error only when all attempts fail.
    """
    total_attempts = len(RETRY_DELAYS)
    last_error = None

    for attempt in range(1, total_attempts + 1):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, password)
                server.sendmail(sender, recipients, message.as_string())
            logger.info("Email sent to %s (attempt %d)", ", ".join(recipients), attempt)
            return
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            logger.warning(
                "Email send attempt %d/%d to %s failed: %s: %s",
                attempt, total_attempts, ", ".join(recipients),
                type(exc).__name__, exc,
            )
            if attempt < total_attempts:
                time.sleep(RETRY_DELAYS[attempt - 1])

    logger.error("All %d email send attempts failed", total_attempts)
    raise last_error
