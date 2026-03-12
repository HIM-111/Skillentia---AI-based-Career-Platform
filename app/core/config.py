from pydantic import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Skillentia"
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:8b"
    TAVILY_API_KEY: str = ""

    # OpenAI (optional)
    LLM_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Local auth/session database
    AUTH_DB_PATH: str = "data/auth.db"
    AUTH_SESSION_HOURS: int = 168
    CONTEXT_ENCRYPTION_KEY: str = ""
    CONTEXT_KEY_PATH: str = "data/context.key"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
