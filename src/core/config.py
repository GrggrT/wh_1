from pydantic import AliasChoices, Field
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

    # Daily digest delivered to owner_tg_id
    daily_digest_enabled: bool = True
    daily_digest_hour: int = 22  # local hour (timezone setting)

    # Auto-close breaks running longer than this many hours
    max_break_hours: int = 4

    # FastAPI admin panel — empty admin_password disables the panel
    admin_password: str = ""
    admin_username: str = "owner"
    # Failed-auth rate limit (per client IP): K failures within window_seconds → block_seconds.
    admin_auth_max_failures: int = 5
    admin_auth_window_seconds: int = 60
    admin_auth_block_seconds: int = 300
    # Railway/Heroku-style $PORT is preferred; ADMIN_PORT overrides for local use.
    admin_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("ADMIN_PORT", "PORT"),
    )
    admin_host: str = "0.0.0.0"  # noqa: S104  # bind all on hosting platforms

    # Webhook mode — empty webhook_url falls back to long polling
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_path: str = "/tg/webhook"

    # OpenAI Whisper transcription for voice notes — empty key disables it
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    whisper_language: str = "ru"

    # Sentry error tracking — empty DSN disables it
    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.0


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
