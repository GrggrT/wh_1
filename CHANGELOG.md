# Changelog

All notable changes to this project are documented in this file.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Defensive `send_default_pii=False` pinned in Sentry init (guard against
  future SDK default flips).
- RLS enabled on every application table via alembic `017_enable_rls`. The
  bot uses the privileged `postgres`/`service_role` role (which bypasses
  RLS), but the Supabase Data API exposes the same tables to `anon` /
  `authenticated`; turning RLS on with zero policies denies those roles
  every row and resolves the `sensitive_columns_exposed` advisor on
  `share_tokens.token`.
- Admin HTTP Basic auth wrapped in per-IP rate limiter (5 fails / 60s →
  5min block, in-memory).
- Telegram webhook secret-token validated with `secrets.compare_digest`.

### CI / Dev
- Upper bounds pinned for `mypy`, `pytest`, `pytest-asyncio`, `ruff`,
  `pytest-cov`, `aiosqlite`, `httpx` in `[dev]` deps. A silent
  `mypy 2.x` auto-upgrade had broken CI for 8 commits.
- Fixed mypy `--strict` failure on SQLAlchemy 2.x by casting
  `session.execute(delete(...))` through `CursorResult[Any]` to access
  `.rowcount` in `share_cleanup.py`.

## [1.0.0] — 2026-05-13

First production-ready cut. Single-tenant Telegram time-tracking bot,
deployed on Railway with Supabase Postgres + Storage, admin web panel
behind HTTP Basic.

### Phase 7 — backup, smart reminders, observability
- `/backup` — full XLSX dump of profile + days + advances + payments
  (commit `08c869d`).
- `/restore` — additive import of a `/backup` XLSX with dedup by natural
  key, with a confirm step (`976fe58`, `434add6`).
- `/share_backup` — one-shot tokens for cross-account transfer
  (`3293631`); active-token cap + automatic hourly pruning of expired
  rows (`f65da0a`, `401941e`).
- `/backup_to_cloud` + `/restore_from_cloud` — Supabase Storage-backed
  cloud backups with TTL (`c59b0be`).
- `/export_archive` — bundles XLSX + PDF + PNG report into one ZIP
  (`1c0d1b2`).
- `/range YYYY-MM-DD YYYY-MM-DD` + preset picker + NL routing
  (`11f8783`, `c3cffd6`, `aaa77de`).
- `/forecast` command + NL routing + inline button on current-month
  `/period` (`c05fb57`, `3c441e6`).
- Smart reminders: 3-day gap nudge + Monday weekly-debt ping
  (`574b999`).
- Personalised `/h` quick-pick keyboard (`758fed3`).
- Bulk-fill workweek button on inline calendar (`ce8a751`).
- Owner monthly digest with PNG chart attached (`a824ada`).
- Per-user timezone in `/profile` + tz-aware evening reminders
  (`d7b4ac6`, `d035605`).
- Admin POST `/admin/restore` — HTTP Basic-gated XLSX import
  (`0d5a6dd`).
- Pre-commit hooks (ruff + format + safety, pytest on push) (`65c400e`).
- Sentry FSM-transition breadcrumbs (`8a53fc2`).

### Phase 6 — calendar, period accounting, profile editor, reports
- Inline calendar + per-day data entry + `salary_payments` ledger
  (`5899709`).
- Accounting commands `/period`, `/cash`, `/owed` (`db4d626`).
- `/profile` editor + per-user currency (`f4e2b19`).
- Reply keyboard simplified for single-user mode + ⚙ Профиль button
  (`1673888`, `f4f9ac1`).
- `/report` multi-month summary + inline export buttons producing
  XLSX, PDF, PNG (`85d0ecc`, `c31975e`, `a36c95d`, `0d4ae54`).
- NL dispatcher for `/report` / `/period` / `/cash` / `/owed`
  (`ede1e09`).
- Inline month picker for `/period` (`4745b4c`).
- Period-attributed advances (`74df36a`).

### Phase 5 — product simplification
- `/h` daily-hours entry, `/my_days`, `/edit_day` (`f887766`).
- Advances + monthly salary computation (`ab57713`).
- Evening day-entry reminders (`46e520a`).
- `/settings` inline toggle menu gating optional commands (`8be3d22`).
- Dynamic `/help` aware of settings (`d1b4c33`).
- Day-off button + adaptive simple-mode menu (`b57dba0`).

### Phase 4 — onboarding & production polish
- First-run onboarding wizard, refined to ask currency before rate
  (`3beb2df`, `4f956cd`).
- `/metrics` Prometheus-style endpoint (`d4a989a`).
- Admin auth rate-limit (`eb8340a`).
- Scheduled DB-backup GitHub workflow (`fabeb27`).
- Sentry error tracking opt-in via `SENTRY_DSN` (`9f03064`).

### Phase 3 — admin panel & resilience
- FastAPI admin dashboard (`b095d80`).
- Telegram webhook with secret-token validation (`f3632fd`,
  `59f3e25`).
- Shift photo archive + replay + delete restore (`ca18553`,
  `efacdff`).
- Owner daily digest (`0ac9b63`).
- Mid-shift notes, foreman `/stop_for`, audit log viewer (`03ad323`).
- Shift edit / delete / listing with audit log (`c07f442`).
- Lunch-break tracking (`5017e4c`).

### Phase 2 — roles, crews, invites
- Roles + crews + invite codes (`c73c009`).
- Foreman crew reports + crew Excel export (`47de412`, `8339e98`).
- Bot command menu + foreman keyboard (`8339e98`).

### Phase 1 — core MVP
- `/start`, `/stop`, `/status`, lunch, GPS sites, photo proof
  (`24ab3aa`).
- Auto-close + reminders (`55451a2`).
