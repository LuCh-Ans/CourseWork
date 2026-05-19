import httpx
from config import settings

_SYSTEM_PROMPT = (
    "You are a professional academic assistant for the Study Lab platform. "
    "Your goal is to help students analyze educational materials accurately and structurally. "
    "Always use Markdown for formatting (bullet points, bold text, headers). "
    "STRICT RULE FOR MATH: wrap ALL formulas with $ for inline and $$ for block. "
    "Example inline: $f'(x) < 0$. Example block: $$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$. "
    "NEVER use \\( \\) or \\[ \\] or plain brackets for math. Only $ and $$."
)

_USER_PROMPT_TEMPLATE = (
    "Analyze the following educational material fragment. "
    "Create a concise summary in Russian by highlighting: \n"
    "1. Main ideas and key concepts.\n"
    "2. Important definitions and formulas.\n"
    "3. Significant conclusions.\n\n"
    "IMPORTANT: Write in Russian. For ALL math use ONLY $formula$ inline or $$formula$$ block. "
    "Never use ( ) or [ ] for math.\n\n"
    "Text:\n{text}"
)

_COMBINE_PROMPT_TEMPLATE = (
    "Below are partial summaries of different sections of a single educational document. "
    "Combine them into one coherent, logically structured final summary. "
    "Use clear headers and ensure no key information is lost. "
    "The final output must be professional and formatted with Markdown.\n\n"
    "IMPORTANT: Write in the same language as the summaries.\n\n"
    "Summaries:\n{text}"
)

_RAG_PROMPT_TEMPLATE = (
    "You are provided with specific fragments from a document (Context) and a user's question. "
    "Answer the question based ONLY on the provided context. "
    "If the context does not contain the answer, strictly reply: 'The document does not provide information on this topic.' "
    "Do not use any external knowledge or make up facts.\n\n"
    "CONTEXT:\n{text}\n\n"
    "USER QUESTION:\n{query}"
)


async def call_llm(context: str, query: str) -> str:
    if not context or len(context.strip()) < 5:
        return "Контекст для ответа не найден в базе данных."
    final_prompt = _RAG_PROMPT_TEMPLATE.format(text=context, query=query)
    return await _request(final_prompt)


async def summarize(text: str) -> str:
    max_chunk_size = 15000
    chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]

    if len(chunks) == 1:
        return await _request(_USER_PROMPT_TEMPLATE.format(text=chunks[0]))

    partial_summaries = []
    for i, chunk in enumerate(chunks, start=1):
        prompt = _USER_PROMPT_TEMPLATE.format(text=chunk) + f"\n\n(Part {i} of {len(chunks)})"
        partial = await _request(prompt)
        partial_summaries.append(f"Part {i}:\n{partial}")

    combined = "\n\n".join(partial_summaries)
    return await _request(_COMBINE_PROMPT_TEMPLATE.format(text=combined))


async def _request(full_content: str) -> str:

    try:
        return await _openrouter_request(full_content)
    except Exception as e:
        print(f"OpenRouter failed: {e}, falling back to Groq...", flush=True)
        return await _groq_request(full_content)


async def _openrouter_request(full_content: str) -> str:
    if not settings.OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_KEY is not set")

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "StudyLab"
    }
    payload = {
        "model": settings.CURRENT_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": full_content}
        ],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")
        return response.json()['choices'][0]['message']['content']


async def _groq_request(full_content: str) -> str:
    if not settings.GROQ_KEY:
        raise RuntimeError("GROQ_KEY is not set")

    headers = {
        "Authorization": f"Bearer {settings.GROQ_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "StudyLab"
    }
    payload = {
        "model": settings.CURRENT_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": full_content}
        ],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers
        )
        if response.status_code != 200:
            raise RuntimeError(f"Groq error {response.status_code}: {response.text}")
        return response.json()['choices'][0]['message']['content']


async def _openai_compat_summarize(text: str, prompt_template: str) -> str:

    full_content = f"{prompt_template}\n\n{text}".strip()
    return await _request(full_content)