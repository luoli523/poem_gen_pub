"""Smoke test: run full pipeline to verify orchestration."""

import os
import pytest
import subprocess
import sys


class TestPipelineSmoke:
    """End-to-end smoke tests running main.py."""

    def _run_main(self, extra_args: list[str], timeout: int = 30, extra_env: dict | None = None):
        """Helper to run main.py in a subprocess with isolated env.

        Explicitly disables all external services to prevent real API calls.
        """
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": ".",
            "HOME": os.environ.get("HOME", "/tmp"),
            "OPENAI_API_KEY": "test-key-for-smoke",
            "TELEGRAM_ENABLED": "false",
            "IG_ENABLED": "false",
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "main.py"] + extra_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    def test_no_nlm_no_poetry(self):
        """Pipeline runs with no NotebookLM + no poetry + no publishing."""
        result = self._run_main(["--no-nlm", "--no-ig", "--no-poetry"])
        assert result.returncode == 0, f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        assert "古诗词与节气" in result.stdout

    def test_missing_api_key_exits_early(self):
        """Without any LLM API key, pipeline should exit early."""
        result = self._run_main(
            ["--no-nlm", "--no-ig"],
            extra_env={"OPENAI_API_KEY": "", "GROK_API_KEY": ""},
        )
        assert "LLM API Key 未配置" in result.stdout

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "main.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--no-nlm" in result.stdout
        assert "--no-ig" in result.stdout
        assert "--no-poetry" in result.stdout


def test_beijing_today_uses_asia_shanghai(monkeypatch):
    """runner 是 UTC；'今天'必须按北京时间算。构造 UTC 22:30（北京次日 06:30）验证跨日。"""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    import src.common.constants as c

    fixed_utc = datetime(2026, 9, 14, 22, 30, tzinfo=timezone.utc)

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_utc.astimezone(tz) if tz else fixed_utc.replace(tzinfo=None)

    monkeypatch.setattr(c, "datetime", _FakeDT)
    assert c.beijing_today() == "2026-09-15"
    assert c.beijing_now().tzinfo == ZoneInfo("Asia/Shanghai")
