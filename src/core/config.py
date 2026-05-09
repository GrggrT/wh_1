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

    # Supabase Storage for shift photos (optional — empty disables uploads)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "shift-photos"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
