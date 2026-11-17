"""News summarizer module using the Claude API for Chinese translation and ranking."""

import logging
import os
import time
from datetime import datetime

import anthropic
from anthropic.types.beta import BetaMessage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# 默认 high：max 档用真实新闻量实测一期输出了 12.1 万 token，贴着 12.8 万的上限，新闻再多就会被截断
DEFAULT_EFFORT = "high"
ALLOWED_EFFORTS = ("low", "medium", "high", "xhigh", "max")
# 思考也算在 max_tokens 里，所以直接给到模型的输出上限
MAX_OUTPUT_TOKENS = 128000
SERVER_SIDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# 流式请求下这是相邻两段数据之间的读超时，不是整次请求的时长上限；
# 一次摘要要跑好几分钟（max 档实测 18 分钟）
READ_TIMEOUT_SECONDS = 600
CONNECT_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
TRUNCATED_STOP_REASONS = ("max_tokens", "model_context_window_exceeded")
TRUNCATION_NOTICE = "\n\n---\n\n⚠️ 本期摘要输出达到长度上限被截断，以上是已生成的部分。"
MAX_ERROR_DETAIL_CHARS = 200


class SummaryUnavailableError(Exception):
    """Claude 这次给不出可用的摘要；异常消息会原样写进说明邮件。"""


def summarize_news(news: dict) -> str:
    """Summarize and translate news articles into structured Chinese Markdown.

    Args:
        news: Dict with "international" and "tech" keys, each containing
              a list of article dicts with title, summary, link, source, published.

    Returns:
        Markdown string with ranked, translated news summaries.
    """
    all_empty = all(len(news.get(key, [])) == 0 for key in news)
    if all_empty:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"# {today} 每日新闻摘要\n\n今日暂无新闻更新。"

    prompt = _build_prompt(news)

    # 兜底：LLM 层任何失败都产出可发送内容，宁发说明邮件不断邮件
    try:
        return _generate_summary(prompt)
    except SummaryUnavailableError as error:
        logger.error("Summary unavailable: %s", error)
        return _error_fallback(str(error))
    except anthropic.APIConnectionError as error:
        logger.error("Failed to connect to Claude API: %s", error)
        return _error_fallback("无法连接到 AI 服务，请检查网络连接。")
    except anthropic.AuthenticationError as error:
        logger.error("Claude API authentication failed request_id=%s: %s", error.request_id, error)
        return _error_fallback("AI 服务认证失败，请检查 API Key。")
    except anthropic.RateLimitError as error:
        logger.error("Claude API rate limited request_id=%s: %s", error.request_id, error)
        return _error_fallback(f"AI 服务限流 (HTTP 429)：{_describe_api_error(error)}")
    except anthropic.APIStatusError as error:
        logger.error(
            "Claude API error status=%s request_id=%s: %s",
            error.status_code,
            error.request_id,
            error,
        )
        reason = f"AI 服务返回错误 (HTTP {error.status_code})：{_describe_api_error(error)}"
        return _error_fallback(reason)
    except Exception as error:
        logger.exception("Unexpected error during summarization")
        return _error_fallback(f"发生未知错误（{type(error).__name__}），请检查容器日志。")


def _generate_summary(prompt: str) -> str:
    """Send one streaming request to Claude and return the digest body.

    Raises SummaryUnavailableError when the configuration is invalid or Claude
    returns nothing usable; SDK errors propagate to the caller's fallback chain.
    """
    request = _build_request(prompt)
    client = _create_client()
    started_at = time.monotonic()
    # 必须流式：这么大的 max_tokens，非流式请求 SDK 会直接拒发，长连接也容易中途被掐
    with client.beta.messages.stream(**request) as stream:
        final_message = stream.get_final_message()
    summary = "".join(block.text for block in final_message.content if block.type == "text")
    _log_usage(final_message, time.monotonic() - started_at, len(summary))
    return _check_summary(final_message, summary)


def _create_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SummaryUnavailableError("未配置环境变量 ANTHROPIC_API_KEY。")
    return anthropic.Anthropic(
        api_key=api_key,
        timeout=anthropic.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
        max_retries=MAX_RETRIES,
    )


def _build_request(prompt: str) -> dict:
    return {
        "model": os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_MODEL,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": _read_effort()},
        # 官方拒答兜底：Claude 因安全策略拒答时，服务端在同一次请求里换模型重跑
        "betas": [SERVER_SIDE_FALLBACK_BETA],
        "fallbacks": "default",
    }


def _read_effort() -> str:
    effort = os.environ.get("CLAUDE_EFFORT", "").strip() or DEFAULT_EFFORT
    if effort not in ALLOWED_EFFORTS:
        raise SummaryUnavailableError(
            f"环境变量 CLAUDE_EFFORT={effort!r} 无效，可选：{', '.join(ALLOWED_EFFORTS)}。"
        )
    return effort


def _log_usage(final_message: BetaMessage, elapsed_seconds: float, summary_chars: int) -> None:
    """One line per call so each run's cost can be worked out from the log."""
    usage = final_message.usage
    logger.info(
        "summarize done model=%s stop_reason=%s input_tokens=%s output_tokens=%s "
        "elapsed_seconds=%.1f total_chars=%s",
        final_message.model,
        final_message.stop_reason,
        usage.input_tokens,
        usage.output_tokens,
        elapsed_seconds,
        summary_chars,
    )


def _check_summary(final_message: BetaMessage, summary: str) -> str:
    """Return a sendable digest body, or raise with the reason it is not usable."""
    stop_reason = final_message.stop_reason
    if stop_reason == "refusal":
        logger.error("Claude refused the digest request, details=%s", final_message.stop_details)
        raise SummaryUnavailableError("Claude 因安全策略拒绝了本次摘要请求。")
    if not summary.strip():
        raise SummaryUnavailableError(f"模型没有返回正文（stop_reason={stop_reason}）。")
    if stop_reason in TRUNCATED_STOP_REASONS:
        logger.warning("Summary truncated, stop_reason=%s; sending the partial digest", stop_reason)
        return summary + TRUNCATION_NOTICE
    return summary


def _describe_api_error(error: anthropic.APIStatusError) -> str:
    """Pull the API's own message out of the error body, shortened for the notice email."""
    detail = error.body.get("error") if isinstance(error.body, dict) else None
    message = detail.get("message") if isinstance(detail, dict) else None
    return " ".join(str(message or error).split())[:MAX_ERROR_DETAIL_CHARS]


def _build_prompt(news: dict) -> str:
    """Build the summarization prompt with all articles."""
    today = datetime.now().strftime("%Y-%m-%d")

    section_config = [
        ("international", "英文国际新闻原文"),
        ("tech", "英文科技新闻原文"),
        ("ai_dev", "AI 技术博客与开发者社区讨论原文"),
        ("finance", "英文金融财经新闻原文"),
        ("cn_news", "中文国内新闻原文"),
        ("cn_tech", "中文科技新闻原文"),
        ("cn_finance", "中文财经新闻原文"),
        ("cn_health", "中文医疗健康新闻原文"),
    ]

    MAX_ARTICLES_PER_SECTION = 30

    sections = []
    for key, title in section_config:
        articles = news.get(key, [])[:MAX_ARTICLES_PER_SECTION]
        if articles:
            sections.append(f"## {title}\n")
            for i, article in enumerate(articles, 1):
                sections.append(_format_article(i, article))

    # Health hot topics from DailyHotApi (different format: dict of platform -> items)
    health_hot = news.get("health_hot", {})
    if health_hot and isinstance(health_hot, dict):
        sections.append("## 各平台医疗健康热搜原始数据\n")
        for platform, items in health_hot.items():
            sections.append(f"### {platform}\n")
            for i, item in enumerate(items, 1):
                title = item.get("title", "")
                hot = item.get("hot", "")
                link = item.get("link", "")
                sections.append(f"{i}. **{title}** (热度: {hot})\n   Link: {link}\n")

    articles_text = "\n".join(sections)

    return f"""你是一位专业的新闻编辑。请将以下新闻整理为中文每日摘要。
新闻来源包含英文和中文，英文新闻需翻译为中文，中文新闻直接整理。

日期：{today}

{articles_text}

请按以下格式输出 Markdown：

# {today} 每日新闻摘要

## 🌍 国际大事
（综合英文国际新闻源，按重要性排序，精选 10 条最重要的新闻）

格式：
### 1. 中文标题
摘要内容（2-3句话概括要点）
[阅读原文](链接) — 来源

## 💻 科技新闻
（综合英文和中文科技新闻源，按重要性排序，精选 10 条；AI 技术类内容归入下面的 AI 前沿板块，此处不重复）

## 🤖 AI 前沿（开发者视角）
（来自 AI 技术博客与开发者社区讨论，读者是程序员，目的是跟上 AI 技术演进。精选 8-12 条，优先级：
1. 新模型/新能力发布及其对开发者的实际影响
2. 开发工具链动向：agent 框架、编程助手、API、重要开源库
3. 工程实践与经验分享：RAG、微调、推理优化、评测、踩坑复盘
4. 开发者社区热议话题（Hacker News / Reddit 高热度讨论，标注来源）
博客深度文章要提炼核心观点和结论，不要只翻译标题；论文类只选最重要的 1-2 篇并用一句话说明其意义。）

## 💰 金融财经
（综合英文和中文财经新闻源，精选 10 条，涵盖股市、货币、大宗商品、宏观经济等）

## 🇨🇳 国内热点
（来自中文国内新闻源，精选 10 条最重要的国内新闻）

## 🏥 女性健康与医疗热点
（分两部分输出）

### 👩 女性健康
（从中文医疗健康新闻中精选与女性健康相关的内容，如：妇科、备孕、孕期、产后、乳腺、子宫、卵巢、HPV、更年期、内分泌等。
精选 5-10 条，每条标题+2-3句摘要+原文链接。
这是给公众号找话题用的，侧重有话题性、读者关注度高的内容。）

### 🔬 医疗热点
（从中文医疗健康新闻+各平台热搜中精选医疗相关热点，如：重大疾病、新药/疫苗、医保政策、医疗事件等。
精选 5-10 条，每条标题+2-3句摘要+原文链接。
如有平台热搜数据，在对应条目后标注热搜来源和热度。）

## 📊 今日趋势
（总结今天新闻中的 3-5 个主要趋势或热点话题，每个1-2句话）

要求：
1. 按重要性和影响力对每个分类内的新闻排序
2. 每个板块按其说明中的数量精选（未注明的默认 10 条）
3. **如果多条新闻报道的是同一事件或内容高度相似，合并为一条**，综合多个来源的信息，附上最佳的一个原文链接
4. 科技、AI 前沿和财经板块应**融合中英文源**，不要按语言分开列；AI 技术内容只出现在 AI 前沿板块，科技新闻板块不重复
5. 英文新闻翻译要自然流畅，不要机翻感；中文新闻直接整理摘要
6. 摘要要抓住核心要点，不要遗漏关键信息
7. 如果某个分类没有新闻，省略该分类
8. 直接输出 Markdown，不要加任何前缀说明"""


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
