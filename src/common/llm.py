"""LLM 调用的共用小工具"""


def log_usage(label: str, response) -> dict | None:
    """打印一次调用的 token 用量（含推理 token），返回字典便于测试。

    OpenAI 兼容 API 的 usage 结构不完全一致：reasoning_tokens 可能缺失，usage 也可能为 None。
    只记录、不影响主流程。
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None

    parts = [f"in={prompt}", f"out={completion}"]
    if reasoning:
        parts.append(f"(reasoning={reasoning})")
    print(f"  ⏱ tokens[{label}]: " + " ".join(parts))
    return {"prompt": prompt, "completion": completion, "reasoning": reasoning}
