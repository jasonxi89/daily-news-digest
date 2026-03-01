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
        "name": "NHK World",
        "url": "https://www3.nhk.or.jp/nhkworld/en/news/feeds/",
    },
]

TECH_RSS_SOURCES = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
    },
    {
        "name": "Google News Tech",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB",
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
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT)
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
    international_articles: list[dict] = []
    tech_articles: list[dict] = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {}

        # Submit international RSS feeds
        for source in INTERNATIONAL_RSS_SOURCES:
            future = executor.submit(_fetch_rss, source, cutoff)
            futures[future] = ("international", source["name"])

        # Submit tech RSS feeds
        for source in TECH_RSS_SOURCES:
            future = executor.submit(_fetch_rss, source, cutoff)
            futures[future] = ("tech", source["name"])

        # Submit Hacker News
        hn_future = executor.submit(_fetch_hacker_news, cutoff)
        futures[hn_future] = ("tech", "Hacker News")

        # Collect results
        for future in as_completed(futures):
            category, source_name = futures[future]
            try:
                articles = future.result()
                if category == "international":
                    international_articles.extend(articles)
                else:
                    tech_articles.extend(articles)
            except Exception as exc:
                logger.warning("Unexpected error fetching %s: %s", source_name, exc)

    # Sort by published date, newest first
    international_articles.sort(key=lambda a: a["published"], reverse=True)
    tech_articles.sort(key=lambda a: a["published"], reverse=True)

    logger.info(
        "Total: %d international, %d tech articles",
        len(international_articles),
        len(tech_articles),
    )

    return {
        "international": international_articles,
        "tech": tech_articles,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    results = fetch_all_news()
    for category, articles in results.items():
        print(f"\n=== {category.upper()} ({len(articles)} articles) ===")
        for article in articles[:5]:
            print(f"  [{article['source']}] {article['title']}")
            print(f"    {article['link']}")
            print(f"    {article['published'].isoformat()}")
