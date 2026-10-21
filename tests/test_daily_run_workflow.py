"""daily-run 在内容提交之后通知图片机器人，且不会把 key 打进日志。"""

from pathlib import Path

WORKFLOW = Path(".github/workflows/daily-run.yml")


def test_image_bot_step_follows_a_real_commit():
    text = WORKFLOW.read_text(encoding="utf-8")
    commit = text.index("name: Commit generated content")
    notify = text.index("name: Notify image bot")
    upload = text.index("name: Upload output as artifact")
    assert commit < notify < upload

    commit_block = text[commit:notify]
    notify_block = text[notify:upload]
    assert "id: commit" in commit_block
    assert 'echo "committed=$committed" >> "$GITHUB_OUTPUT"' in commit_block
    assert "committed=true" in commit_block

    assert "continue-on-error: true" in notify_block
    assert "secrets.IMAGE_BOT_WEBHOOK_URL" in notify_block
    assert "secrets.IMAGE_BOT_WEBHOOK_KEY" in notify_block
    assert "IMAGE_BOT_WEBHOOK_URL" in notify_block and "IMAGE_BOT_WEBHOOK_KEY" in notify_block
    assert '::notice::缺少 secret IMAGE_BOT_WEBHOOK_URL 或 IMAGE_BOT_WEBHOOK_KEY' in notify_block
    assert "Authorization: Bearer ${IMAGE_BOT_WEBHOOK_KEY}" in notify_block
    assert "Content-Type: application/json" in notify_block
    assert "--max-time 30" in notify_block
    assert "--data-binary" in notify_block
    assert "steps.commit.outputs.committed == 'true'" in notify_block
    assert "inputs.dry_run == false" in notify_block
    assert "image_overwrite:" in text
    assert "--image-overwrite" in text
    assert 'echo "$IMAGE_BOT_WEBHOOK_KEY"' not in text
    assert "echo '$IMAGE_BOT_WEBHOOK_KEY'" not in text
    assert "curl -v" not in notify_block and "--verbose" not in notify_block
