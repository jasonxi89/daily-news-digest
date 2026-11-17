# HANDOFF — daily-news-digest
> 跨 agent/IDE 接手文档 | 最后更新: 2026-11-16 | 改动项目后请同步更新此文档

## 项目定位
每日新闻摘要邮件服务：定时抓取全球新闻 → Claude（Opus 5.5）总结翻译成中文 Markdown → Gmail SMTP 推送邮件。
跑在极空间 NAS 的 Docker **cron 容器**（无对外端口，靠 crond 定时触发，不是常驻 web 服务）。
北京时间 **07:00 / 23:00** 各跑一次，每次只覆盖上次成功发送之后的新闻（双窗口，不重叠、省一半 token）。

## 当前状态
- **2026-11-16 起 LLM 改走 Claude API**：官方 `anthropic` SDK 2.3.0，模型 `claude-opus-5-5`，思考强度 `max`（用户指定）。**部署 SHA：待主会话部署后回填**。切换前线上是 `88071f4`（DeepSeek 官网直连 `deepseek-flash`），回滚办法见「约定与坑」。
- 配置走 compose env：`ANTHROPIC_API_KEY`（必填）、`CLAUDE_MODEL`（默认 `claude-opus-5-5`）、`CLAUDE_EFFORT`（默认 `max`，可选 low / medium / high / xhigh / max）。`OPENROUTER_*` 全部废弃。max 档一次摘要估计要 5 到 15 分钟（估计值，还没实测，部署后以 cron.log 里 `summarize done` 行的 `elapsed_seconds` 为准），07:00 / 23:00 的邮件会相应晚到。
- 2026-07-30 新增 **AI 前沿板块**（`ai_dev` 分类）：11 个 AI 工程博客/社区源（Simon Willison、HF Blog、Latent Space、Interconnects、Ahead of AI、DeepMind、OpenAI News、HF Daily Papers、r/LocalLLaMA、Lobsters AI、量子位）+ HN 讨论帖按标题 AI 关键词自动路由（`is_ai_related`，HN_TOP_N 30→50）；邮件新增"🤖 AI 前沿（开发者视角）"章节。
- 已具备：邮件重试（指数退避）、LLM 异常全兜底（宁发说明邮件不断邮件）、双窗口自动交替/失败扩窗、webhook 失败告警。
- ⚠️ `ALERT_WEBHOOK_URL` **未配置** → 告警静默禁用（NAS compose 里没填，等用户给 webhook）。
- 无版本号项目，靠**镜像 SHA + 容器日志 + 收到邮件**验证，不走 `/api/health`。

## 技术栈与结构
- Python 3.11 + feedparser + requests + **官方 anthropic SDK 2.3.0（Claude API，底层是 httpx2）** + Gmail SMTP；Docker Alpine + crond；GitHub Actions CI（pytest 门控 + build/push 到 Docker Hub）。
- 模型和思考强度由 env 决定：`CLAUDE_MODEL` + `CLAUDE_EFFORT`（代码默认 `claude-opus-5-5` / `max`）。渠道历史：Anthropic API → OpenRouter → DeepSeek 官网直连（后两段用 openai SDK）→ 2026-11-16 回到官方 anthropic SDK。
- `src/main.py` — 编排入口：算窗口 → 抓取+总结 → 发邮件 → 记录成功时间；每层异常都有兜底。
- `src/news_fetcher.py` — 抓 49 个源 URL，8 大分类（international/tech/ai_dev/finance/cn_news/cn_tech/cn_finance/cn_health）+ DailyHot 医疗热搜；HN 讨论帖按 `is_ai_related` 关键词路由到 ai_dev。抓取函数（网络层）仍无单测，纯函数已覆盖。
- `src/summarizer.py` — Claude 流式总结：`client.beta.messages.stream(...)` + `get_final_message()`，max_tokens=128000（思考也算在内），读超时 600 秒、连接超时 10 秒、max_retries=2，带官方拒答兜底（beta `server-side-fallback-2026-07-01` + `fallbacks="default"`）。拒答、空正文、配置错误（key 缺失、`CLAUDE_EFFORT` 无效）和各类 API 异常都兜底为说明邮件；输出被截断时照发已有正文并在末尾加一行说明。每次调用结束打一行 `summarize done model=... stop_reason=... input_tokens=... output_tokens=... elapsed_seconds=...`，用来核算花费。
- `src/emailer.py` — Gmail `SMTP_SSL:465`，重试+指数退避，`RECIPIENT_EMAIL` 逗号分隔多收件人。
- `src/alerter.py` — POST `ALERT_WEBHOOK_URL`，JSON `{title, body, desp}`（兼容 Server酱），留空即禁用。
- `src/run_state.py` — 双窗口状态：成功后写 `/app/data/last_success.json`，下次窗口 = now − 上次成功（下限 1h、封顶 48h）；无状态文件回退 `DEFAULT_WINDOW_HOURS`(24)。
- `entrypoint.sh` — 用 python `shlex.quote` 把 env 转义写入 `/app/.env.sh` 并 `chmod 600`（cron job source 它）；`crontab` 定义两条定时。
- `tests/` — 51 个测试，覆盖 summarizer/emailer/alerter/run_state/news_fetcher（后者仅纯函数：AI 路由关键词、日期解析）。summarizer 的测试分两个文件：`test_summarizer.py` 用假的流对象（`summarizer_fakes.py`，fixture 在 `conftest.py`），`test_summarizer_real_sdk.py` 保留真实 SDK、只把 HTTP 传输层换成假的（不联网），核对实际发出的请求体和流式解析。

## 常用命令
```bash
# 本地跑（需先 pip install -r requirements.txt，含 anthropic/markdown/feedparser）
python src/main.py
# 测试（先 pip install -r requirements.txt -r requirements-dev.txt；缺 anthropic/markdown 会 2 个文件收集报错，非代码问题）
pytest
# Docker 本地
docker compose up --build
# NAS 运维（工具 C:\Users\goodb\nas_ssh.py：ps / images / logs / pull / restart）
py C:\Users\goodb\nas_ssh.py ps
py C:\Users\goodb\nas_ssh.py logs daily-news-digest
# 每次运行的日志（含摘要调用的 usage 行）写在容器内的 cron.log，不进 docker logs
py C:\Users\goodb\nas_ssh.py "docker exec daily-news-digest tail -n 50 /var/log/cron.log"
# 不发邮件验证摘要调用：在 NAS 上执行，会真实调用一次 Claude 并计费；
# 只想验证连通就在 exec 后加 -e CLAUDE_EFFORT=low。命令里有单引号，不能经 nas_ssh.py 转发
docker exec -w /app/src daily-news-digest python -c 'import logging; logging.basicConfig(level=logging.INFO); from summarizer import summarize_news; print(summarize_news({"tech": [{"title": "Test article", "summary": "A short test article.", "link": "https://example.com/a", "source": "Test", "published": "2026-11-16"}]}))'
```

## 约定与坑
- **部署**：`git push` → CI 自动构建推 Docker Hub（NAS 不会自动拉）→ NAS compose 用 **commit SHA tag**，**绝不用 `:latest`**（registry mirror 会缓存旧 manifest）→ `pull` + `up -d --force-recreate`。
- **`/app/data` volume 必须保留**：NAS 路径 `/tmp/zfsv3/nvme12/18363877578/data/docker/daily-news-digest/data`。丢了 → 状态文件没了 → 回退 24h 窗口，会**重复发/漏发新闻**、双窗口省 token 失效。
- **凭据只在 NAS compose 环境变量**里；`config.env` 已 gitignore、含密钥，切勿提交；本文档与任何提交都**不得写入密钥/授权码**。
- LLM 长请求：max_tokens=128000 的非流式请求 anthropic SDK 会直接拒发，所以必须用 `messages.stream()`；改总结逻辑时保留流式和逐层兜底（宁发说明邮件不断邮件）。600 秒是相邻两段数据之间的读超时，不是整次请求的时长上限；流中途断开不会自动重试，那一期会发失败说明。
- **切模型或降档**：改 NAS compose 的 `CLAUDE_MODEL` / `CLAUDE_EFFORT` 后 recreate 容器，不用改代码。`CLAUDE_EFFORT` 填错不会断邮件，会收到一封写明原因的失败说明。
- **回滚到 DeepSeek 版**：NAS compose 换回切换前的备份（镜像 `88071f4` + `OPENROUTER_*` 三个 env；备份文件名待主会话部署后回填），再 `pull` + `up -d --force-recreate`。
- **花费和额度**：Claude key 如果和 video-voice 等项目同属一个 Console 组织，余额和用量上限是共用的；撞到上限时摘要失败，说明邮件里会带接口返回的原话（HTTP 400，usage limits）。每次运行用了多少 token 看 cron.log 里的 `summarize done` 行。
- 语义注意：fetch 全挂或生成失败也会**发 fallback 说明邮件并推进窗口**（"已送达即覆盖"），不是 bug 是设计。
- DailyHot 医疗热搜依赖 NAS 局域网 `192.168.1.64:6688`（`DAILYHOT_API_URL`），容器需能访问 LAN。
- Git：commit message `type: 描述`，**不加 Co-Authored-By**，不写 Claude 进 contributor。

## 进行中 / TODO
- [ ] 观察 max 档每次运行的耗时和花费（cron.log 的 `summarize done` 行）；太慢或太贵就把 `CLAUDE_EFFORT` 降到 high 或 medium。
- [ ] 配置 `ALERT_WEBHOOK_URL`（目前告警静默，发送失败无外部通知）。
- [ ] `news_fetcher.py` 网络层抓取函数补单测（纯函数部分 2026-07-30 已覆盖）。
- [ ] 评估 "fetch 全挂仍推进窗口" 语义：是否该失败时不推进、留给下次扩窗补捞。
- [ ] 观察 AI 前沿板块信噪比：HF Daily Papers（第三方镜像 papers.takara.ai）与 r/LocalLLaMA 若噪音大可再调关键词/去源。

## 相关资源
- 仓库：https://github.com/jasonxi89/daily-news-digest ｜ 镜像：Docker Hub `jasonxi89/daily-news-digest:<sha>`
- Memory：`daily_news_digest.md`、`nas_deployment.md`（部署流程/版本规则）、`tool_mistakes.md`（历史踩坑）
- NAS：SSH `192.168.1.64:10000` 用户 `18363877578`；compose 目录 `/zspace/applications/services/zdocker/config/compose_config/`；工具 `C:\Users\goodb\nas_ssh.py`
