# 古诗词与节气内容生成系统

每日自动检测节气和节日，调用 LLM 匹配应景古诗词，通过 NotebookLM 生成精美 infographic，并自动推送到 Telegram 和 Instagram。

支持 Grok (xAI)、ChatGPT、DeepSeek 等 OpenAI 兼容 API。

## 功能

- **节气检测**：自动识别二十四节气及传统节日（七夕、重阳等）
- **诗词匹配**：调用 LLM 动态匹配当日最应景的古诗词
- **Infographic 生成**：通过 NotebookLM 将内容渲染为精美图片
- **多平台发布**：自动推送到 Telegram、Instagram
- **每日自动运行**：GitHub Actions 每天北京时间 7:00 执行
- **多 LLM 支持**：Grok、ChatGPT、DeepSeek 等 OpenAI 兼容服务均可使用

## 流程

```
节气检测 → 生成节气 Markdown → NotebookLM infographic → Telegram → Instagram
诗词检测（LLM）→ 生成诗词 Markdown → NotebookLM infographic → Telegram → Instagram
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
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

**NotebookLM**（必须）：
```bash
python -c "from notebooklm import login; login()"
```

**Instagram**（可选）：
```bash
python scripts/ig_login.py
```

### 5. 运行

```bash
python main.py
```

**可选参数：**

| 参数 | 说明 |
|---|---|
| `--no-nlm` | 跳过 NotebookLM，只生成 Markdown |
| `--no-ig` | 跳过 Instagram 发布 |
| `--no-poetry` | 跳过诗词模块（不调用 LLM） |

## GitHub Actions 自动化

在仓库 **Settings → Secrets and variables → Actions** 中配置以下 secrets：

| Secret | 说明 |
|---|---|
| `GROK_API_KEY` | Grok (xAI) API Key（与 OPENAI_API_KEY 二选一） |
| `OPENAI_API_KEY` | OpenAI API Key（与 GROK_API_KEY 二选一） |
| `NOTEBOOKLM_STORAGE_STATE` | NotebookLM 登录态（base64） |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| `IG_USERNAME` | Instagram 用户名 |
| `IG_PASSWORD` | Instagram 密码 |
| `IG_SESSION` | Instagram session（base64，可选） |

生成 base64 session：
```bash
base64 < ~/.notebooklm/storage_state.json | gh secret set NOTEBOOKLM_STORAGE_STATE
base64 < ~/.instagram/session.json | gh secret set IG_SESSION
```

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
│   │   └── instagram.py         # Instagram 发布
│   ├── poetry/                  # 诗词模块
│   │   ├── detector.py          # LLM 诗词匹配
│   │   └── content.py           # Markdown / IG 文案 / TG 文案
│   └── solar_term/              # 节气模块
│       ├── detector.py          # 节气检测 + LLM 内容生成
│       └── content.py           # Markdown / IG 文案 / TG 文案
├── scripts/
│   └── ig_login.py              # Instagram 登录辅助
└── tests/                       # 测试
```
