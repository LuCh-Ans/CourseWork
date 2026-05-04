import httpx
import asyncio

async def check():
    # Заменяем на версию 2.0 Flash, так как 1.5 у вас недоступна
    model_name = "gemini-2.0-flash-lite" 
    key = "AIzaSyBKqQoh44pH2cOwxWRSAm-3O1GjxpZwZAw"
    
    # Используем v1beta, так как 2.0 часто еще в бете
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
    
    payload = {
        "contents": [{"parts": [{"text": "Проверка модели 2.0"}]}]
    }
    
    async with httpx.AsyncClient() as client:
        
        res = await client.post(url, json=payload)
        print(f"Статус: {res.status_code}")
        if res.status_code == 200:
            print("Ответ:", res.json()['candidates'][0]['content']['parts'][0]['text'])
        else:
            print("Ошибка:", res.text)

asyncio.run(check())