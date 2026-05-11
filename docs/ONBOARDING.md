# Onboarding

How a brand-new crew gets onto the bot. Two flows: the **foreman** (or owner) sets up sites and invite codes; **workers** join with `/join <code>`.

The bot is Russian-language; English glosses are given in parentheses.

## Prerequisites (owner, one-time)

The owner has already deployed the bot to Railway and set `OWNER_TG_ID` to their own Telegram numeric id (look it up in [`@userinfobot`](https://t.me/userinfobot)). DM the bot — the first `/start` from `OWNER_TG_ID` upserts them with role `owner`. Everything below is a chat with `@<your_bot_username>`.

## 1. Owner promotes a foreman

A foreman is the crew lead. They get an auto-created crew on promotion.

1. Foreman-to-be DMs the bot `/start` once — this records their Telegram id in the database with default role `worker`.
2. Foreman tells the owner their numeric Telegram id (visible via `/whoami`).
3. Owner runs `/add_foreman <tg_id>` (and optionally `/add_foreman <tg_id> "Crew name"`). The bot creates a crew, makes the user its foreman, and audits the change.

Verify: owner runs `/foremen` — the new foreman should be listed with their crew.

## 2. Foreman adds at least one site

A site is a job location. It can be a plain name, or a name + geofence polygon for location verification at clock-in.

1. Foreman taps the **«Объекты»** ("Sites") button on the keyboard, then **«Создать объект»** ("Create site").
2. Sends the site name in chat. The site is created and added to the foreman's crew.
3. (Optional) Add a geofence:
   - `/geofence_set <site_id>` — bot replies with instructions.
   - Send 3+ location messages tracing the perimeter (Telegram → attach → location).
   - `/geofence_save` — polygon is saved; future clock-ins from outside the polygon are rejected.
   - `/geofence_cancel` aborts; `/geofence_clear <site_id>` removes an existing polygon.
4. (Optional) Set the hourly rate: `/set_site_rate <site_id> <PLN_per_hour>`. Per-user rates override site rates: `/set_rate <tg_id> <rate>`.

## 3. Foreman issues an invite code

1. Foreman runs `/invite` — bot replies with a 6-character code (e.g. `K7H3PQ`). Codes are single-use and expire after 7 days.
2. Foreman shares the code with the worker over any channel (SMS, voice, Telegram).

To reissue: run `/invite` again — that revokes the previous unused code.

## 4. Worker joins the crew

1. Worker DMs the bot `/start` once.
2. Worker runs `/join <code>` — for example `/join K7H3PQ`. The bot attaches the worker to the foreman's crew and replies with a confirmation.
3. Worker can now see the **«Начать смену»** ("Start shift") flow on their keyboard.

If the code is wrong, expired, or already used, the bot says so — foreman just issues a fresh `/invite`.

## 5. Worker starts their first shift

1. Worker taps **«Начать смену»** ("Start shift"). Bot shows the crew's active sites.
2. Worker taps a site. Bot asks for current location (Telegram → attach → location).
3. If the site has a geofence, the bot checks that the location is inside; outside → shift is refused.
4. (Optional) Bot asks for a start photo. Skip with the inline button if not required.
5. Shift is open. Worker sees **«Завершить смену»** ("Stop shift") on the keyboard.

Stopping the shift mirrors step 1: location, optional end photo, optional voice note.

## 6. Day-to-day commands the worker needs

- `/me` — hours and PLN earned this month.
- `/me_yesterday` — yesterday's shift summary.
- `/break_start` / `/break_stop` / `/break_status` — pause and resume the active shift.
- `/leave_crew` — leave the current crew (refused if a shift is open).
- `/help` — full command list.

## 7. Day-to-day commands the foreman needs

- `/crew` — list crew members.
- `/crew_today` / `/crew_week` / `/crew_month` — aggregated hours and earnings.
- `/active` — who is currently clocked in.
- `/crew_shifts` and `/shifts` — detailed shift listing.
- `/crew_export YYYY-MM` — payroll-ready XLSX for the crew.
- `/remove_member <tg_id>` — remove a worker (refused if shift open).
- `/transfer_crew <tg_id> <crew_id>` (owner only) — move a worker between crews.
- `/admin_audit` — last 20 admin actions.

## 8. Common first-day issues

| Symptom | Fix |
| --- | --- |
| Worker types `/join CODE` and gets "invalid code" | Foreman has not run `/invite` yet, or the code was already redeemed. Issue a fresh one. |
| Worker can't see the "Start shift" button | They haven't joined a crew yet. Run `/whoami` — `crew_id` should be set. |
| Geofence rejects clock-in at the actual site | Polygon is too tight or wrong. Foreman runs `/geofence_clear <site_id>` then redoes `/geofence_set`. |
| Foreman wants to clock someone out remotely | `/stop_for <tg_id>` (owner or that worker's foreman). |

For deeper trouble (deploy crashes, migrations, backups), see [RUNBOOK.md](./RUNBOOK.md).
