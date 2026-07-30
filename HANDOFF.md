# HANDOFF — daily-news-digest
> 跨 agent/IDE 接手文档 | 最后更新: 2026-07-30 | 改动项目后请同步更新此文档

## 项目定位
每日新闻摘要邮件服务：定时抓取全球新闻 → OpenRouter LLM 总结翻译成中文 Markdown → Gmail SMTP 推送邮件。
跑在极空间 NAS 的 Docker **cron 容器**（无对外端口，靠 crond 定时触发，不是常驻 web 服务）。
北京时间 **07:00 / 23:00** 各跑一次，每次只覆盖上次成功发送之后的新闻（双窗口，不重叠、省一半 token）。

## 当前状态
- 稳定运行中，部署镜像 SHA **`da88590`**（2026-07-30 部署，容器内实测抓取 AI_DEV 53 篇、状态文件完好、旧镜像已清）。
- 2026-07-30 新增 **AI 前沿板块**（`ai_dev` 分类）：11 个 AI 工程博客/社区源（Simon Willison、HF Blog、Latent Space、Interconnects、Ahead of AI、DeepMind、OpenAI News、HF Daily Papers、r/LocalLLaMA、Lobsters AI、量子位）+ HN 讨论帖按标题 AI 关键词自动路由（`is_ai_related`，HN_TOP_N 30→50）；邮件新增"🤖 AI 前沿（开发者视角）"章节。
- 已具备：邮件重试（指数退避）、LLM 异常全兜底（宁发说明邮件不断邮件）、双窗口自动交替/失败扩窗、webhook 失败告警。
- ⚠️ `ALERT_WEBHOOK_URL` **未配置** → 告警静默禁用（NAS compose 里没填，等用户给 webhook）。
- 无版本号项目，靠**镜像 SHA + 容器日志 + 收到邮件**验证，不走 `/api/health`。

## 技术栈与结构
- Python 3.11 + feedparser + requests + **openai SDK（走 OpenRouter 网关）** + Gmail SMTP；Docker Alpine + crond；GitHub Actions CI（pytest 门控 + build/push 到 Docker Hub）。
- 默认模型 `deepseek/deepseek-v4-pro`，切模型改 env `OPENROUTER_MODEL`。历史用过 Anthropic API，**已完全迁走，所有 `ANTHROPIC_*` 配置废弃**。
- `src/main.py` — 编排入口：算窗口 → 抓取+总结 → 发邮件 → 记录成功时间；每层异常都有兜底。
- `src/news_fetcher.py` — 抓 49 个源 URL，8 大分类（international/tech/ai_dev/finance/cn_news/cn_tech/cn_finance/cn_health）+ DailyHot 医疗热搜；HN 讨论帖按 `is_ai_related` 关键词路由到 ai_dev。抓取函数（网络层）仍无单测，纯函数已覆盖。
- `src/summarizer.py` — OpenRouter 流式总结（`stream=True`, timeout=600, max_tokens=32768），逐 chunk 累加，各类 API 异常兜底为说明邮件。
- `src/emailer.py` — Gmail `SMTP_SSL:465`，重试+指数退避，`RECIPIENT_EMAIL` 逗号分隔多收件人。
- `src/alerter.py` — POST `ALERT_WEBHOOK_URL`，JSON `{title, body, desp}`（兼容 Server酱），留空即禁用。
- `src/run_state.py` — 双窗口状态：成功后写 `/app/data/last_success.json`，下次窗口 = now − 上次成功（下限 1h、封顶 48h）；无状态文件回退 `DEFAULT_WINDOW_HOURS`(24)。
- `entrypoint.sh` — 用 python `shlex.quote` 把 env 转义写入 `/app/.env.sh` 并 `chmod 600`（cron job source 它）；`crontab` 定义两条定时。
- `tests/` — 31 个测试，覆盖 summarizer/emailer/alerter/run_state/news_fetcher（后者仅纯函数：AI 路由关键词、日期解析）。

## 常用命令
```bash
# 本地跑（需先 pip install -r requirements.txt，含 openai/markdown/feedparser）
python src/main.py
# 测试（先 pip install -r requirements-dev.txt；缺 openai/markdown 会 2 个文件收集报错，非代码问题）
pytest
# Docker 本地
docker compose up --build
# NAS 运维（工具 C:\Users\goodb\nas_ssh.py：ps / images / logs / pull / restart）
py C:\Users\goodb\nas_ssh.py ps
py C:\Users\goodb\nas_ssh.py logs daily-news-digest
```

## 约定与坑
- **部署**：`git push` → CI 自动构建推 Docker Hub（NAS 不会自动拉）→ NAS compose 用 **commit SHA tag**，**绝不用 `:latest`**（registry mirror 会缓存旧 manifest）→ `pull` + `up -d --force-recreate`。
- **`/app/data` volume 必须保留**：NAS 路径 `/tmp/zfsv3/nvme12/18363877578/data/docker/daily-news-digest/data`。丢了 → 状态文件没了 → 回退 24h 窗口，会**重复发/漏发新闻**、双窗口省 token 失效。
- **凭据只在 NAS compose 环境变量**里；`config.env` 已 gitignore、含密钥，切勿提交；本文档与任何提交都**不得写入密钥/授权码**。
- LLM 长请求历史坑：Anthropic SDK 非流式 >10min 会被限制 → 现走 openai SDK + `stream=True` 规避；改总结逻辑保留流式累加。OpenRouter 偶发内容异常/空 delta，靠逐层兜底成说明邮件，不要去掉兜底。
- 语义注意：fetch 全挂或生成失败也会**发 fallback 说明邮件并推进窗口**（"已送达即覆盖"），不是 bug 是设计。
- DailyHot 医疗热搜依赖 NAS 局域网 `192.168.1.64:6688`（`DAILYHOT_API_URL`），容器需能访问 LAN。
- Git：commit message `type: 描述`，**不加 Co-Authored-By**，不写 Claude 进 contributor。

## 进行中 / TODO
- [ ] 配置 `ALERT_WEBHOOK_URL`（目前告警静默，发送失败无外部通知）。
- [ ] `news_fetcher.py` 网络层抓取函数补单测（纯函数部分 2026-07-30 已覆盖）。
- [ ] 评估 "fetch 全挂仍推进窗口" 语义：是否该失败时不推进、留给下次扩窗补捞。
- [ ] 观察 AI 前沿板块信噪比：HF Daily Papers（第三方镜像 papers.takara.ai）与 r/LocalLLaMA 若噪音大可再调关键词/去源。

## 相关资源
- 仓库：https://github.com/jasonxi89/daily-news-digest ｜ 镜像：Docker Hub `jasonxi89/daily-news-digest:<sha>`
- Memory：`daily_news_digest.md`、`nas_deployment.md`（部署流程/版本规则）、`tool_mistakes.md`（历史踩坑）
- NAS：SSH `192.168.1.64:10000` 用户 `18363877578`；compose 目录 `/zspace/applications/services/zdocker/config/compose_config/`；工具 `C:\Users\goodb\nas_ssh.py`
