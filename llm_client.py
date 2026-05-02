import httpx
from config import settings

# Константы промптов
_SYSTEM_PROMPT = (
    "You are a professional academic assistant for the Study Lab platform. "
    "Your goal is to help students analyze educational materials accurately and structurally. "
    "Always use Markdown for formatting (bullet points, bold text, headers) to make the output easy to read."
)

_USER_PROMPT_TEMPLATE = (
    "Analyze the following educational material fragment. "
    "Create a concise summary by highlighting: \n"
    "1. Main ideas and key concepts.\n"
    "2. Important definitions and formulas.\n"
    "3. Significant conclusions.\n\n"
    "IMPORTANT: Write the summary in the same language as the source text.\n\n"
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

_ENDPOINTS: dict[str, str] = {
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{settings.CURRENT_MODEL}:generateContent?key={settings.GEMINI_API_KEY}",
     "yagpt": "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
}
async def call_llm(context: str, query: str) -> str:
    """
    Универсальная функция для общения с LLM. 
    Используется для RAG (вопрос-ответ) и суммаризации.
    """
    if not context or len(context.strip()) < 5:
        return "Контекст для ответа не найден в базе данных."
    final_prompt = _RAG_PROMPT_TEMPLATE.format(text=context, query=query)
    return await _openai_compat_summarize(text="", prompt_template=final_prompt)
async def summarize(text: str) -> str:
    """
    Твоя текущая функция суммаризации. 
    Она вызывает call_llm (через приватные методы) для обработки чанков.
    """
    max_chunk_size = 15000 
    chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]

    if len(chunks) == 1:
        return await _openai_compat_summarize(chunks[0], _USER_PROMPT_TEMPLATE)

    partial_summaries = []
    for i, chunk in enumerate(chunks, start=1):
        partial = await call_llm(chunk, _USER_PROMPT_TEMPLATE)
        partial_summaries.append(f"Part {i}:\n{partial}")

    combined = "\n\n".join(partial_summaries)
    return await call_llm(combined, _COMBINE_PROMPT_TEMPLATE)

async def _summarize_chunk(text: str, prompt_template: str) -> str:
    """Выбор метода суммаризации в зависимости от провайдера"""
    if settings.CURRENT_PROVIDER == "yagpt":
        return await _yagpt_summarize(text, prompt_template)
    return await _openai_compat_summarize(text, prompt_template)


async def _openai_compat_summarize(text: str, prompt_template: str) -> str:
    """
    Универсальная функция: поддерживает Gemini и Hugging Face (Qwen).
    """
    full_content = f"{prompt_template}\n\n{text}".strip()

    async with httpx.AsyncClient() as client:
        try:
            if settings.CURRENT_PROVIDER == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{settings.CURRENT_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                )
                payload = {
                    "contents": [{"parts": [{"text": full_content}]}],
                    "generationConfig": {
                        "maxOutputTokens": settings.LLM_MAX_TOKENS,
                        "temperature": settings.LLM_TEMPERATURE
                    }
                }
                headers = {"Content-Type": "application/json"}
            
            else:
                url = settings.BASE_URL 
                headers = {
                    "Authorization": f"Bearer {settings.HF_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": settings.CURRENT_MODEL,
                    "messages": [{"role": "user", "content": full_content}],
                    "max_tokens": settings.LLM_MAX_TOKENS,
                    "temperature": settings.LLM_TEMPERATURE
                }

            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            
            if response.status_code != 200:
                print(f"--- {settings.CURRENT_PROVIDER} Error Body: {response.text} ---")
                raise RuntimeError(f"[{settings.CURRENT_PROVIDER}] Error {response.status_code}")

            data = response.json()
            if settings.CURRENT_PROVIDER == "gemini":
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                return data['choices'][0]['message']['content']

        except Exception as e:
            raise RuntimeError(f"LLM request failed: {str(e)}")
async def _yagpt_summarize(text: str, prompt_template: str) -> str:
    """Специфичный метод для YandexGPT"""
    if not settings.YAGPT_FOLDER_ID:
        raise RuntimeError("YAGPT_FOLDER_ID is not set in .env")
        
    headers = {
        "Authorization": f"Api-Key {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{settings.YAGPT_FOLDER_ID}/yandexgpt",
        "completionOptions": {
            "stream": False,
            "temperature": settings.LLM_TEMPERATURE,
            "maxTokens": str(settings.LLM_MAX_TOKENS),
        },
        "messages": [
            {"role": "system", "text": _SYSTEM_PROMPT},
            {"role": "user", "text": prompt_template.format(text=text)},
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