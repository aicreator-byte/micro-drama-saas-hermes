import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Micro Drama SaaS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://drama_user:drama_pass@localhost:5432/micro_drama_saas"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60  # 30 days

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # File storage
    UPLOAD_DIR: Path = Path("/home/hatch/workspace/micro-drama-saas/hermes/uploads")
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Google Account limits
    MAX_GOOGLE_ACCOUNTS_PER_USER: int = 20

    # Google OAuth redirect URI (must match the frontend callback page
    # and the URI registered in Google Cloud Console)
    GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:3000/dashboard/google-accounts/callback",
    )

    # Browser login (Flow Bridge, Di order 2026-11-17 22:22 WIB):
    # login Google biasa lewat browser per akun — TANPA Cloud Console.
    # Satu profil browser persisten per akun di bawah dir ini.
    BROWSER_PROFILE_DIR: Path = Path(os.getenv(
        "BROWSER_PROFILE_DIR",
        "/home/hatch/workspace/micro-drama-saas/hermes/browser-profiles",
    ))
    FLOW_URL: str = os.getenv(
        "FLOW_URL", "https://labs.google/fx/tools/flow"
    )
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"

    # AI Provider (for LLM integration)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "nvidia")
    AI_MODEL: str = os.getenv("AI_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Ensure upload directory exists
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)