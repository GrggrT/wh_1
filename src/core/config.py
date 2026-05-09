from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    database_url: str = "postgresql+asyncpg://timetrack:timetrack@localhost:5432/timetrack"
    owner_tg_id: int
    log_level: str = "INFO"
    timezone: str = "Europe/Warsaw"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
