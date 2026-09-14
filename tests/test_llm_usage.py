"""Tests for token usage logging."""

from types import SimpleNamespace
from src.common.llm import log_usage


def test_logs_prompt_completion_and_reasoning(capsys):
    resp = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=1200, completion_tokens=3400,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=2100)))
    assert log_usage("故事", resp) == {"prompt": 1200, "completion": 3400, "reasoning": 2100}
    out = capsys.readouterr().out
    assert "tokens[故事]" in out and "in=1200" in out and "out=3400" in out and "reasoning=2100" in out


def test_no_reasoning_details(capsys):
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20))
    assert log_usage("x", resp)["reasoning"] is None
    assert "reasoning" not in capsys.readouterr().out


def test_missing_usage_is_quiet(capsys):
    assert log_usage("x", SimpleNamespace()) is None
    assert log_usage("x", SimpleNamespace(usage=None)) is None
    assert capsys.readouterr().out == ""
