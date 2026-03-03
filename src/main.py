import logging
import sys

from news_fetcher import fetch_all_news
from summarizer import summarize_news
from emailer import send_email

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
        intl_count = len(news.get("international", []))
        tech_count = len(news.get("tech", []))
        fin_count = len(news.get("finance", []))
        logger.info(f"Fetched {intl_count} international + {tech_count} tech + {fin_count} finance articles")
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        sys.exit(1)

    # Step 2: Summarize with Claude
    try:
        summary = summarize_news(news)
        logger.info("Summary generated")
    except Exception as e:
        logger.error(f"Failed to summarize news: {e}")
        sys.exit(1)

    # Step 3: Send email
    try:
        send_email(summary)
        logger.info("Email sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
