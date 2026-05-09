# Construction Time-Tracking Telegram Bot

Single-tenant Telegram bot for tracking work shifts on construction sites with location verification, photo evidence, and Excel export for payroll.

## Requirements

- Python 3.12+
- PostgreSQL 16+ with PostGIS extension
- Active Telegram Bot Token

## Setup

```bash
# Clone and install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your BOT_TOKEN, DATABASE_URL, OWNER_TG_ID

# Database setup
createdb timetrack
psql timetrack -c "CREATE EXTENSION postgis; CREATE EXTENSION btree_gist;"
alembic upgrade head
```

## Run

```bash
python -m src.bot.main
```

## Development

```bash
# Tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy --strict src/
```

## Deploy (systemd)

```ini
[Unit]
Description=Construction Timetrack Bot
After=network.target postgresql.service

[Service]
Type=simple
User=timetrack
WorkingDirectory=/opt/timetrack-bot
Environment=PYTHONPATH=/opt/timetrack-bot
ExecStart=/opt/timetrack-bot/.venv/bin/python -m src.bot.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Commands

- `/start` — initialize bot
- `/help` — show help
- `/today` — today's shifts summary
- `/week` — this week's summary
- `/month` — this month's summary
- `/export YYYY-MM` — download Excel timesheet
- `/cancel` — cancel current action

## Bot Buttons

- Green: Start shift (site selection -> location -> optional photo)
- Red: Stop shift (confirm -> end location -> optional photo)
