# Construction Time-Tracking Telegram Bot

Russian-language single-tenant Telegram bot for construction-crew time tracking. The default flow is **simple**: workers type hours at end of day; owners record advances and see monthly salary. Advanced features (per-site rates, crews, geofencing, the legacy clock-in/out flow) are opt-in via `/settings` (owner-only).

Stack: **Python 3.12** · **aiogram 3** · **FastAPI** · **SQLAlchemy 2 async + asyncpg** · **PostgreSQL 16 + PostGIS** · **Alembic** · **Jinja2** · **structlog** · **ruff + mypy --strict** · **pytest**.

## Default (simple) mode

- **Daily hours** — `/h 8` (or `/h` for inline quick-picks 6/7/8/9/10/12 + smart-suggested modal value); `/edit_day YYYY-MM-DD <часы>`; `/my_days` for the last 14
- **Evening reminders** — `/remind_on 19` schedules a per-user push at the chosen local hour; `/remind_off` disables; idempotent per day
- **Advances** — foreman/owner records `/advance <tg_id> <amount>`; users see `/my_advances`
- **Salary** — `/salary [YYYY-MM]` returns hours × rate − advances for the period
- **Rates** — owner/foreman sets `/set_rate <tg_id> <amount>`; users check `/my_rate`

## Optional features (flip in /settings)

Owner toggles in `/settings` enable extra `/command` entry points. Disabled commands politely report "feature disabled — owner can enable it in /settings".

- **`sites_enabled`** — per-site CRUD (`/sites`, `/site_info`, `/set_site_rate`, archive/rename), site rate overrides user rate
- **`crews_enabled`** — crew membership (`/invite`, `/join`, `/crew`, `/leave_crew`), foreman role, `/crew_advances`, `/crew_salary`, `/crew_today` etc.
- **`geofence_enabled`** — owner/foreman draws site polygons (`/geofence_set`, `/geofence_save`)
- **`legacy_clock_inout_enabled`** — the original FSM clock-in/out flow (`/quick_start`, `/my_open`, `/break_*`, `/today`, `/week`, `/export`, etc.). Default ON for existing deployments; flip OFF to hide the legacy commands

Plus, always available regardless of toggles:

- **Voice notes** — Whisper transcription appended to active shift (`F.voice` handler, OpenAI API; requires legacy mode)
- **Admin web panel** (FastAPI + Jinja2 + Chart.js) — `/`, `/users`, `/sites`, `/shifts`, `/calendar`, `/audit`. HTTP Basic auth with per-IP rate limiting
- **Scheduled jobs** — daily/weekly/monthly digests to owner, evening day-entry reminders, stale-shift/break auto-close (legacy)
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
