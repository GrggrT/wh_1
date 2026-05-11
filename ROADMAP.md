# Roadmap

## Shipped
- **Phase 0** — MVP single-tenant shift tracking, location, photos, XLSX export
- **Phase 1.1–1.4** — auto clock-out + reminders, Supabase Storage photo archive, roles + crews + invite codes, foreman crew reports
- **Phase 1A/1B** — FastAPI admin panel + Telegram webhook (HTTP Basic, secret-token)
- **Phase 2.1–2.10** — period earnings, /shift_info, geofence editor, /active, /stats, stale-break auto-close, /quick_start, /me YYYY-MM, crew-scoped sites, /help sync, /sites for workers, /crew_shifts, rate-change notify, /unarchive_site, /rename_site
- **Phase 2A/2B/2C** — dashboard charts + calendar, Whisper voice→note, admin filters + bot stat breakdowns (/work_stats, /site_stats)
- **Phase 3.1–3.6** — admin audit trail (/admin_audit), retroactive break edit, /my_open + /leave_crew, /site_info + /sites_archive, /remove_member + crew details, weekly digest
- **Phase 4 P0** — README rewrite, CI workflow, consolidated start command, Railway healthcheck
- **Phase 4 P1** — Sentry integration, scheduled DB backups, RUNBOOK, admin auth rate-limit, ONBOARDING

## Phase 5 — Product simplification (next)

Goal: make the **default flow much simpler** — workers just type how many hours they worked today. Sites, crews, geofence become optional feature toggles for users who actually need them.

### Batch 5.1 — Daily hours entry (start here)
- [ ] New table `day_entries` (user_id, date, hours, site_id NULLABLE, note NULLABLE, created_at, updated_at) + alembic migration
- [ ] Command `/h 8` and inline keyboard with quick numbers (6, 7, 8, 9, 10, 12) — one tap = "сегодня X часов"
- [ ] Smart suggest: if the worker's last 5 days have a clear modal value (e.g. 8h on 4 of 5 days), the first button in the inline keyboard shows that value
- [ ] `/edit_day YYYY-MM-DD <hours>` and a "Изменить" inline button on each entry in `/my_days`
- [ ] `/my_days` — list last 14 days with hours, total at the bottom
- [ ] Skip empty days (no entry = 0 hours, no row)

### Batch 5.2 — Advances + payroll
- [ ] New table `advances` (user_id, date, amount_pln, note, recorded_by_id, created_at) + migration
- [ ] `/advance <tg_id> <amount>` — foreman/owner records an advance; worker gets a notification
- [ ] `/my_advances` for the worker, `/crew_advances` for the foreman
- [ ] `/salary YYYY-MM` — итог: hours × rate − advances, both for `day_entries` and existing `shifts` (unified)
- [ ] `/crew_salary YYYY-MM` — same per crew, XLSX export

### Batch 5.3 — Evening reminders
- [ ] Per-user setting `remind_hour_local` (default 19:00, NULL = disabled)
- [ ] Scheduler check every 15 min: for each user with no `day_entry` for today and `remind_hour_local` already past → send "Не забудь поставить часы за сегодня" with the inline quick-buttons from 5.1
- [ ] `/remind_off` and `/remind_on HH:MM` commands

### Batch 5.4 — Feature toggles
- [ ] New table `app_settings` (key, value) — single-row config per owner
- [ ] `/settings` opens an inline-keyboard menu with toggles:
  - "Привязка к объектам" → enables site selection in `/h`
  - "Бригады" → enables /invite, /join, foreman features
  - "Геозоны" → requires sites enabled
  - "Старый режим (clock-in/out)" → keeps existing `/start`-button shift flow available
- [ ] Defaults: simple mode (all toggles OFF except старый режим for owner only during transition)
- [ ] Migration plan: existing shift data stays readable in reports; new entries go to `day_entries` by default

### Batch 5.5 — Cleanup + cutover
- [ ] Update `/help` and main menu keyboard to reflect simple mode
- [ ] Update README + ONBOARDING for the simple flow
- [ ] Run on staging, verify
- [ ] Single release: simple mode becomes default, advanced features hide behind toggles

## Phase 4 — Production polish (remaining)

### P2 — quality (deferred — non-blocker)
- [ ] **Phase 2C/3.x test coverage** — admin filter paths + Phase 3.x feature tests (deferred until DB test infra exists)
- [ ] **Doc cleanup** — update or archive `AGENT_SPEC_phase0.md`, `AUDIT.md`, `DECISIONS.md` (all reflect Phase 0 only)
- [ ] **Metrics endpoint** — `/metrics` in admin panel: shifts/day, active users, error rate

## Future (post-Phase 5)
- Geofence as activated feature (currently deferred)
- Multi-language UI (pl, uk) — strings table refactor
- Telegram inline mode
- Mobile app companion
- Integrations (1C, accounting systems)
- Billing / subscriptions
