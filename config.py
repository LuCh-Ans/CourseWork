import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")


    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "")
    POPPLER_PATH: str = os.getenv("POPPLER_PATH", "")

    
    HF_API_KEY: str = os.getenv("HF_API_KEY", "") 
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    

    BASE_URL: str = os.getenv("BASE_URL", "https://api-inference.huggingface.co/v1/chat/completions")

    CURRENT_PROVIDER: str = os.getenv("CURRENT_PROVIDER", "gemini")
    CURRENT_MODEL: str = os.getenv("CURRENT_MODEL", "gemini-1.5-flash") # Для HF тут будет Qwen/...
    
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", 1500))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", 0.5))

settings = Settings()

if __name__ == "__main__":
    print(f"--- Диагностика конфига ---")
    print(f"Ищем .env тут: {ENV_PATH}")
    print(f"Provider: {settings.CURRENT_PROVIDER}")
    print(f"Model: {settings.CURRENT_MODEL}")
    print(f"Base URL: {settings.BASE_URL}")
    print(f"HF_KEY: {'ОК' if settings.HF_API_KEY else 'ПУСТО'}")