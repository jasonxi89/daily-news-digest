"""News summarizer module using Claude API for Chinese translation and ranking."""

import logging
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)


def summarize_news(news: dict) -> str:
    """Summarize and translate news articles into structured Chinese Markdown.

    Args:
        news: Dict with "international" and "tech" keys, each containing
              a list of article dicts with title, summary, link, source, published.

    Returns:
        Markdown string with ranked, translated news summaries.
    """
    international = news.get("international", [])
    tech = news.get("tech", [])

    if not international and not tech:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"# {today} 每日新闻摘要\n\n今日暂无新闻更新。"

    prompt = _build_prompt(international, tech)

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.APIConnectionError as e:
        logger.error("Failed to connect to Anthropic API: %s", e)
        return _error_fallback("无法连接到 AI 服务，请检查网络连接。")
    except anthropic.AuthenticationError as e:
        logger.error("Anthropic API authentication failed: %s", e)
        return _error_fallback("AI 服务认证失败，请检查 API Key。")
    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error (status %s): %s", e.status_code, e)
        return _error_fallback(f"AI 服务返回错误 (HTTP {e.status_code})。")


def _build_prompt(international: list, tech: list) -> str:
    """Build the summarization prompt with all articles."""
    today = datetime.now().strftime("%Y-%m-%d")

    sections = []

    if international:
        sections.append("## 国际新闻原文\n")
        for i, article in enumerate(international, 1):
            sections.append(_format_article(i, article))

    if tech:
        sections.append("## 科技新闻原文\n")
        for i, article in enumerate(tech, 1):
            sections.append(_format_article(i, article))

    articles_text = "\n".join(sections)

    return f"""你是一位专业的新闻编辑。请将以下英文新闻整理为中文每日摘要。

日期：{today}

{articles_text}

请按以下格式输出 Markdown：

# {today} 每日新闻摘要

## 🌍 国际大事
（按重要性排序，每条包含：中文标题、2-3句中文摘要、原文链接）

格式：
### 1. 中文标题
摘要内容（2-3句话概括要点）
[阅读原文](链接) — 来源

## 💻 科技新闻
（同上格式）

## 📊 今日趋势
（总结今天新闻中的2-3个主要趋势或热点话题，每个1-2句话）

要求：
1. 按重要性和影响力对每个分类内的新闻排序
2. 翻译要自然流畅，不要机翻感
3. 摘要要抓住核心要点，不要遗漏关键信息
4. 如果某个分类没有新闻，省略该分类
5. 直接输出 Markdown，不要加任何前缀说明"""


def _format_article(index: int, article: dict) -> str:
    """Format a single article for the prompt."""
    title = article.get("title", "No title")
    summary = article.get("summary", "No summary available")
    link = article.get("link", "")
    source = article.get("source", "Unknown")
    published = article.get("published", "")

    return (
        f"{index}. **{title}**\n"
        f"   Source: {source} | Published: {published}\n"
        f"   Summary: {summary}\n"
        f"   Link: {link}\n"
    )


def _error_fallback(reason: str) -> str:
    """Generate a fallback message when API call fails."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# {today} 每日新闻摘要\n\n"
        f"⚠️ 摘要生成失败：{reason}\n\n"
        "请稍后重试或检查日志获取详细错误信息。"
    )
