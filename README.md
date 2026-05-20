# Study AI

**Курсовая работа** · НИУ ВШЭ, факультет ИМиКН, программа «Бизнес-информатика»  
**Участники команды:** Поминова Алёна Игоревна  
                       Чибакова Любовь Анатольевна
                       Артемьева Яна Викторовна
**Научный руководитель:** Улитин Борис Игоревич  
**Год:** 2026

---

## Содержание

1. [О проекте](#1-о-проекте)
2. [Архитектура](#2-архитектура)
3. [Технологический стек](#3-технологический-стек)
4. [Структура проекта](#4-структура-проекта)
5. [Требования к окружению](#5-требования-к-окружению)
6. [Быстрый старт (Docker)](#6-быстрый-старт-docker)
7. [Запуск без Docker](#7-запуск-без-docker)
8. [Переменные окружения](#8-переменные-окружения)
9. [Миграции базы данных](#9-миграции-базы-данных)
10. [API — справочник эндпоинтов](#10-api--справочник-эндпоинтов)
11. [Тестирование](#11-тестирование)
12. [Известные ограничения](#12-известные-ограничения)
13. [Связанные подсистемы](#13-связанные-подсистемы)

---

## 1. О проекте

**Study AI** — образовательная платформа с элементами геймификации, которая автоматически создаёт конспекты учебных материалов с помощью больших языковых моделей (LLM), генерирует флеш-карточки и дорожные карты по изученному документу, а также мотивирует пользователей через систему достижений и серий активности (streak).

Данный репозиторий содержит **backend-подсистему** — монолитное REST API приложение, реализующее:

- управление пользователями и сессиями (регистрация, авторизация, сессионные cookie);
- загрузку и хранение учебных документов (PDF, DOCX, TXT, до 50 МБ);
- интеграцию с LLM-провайдерами (OpenRouter, Groq) для суммаризации;
- диалоговый режим с документом (RAG — Retrieval-Augmented Generation);
- генерацию флеш-карточек и дорожных карт на основе конспекта;
- механику геймификации: серии активности, история событий, достижения.

> **Примечание.** Данная подсистема является индивидуальной частью группового проекта. Модули извлечения текста из файлов (`pdf_service`), LLM-оркестрации (`llm_orchestrator`) и векторного поиска (`vector_search`) реализованы другими участниками команды.

---

## 2. Архитектура

```
┌──────────────────────────────────────────────────────┐
│                    Клиент (SPA)                       │
│           React / HTML · localhost:8000               │
└────────────────────┬─────────────────────────────────┘
                     │ HTTP/1.1 · JSON · Cookie
┌────────────────────▼─────────────────────────────────┐
│              FastAPI + Uvicorn (ASGI)                 │
│                                                       │
│  Роутеры → Сервисный слой → Репозитории               │
│                                                       │
│  /auth   /documents   /chat   /profile                │
└────────┬───────────────────────┬─────────────────────┘
         │                       │
┌────────▼────────┐   ┌──────────▼────────────────────┐
│  PostgreSQL 16  │   │  LLM-провайдер                 │
│  (SQLAlchemy +  │   │  OpenRouter (основной)         │
│   asyncpg)      │   │  Groq          (резервный)     │
└─────────────────┘   └───────────────────────────────┘
```

Подсистема организована по принципу разделения ответственности:

- **Роутеры** — принимают HTTP-запросы, валидируют входные данные через Pydantic, формируют ответы.
- **Сервисный слой** — содержит бизнес-логику (хеширование паролей, streak-расчёты, вызов LLM).
- **Репозитории / SQLAlchemy session** — взаимодействие с базой данных.
- **config.py (pydantic-settings)** — все параметры конфигурации, загружаются из `.env`.

---

## 3. Технологический стек

| Компонент | Технология | Версия |
|---|---|---|
| Язык | Python | 3.11+ |
| Web-фреймворк | FastAPI | 0.111+ |
| ASGI-сервер | Uvicorn | последняя стабильная |
| ORM | SQLAlchemy (async) | 2.0+ |
| Драйвер БД | asyncpg | последняя стабильная |
| СУБД | PostgreSQL | 16 |
| Миграции | Alembic | последняя стабильная |
| Аутентификация | bcrypt + сессионные cookie (passlib) | — |
| HTTP-клиент | httpx (async) | последняя стабильная |
| Валидация | Pydantic v2 | — |
| Контейнеризация | Docker + Docker Compose | Compose v2+ |
| LLM (основной) | OpenRouter · meta-llama/llama-3.3-70b-instruct | — |
| LLM (резервный) | Groq · llama-3.3-70b-versatile | — |

---

## 4. Структура проекта

```
study-ai-backend/
│
├── main.py                    # Точка входа, регистрация роутеров, CORS, StaticFiles
├── config.py                  # Pydantic-settings: все переменные окружения
├── database.py                # AsyncEngine, AsyncSession, Base
│
├── auth/
│   ├── router.py              # POST /auth/register, /auth/login, /auth/logout
│   ├── service.py             # Хеширование паролей, создание/проверка сессий
│   └── models.py              # SQLAlchemy-модели: User, Session
│
├── documents/
│   ├── router.py              # POST/GET /documents, GET /documents/{id}
│   ├── service.py             # Вызов pdf_service, llm_client, сохранение конспекта
│   └── models.py              # Document
│
├── chat/
│   ├── router.py              # POST /chat, GET/POST /chat-sessions, /messages
│   ├── service.py             # Контекстный поиск, вызов LLM
│   └── models.py              # ChatSession, ChatMessage
│
├── flashcards/
│   ├── router.py              # POST/GET /chat-sessions/{id}/cards
│   └── models.py              # Card
│
├── roadmap/
│   ├── router.py              # POST/GET /chat-sessions/{id}/roadmap
│   └── models.py              # RoadmapItem
│
├── profile/
│   ├── router.py              # GET /profile/me, POST /profile/me/event
│   ├── service.py             # Расчёт streak, история событий
│   └── models.py              # ProfileEvent
│
├── llm/
│   ├── llm_client.py          # Прямые вызовы к LLM API (суммаризация, чанкинг)
│   └── llm_orchestrator.py    # Fallback-стратегия: OpenRouter → Groq
│
├── alembic/
│   ├── env.py
│   └── versions/              # Файлы миграций
│
├── files/
│   └── uploads/               # Загружаемые пользователями документы
│
├── Dockerfile
├── docker-compose.yml
├── .env.example               # Шаблон переменных окружения
├── requirements.txt
└── README.md
```

---

## 5. Требования к окружению

### Вариант A — через Docker (рекомендуется)

| Программа | Минимальная версия | Проверка |
|---|---|---|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |

### Вариант Б — локально без Docker

| Программа | Минимальная версия | Проверка |
|---|---|---|
| Python | 3.11+ | `python --version` |
| PostgreSQL | 16 | `psql --version` |
| pip | — | `pip --version` |

### Аппаратные требования

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| CPU | x86-64, 2 ГГц | 4+ ядра |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 10 ГБ | 20 ГБ |
| Сеть | Интернет + VPN | — |

> ⚠️ **Важно.** Для работы с LLM-провайдерами (OpenRouter, Groq) из России необходим активный VPN-сервис. Без VPN запросы к API завершаются с кодом `403 Forbidden`.

---

## 6. Быстрый старт (Docker)

### Шаг 1. Клонирование репозитория

```bash
git clone https://github.com/<ваш-логин>/study-ai-backend.git
cd study-ai-backend
```

### Шаг 2. Создание файла окружения

Скопируйте шаблон и заполните обязательные поля:

```bash
cp .env.example .env
```

Откройте `.env` в любом текстовом редакторе и укажите ключи API:

```bash
# Linux / macOS
nano .env

# Windows
notepad .env
```

Обязательно заполните (минимум один из двух ключей):

```
OPENROUTER_API_KEY=sk-or-v1-...
GROQ_KEY=gsk_...
```

### Шаг 3. Запуск

```bash
docker compose up --build
```

При первом запуске Docker:
1. Соберёт образ приложения (занимает 2–5 минут).
2. Поднимет контейнер PostgreSQL и дождётся его готовности (healthcheck).
3. Автоматически применит все миграции Alembic (`alembic upgrade head`).
4. Запустит Uvicorn на порту `8000`.

После успешного старта в консоли появится:

```
backend_1  | INFO:     Application startup complete.
backend_1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Шаг 4. Проверка работоспособности

Откройте в браузере:

- **Swagger UI (интерактивная документация API):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Главная страница SPA:** http://localhost:8000/

### Шаг 5. Остановка

```bash
# Остановить контейнеры, сохранив данные БД:
docker compose stop

# Остановить и удалить контейнеры (данные БД сохраняются в volume):
docker compose down

# Остановить и полностью удалить все данные (включая БД):
docker compose down -v
```

---

## 7. Запуск без Docker

Этот способ подходит для локальной разработки с горячей перезагрузкой кода.

### Шаг 1. Клонирование репозитория

```bash
git clone https://github.com/<ваш-логин>/study-ai-backend.git
cd study-ai-backend
```

### Шаг 2. Создание и активация виртуального окружения

```bash
# Создать окружение
python -m venv .venv

# Активировать (Linux / macOS)
source .venv/bin/activate

# Активировать (Windows CMD)
.venv\Scripts\activate.bat

# Активировать (Windows PowerShell)
.venv\Scripts\Activate.ps1
```

### Шаг 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 4. Настройка PostgreSQL

Убедитесь, что PostgreSQL запущен локально, и создайте базу данных:

```bash
psql -U postgres
```

```sql
CREATE USER studylab WITH PASSWORD 'studylab';
CREATE DATABASE studylab OWNER studylab;
\q
```

### Шаг 5. Настройка переменных окружения

```bash
cp .env.example .env
```

Для локального запуска (без Docker) измените `DATABASE_URL` в `.env`:

```
DATABASE_URL=postgresql+asyncpg://studylab:studylab@localhost:5432/studylab
```

Заполните ключи API (см. [раздел 8](#8-переменные-окружения)).

### Шаг 6. Применение миграций

```bash
alembic upgrade head
```

Ожидаемый вывод:

```
INFO  [alembic.runtime.migration] Running upgrade  -> a1b2c3d4e5f6, Initial schema
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f6 -> ..., Add profile events
```

### Шаг 7. Запуск сервера

```bash
# Режим разработки с авторестартом при изменении файлов:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Продакшн-режим (без --reload):
uvicorn main:app --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу http://localhost:8000.

---

## 8. Переменные окружения

Все переменные задаются в файле `.env` в корне проекта. Ниже полный перечень:

| Переменная | Обязательная | Значение по умолчанию | Описание |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://studylab:studylab@db:5432/studylab` | URL подключения к PostgreSQL (asyncpg) |
| `SESSION_EXPIRE_SECONDS` | — | `604800` | Время жизни сессии, сек (7 дней) |
| `UPLOAD_DIR` | — | `files/uploads` | Путь для сохранения загруженных файлов |
| `MAX_FILE_SIZE_MB` | — | `10` | Максимальный размер загружаемого файла, МБ |
| `OPENROUTER_API_KEY` | ⚠️* | — | Ключ API OpenRouter |
| `GROQ_KEY` | ⚠️* | — | Ключ API Groq |
| `BASE_URL` | — | `https://api.groq.com/openai/v1/chat/completions` | Базовый URL LLM-провайдера |
| `CURRENT_PROVIDER` | — | `groq` | Активный провайдер: `groq` или `openrouter` |
| `CURRENT_MODEL` | — | `llama-3.3-70b-versatile` | Название модели |
| `LLM_MAX_TOKENS` | — | `1500` | Максимальное число токенов в ответе LLM |
| `LLM_TEMPERATURE` | — | `0.5` | Температура генерации (0.0 – 2.0) |

> ⚠️ \* Необходимо указать хотя бы один из ключей (`OPENROUTER_API_KEY` или `GROQ_KEY`). При отсутствии обоих все эндпоинты, обращающиеся к LLM, будут возвращать ошибку `500`.

### Пример заполненного .env

```dotenv
DATABASE_URL=postgresql+asyncpg://studylab:studylab@db:5432/studylab
SESSION_EXPIRE_SECONDS=604800
UPLOAD_DIR=files/uploads
MAX_FILE_SIZE_MB=50

OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
GROQ_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
CURRENT_PROVIDER=openrouter
CURRENT_MODEL=meta-llama/llama-3.3-70b-instruct
LLM_MAX_TOKENS=1500
LLM_TEMPERATURE=0.5
```

### Получение API-ключей

**OpenRouter:**
1. Зарегистрируйтесь на [openrouter.ai](https://openrouter.ai) (требуется VPN из России).
2. Перейдите в раздел **Keys** → **Create Key**.
3. Скопируйте ключ вида `sk-or-v1-...`.

**Groq:**
1. Зарегистрируйтесь на [console.groq.com](https://console.groq.com) (требуется VPN).
2. Перейдите в раздел **API Keys** → **Create API Key**.
3. Скопируйте ключ вида `gsk_...`.

---

## 9. Миграции базы данных

Проект использует Alembic для версионированного управления схемой БД.

### Применить все миграции (при первом запуске или после обновления)

```bash
alembic upgrade head
```

### Откатить последнюю миграцию

```bash
alembic downgrade -1
```

### Откатить все миграции (сбросить схему)

```bash
alembic downgrade base
```

### Создать новую миграцию после изменения моделей

```bash
alembic revision --autogenerate -m "Краткое описание изменений"
```

После выполнения команды в папке `alembic/versions/` появится новый файл. Просмотрите его перед применением — автогенерация не всегда улавливает сложные изменения (переименование столбцов, изменение типов).

### Просмотр истории миграций

```bash
alembic history --verbose
```

---

## 10. API — справочник эндпоинтов

Интерактивная документация (Swagger UI) доступна по адресу http://localhost:8000/docs после запуска сервера.

### Аутентификация

| Метод | Путь | Описание | Требует cookie |
|---|---|---|---|
| `POST` | `/auth/register` | Регистрация нового пользователя | Нет |
| `POST` | `/auth/login` | Вход; в ответе устанавливается `session_id` cookie (TTL 7 дней) | Нет |
| `POST` | `/auth/logout` | Выход; сессия удаляется из БД | Да |

Пример запроса на регистрацию:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@hse.ru", "password": "MyPass123!"}'
```

### Документы

| Метод | Путь | Описание | Требует cookie |
|---|---|---|---|
| `POST` | `/documents` | Загрузка файла; создаёт конспект через LLM | Да |
| `GET` | `/documents` | Список всех конспектов текущего пользователя | Да |
| `GET` | `/documents/{id}` | Конспект по идентификатору | Да |
| `DELETE` | `/documents/{id}` | Удаление документа и связанных данных | Да |

Пример загрузки файла:

```bash
curl -X POST http://localhost:8000/documents \
  -b "session_id=<ваш_session_id>" \
  -F "file=@lecture.pdf"
```

### Чат с документом

| Метод | Путь | Описание | Требует cookie |
|---|---|---|---|
| `POST` | `/chat` | Отправка вопроса в рамках чат-сессии | Да |
| `GET` | `/chat-sessions` | Список чат-сессий пользователя | Да |
| `GET` | `/chat-sessions/{id}/messages` | История сообщений сессии | Да |

### Флеш-карточки и дорожная карта

| Метод | Путь | Описание | Требует cookie |
|---|---|---|---|
| `POST` | `/chat-sessions/{id}/cards` | Генерация флеш-карточек из конспекта | Да |
| `GET` | `/chat-sessions/{id}/cards` | Получение карточек сессии | Да |
| `POST` | `/chat-sessions/{id}/roadmap` | Генерация дорожной карты | Да |
| `GET` | `/chat-sessions/{id}/roadmap` | Получение дорожной карты | Да |

### Профиль

| Метод | Путь | Описание | Требует cookie |
|---|---|---|---|
| `GET` | `/profile/me` | Профиль пользователя, текущий streak, статистика | Да |
| `POST` | `/profile/me/event` | Фиксация события активности (для обновления streak) | Да |

### Коды ответов

| Код | Значение |
|---|---|
| `200` | Успешный запрос |
| `201` | Ресурс создан |
| `400` | Некорректные входные данные |
| `401` | Не авторизован (отсутствует или истёк cookie) |
| `404` | Ресурс не найден |
| `413` | Файл превышает допустимый размер |
| `500` | Внутренняя ошибка сервера (в т.ч. недоступность LLM) |

---

## 11. Тестирование

### Функциональное тестирование через Swagger UI

1. Откройте http://localhost:8000/docs.
2. Выполните `POST /auth/register` → `POST /auth/login` (Swagger автоматически сохранит cookie).
3. Последовательно проверяйте остальные эндпоинты через интерфейс.

### Функциональное тестирование через curl

```bash
# 1. Регистрация
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@hse.ru", "password": "Test1234!"}' \
  -c cookies.txt

# 2. Вход
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@hse.ru", "password": "Test1234!"}' \
  -c cookies.txt -b cookies.txt

# 3. Загрузка документа (после входа)
curl -X POST http://localhost:8000/documents \
  -b cookies.txt \
  -F "file=@/путь/к/файлу.pdf"

# 4. Просмотр профиля
curl http://localhost:8000/profile/me -b cookies.txt
```

### Нагрузочное тестирование

Простой тест с 50 конкурентными запросами (требует установленного httpx):

```bash
python - <<'EOF'
import asyncio, httpx, time

COOKIES = {"session_id": "<ваш_session_id>"}

async def single_request(client):
    r = await client.get("http://localhost:8000/profile/me", cookies=COOKIES)
    return r.status_code, r.elapsed.total_seconds()

async def main():
    async with httpx.AsyncClient() as client:
        start = time.time()
        results = await asyncio.gather(*[single_request(client) for _ in range(50)])
    latencies = [r[1] for r in results]
    errors = sum(1 for r in results if r[0] != 200)
    latencies.sort()
    print(f"Запросов: 50 | Ошибок: {errors}")
    print(f"Среднее: {sum(latencies)/len(latencies)*1000:.0f} мс")
    print(f"P95: {latencies[int(len(latencies)*0.95)]*1000:.0f} мс")
    print(f"P99: {latencies[int(len(latencies)*0.99)]*1000:.0f} мс")

asyncio.run(main())
EOF
```

### Результаты тестирования (из пояснительной записки)

| Тест | Результат |
|---|---|
| Регистрация пользователя | HTTP 201, время ответа 894 мс |
| Аутентификация + сессия | HTTP 200, время ответа 76 мс |
| Загрузка PDF + конспект | HTTP 201, время 47,7 с (с учётом LLM) |
| Превышение лимита файла | HTTP 413 |
| Генерация флеш-карточек | 15 карточек успешно |
| Streak-механика | currentStreak корректно инкрементируется |
| 50 конкурентных GET /profile/me | 0 ошибок, p95 = 1338 мс (локально) |

---

## 12. Известные ограничения

| Ограничение | Причина | Обходное решение |
|---|---|---|
| LLM недоступен без VPN из России | Региональные блокировки OpenRouter и Groq | Подключить VPN, сменить `BASE_URL` на незаблокированный прокси |
| p95 > 200 мс на локальном Docker | Ограниченные ресурсы ПК + накладные расходы Docker | На выделенном сервере с SSD ожидается p95 ≤ 200 мс |
| Один API-ключ Groq без разделения квот | Ограничение бесплатного тарифа | Использовать OpenRouter как основной провайдер |
| Суммаризация объёмных документов занимает до 60 с | Чанкинг + несколько LLM-запросов (map-reduce) | Не нагружать одновременно; rate limit провайдера |

---

## 13. Связанные подсистемы

Данный репозиторий является частью группового проекта **Study AI**. Остальные подсистемы:

| Подсистема | Описание |
|---|---|
| **Frontend** | SPA-интерфейс (React); раздаётся бэкендом через `/` |
| **pdf_service** | Извлечение текста из PDF/DOCX, OCR, чанкинг |
| **llm_orchestrator** | Управление промптами, конфигурация LLM-вызовов |
| **vector_search** | Генерация эмбеддингов (sentence-transformers), RAG-поиск |
| **Общее ТЗ** | Техническое задание на всю систему |

---

*Документ составлен в соответствии с требованиями к оформлению технической документации курсовых работ НИУ ВШЭ (2025/2026 уч. год).*
