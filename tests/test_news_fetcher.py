"""Unit tests for news_fetcher: AI title routing and date parsing."""

from datetime import datetime, timezone

from src.news_fetcher import AI_DEV_RSS_SOURCES, is_ai_related, _parse_published_date


# --- is_ai_related: HN 标题路由到 ai_dev 板块 ---

def test_should_match_model_and_vendor_names():
    assert is_ai_related("OpenAI releases GPT-5.6")
    assert is_ai_related("Claude Code is now generally available")
    assert is_ai_related("Running Llama locally with Ollama")
    assert is_ai_related("DeepSeek v4 benchmarks")

def test_should_match_ai_engineering_terms():
    assert is_ai_related("Show HN: A fast RAG pipeline in Rust")
    assert is_ai_related("Fine-tuning embedding models on a budget")
    assert is_ai_related("Why we moved our agents off LangChain")
    assert is_ai_related("Machine learning for the working programmer")

def test_should_match_case_insensitively():
    assert is_ai_related("MY LLM IS SMARTER THAN YOURS")
    assert is_ai_related("chatgpt wrote this title")

def test_should_not_match_general_tech_titles():
    assert not is_ai_related("PostgreSQL 18 released")
    assert not is_ai_related("Show HN: A terminal file manager in Zig")
    assert not is_ai_related("The Linux kernel scheduler explained")

def test_should_not_match_keyword_inside_word():
    # "ai" 作为子串不应命中（\b 词边界）
    assert not is_ai_related("Repairing my air conditioner")
    assert not is_ai_related("Traveling in Thailand")

def test_should_not_match_empty_title():
    assert not is_ai_related("")


# --- AI_DEV_RSS_SOURCES 配置完整性 ---

def test_should_have_name_and_url_for_every_ai_source():
    for source in AI_DEV_RSS_SOURCES:
        assert source.get("name")
        assert source.get("url", "").startswith("http")


# --- _parse_published_date ---

def test_should_parse_valid_time_struct():
    entry = {"published_parsed": (2026, 7, 30, 12, 0, 0, 0, 0, 0)}
    assert _parse_published_date(entry) == datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)

def test_should_fall_back_to_updated_when_no_published():
    entry = {"published_parsed": None, "updated_parsed": (2026, 7, 30, 8, 30, 0, 0, 0, 0)}
    assert _parse_published_date(entry) == datetime(2026, 7, 30, 8, 30, 0, tzinfo=timezone.utc)

def test_should_return_none_when_no_date_fields():
    assert _parse_published_date({}) is None
