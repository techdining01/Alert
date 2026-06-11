from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

   
    database_url: str = 'postgresql+asyncpg://postgres:idrees@localhost:5432/notification_db'
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379




settings = Settings()   