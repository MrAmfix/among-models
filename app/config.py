import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-please-use-random-string")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "llmgame")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "llmgame_secret")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "llmgame")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    ADMIN_LOGIN: str = os.getenv("ADMIN_LOGIN", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )

    SESSION_MAX_AGE: int = 60 * 60 * 24 * 7  # 7 days


settings = Settings()
