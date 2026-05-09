from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    database_url: str = "postgresql+asyncpg://timetrack:timetrack@localhost:5432/timetrack"
    owner_tg_id: int
    log_level: str = "INFO"
    timezone: str = "Europe/Warsaw"

    # Auto clock-out: shifts open longer than this are force-closed
    max_shift_hours: int = 14
    # Send "still working?" reminder after a shift has been open this long
    reminder_after_hours: int = 8
    # How often the scheduler loop wakes up (seconds)
    scheduler_interval_seconds: int = 300


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
