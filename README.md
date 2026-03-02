# Daily News Digest 每日新闻摘要

每天自动抓取全球新闻，用 AI 总结翻译成中文，发送邮件摘要。

## 功能

- **10+ 新闻源**：BBC、CNN、Al Jazeera、Google News、Hacker News、TechCrunch、Ars Technica 等
- **AI 总结**：Claude API 按重要性排序，翻译成中文，识别趋势
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
