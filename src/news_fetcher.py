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

CN_HEALTH_RSS_SOURCES = [
    {
        "name": "Google女性健康",
        "url": "https://news.google.com/rss/search?q=%E5%A5%B3%E6%80%A7%E5%81%A5%E5%BA%B7+OR+%E5%A6%87%E7%A7%91+OR+%E5%A4%87%E5%AD%95+OR+%E4%B9%B3%E8%85%BA+OR+HPV+OR+%E5%AD%90%E5%AE%AB+OR+%E5%8D%B5%E5%B7%A2+OR+%E6%9B%B4%E5%B9%B4%E6%9C%9F+OR+%E7%97%9B%E7%BB%8F&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "name": "Google医疗热点",
        "url": "https://news.google.com/rss/search?q=%E5%8C%BB%E7%96%97+OR+%E7%99%8C%E7%97%87+OR+%E7%96%AB%E8%8B%97+OR+%E5%8C%BB%E4%BF%9D+OR+%E4%BD%93%E6%A3%80+OR+%E7%96%BE%E7%97%85+OR+%E6%89%8B%E6%9C%AF+OR+%E8%8D%AF%E5%93%81&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
]

HACKER_NEWS_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HACKER_NEWS_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

FETCH_TIMEOUT = 10  # seconds per source
HN_TOP_N = 30  # number of HN stories to fetch

# --- DailyHotApi 医疗健康热搜 ---

import os
import re

DAILYHOT_API_URL = os.getenv("DAILYHOT_API_URL", "http://localhost:6688")

HEALTH_PLATFORMS = {
    "weibo": "微博",
    "douyin": "抖音",
    "bilibili": "B站",
    "baidu": "百度",
    "zhihu": "知乎",
    "thepaper": "澎湃",
}

# 女性健康 + 医疗热点关键词
HEALTH_KEYWORDS = [
    # 女性健康
    "妇科", "月经", "痛经", "姨妈", "备孕", "怀孕", "孕期", "孕妇", "产后", "产检",
    "哺乳", "母乳", "乳腺", "乳房", "子宫", "卵巢", "宫颈", "HPV", "避孕",
    "更年期", "内分泌", "多囊", "试管婴儿", "不孕", "宫外孕", "顺产", "剖腹产",
    "叶酸", "雌激素", "黄体酮", "白带", "盆底肌", "产后抑郁", "围绝经",
    # 医疗热点
    "医院", "医生", "护士", "手术", "癌症", "肿瘤", "化疗", "放疗",
    "疫苗", "药品", "药物", "确诊", "体检", "核酸", "疾病", "治疗",
    "心脏病", "高血压", "糖尿病", "抑郁症", "焦虑症", "失眠",
    "甲状腺", "肺炎", "流感", "新冠", "艾滋", "乙肝",
    "整形", "医美", "近视", "眼科", "牙科", "口腔",
    "过敏", "免疫", "中医", "针灸", "骨科", "骨折",
    "急救", "猝死", "心梗", "脑梗", "中风",
    "医保", "医疗", "卫健委", "药监局", "集采", "带量采购",
    "罕见病", "基因", "干细胞", "器官移植",
]

# 编译为正则，一次匹配所有关键词
_HEALTH_PATTERN = re.compile("|".join(re.escape(kw) for kw in HEALTH_KEYWORDS))


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


def _fetch_health_hot() -> dict[str, list[dict]]:
    """从 DailyHotApi 拉取各平台热榜，过滤出医疗健康相关话题。"""
    result: dict[str, list[dict]] = {}

    for endpoint, platform_name in HEALTH_PLATFORMS.items():
        items = []
        try:
            url = f"{DAILYHOT_API_URL}/{endpoint}"
            resp = requests.get(url, timeout=FETCH_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            for entry in data.get("data", []):
                title = entry.get("title", "")
                if not title or not _HEALTH_PATTERN.search(title):
                    continue
                hot = entry.get("hot", 0)
                link = entry.get("url", "") or entry.get("mobileUrl", "")
                items.append({
                    "title": title,
                    "hot": hot,
                    "link": link,
                    "platform": platform_name,
                })
            logger.info("Health hot: %d items from %s", len(items), platform_name)
        except Exception as exc:
            logger.warning("Failed to fetch health hot from %s: %s", platform_name, exc)

        if items:
            result[platform_name] = items

    return result


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
        "cn_health": [],
    }

    source_map = [
        (INTERNATIONAL_RSS_SOURCES, "international"),
        (TECH_RSS_SOURCES, "tech"),
        (FINANCE_RSS_SOURCES, "finance"),
        (CN_NEWS_RSS_SOURCES, "cn_news"),
        (CN_TECH_RSS_SOURCES, "cn_tech"),
        (CN_FINANCE_RSS_SOURCES, "cn_finance"),
        (CN_HEALTH_RSS_SOURCES, "cn_health"),
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

    # Fetch health hot topics from DailyHotApi
    health_hot = _fetch_health_hot()
    if health_hot:
        categories["health_hot"] = health_hot

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
