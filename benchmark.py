import asyncio
import httpx
import time
from pathlib import Path
from pdf_service import process_file, blocks_to_text

# === КЛЮЧИ ===
HF_KEY = "your_key"
GEMINI_KEY = "your_key"
GROQ_KEY = "your_key"
# ==================

async def call_llm(text, prompt, model, api_key):
    model = model.strip().replace('"', '').replace("'", "")
    api_key = api_key.strip().replace('"', '').replace("'", "")
    
    is_gemini = "gemini" in model.lower()
    # Определяем Groq по префиксу ключа или названию модели
    is_groq = api_key.startswith("gsk_") 
    
    full_prompt = prompt.format(text=text)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # 1. ЛОГИКА ДЛЯ GEMINI
            if is_gemini:
                short_model = model.replace("models/", "")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{short_model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {"temperature": 0.5, "maxOutputTokens": 2000}
                }
                response = await client.post(url, json=payload)
                
                if response.status_code == 429:
                    return "Ошибка: Лимит запросов Google исчерпан (429)."
                if response.status_code != 200:
                    return f"Ошибка Gemini API {response.status_code}: {response.text}"
                
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]

            # 2. ЛОГИКА ДЛЯ GROQ И HUGGING FACE
            else:
                # Меняем URL в зависимости от провайдера
                if is_groq:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                else:
                    url = "https://router.huggingface.co/v1/chat/completions"
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Ты профессиональный ассистент по учебе. Делай подробные конспекты."},
                        {"role": "user", "content": full_prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 2000
                }
                
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    return f"Ошибка API {response.status_code}: {response.text}"
                
                return response.json()["choices"][0]["message"]["content"]

        except Exception as e:
            return f"Критическая ошибка соединения: {e}"

async def complex_benchmark():
    file_name = "study_material.pdf"
    if not Path(file_name).exists():
        print(f"❌ Файл {file_name} не найден!")
        return

    print(f"📄 Парсим документ...")
    blocks = process_file(Path(file_name))
    full_text = blocks_to_text(blocks)
    
    prompt = "Сделай подробный конспект этого текста на русском языке: {text}"
    
    # ТЕПЕРЬ ЗДЕСЬ 3 МОДЕЛИ
    test_configs = [
        {
            "name": "Gemini 2.5 Flash (Google)", 
            "model": "gemini-2.5-flash", 
            "key": GEMINI_KEY
        },
        {
            "name": "Llama 3.3 70B (Groq)", 
            "model": "llama-3.3-70b-versatile", 
            "key": GROQ_KEY
        },
        {
            "name": "Qwen 2.5 72B (HuggingFace)", 
            "model": "Qwen/Qwen2.5-72B-Instruct", 
            "key": HF_KEY
        }
    ]
    
    for cfg in test_configs:
        print(f"\n🚀 ТЕСТИРУЕМ: {cfg['name']}...")
        start = time.perf_counter()
        
        res = await call_llm(full_text, prompt, cfg['model'], cfg['key'])
        
        duration = time.perf_counter() - start
        print(f"⏱ Время: {duration:.2f} сек")
        # Показываем чуть больше текста для оценки качества
        print(f"📝 Конспект (первые 500 симв.):\n{res[:500]}...")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(complex_benchmark())