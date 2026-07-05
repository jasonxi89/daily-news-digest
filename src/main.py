import logging
import sys
from datetime import datetime, timezone

from alerter import send_alert
from emailer import send_email
from news_fetcher import fetch_all_news
from run_state import compute_window_hours, save_last_success
from summarizer import summarize_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _generate_summary(window_hours: float) -> str:
    """Fetch news and summarize. summarize_news 内部已兜底 LLM 异常。"""
    news = fetch_all_news(window_hours=window_hours)
    counts = {k: len(v) for k, v in news.items()}
    total = sum(counts.values())
    detail = ", ".join(f"{v} {k}" for k, v in counts.items())
    logger.info(f"Fetched {total} articles: {detail}")
    return summarize_news(news)


def _generation_failure_notice(error: Exception) -> str:
    """Fallback email body when fetch/summarize crashes unexpectedly."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# {today} 每日新闻摘要\n\n"
        f"⚠️ 本期摘要生成失败（{type(error).__name__}: {error}），"
        "请检查容器日志排查原因。\n"
    )


def main():
    now = datetime.now(timezone.utc)
    window_hours = compute_window_hours(now)
    logger.info("Starting daily news digest, window=%.1f hours", window_hours)

    # 生成环节挂了也尝试发说明邮件，宁发说明邮件不断邮件
    try:
        summary = _generate_summary(window_hours)
        logger.info("Summary generated")
    except Exception as e:
        logger.exception("Digest generation failed, sending fallback notice email")
        summary = _generation_failure_notice(e)

    # 邮件环节（send_email 内部已重试）；连 fallback 邮件都发不出去才告警退出
    try:
        send_email(summary, window_hours=window_hours)
        logger.info("Email sent successfully!")
    except Exception as e:
        logger.exception("Failed to send email after retries")
        send_alert(
            "Daily News Digest 邮件发送失败",
            f"邮件发送已重试仍失败：{type(e).__name__}: {e}",
        )
        sys.exit(1)

    # 邮件成功发出后才记录本次成功时间（写失败只 log 不影响主流程）
    save_last_success(now)


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
