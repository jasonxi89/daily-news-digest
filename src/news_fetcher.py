"""
News fetcher module - fetches articles from RSS feeds and APIs,
filters to last 24 hours, returns categorized results.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

# --- Source definitions ---

INTERNATIONAL_RSS_SOURCES = [
    {
        "name": "BBC World News",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "name": "CNN World",
        "url": "http://rss.cnn.com/rss/edition_world.rss",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
    },
    {
        "name": "Google News International",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB",
    },
    {
        "name": "The Guardian World",
        "url": "https://www.theguardian.com/world/rss",
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
    },
    {
        "name": "Google News World",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    },
]

TECH_RSS_SOURCES = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
    },
    {
        "name": "Google News Tech",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB",
    },
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
    },
    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
    },
    {
        "name": "Engadget",
        "url": "https://www.engadget.com/rss.xml",
    },
]

FINANCE_RSS_SOURCES = [
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/rss/home",
    },
    {
        "name": "Bloomberg via Google News",
        "url": "https://news.google.com/rss/search?q=site:bloomberg.com+finance+OR+markets+OR+economy&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News Finance",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
    },
    {
        "name": "Investing.com News",
        "url": "https://www.investing.com/rss/news.rss",
    },
    {
        "name": "Google News Economy",
        "url": "https://news.google.com/rss/search?q=economy+OR+stock+market+OR+federal+reserve+OR+inflation&hl=en-US&gl=US&ceid=US:en",
    },
]

CN_NEWS_RSS_SOURCES = [
    {
        "name": "澎湃新闻",
        "url": "https://feedx.net/rss/thepaper.xml",
    },
    {
        "name": "界面新闻",
        "url": "https://feedx.net/rss/jiemian.xml",
    },
    {
        "name": "南方周末",
        "url": "https://feedx.net/rss/infzm.xml",
    },
    {
        "name": "中国日报",
        "url": "https://www.chinadaily.com.cn/rss/china_rss.xml",
    },
]

CN_TECH_RSS_SOURCES = [
    {
        "name": "36氪",
        "url": "https://36kr.com/feed",
    },
    {
        "name": "虎嗅",
        "url": "https://feedx.net/rss/huxiu.xml",
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
    },
    {
        "name": "爱范儿",
        "url": "https://www.ifanr.com/feed",
    },
    {
        "name": "IT之家",
        "url": "https://www.ithome.com/rss/",
        "headers": True,
    },
]

CN_FINANCE_RSS_SOURCES = [
    {
        "name": "Google中文财经",
        "url": "https://news.google.com/rss/search?q=%E8%82%A1%E5%B8%82+OR+A%E8%82%A1+OR+%E7%BB%8F%E6%B5%8E+OR+%E5%A4%AE%E8%A1%8C&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "name": "Google A股",
        "url": "https://news.google.com/rss/search?q=A%E8%82%A1+OR+%E6%B2%AA%E6%8C%87+OR+%E6%B7%B1%E6%8C%87+OR+%E5%88%9B%E4%B8%9A%E6%9D%BF&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "name": "经济观察报",
        "url": "http://www.eeo.com.cn/rss.xml",
    },
]

HACKER_NEWS_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HACKER_NEWS_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

FETCH_TIMEOUT = 10  # seconds per source
HN_TOP_N = 30  # number of HN stories to fetch


def _parse_published_date(entry: Any) -> datetime | None:
    """Extract a timezone-aware UTC datetime from a feedparser entry."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    try:
        dt = datetime(*parsed[:6], tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _fetch_rss(source: dict, cutoff: datetime) -> list[dict]:
    """Fetch and parse a single RSS feed, returning articles newer than cutoff."""
    name = source["name"]
    url = source["url"]
    articles = []
    headers = None
    if source.get("headers"):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=headers)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries:
            published = _parse_published_date(entry)
            if published is None:
                continue
            if published < cutoff:
                continue

            summary = entry.get("summary", "") or ""
            # Strip HTML tags from summary (basic cleanup)
            if "<" in summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
            # Truncate long summaries
            if len(summary) > 500:
                summary = summary[:497] + "..."

            articles.append({
                "title": entry.get("title", "").strip(),
                "summary": summary,
                "link": entry.get("link", ""),
                "source": name,
                "published": published,
            })

        logger.info("Fetched %d articles from %s", len(articles), name)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", name, exc)

    return articles


def _fetch_hacker_news(cutoff: datetime) -> list[dict]:
    """Fetch top Hacker News stories from the past 24 hours."""
    articles = []
    try:
        resp = requests.get(HACKER_NEWS_TOP_STORIES_URL, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        story_ids = resp.json()[:HN_TOP_N]

        def fetch_item(story_id: int) -> dict | None:
            try:
                item_resp = requests.get(
                    HACKER_NEWS_ITEM_URL.format(id=story_id),
                    timeout=FETCH_TIMEOUT,
                )
                item_resp.raise_for_status()
                return item_resp.json()
            except Exception as exc:
                logger.warning("Failed to fetch HN item %d: %s", story_id, exc)
                return None

        # Fetch individual stories in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_item, sid): sid for sid in story_ids}
            for future in as_completed(futures):
                item = future.result()
                if item is None:
                    continue

                timestamp = item.get("time")
                if timestamp is None:
                    continue
                published = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                if published < cutoff:
                    continue

                title = item.get("title", "").strip()
                url = item.get("url", "")
                # HN items may not have a URL (e.g. Ask HN), use HN link instead
                if not url:
                    url = f"https://news.ycombinator.com/item?id={item.get('id', '')}"

                articles.append({
                    "title": title,
                    "summary": "",  # HN API doesn't provide summaries
                    "link": url,
                    "source": "Hacker News",
                    "published": published,
                })

        logger.info("Fetched %d articles from Hacker News", len(articles))
    except Exception as exc:
        logger.warning("Failed to fetch Hacker News: %s", exc)

    return articles


def fetch_all_news() -> dict[str, list[dict]]:
    """
    Fetch news from all sources in parallel, filter to last 24 hours.

    Returns:
        dict with "international" and "tech" lists of article dicts.
        Each article: {"title", "summary", "link", "source", "published"}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    categories: dict[str, list[dict]] = {
        "international": [],
        "tech": [],
        "finance": [],
        "cn_news": [],
        "cn_tech": [],
        "cn_finance": [],
    }

    source_map = [
        (INTERNATIONAL_RSS_SOURCES, "international"),
        (TECH_RSS_SOURCES, "tech"),
        (FINANCE_RSS_SOURCES, "finance"),
        (CN_NEWS_RSS_SOURCES, "cn_news"),
        (CN_TECH_RSS_SOURCES, "cn_tech"),
        (CN_FINANCE_RSS_SOURCES, "cn_finance"),
    ]

    with ThreadPoolExecutor(max_workers=24) as executor:
        futures = {}

        for sources, category in source_map:
            for source in sources:
                future = executor.submit(_fetch_rss, source, cutoff)
                futures[future] = (category, source["name"])

        # Submit Hacker News
        hn_future = executor.submit(_fetch_hacker_news, cutoff)
        futures[hn_future] = ("tech", "Hacker News")

        for future in as_completed(futures):
            category, source_name = futures[future]
            try:
                articles = future.result()
                categories[category].extend(articles)
            except Exception as exc:
                logger.warning("Unexpected error fetching %s: %s", source_name, exc)

    for cat_articles in categories.values():
        cat_articles.sort(key=lambda a: a["published"], reverse=True)

    counts = ", ".join(f"{len(v)} {k}" for k, v in categories.items())
    logger.info("Total: %s", counts)

    return categories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    results = fetch_all_news()
    for category, articles in results.items():
        print(f"\n=== {category.upper()} ({len(articles)} articles) ===")
        for article in articles[:5]:
            print(f"  [{article['source']}] {article['title']}")
            print(f"    {article['link']}")
            print(f"    {article['published'].isoformat()}")
