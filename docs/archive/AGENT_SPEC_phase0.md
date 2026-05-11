# Agent Spec — Construction Time-Tracking Telegram Bot, Phase 0 (MVP)

> **Audience:** autonomous coding agent (Claude Code or equivalent).
> **Style:** locked-decision, self-auditing. The agent does not pause to ask questions — it makes decisions on the principles in this doc and logs them in `DECISIONS.md`.

---

## 1. Mission

Build a working Telegram bot that lets **one user** (the bot owner) track work shifts on construction sites with location verification, photo/note evidence, and Excel export for payroll. Single-tenant. Dogfooding stage. No multi-user, no crews, no web dashboard yet.

## 2. Success criteria (definition of done)

The MVP is **done** when ALL of these hold:

1. Owner can start a shift via inline button → site selection → location.
2. Owner can stop the open shift → end location.
3. Each shift persists: start/end time (TZ-aware), GPS points, optional start/end photo, optional note, work type.
4. Commands `/today`, `/week`, `/month` return summaries.
5. `/export YYYY-MM` produces a valid XLSX.
6. All data survives bot restart.
7. Bot recovers gracefully from Telegram API errors and DB disconnects (retries with backoff, logs structured).
8. Test suite passes; `ruff check` clean; `mypy --strict src/` clean.
9. `AUDIT.md` exists with results of all 9 paranoid checks (§9).

## 3. Locked technical decisions

These are **not** open for the agent to change. If a constraint becomes painful, log it in `DECISIONS.md` and proceed.

- Python 3.12+
- aiogram 3.x (long polling — NOT webhooks in Phase 0)
- SQLAlchemy 2.0 async + asyncpg
- PostgreSQL 16+ with PostGIS extension
- Alembic for migrations
- pytest + pytest-asyncio
- pydantic-settings for config
- openpyxl for XLSX
- structlog for logging
- ruff + mypy --strict
- **No Celery. No Redis. No Docker-compose with 5 services.** Background tasks via `asyncio.create_task` or aiogram's scheduler if needed.
- Russian UI only.

## 4. Repository layout

```
.
├── alembic/
├── src/
│   ├── bot/
│   │   ├── main.py            # entry point, dispatcher setup
│   │   ├── handlers/
│   │   │   ├── common.py      # /start /help /cancel
│   │   │   ├── shifts.py      # start/stop/break flows
│   │   │   ├── reports.py     # /today /week /month
│   │   │   └── exports.py     # /export
│   │   ├── keyboards.py
│   │   ├── states.py          # FSM groups
│   │   └── filters.py         # OwnerOnlyFilter
│   ├── core/
│   │   ├── config.py
│   │   ├── db.py              # engine + session factory
│   │   └── models.py          # SQLAlchemy models
│   ├── services/
│   │   ├── shifts.py          # business logic, pure-ish
│   │   ├── geofence.py        # PostGIS queries
│   │   └── reports.py         # aggregations
│   └── exporters/
│       └── xlsx.py
├── tests/
│   ├── conftest.py            # pg testcontainer or sqlite-where-possible
│   ├── test_shifts_service.py
│   ├── test_geofence.py
│   ├── test_xlsx.py
│   └── test_handlers_smoke.py
├── pyproject.toml
├── .env.example
├── README.md
├── DECISIONS.md               # agent's running log of choices
├── AUDIT.md                   # final self-audit report
└── samples/
    └── timesheet_demo.xlsx
```

## 5. Data model

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- needed for the EXCLUDE constraint below

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'ru',
    hourly_rate NUMERIC(10,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sites (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    polygon GEOGRAPHY(POLYGON, 4326),         -- NULL allowed → "any location"
    hourly_rate NUMERIC(10,2),                -- override on user.hourly_rate
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shifts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    site_id BIGINT REFERENCES sites(id),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ,                        -- NULL = open shift
    start_location GEOGRAPHY(POINT, 4326),
    end_location GEOGRAPHY(POINT, 4326),
    start_photo_file_id TEXT,
    end_photo_file_id TEXT,
    note TEXT,
    work_type TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_two_open_shifts
        EXCLUDE USING gist (user_id WITH =) WHERE (end_at IS NULL)
);

CREATE TABLE breaks (
    id BIGSERIAL PRIMARY KEY,
    shift_id BIGINT NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ
);

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    entity_type TEXT NOT NULL,                 -- 'shift' | 'site' | ...
    entity_id BIGINT NOT NULL,
    action TEXT NOT NULL,                      -- 'create' | 'update' | 'delete'
    diff JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**The `EXCLUDE USING gist` constraint is non-negotiable** — it enforces "max one open shift per user" at the DB level. Never rely on app-level checks for this invariant.

## 6. FSM — start shift

States: `idle` → `selecting_site` → `awaiting_location` → `awaiting_photo_optional` → `idle`

1. User taps 🟢 **Начать смену**
   - if open shift exists → send "У тебя уже открыта смена с HH:MM на <site>. Сначала закрой её." → stay `idle`
   - else → show inline keyboard with sites + "➕ Новый объект" → `selecting_site`
2. User picks site (callback) → store site_id in FSM state → prompt "📍 Отправь геолокацию" with location request button → `awaiting_location`
3. User sends Location message
   - if site has polygon and point ∉ polygon → reply with warning **but allow** ("⚠ Локация вне границ объекта, но смена начата. Дальше — фото или /skip.")
   - INSERT shift row inside a transaction
   - on `IntegrityError` from the EXCLUDE constraint → reply "Не удалось — уже есть открытая смена. /cancel" → reset to `idle`
   - on success → `awaiting_photo_optional`
4. User sends Photo OR taps "Пропустить"
   - persist photo file_id if any
   - reply with shift summary → `idle`

**Invariants:**
- `/cancel` works in any state → wipe FSM data → `idle`. Does not delete an already-created shift row.
- Photo step is opt-in, never blocking.
- Polygon check is informational in Phase 0.

## 7. FSM — stop shift

States: `idle` → `confirming_stop` → `awaiting_end_location` → `awaiting_end_photo_optional` → `idle`

1. User taps 🔴 **Закончить смену**
   - if no open shift → "Нет открытой смены." → stay `idle`
   - else → show summary + "✅ Подтвердить" / "❌ Отмена" → `confirming_stop`
2. Confirm → request end location → `awaiting_end_location`
3. User sends Location → UPDATE shift SET end_at=now(), end_location=… → `awaiting_end_photo_optional`
4. Photo or skip → final summary with hours & amount → `idle`

## 8. XLSX export

Filename: `timesheet_{user_name}_{YYYY-MM}.xlsx`

**Sheet 1 — "Shifts":**

| Date | Site | Start | End | Hours | Rate (zł) | Amount (zł) | Note |
|------|------|-------|-----|-------|-----------|-------------|------|

- Date: `YYYY-MM-DD` (sortable text)
- Start/End: `HH:MM`
- Hours: decimal, 2 dp (e.g. `8.50` not `8:30`)
- Rate: from `sites.hourly_rate` if set, else `users.hourly_rate`, else blank
- Amount: `Hours × Rate`, blank if Rate is blank
- One row per shift; if a shift crosses midnight, **split into two rows** at local midnight (Europe/Warsaw)

**Sheet 2 — "Summary":**
- Block 1: Total hours per site
- Block 2: Total hours per work_type
- Block 3: Grand total hours + grand total amount

All numeric cells use Excel number formatting, not stringified numbers.

## 9. Paranoid self-audit (mandatory)

Before declaring done, agent runs each check, captures output, and writes results to `AUDIT.md`. Failure on any check → fix and re-run.

1. **Race condition** — fire 2 concurrent `start_shift(user_id=X)` calls. Exactly one shift row created, the other got `IntegrityError`.
2. **Crash recovery** — kill bot mid-FSM (e.g. between site selection and location). Restart. User can `/cancel` and start over without orphan rows or stuck states.
3. **Timezone correctness** — user in Europe/Warsaw starts shift `2026-05-08 23:30+02:00`, ends `2026-05-09 00:30+02:00`. `/today` on May 9 shows 30 min. `/today` on May 8 shows 30 min. Hours never double-count.
4. **DST transition** — synthetic shift across spring-forward and fall-back nights. Hours computed by wall-clock arithmetic, not naive subtraction.
5. **Empty state** — brand new user: `/today`, `/week`, `/month`, `/export 2026-05` all return graceful empty messages, never crash.
6. **Geofence math** — point inside polygon → ok; point 100 m outside → warning; point exactly on edge → defined behavior (pick inclusive, document it).
7. **XLSX integrity** — open exported file in LibreOffice. Sheets render. Hours sum matches Python-side calculation to 0.01 precision.
8. **Migration round-trip** — `alembic upgrade head` on empty DB succeeds; `alembic downgrade base` cleans everything.
9. **Lint & types** — `ruff check` zero issues; `mypy --strict src/` zero errors; coverage ≥ 80% on `src/services/` and `src/exporters/`.

## 10. Anti-patterns the agent MUST avoid

1. **Trusting client timestamps.** Always use server `now()` for shift events. Telegram's `message.date` is fine for ordering but not for billable time.
2. **Naive `datetime.now()` without tz.** Use `datetime.now(tz=ZoneInfo("Europe/Warsaw"))` or UTC + convert.
3. **Float math on time.** Use `timedelta`. Never `seconds / 3600.0` chains.
4. **Catch-all `except Exception`** in handlers. Catch specific exceptions; let unknowns bubble to global error handler.
5. **Inline SQL in handlers.** Handlers → services → repositories. No SQL above the service layer.
6. **Storing GPS as twin NUMERIC columns.** Use PostGIS GEOGRAPHY (the right tool, indexed correctly).
7. **Assuming Telegram `file_id` is permanent.** Document that Phase 0 stores file_ids only; in Phase 1+ download to S3-compatible storage. Add a TODO.
8. **Silent Telegram API errors.** Wrap bot calls; log with structlog including `update_id`, `chat_id`; surface to user on failures.
9. **Bare migrations without downgrades.** Every alembic migration has a working `downgrade()`.
10. **Hard-coded strings.** All user-facing copy lives in `src/bot/strings.py` (single dict). Russian only in Phase 0, but the structure must be ready for `pl`/`uk`.

## 11. Configuration

`.env.example`:

```
BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://timetrack:timetrack@localhost:5432/timetrack
OWNER_TG_ID=                 # only this user is accepted in Phase 0
LOG_LEVEL=INFO
TIMEZONE=Europe/Warsaw
```

`OwnerOnlyFilter` rejects every other user with a polite "Это приватный бот." reply. Do **not** crash on unknown users.

## 12. Out of scope for Phase 0

Do **not** implement, even partially:

- Multi-user, crews, foreman role
- Voice transcription / Whisper
- Web dashboard / FastAPI
- Billing / subscriptions
- Auto clock-out / scheduled reminders
- Push notifications beyond bot replies
- Multi-language UI
- Telegram inline mode
- Webhook deployment
- Photo download / S3
- Admin panel

Each of these gets a one-line stub in `ROADMAP.md` so future phases know where to plug in.

## 13. Working order

The agent works in this order; each step ends with a commit + audit subset.

1. `pyproject.toml`, `.env.example`, `core/config.py`, `core/db.py` — bootstrap.
2. SQLAlchemy models + initial alembic migration. **Run migration up + down.**
3. Services layer with unit tests (no bot, just DB). Tests for: open-shift invariant, hours calculation across midnight & DST, geofence point-in-polygon.
4. XLSX exporter with unit tests against in-memory shift fixtures.
5. Handlers: common → shifts (start) → shifts (stop) → reports → exports.
6. Smoke tests for handlers via aiogram test utilities.
7. Run all 9 paranoid checks. Write `AUDIT.md`.
8. Write `README.md` with setup, migrate, run, deploy (systemd unit example).
9. Generate `samples/timesheet_demo.xlsx` from a seeded fixture.

## 14. Decision log policy

Whenever the agent makes a non-trivial choice not covered above, append to `DECISIONS.md`:

```
## YYYY-MM-DD — short title
**Context:** what triggered the decision
**Options considered:** A, B, C
**Chosen:** B
**Rationale:** one paragraph
**Reversibility:** trivial / moderate / hard
```

This is the same paranoid-audit discipline used on pred1's CLV validation work — it makes review fast and disagreement specific.

---

**End of spec.** The agent does not request clarifications on items covered above; it implements per spec, logs decisions, and self-audits.
