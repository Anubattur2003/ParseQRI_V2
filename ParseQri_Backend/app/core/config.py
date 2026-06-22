from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Resolve .env next to ParseQri_Backend so uvicorn works from any cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3306/parseqri"
    SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # Default to 30 days
    
    # Optional Redis configuration (can be disabled)
    REDIS_URL: Optional[str] = None
    
    # Optional ChromaDB configuration
    CHROMA_PERSIST_DIR: Optional[str] = "./data/chroma_storage"
    
    # Google API configuration for Text-to-SQL functionality
    GOOGLE_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra environment variables
    )

settings = Settings()