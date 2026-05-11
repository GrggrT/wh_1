# Onboarding

Two paths through the bot:

- **Simple mode (default)** — workers type hours at end of day, owner records advances, monthly salary computed automatically. No crews, no sites, no geofence.
- **Full mode** — owner flips toggles in `/settings`: crews, sites, geofencing, and the legacy clock-in/out flow with location and photo verification.

The bot is Russian-language; English glosses are given in parentheses.

## Prerequisites (owner, one-time)

Owner has deployed the bot (Railway/anywhere) and set `OWNER_TG_ID` to their own Telegram numeric id (look it up via [`@userinfobot`](https://t.me/userinfobot)). DM the bot — the first `/start` from `OWNER_TG_ID` upserts that user with role `owner`. Everything below is a chat with `@<your_bot_username>`.

## Simple mode walkthrough

### 1. Worker logs hours

1. Worker DMs the bot `/start` once. They appear in the database with role `worker`.
2. Owner sets the worker's hourly rate: `/set_rate <tg_id> <PLN_per_hour>`. Worker checks with `/my_rate`.
3. At end of day worker runs `/h` — bot shows inline quick-picks (6, 7, 8, 9, 10, 12 ч) plus the modal value if they've been habitual. Tap to record. Or type: `/h 8.5`.
4. Mistyped? `/edit_day 2026-05-11 9` overwrites that day.
5. Worker reviews `/my_days` for the last 14 days.

### 2. Owner records advances and salary

- `/advance <tg_id> <amount> [note]` — books a mid-month cash advance against a worker.
- `/salary [YYYY-MM]` — that user's monthly summary: hours, earnings, advances, net payable.
- `/my_advances [YYYY-MM]` — worker's own view of their advances.

### 3. Evening reminders (optional, per-user)

- `/remind_on 19` — bot pings the worker daily after 19:00 local time, *unless* they've already recorded that day's hours. Idempotent — one ping per day.
- `/remind_off` — turn off for that user.

That's the full simple flow.

## Enabling advanced features

Owner runs `/settings`. Inline menu shows four toggles (✅ enabled, ⬜ disabled):

- **Объекты (sites)** — per-site rates that override user rates, site CRUD commands.
- **Бригады (crews)** — crew membership, foreman role, crew-scoped reports/exports/salaries.
- **Геозоны (geofence)** — owner/foreman draws site polygons; clock-ins outside are rejected (requires legacy clock-in/out).
- **Старый режим (legacy clock-in/out)** — the original FSM shift flow with location and photo verification, breaks, retroactive edits, and per-shift reports.

Tap a row to flip; the bot saves and updates the keyboard. Disabled `/commands` reply "функция выключена" until re-enabled.

## Full mode setup (when toggles are on)

### Owner promotes a foreman (crews_enabled)

1. Foreman-to-be DMs the bot `/start` once.
2. Foreman tells the owner their numeric Telegram id (`/whoami`).
3. Owner runs `/add_foreman <tg_id> [crew name]`. Bot creates a crew, assigns the foreman, audits the change.
4. Verify with `/foremen`.

### Foreman adds a site (sites_enabled)

1. `/sites` lists existing sites. From the keyboard, foreman taps **«Объекты» → «Создать объект»**, then sends a name.
2. Set the site rate: `/set_site_rate <site_id> <PLN_per_hour>`. Site rate wins over user rate.
3. (geofence_enabled) `/geofence_set <site_id>` → send 3+ location pings tracing the perimeter → `/geofence_save`. `/geofence_cancel` aborts; `/geofence_clear <site_id>` removes.

### Foreman invites workers (crews_enabled)

1. `/invite` → bot returns a 6-character code (e.g. `K7H3PQ`). Single-use, 7-day expiry.
2. Worker runs `/join K7H3PQ`. Reissuing `/invite` revokes the prior code.

### First clock-in/out shift (legacy_clock_inout_enabled)

1. Worker taps **«Начать смену»**. Bot shows the crew's active sites.
2. Tap a site → bot asks for current location.
3. If site has a geofence, location is checked.
4. Optional start photo.
5. Stopping the shift mirrors: location, optional end photo, optional voice note.

### Day-to-day in full mode

- Worker: `/me`, `/me_yesterday`, `/break_start`/`/break_stop`/`/break_status`, `/leave_crew`.
- Foreman: `/crew`, `/crew_today`/`/crew_week`/`/crew_month`, `/active`, `/shifts`, `/crew_shifts`, `/crew_export YYYY-MM`, `/remove_member <tg_id>`.
- Owner: `/transfer_crew <tg_id> <crew_id>`, `/admin_audit`, `/stats`, `/digest`, `/digest_week`, `/digest_month`.

## Common first-day issues

| Symptom | Fix |
| --- | --- |
| `/h` says "feature disabled" | Shouldn't happen — `/h` is always on. Likely the worker mistyped a different command. |
| `/quick_start` (or any legacy command) says "feature disabled" | Owner has `legacy_clock_inout_enabled` off in `/settings`. Either enable it or use simple mode (`/h`). |
| Worker types `/join CODE` and gets "invalid code" | Foreman hasn't run `/invite` yet, or the code was already redeemed. Issue a fresh one. |
| Worker can't see the "Start shift" button | crews_enabled is off, or they haven't joined a crew (`/whoami` shows no `crew_id`). |
| Geofence rejects clock-in at the actual site | Polygon is too tight or wrong. Foreman runs `/geofence_clear <site_id>` then redoes `/geofence_set`. |
| Foreman wants to clock someone out remotely | `/stop_for <tg_id>` (owner or that worker's foreman; legacy mode only). |

For deeper trouble (deploy crashes, migrations, backups), see [RUNBOOK.md](./RUNBOOK.md).
