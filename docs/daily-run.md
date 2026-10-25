# 每日 daily-run 流程

## 触发与运行环境

`.github/workflows/daily-run.yml` 每天 UTC 23:00（北京时间次日 7:00）触发，GitHub 调度可能延迟。运行于 ubuntu-latest、Python 3.13，任务超时 30 分钟。支持手动 dispatch。

每日入口固定为 `python main.py --image-webhook`。不恢复 NotebookLM 登录态，不做 NotebookLM 认证或生图；图片由外部 webhook 机器人异步生成并推回仓库。

## 每日执行顺序

1. Checkout、安装 `requirements.lock` 中的依赖。
2. 执行 `main.py --image-webhook`，按 Asia/Shanghai 确定日期，读取 LLM 配置。
3. 本地日历检测节气与节日。有节令时先处理节令，再处理每日诗词。
4. 写出文字页面、Markdown、生图提示词和信息图 manifest。
5. Telegram 推送「标题 + 引子 + 页面链接」，不等待图片。图片稍后由机器人补上。
6. 提交 `site/content` 和 `data/poem_history.json`，pull --rebase 后 push。
7. 内容确实提交成功且不是 dry_run 时，逐份 POST manifest 给图片机器人。
8. 上传 `output/` 为 Actions artifact，保留 7 天。
9. `pages.yml` 在每日任务完成后构建 Hugo、Pagefind 并部署 GitHub Pages；部署后发送当天新诗词订阅邮件。机器人回传图片的提交由站点 push 规则再次触发部署。

站点模板会自动识别内容目录中的 `infographic.webp`，机器人只回传图片文件也能显示，无需修改 frontmatter 或正文。首页始终按日期展示最新诗词，图片尚未回传时先显示文字。

webhook 模式没有本地产出的图片，因此 daily-run 中原有的 Instagram 图片发布步骤不会执行。

## 内容如何生成

### 节令

本地用 sxtwl 检测节气、zhdate 换算农历并查表判断节日；部分节日按公历或年度表判断。同一天有多个节令时依次处理。

读取往年同名 `story.json` 作为排除要点，调用 LLM 生成六类素材：名义与物候、历代风俗、饮食与器物、诗文、人物与传说、方志记载。每条带可信度与出处，同时生成引子和信息图 prompt。

文字落在 `site/content/terms/<节令名>/<年>/index.md`，素材另存 `story.json`。

### 诗词

LLM 按精确农历和节令选择关联名篇，排除近 90 天推荐过的诗；无关联时再推荐应季经典。返回诗题、作者、朝代、全文、赏析、风俗与信息图 prompt，并更新 `data/poem_history.json`。

再次调用 LLM 整理六类背后故事：作者轶事、本事与创作背景、时代背景、风土人情、民间传说、典故名物。标作史实却没有出处的条目降为存疑。

页面写入 `site/content/poems/<日期>-<诗题>/index.md`。`tale.enabled` 控制衍生故事，目前关闭。

## 生图 webhook

每条非空 prompt 写一份 `output/infographic-manifests/<poetry|jieling>_<日期>_<名称>.json`。

字段为 `date`、`prompt`、`content_dir`、`upload_path`、可选 `page_url`、`overwrite`。机器人将图片保存为目标内容目录下的 `infographic.webp` 并推回仓库。完整载荷示例见 README「信息图机器人」。

工作流读取 Secrets：

- `IMAGE_BOT_WEBHOOK_URL`：HTTP(S) webhook 地址。
- `IMAGE_BOT_WEBHOOK_KEY`：请求头 `Authorization: Bearer <key>` 的令牌。

每份 manifest 单独 POST，Content-Type 为 application/json，超时 30 秒。缺少任一 secret 时记录 notice 并跳过；请求失败记录 warning，步骤为 continue-on-error，不单独使 run 标红。接收端返回任务 ID 表示已接收，不代表已经出图。

仅在 `Commit generated content` 成功且确实 push 了新 commit 后通知。即使文字流程最终 exit 1，只要内容提交成功，仍通知已有 manifest。没有新 commit 或没有 manifest 时跳过。

`overwrite` 默认 false：新页面没有图片，由机器人生成；已有图片不覆盖。手动 dispatch 勾选 `image_overwrite` 时才设为 true。

## dry_run 与命令行

- 手动勾选 `dry_run`：在 `--image-webhook` 之外传 `--no-nlm --no-ig`，生成文字和 manifest 并提交，但不推送 Telegram、不调用 webhook。
- `--image-webhook`：跳过 NotebookLM，保留 Telegram 链接推送。POST 操作由工作流负责，本地运行此命令不会自动 POST。
- `--no-nlm`：保留原有只生成内容、不推送页面链接的行为。
- `--date YYYY-MM-DD`：指定日期；`--no-poetry`：仅节令；`--image-overwrite`：让 manifest 请求覆盖已有图。
- 不带 `--image-webhook` 的本地旧流程仍支持 NotebookLM；每日工作流不走此路径。

## 失败与维护

- LLM key 缺失：通知后退出，不能生成内容。
- 取诗、素材或故事失败：记录降级，尽可能保留文字页面，结束时汇总 Telegram 并 exit 1。
- 提交和 artifact 上传使用 if: always()，保留已生成内容。
- webhook 出图异步完成，失败需查看机器人任务日志；每日任务成功不表示机器人已生成图片。
- 改模型：编辑 `config/config.yaml` 并配置对应 API key。
- 查看当日提示词和 manifest：下载 Actions 的 `poem-output-<run_id>` artifact（7 天内）。
- 重画近 7 天的图：在 Actions 手动运行「重新生成历史信息图」（`redraw-images.yml`），填写原 daily-run 的运行 ID，多个用逗号分隔。它下载原 artifact，使用当天的 manifest 并强制 overwrite=true；不重跑选诗、文字生成或 Telegram 推送。
- 更早的图：需已有 manifest，再调用机器人，明确需要替换时设置 overwrite=true。

每日生图不再需要 `NOTEBOOKLM_MASTER_TOKEN`，已有 secret 可以保留，工作流不会读取。
