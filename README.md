# Daily News Digest — AI-Powered News Summarization Service

Automatically fetches global news daily, summarizes and translates to Chinese using Claude AI, and delivers a formatted digest via email.

## Features

- **10+ news sources**: BBC, CNN, Al Jazeera, Google News, Hacker News, TechCrunch, Ars Technica, MarketWatch, and more
- **AI summarization**: Claude API ranks by importance, translates to Chinese, identifies trends, deduplicates across sources
- **Email delivery**: Gmail SMTP sends HTML-formatted digest, supports multiple recipients
- **Automated scheduling**: Docker + cron, runs daily without intervention

## Quick Start

### Environment Variables

Copy `config.env.example` to `config.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
RECIPIENT_EMAIL=recipient1@example.com,recipient2@example.com
TZ=Asia/Shanghai
```

> Generate Gmail App Password at [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification enabled)

### Local Testing

```bash
# Run directly
pip install -r requirements.txt
python src/main.py

# Docker
docker compose up --build
```

### Deployment

Docker image auto-built and pushed to Docker Hub via GitHub Actions:

```
jasonxi89/daily-news-digest:latest
```

Cron schedule:
- `0 7 * * *` — 7:00 AM China time daily
- `0 23 * * *` — 7:00 AM PST daily

## Tech Stack

- Python 3.11 + feedparser + requests
- Anthropic SDK (Claude Sonnet)
- Gmail SMTP
- Docker Alpine + crond
- GitHub Actions CI/CD

---

# 每日新闻摘要 — AI 新闻总结服务

每天自动抓取全球新闻，用 AI 总结翻译成中文，发送邮件摘要。

## 功能

- **10+ 新闻源**：BBC、CNN、Al Jazeera、Google News、Hacker News、TechCrunch、Ars Technica 等
- **AI 总结**：Claude API 按重要性排序，翻译成中文，识别趋势，跨源去重
- **邮件推送**：Gmail SMTP 发送 HTML 格式邮件，支持多收件人
- **定时执行**：Docker + cron，每天自动运行

## 快速开始

### 环境变量

复制 `config.env.example` 为 `config.env`，填入：

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
RECIPIENT_EMAIL=recipient1@example.com,recipient2@example.com
TZ=Asia/Shanghai
```

> Gmail App Password 在 [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords) 生成（需先开启两步验证）

### 本地测试

```bash
# 直接运行
pip install -r requirements.txt
python src/main.py

# Docker
docker compose up --build
```

### 部署

Docker 镜像自动通过 GitHub Actions 构建推送到 Docker Hub：

```
jasonxi89/daily-news-digest:latest
```

Cron 定时：
- `0 7 * * *` — 每天 7:00 AM 中国时间
- `0 23 * * *` — 每天 7:00 AM PST

## 技术栈

- Python 3.11 + feedparser + requests
- Anthropic SDK (Claude Sonnet)
- Gmail SMTP
- Docker Alpine + crond
- GitHub Actions CI/CD
