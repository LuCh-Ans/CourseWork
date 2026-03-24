from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/studylab"

    # Sessions
    SESSION_EXPIRE_SECONDS: int = 7 * 24 * 3600  # 7 дней

    # File upload
    UPLOAD_DIR: str = "files/uploads"
    MAX_FILE_SIZE_MB: int = 10

    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3
    YAGPT_FOLDER_ID: str = ""


settings = Settings()
