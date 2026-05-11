# Construction Time-Tracking Telegram Bot

Russian-language single-tenant Telegram bot that tracks construction crew work shifts. Workers clock in/out via Telegram with location verification and photos; the owner gets payroll-ready Excel exports, an admin web panel, and scheduled digests.

Stack: **Python 3.12** · **aiogram 3** · **FastAPI** · **SQLAlchemy 2 async + asyncpg** · **PostgreSQL 16 + PostGIS** · **Alembic** · **Jinja2** · **structlog** · **ruff + mypy --strict** · **pytest**.

## Features

- **Shift tracking** — `/start`-button flow with site selection, location check vs. site geofence, optional start/end photos
- **Crews & roles** — owner manages foremen; foremen invite workers via 6-char codes (`/invite`, `/join`); per-crew default hourly rate; transfer, remove, leave-crew, archived sites
- **Rates & earnings** — site-level and user-level hourly rates (PLN), automatic earnings computation, break-time subtraction (`/break_start`, `/break_stop`, `/break_status`, retroactive break edits)
- **Reports** — `/today`, `/me_yesterday`, `/week`, `/month`, `/me YYYY-MM`, `/active`, `/stats`; foreman variants `/crew_today`/`/crew_week`/`/crew_month`/`/crew_shifts`; XLSX export `/export YYYY-MM` and `/crew_export YYYY-MM`
- **Geofencing** — owner/foreman draw site polygons by sending location messages (`/geofence_set`, `/geofence_save`)
- **Audit & retroactive edits** — every admin action lands in `audit_log`; `/shifts`, `/edit_shift`, `/delete_shift`, `/restore_shift`, `/add_break`, `/edit_break`, `/delete_break`, `/admin_audit`, `/audit`
- **Voice notes** — Whisper transcription appends to active shift (`F.voice` handler, OpenAI API)
- **Photo archive** — start/end photos uploaded to Supabase Storage; `file_id` fallback when storage is disabled
- **Scheduled jobs** — reminders, stale-shift auto-close, stale-break auto-close, daily/weekly/monthly digests to owner
- **Admin web panel** (FastAPI + Jinja2 + Chart.js) — `/`, `/users`, `/sites`, `/shifts` (filterable), `/calendar`, `/audit` (filterable). HTTP Basic auth.
- **Webhook or polling** — same FastAPI process can serve Telegram webhook with `X-Telegram-Bot-Api-Secret-Token` validation; falls back to long-polling when webhook env is empty

## Setup

### Requirements
- Python 3.12+
- PostgreSQL 16+ with extensions `postgis` and `btree_gist`
- Telegram bot token (`@BotFather`)
- Optional: Supabase Storage for photos, OpenAI API key for Whisper

### Local install
```bash
git clone https://github.com/GrggrT/wh_1.git
cd wh_1
pip install -e ".[dev]"

cp .env.example .env       # fill in BOT_TOKEN, DATABASE_URL, OWNER_TG_ID, etc.

# database (one-time)
createdb timetrack
psql timetrack -c "CREATE EXTENSION postgis; CREATE EXTENSION btree_gist;"
python -m alembic upgrade head

python -m src.bot.main
```

### Environment variables
See [.env.example](./.env.example). Required: `BOT_TOKEN`, `DATABASE_URL`, `OWNER_TG_ID`, `TIMEZONE`. Optional: `ADMIN_PASSWORD` (enables admin panel), `WEBHOOK_URL`+`WEBHOOK_SECRET` (enables webhook instead of polling), `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY` (enables photo archive), `OPENAI_API_KEY` (enables Whisper), `MAX_SHIFT_HOURS`, `REMINDER_AFTER_HOURS`, `MAX_BREAK_HOURS`, `DAILY_DIGEST_HOUR`.

## Development
```bash
ruff check src tests
mypy src
pytest -q
```

CI runs the same three checks on every push (`.github/workflows/ci.yml`).

## Deploy (Railway)

The repo deploys to Railway via Nixpacks. Source of truth for the start command is [`railway.json`](./railway.json).

```bash
# Railway picks up pushes to main automatically once the service is linked to the repo
git push origin main
```

Set the env vars listed above in the Railway service. `/healthz` is wired as the Railway healthcheck path so the service auto-restarts on crashes.

## Repository layout

```
src/
  bot/            # aiogram handlers, scheduler, main entry point
  admin/          # FastAPI app, Jinja2 templates, HTTP Basic auth
  services/       # business logic: shifts, breaks, photos, geofence, digest, reports, transcription, audit
  core/           # config, db, models, repositories
alembic/          # migrations 001..005
tests/            # 79 tests; all use in-memory fakes (no live DB needed)
```

## License

Private — single-tenant deployment for the owner of this repository.
