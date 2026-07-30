# Daily News Digest — AI-Powered News Summarization Service

Automatically fetches global news twice a day, summarizes and translates to Chinese via OpenRouter (default model: deepseek-v4-pro), and delivers a formatted digest via email.

> History: this project originally used the Anthropic API (Claude). It has been fully migrated to OpenRouter + the openai SDK; all `ANTHROPIC_*` configuration is obsolete.

## Features

- **40+ news sources**: BBC, CNN, Al Jazeera, Google News, Hacker News, TechCrunch, Ars Technica, MarketWatch, and more
- **AI dev radar**: dedicated "AI 前沿" section for developers, sourced from AI engineering blogs and communities (Simon Willison, Hugging Face, OpenAI, DeepMind, Latent Space, Interconnects, r/LocalLLaMA, Lobsters, 量子位); AI-related Hacker News threads are auto-routed here by title keywords
- **AI summarization**: LLM ranks by importance, translates to Chinese, identifies trends, deduplicates across sources
- **Email delivery**: Gmail SMTP with retry + exponential backoff, supports multiple recipients
- **Dual-window scheduling**: runs at 07:00 and 23:00 Beijing time; each run only covers news since the last successful send (no overlap, half the tokens)
- **Failure alerting**: optional webhook alert when even the fallback email cannot be sent

## Quick Start

### Environment Variables

Copy `config.env.example` to `config.env` and fill in:

```env
# OpenRouter (required)
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=deepseek/deepseek-v4-pro

# Gmail SMTP (required; use App Password, not account password)
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
RECIPIENT_EMAIL=recipient1@example.com,recipient2@example.com

# Timezone
TZ=Asia/Shanghai

# DailyHotApi for health hot topics (optional; LAN service on the NAS)
DAILYHOT_API_URL=http://192.168.1.64:6688

# Failure alert webhook (optional, empty = disabled; Server酱-compatible)
ALERT_WEBHOOK_URL=

# Dual-window state (optional; defaults shown)
STATE_FILE=/app/data/last_success.json
DEFAULT_WINDOW_HOURS=24
```

> Generate Gmail App Password at [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification enabled)

### Local Testing

```bash
# Run directly
pip install -r requirements.txt
python src/main.py

# Tests
pip install -r requirements-dev.txt
pytest

# Docker
docker compose up --build
```

### Deployment

Docker image auto-built and pushed to Docker Hub via GitHub Actions (pytest must pass before build):

```
jasonxi89/daily-news-digest:latest
jasonxi89/daily-news-digest:<commit-sha>
```

Cron schedule (container timezone is Asia/Shanghai):

- `0 7 * * *` — 北京时间 07:00（= 23:00 UTC 前一天）
- `0 23 * * *` — 北京时间 23:00（= 15:00 UTC）

### Dual-Window Mechanism

Each successful email send records its time to `STATE_FILE` (persisted via the `/app/data` volume). The next run fetches only news published since that timestamp:

- Normal operation: windows alternate between ~8h (07:00 → 23:00... 23:00 run) and ~16h (23:00 → next 07:00 run) — no duplicated content, roughly half the LLM tokens vs. two full 24h summaries.
- Window is clamped to **min 1h, max 48h**. If a run fails, the next run's window automatically widens to catch up on missed news.
- No state file (first run / volume wiped): falls back to `DEFAULT_WINDOW_HOURS` (default 24).
- The covered window is noted in the email subject and body (e.g. "过去 8 小时").

## Tech Stack

- Python 3.11 + feedparser + requests
- openai SDK → OpenRouter gateway (default `deepseek/deepseek-v4-pro`)
- Gmail SMTP
- Docker Alpine + crond
- GitHub Actions CI/CD (pytest gate + build/push)

---

# 每日新闻摘要 — AI 新闻总结服务

每天两次自动抓取全球新闻，通过 OpenRouter（默认 deepseek-v4-pro）总结翻译成中文，发送邮件摘要。

> 历史说明：项目最初使用 Anthropic API（Claude），现已完全迁移到 OpenRouter + openai SDK，所有 `ANTHROPIC_*` 配置已废弃。

## 功能

- **40+ 新闻源**：BBC、CNN、Al Jazeera、Google News、Hacker News、TechCrunch、Ars Technica 等
- **AI 前沿板块**：面向程序员的 AI 技术动态，来自 AI 工程博客与社区（Simon Willison、Hugging Face、OpenAI、DeepMind、Latent Space、Interconnects、r/LocalLLaMA、Lobsters、量子位）；HN 上 AI 相关讨论帖按标题关键词自动归入此板块
- **AI 总结**：LLM 按重要性排序，翻译成中文，识别趋势，跨源去重
- **邮件推送**：Gmail SMTP 发送，带重试+指数退避，支持多收件人
- **双窗口机制**：北京时间 07:00 / 23:00 各跑一次，每次只总结上次成功发送之后的新闻（不重叠，省一半 token）
- **失败告警**：连说明邮件都发不出去时，POST 到可选的 webhook（兼容 Server酱）

## 快速开始

### 环境变量

复制 `config.env.example` 为 `config.env`，参考上方英文段落填写：

- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` — OpenRouter 网关（必填）
- `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` / `RECIPIENT_EMAIL` — Gmail SMTP（必填）
- `DAILYHOT_API_URL` — 医疗健康热搜数据源，依赖 NAS 局域网服务 `192.168.1.64:6688`（可选）
- `ALERT_WEBHOOK_URL` — 失败告警 webhook，留空禁用（可选）
- `STATE_FILE` / `DEFAULT_WINDOW_HOURS` — 双窗口状态文件与默认窗口（可选）

> Gmail App Password 在 [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords) 生成（需先开启两步验证）

### 本地测试

```bash
# 直接运行
pip install -r requirements.txt
python src/main.py

# 跑测试
pip install -r requirements-dev.txt
pytest

# Docker
docker compose up --build
```

### 部署

Docker 镜像通过 GitHub Actions 自动构建推送到 Docker Hub（pytest 通过后才 build）：

```
jasonxi89/daily-news-digest:latest
jasonxi89/daily-news-digest:<commit-sha>
```

Cron 定时（容器时区 Asia/Shanghai）：

- `0 7 * * *` — 北京时间 07:00
- `0 23 * * *` — 北京时间 23:00

### 双窗口机制说明

每次邮件成功发出后，把时间写入 `STATE_FILE`（通过 `/app/data` volume 持久化）。下一次运行只抓取该时间点之后发布的新闻：

- 正常情况窗口自然交替为约 8 小时（07:00→23:00 那次）和约 16 小时（23:00→次日 07:00 那次），内容不重叠，LLM token 消耗约为原来的一半
- 窗口**下限 1 小时、封顶 48 小时**；某次运行失败后，下次自动扩窗补捞漏掉的新闻
- 无状态文件（首次运行/volume 被清）时回退到 `DEFAULT_WINDOW_HOURS`（默认 24）
- 邮件主题和正文会标注本期窗口（如"过去 8 小时"），方便人工核对

## 技术栈

- Python 3.11 + feedparser + requests
- openai SDK → OpenRouter 网关（默认 `deepseek/deepseek-v4-pro`）
- Gmail SMTP
- Docker Alpine + crond
- GitHub Actions CI/CD（pytest 门控 + 构建推送）
