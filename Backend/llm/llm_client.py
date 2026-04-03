import os
import httpx

LLM_API_KEY = "ollama"
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

OLLAMA_ENDPOINT = "http://localhost:11434/v1/chat/completions"

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


async def summarize(text: str) -> str:
    chunks = _split_into_chunks(text)

    if len(chunks) == 1:
        return await _summarize_chunk(chunks[0], _USER_PROMPT_TEMPLATE)

    partial_summaries = []
    for i, chunk in enumerate(chunks, start=1):
        partial = await _summarize_chunk(chunk, _USER_PROMPT_TEMPLATE)
        partial_summaries.append(f"Part {i}:\n{partial}")

    combined = "\n\n".join(partial_summaries)
    return await _summarize_chunk(combined, _COMBINE_PROMPT_TEMPLATE)


def _split_into_chunks(text: str, max_size: int = 5000) -> list[str]:
    return [text[i:i + max_size] for i in range(0, len(text), max_size)]


async def _summarize_chunk(text: str, prompt_template: str) -> str:
    headers = {
        "Authorization": "Bearer ollama",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt_template.format(text=text)},
        ],
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_ENDPOINT, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"[OLLAMA] API error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected response format from Ollama: {data}") from exc
