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


settings = Settings()
