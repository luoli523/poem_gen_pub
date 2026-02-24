"""NotebookLM 共享基础功能

提供 notebook 查找/创建、source 上传、infographic 创建（含重试）和通用 pipeline，
供 solar_term 和 poetry 模块复用。
"""

import asyncio
from pathlib import Path

from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail

NOTEBOOK_TITLE = "poem_solar_term"

RATIO_TO_ORIENTATION = {
    "4:5": InfographicOrientation.PORTRAIT,
    "9:16": InfographicOrientation.PORTRAIT,
    "1:1": InfographicOrientation.SQUARE,
    "16:9": InfographicOrientation.LANDSCAPE,
}


async def check_auth() -> bool:
    """检测 NotebookLM 认证是否有效。

    尝试创建客户端并列出 notebook，成功返回 True，失败返回 False。
    """
    try:
        async with await NotebookLMClient.from_storage() as client:
            await client.notebooks.list()
            return True
    except FileNotFoundError:
        print("  ⚠ NotebookLM storage_state.json 不存在")
        return False
    except Exception as e:
        print(f"  ⚠ NotebookLM 认证失败: {type(e).__name__}: {e}")
        return False


async def find_or_create_notebook(client: NotebookLMClient) -> str:
    """查找 poem_solar_term notebook，不存在则创建。返回 notebook_id"""
    notebooks = await client.notebooks.list()
    for nb in notebooks:
        if nb.title == NOTEBOOK_TITLE:
            print(f"  找到已有 notebook: {NOTEBOOK_TITLE} (id={nb.id[:8]}...)")
            return nb.id

    print(f"  未找到 {NOTEBOOK_TITLE}，正在创建...")
    nb = await client.notebooks.create(NOTEBOOK_TITLE)
    print(f"  已创建 notebook: {NOTEBOOK_TITLE} (id={nb.id[:8]}...)")
    return nb.id


async def upload_source(client: NotebookLMClient, notebook_id: str, md_file: str) -> str:
    """上传 markdown 文件到 notebook，返回 source_id。

    如果 notebook 中已有同名 source，先删除再上传。
    """
    file_path = Path(md_file)
    file_name = file_path.name

    # 检查是否有同名 source，有则删除
    existing_sources = await client.sources.list(notebook_id)
    for src in existing_sources:
        if src.title == file_name:
            print(f"  发现同名 source: {file_name}，正在删除旧版本...")
            await client.sources.delete(notebook_id, src.id)

    print(f"  正在上传: {file_name}")
    source = await client.sources.add_file(notebook_id, str(file_path), wait=True)
    print(f"  上传完成: source_id={source.id[:8]}... title={source.title}")
    return source.id


async def create_infographic_with_retry(
    client: NotebookLMClient,
    notebook_id: str,
    source_id: str,
    prompt: str,
    orientation: InfographicOrientation = InfographicOrientation.PORTRAIT,
    max_retries: int = 3,
):
    """创建 infographic，带重试逻辑。

    Returns:
        status 对象（含 task_id），全部失败返回 None
    """
    for attempt in range(max_retries):
        try:
            status = await client.artifacts.generate_infographic(
                notebook_id,
                source_ids=[source_id],
                instructions=prompt,
                orientation=orientation,
                detail_level=InfographicDetail.DETAILED,
                language="zh",
            )
            if status and hasattr(status, "task_id") and status.task_id and len(status.task_id) > 5:
                return status
            print(f"    ⚠ 返回无效 status (第{attempt+1}次): {status}")
        except Exception as e:
            err_type = type(e).__name__
            err_cause = f" <- {type(e.__cause__).__name__}: {e.__cause__}" if e.__cause__ else ""
            print(f"    ⚠ 生成请求失败 (第{attempt+1}次): [{err_type}] {e}{err_cause}")

        if attempt < max_retries - 1:
            wait_sec = 10 * (attempt + 1)
            print(f"    ⏳ 等待 {wait_sec}s 后重试...")
            await asyncio.sleep(wait_sec)

    return None


async def run_pipeline(
    label: str,
    md_file: str,
    prompt: str,
    artifact_name: str,
    output_dir: str,
    ratio: str = "4:5",
) -> str | None:
    """通用 NotebookLM pipeline：上传 Markdown → 生成 infographic → 下载

    Args:
        label: 内容类型标签（如 "节气"、"诗词"），用于日志输出
        md_file: Markdown 文件路径
        prompt: infographic 生成 prompt
        artifact_name: 生成物命名
        output_dir: 输出目录
        ratio: 长宽比例（"4:5"、"9:16"、"1:1"、"16:9"），默认 "4:5"

    Returns:
        生成的图片文件路径，失败返回 None
    """
    print(f"\n{label} NotebookLM Pipeline 开始")

    async with await NotebookLMClient.from_storage() as client:
        print("\n[1/3] 查找 notebook...")
        notebook_id = await find_or_create_notebook(client)

        print(f"\n[2/3] 上传{label} source...")
        source_id = await upload_source(client, notebook_id, md_file)

        print(f"\n[3/3] 生成{label} infographic...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        orientation = RATIO_TO_ORIENTATION.get(ratio, InfographicOrientation.PORTRAIT)
        status = await create_infographic_with_retry(
            client, notebook_id, source_id, prompt, orientation=orientation,
        )
        if not status:
            print(f"    ❌ {label} infographic 创建失败")
            return None

        print(f"    等待生成完成 (task_id={status.task_id[:8]}...)...")
        await client.artifacts.wait_for_completion(
            notebook_id, status.task_id, timeout=300
        )

        await client.artifacts.rename(notebook_id, status.task_id, artifact_name)
        print(f"    已命名: {artifact_name}")

        out_file = str(output_path / f"{artifact_name}.png")
        await client.artifacts.download_infographic(
            notebook_id, out_file, artifact_id=status.task_id
        )
        print(f"    已下载: {out_file}")

        print(f"\n{label} NotebookLM Pipeline 完成")
        return out_file
