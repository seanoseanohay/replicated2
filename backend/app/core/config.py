import warnings
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bundleanalyzer"
    REDIS_URL: str = "redis://localhost:6379/0"
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "bundles"
    MAX_BUNDLE_SIZE_MB: int = 500
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-prod"
    ANTHROPIC_API_KEY: str = ""
    AI_ENABLED: bool = False
    AI_MODEL: str = "claude-opus-4-6"
    CORS_ALLOWED_ORIGINS: str = "*"          # comma-separated or "*"
    DB_POOL_SIZE: int = 5
    DB_POOL_OVERFLOW: int = 10
    RATE_LIMIT_UPLOAD: str = "10/minute"     # slowapi format
    RATE_LIMIT_AI: str = "20/minute"         # slowapi format
    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALLOW_REGISTRATION: bool = True
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "bundleanalyzer@example.com"
    APP_BASE_URL: str = "http://localhost:5173"

    @model_validator(mode="after")
    def check_secret_key(self):
        if self.APP_ENV not in ("development", "test") and self.SECRET_KEY == "dev-secret-key-change-in-prod":
            warnings.warn("SECRET_KEY is set to the default dev value in a non-development environment!", stacklevel=2)
        return self

    def get_cors_origins(self) -> list[str]:
        if self.CORS_ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
