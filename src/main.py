import logging
import sys

from alerter import send_alert
from emailer import send_email
from news_fetcher import fetch_all_news
from summarizer import summarize_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting daily news digest...")

    # Step 1: Fetch news
    try:
        news = fetch_all_news()
        counts = {k: len(v) for k, v in news.items()}
        total = sum(counts.values())
        detail = ", ".join(f"{v} {k}" for k, v in counts.items())
        logger.info(f"Fetched {total} articles: {detail}")
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        sys.exit(1)

    # Step 2: Summarize with LLM
    try:
        summary = summarize_news(news)
        logger.info("Summary generated")
    except Exception as e:
        logger.error(f"Failed to summarize news: {e}")
        sys.exit(1)

    # Step 3: Send email (send_email already retries internally)
    try:
        send_email(summary)
        logger.info("Email sent successfully!")
    except Exception as e:
        logger.exception("Failed to send email after retries")
        send_alert(
            "Daily News Digest 邮件发送失败",
            f"邮件发送已重试仍失败：{type(e).__name__}: {e}",
        )
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Unhandled error in daily news digest")
        send_alert(
            "Daily News Digest 未处理异常",
            f"{type(e).__name__}: {e}",
        )
        sys.exit(1)
