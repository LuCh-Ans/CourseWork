import requests
import json
import time

# Конфигурация
BASE_URL = "http://127.0.0.1:8000"
TEST_PDF_PATH = r"C:\Users\yanaa\Downloads\Диплом.pdf"

def test_rag_system(file_path):
    print(f"--- Начинаем полный тест RAG-системы ---")
    
    # ЭТАП 1: Загрузка и индексация
    upload_url = f"{BASE_URL}/upload"
    print(f"\n1. Отправка файла на сервер: {file_path}")
    
    try:
        start_time = time.time()
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "application/pdf")}
            # Ставим timeout=None, так как OCR и LLM могут работать долго (до 2-3 минут)
            response = requests.post(upload_url, files=files, timeout=None)
        
        if response.status_code != 200:
            print(f"❌ Ошибка загрузки {response.status_code}: {response.text}")
            return

        data = response.json()
        print(f"✅ Файл обработан за {time.time() - start_time:.2f} сек.")
        print(f"📝 Первичный конспект:\n{data.get('summary', 'Конспект не получен')[:500]}...")

        # ЭТАП 2: Тестирование вопроса (RAG)
        # Если ты уже создала эндпоинт /ask в main.py
        ask_url = f"{BASE_URL}/ask"
        question = "Кто выдал этот диплом и за какой трек?" # Пример вопроса по твоему файлу
        
        print(f"\n2. Тестируем поиск (RAG). Вопрос: '{question}'")
        
        # Передаем вопрос в JSON
        ask_payload = {"question": question}
        ask_response = requests.post(ask_url, json=ask_payload, timeout=None)
        
        if ask_response.status_code == 200:
            answer_data = ask_response.json()
            print(f"✅ Ответ от системы:\n{answer_data.get('answer')}")
        else:
            print(f"⚠️ Эндпоинт /ask пока не доступен или выдал ошибку: {ask_response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка в ходе теста: {e}")

if __name__ == "__main__":
    test_rag_system(TEST_PDF_PATH)