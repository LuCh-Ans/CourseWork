from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "postgresql+asyncpg://studylab:studylab@db:5432/studylab"
    SESSION_EXPIRE_SECONDS: int = 604800
    UPLOAD_DIR: str = "files/uploads"
    MAX_FILE_SIZE_MB: int = 10

    TESSERACT_PATH: str = "/usr/bin/tesseract"
    POPPLER_PATH: str = ""

    GROQ_API_KEY: str = ""  
    GEMINI_API_KEY: str = ""

    BASE_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    CURRENT_PROVIDER: str = "groq"
    CURRENT_MODEL: str = "llama-3.3-70b-versatile"

    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3


settings = Settings()

if __name__ == "__main__":
    print(f"Ищем .env: {BASE_DIR / '.env'} — {'ЕСТЬ' if (BASE_DIR / '.env').exists() else 'НЕТ'}")
    print(f"Provider: {settings.CURRENT_PROVIDER}")
    print(f"Model: {settings.CURRENT_MODEL}")
    print(f"GROQ_KEY: {'OK' if settings.GROQ_KEY else 'ПУСТО'}")