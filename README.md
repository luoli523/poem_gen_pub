# 古诗词与节气内容生成系统

每日自动检测节气和节日，调用 LLM 匹配应景古诗词，通过 webhook 图片机器人生成 infographic，并推送页面链接到 Telegram。

支持 Grok (xAI)、ChatGPT、DeepSeek 等 OpenAI 兼容 API。

## 功能

- **节气检测**：自动识别二十四节气及传统节日（七夕、重阳等）
- **诗词匹配**：调用 LLM 动态匹配当日最应景的古诗词
- **Infographic 生成**：通过 webhook 将提示词交给图片机器人生成并回传图片
- **多平台发布**：Telegram 推送页面链接（标题 + 引子）；webhook 异步出图模式不在 daily-run 中发布 Instagram
- **背后的故事**：第二次 LLM 调用整理作者轶事、本事、时代背景、风土人情、传说、典故六类素材，每条标注可信度与出处，写入 `site/content/poems/` 并提交回仓库持续积累
- **每日自动运行**：GitHub Actions 每天北京时间 7:00 执行
- **多 LLM 支持**：Grok、ChatGPT、DeepSeek 等 OpenAI 兼容服务均可使用

## 流程

```
节令检测 / 诗词匹配 → LLM 素材与生图提示词 → 文字页面 + manifest → Telegram 链接
提交内容 → POST webhook → 图片机器人出图并推回仓库 → 发布站点
```

## 网站

内容页积累在 `site/content/poems/`（每首一个目录：`index.md` + `infographic.webp`），由 Hugo 构建，
每日流水线完成后自动发布到 <https://guige.ai/poem_gen_pub/>。
版式取自宋版书（界行、竖排题名、眉批式的可信度与出处），主题在 `site/layouts` 与 `site/assets/css`，无外部主题依赖。
可按作者 / 朝代 / 场景 / 素材分类 / 可信度浏览；全文搜索由 Pagefind 在构建后生成。

本地预览：

```bash
hugo --source site server            # 搜索页需先 hugo 构建后执行 npx pagefind --site site/public
```

每日流水线的完整流程、各环节失败后果与维护操作见 [docs/daily-run.md](docs/daily-run.md)。

邮件订阅：版末表单 → `subscribe.guige.ai` → Resend 名单「鬼话诗」；`pages.yml` 部署后把当日新诗词群发给订阅者。运维手册见主站 [docs/NEWSLETTER.md](https://github.com/luoli523/luoli523.github.io/blob/master/docs/NEWSLETTER.md)。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt        # 本地开发
# CI 使用 requirements.lock（精确版本），升级依赖后请重新生成，见文件头注释
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

| 变量 | 说明 | 必填 |
|---|---|---|
| `GROK_API_KEY` | Grok (xAI) API Key（与 OPENAI_API_KEY 二选一） | 是 |
| `OPENAI_API_KEY` | OpenAI API Key（与 GROK_API_KEY 二选一） | 是 |
| `TELEGRAM_ENABLED` | 是否启用 Telegram（true/false） | 否 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | Telegram 启用时必填 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | Telegram 启用时必填 |
| `IG_ENABLED` | 是否启用 Instagram（true/false） | 否 |
| `IG_USERNAME` | Instagram 用户名 | IG 启用时必填 |
| `IG_PASSWORD` | Instagram 密码 | IG 启用时必填 |

LLM API Key 优先级：`GROK_API_KEY` > `OPENAI_API_KEY`。配置 `GROK_API_KEY` 时自动使用 `https://api.x.ai/v1`，无需额外设置 base URL。

### 3. 配置模型

编辑 `config/config.yaml`，设置模型名称：

```yaml
openai:
  model: "grok-3"              # Grok 用 grok-3 / grok-4-1-fast-reasoning 等
  # model: "gpt-5"             # ChatGPT 用 gpt-5 / gpt-4o 等
  # model: "deepseek-chat"     # DeepSeek 用 deepseek-chat
  max_completion_tokens: 16000
```

### 4. 登录第三方服务

**NotebookLM**（仅本地使用旧版直接生图时需要，每日 webhook 流程不需要）：
```bash
python -c "from notebooklm import login; login()"
```

**Instagram**（可选）：
```bash
python scripts/ig_login.py
```

### 5. 运行

```bash
python main.py --image-webhook
```

此命令生成内容、manifest 并按配置推送 Telegram 链接；POST webhook 由 GitHub Actions 在内容提交后执行。

**可选参数：**

| 参数 | 说明 |
|---|---|
| `--image-webhook` | 跳过 NotebookLM，保存 manifest，保留 Telegram 页面链接推送（daily-run 使用） |
| `--no-nlm` | 跳过 NotebookLM，只生成 Markdown |
| `--no-ig` | 跳过 Instagram 发布 |
| `--no-poetry` | 跳过诗词模块（不调用 LLM） |
| `--image-overwrite` | 信息图 manifest 的 `overwrite` 为 true（默认 false） |

## GitHub Actions 自动化

在仓库 **Settings → Secrets and variables → Actions** 中配置以下 secrets：

| Secret | 说明 |
|---|---|
| `GROK_API_KEY` | Grok (xAI) API Key（与 OPENAI_API_KEY 二选一） |
| `OPENAI_API_KEY` | OpenAI API Key（与 GROK_API_KEY 二选一） |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| `IG_USERNAME` | Instagram 用户名 |
| `IG_PASSWORD` | Instagram 密码 |
| `IG_SESSION` | Instagram session（base64，可选） |
| `IMAGE_BOT_WEBHOOK_URL` | 信息图机器人 webhook。内容提交后，把每份 manifest POST 到这个地址。未配置则跳过 |
| `IMAGE_BOT_WEBHOOK_KEY` | 上面那次 POST 的 Bearer token（`Authorization: Bearer <key>`）。未配置则跳过。日志里不会打印 |

生成 base64 session：
```bash
base64 < ~/.instagram/session.json | gh secret set IG_SESSION
```

### 信息图机器人

每日流水线在 **内容确实提交成功之后**，把当天每条信息图请求 POST 给外部图片机器人。机器人按 prompt 生成 `infographic.webp`，再推回仓库。每日任务固定使用 `--image-webhook`，不恢复 NotebookLM 登录态、不调用 NotebookLM。Telegram 正常推送页面链接；图片异步返回，因此本任务不再直接发布 Instagram。

信息图 prompt 的来源：

- 诗词：`src/poetry/detector.py` 在匹配诗词时让 LLM 返回 `infographic_prompt`（故事那一次调用不再生成这段）
- 节令：`src/jieling/story.py` 在六类素材之外返回 `infographic_prompt`。素材生成失败、或 prompt 为空时不写 manifest

`main.py` 对每一条非空 prompt 写一份 JSON 到 `output/infographic-manifests/`（该目录在 `.gitignore` 里，随 Actions artifact 保留 7 天）：

- 诗词：`poetry_<YYYY-MM-DD>_<诗题>.json`，`content_dir` 如 `site/content/poems/2026-10-21-偶成`
- 节令：`jieling_<YYYY-MM-DD>_<节令名>.json`，`content_dir` 如 `site/content/terms/白露/2026`

`--image-webhook` 模式始终跳过 NotebookLM；只要 prompt 非空，就会保存 manifest 供机器人出图。

载荷字段：`date`、`prompt`（完整信息图 prompt）、`content_dir`（相对仓库根）、`upload_path`（`<content_dir>/infographic.webp`）、可选 `page_url`（配置了 `site.base_url` 时才有）、`overwrite`（默认 `false`）。

```json
{
  "date": "2026-10-21",
  "prompt": "中国古典书画风与现代信息图融合……（完整指令）",
  "content_dir": "site/content/poems/2026-10-21-偶成",
  "upload_path": "site/content/poems/2026-10-21-偶成/infographic.webp",
  "page_url": "https://guige.ai/poem_gen_pub/poems/2026-10-21-%E5%81%B6%E6%88%90/",
  "overwrite": false
}
```

手动触发勾上 `image_overwrite` 时，流水线会带 `--image-overwrite`，载荷里的 `overwrite` 为 `true`。定时运行不带这个参数，保持 `false`。

**什么时候 POST**：`Commit generated content` 成功，并且这次确实产生了 commit（`site/content` 或 `data/poem_history.json` 有变化并 push 上去）之后。定时运行会发；手动运行未勾 `dry_run` 也会发。流水线因为降级以 exit 1 结束、但页面已经提交时仍然发，保证已有文字页面仍能交给机器人补图。

**什么时候不 POST**：

- `dry_run`：这一档用来调 prompt，不推送 Telegram，也不通知图片机器人。manifest 仍在 artifact 里，可以查看载荷。
- 没有新 commit（内容与上次相同）。
- `IMAGE_BOT_WEBHOOK_URL` 或 `IMAGE_BOT_WEBHOOK_KEY` 有一个缺失：打一条 notice，跳过。
- 这次提交没有 manifest（例如节令素材失败、诗词没有 prompt）。

每一份 manifest 单独 POST，`Content-Type: application/json`，超时 30 秒。webhook 失败只打 warning，步骤带 `continue-on-error`，不会把这次 run 标红。不会把 key 打进日志。

## 项目结构

```
├── main.py                      # 主入口
├── config/
│   └── config.yaml              # LLM 模型及输出配置
├── src/
│   ├── common/
│   │   ├── config.py            # LLM 配置（自动识别 Grok / OpenAI）
│   │   ├── constants.py         # 共享常量（二十四节气名称等）
│   │   ├── notebooklm.py       # NotebookLM 通用操作及 pipeline
│   │   ├── telegram.py          # Telegram 消息发送
│   │   ├── instagram.py         # Instagram 发布
│   │   └── infographic_manifest.py  # 信息图 webhook 用的 JSON manifest
│   ├── poetry/                  # 诗词模块
│   │   ├── detector.py          # LLM 诗词匹配
│   │   └── content.py           # Markdown / IG 文案 / TG 文案
│   └── jieling/                 # 节令模块（节气 + 汉族节日 + 少数民族节日）
│       ├── calendar.py          # 节令日历：sxtwl 节气 + zhdate 农历定日 + 按年硬编码
│       ├── story.py             # LLM 六类素材 + 信息图 prompt，往年要点排除
│       └── content.py           # 档案页 / story.json / NotebookLM source / 文案
├── scripts/
│   └── ig_login.py              # Instagram 登录辅助
└── tests/                       # 测试
```
