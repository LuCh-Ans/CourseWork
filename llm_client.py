import os
import httpx

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

_ENDPOINTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "qwen":   "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "yagpt":  "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
}

_SYSTEM_PROMPT = (
    "You are a helpful academic assistant. "
    "Your job is to summarize educational materials clearly and concisely."
)

_USER_PROMPT_TEMPLATE = (
    "Summarize the following educational material. "
    "Highlight the main ideas, key concepts, and important conclusions. "
    "Write in the same language as the source text.\n\n"
    "Text:\n{text}"
)

_COMBINE_PROMPT_TEMPLATE = (
    "Below are summaries of consecutive parts of a single educational document. "
    "Combine them into one coherent summary. "
    "Keep the main ideas, key concepts, and important conclusions. "
    "Write in the same language as the summaries.\n\n"
    "{text}"
)


async def summarize(chunks: list[str]) -> str:
    """
    Accepts a list of text chunks from pdf_service.limit().
    If one chunk — summarizes directly.
    If multiple — summarizes each chunk, then merges into one final summary.
    """
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY environment variable is not set.")

    if len(chunks) == 1:
        return await _summarize_chunk(chunks[0], _USER_PROMPT_TEMPLATE)

    # Map: summarize each chunk separately
    partial_summaries = []
    for i, chunk in enumerate(chunks, start=1):
        partial = await _summarize_chunk(chunk, _USER_PROMPT_TEMPLATE)
        partial_summaries.append(f"Part {i}:\n{partial}")

    # Reduce: merge all partial summaries into one
    combined = "\n\n".join(partial_summaries)
    return await _summarize_chunk(combined, _COMBINE_PROMPT_TEMPLATE)


async def _summarize_chunk(text: str, prompt_template: str) -> str:
    if LLM_PROVIDER == "yagpt":
        return await _yagpt_summarize(text, prompt_template)
    return await _openai_compat_summarize(text, prompt_template)


async def _openai_compat_summarize(text: str, prompt_template: str) -> str:
    endpoint = _ENDPOINTS.get(LLM_PROVIDER)
    if not endpoint:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'. "
            f"Valid options: {list(_ENDPOINTS.keys())}"
        )

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt_template.format(text=text)},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(endpoint, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"[{LLM_PROVIDER.upper()}] API error {response.status_code}: {response.text}"
        )

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected response format from {LLM_PROVIDER}: {data}") from exc


async def _yagpt_summarize(text: str, prompt_template: str) -> str:
    folder_id = os.getenv("YAGPT_FOLDER_ID", "")
    if not folder_id:
        raise RuntimeError("YAGPT_FOLDER_ID environment variable is not set.")

    headers = {
        "Authorization": f"Api-Key {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt",
        "completionOptions": {
            "stream": False,
            "temperature": LLM_TEMPERATURE,
            "maxTokens": str(LLM_MAX_TOKENS),
        },
        "messages": [
            {"role": "system", "text": _SYSTEM_PROMPT},
            {"role": "user",   "text": prompt_template.format(text=text)},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(_ENDPOINTS["yagpt"], headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"[YAGPT] API error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["result"]["alternatives"][0]["message"]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected YaGPT response format: {data}") from exc
