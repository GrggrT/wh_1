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
- **Phase 5 — Product simplification** — `day_entries` table + `/h` quick-pick flow with smart-suggest, `advances` + monthly `/salary`, per-user evening reminders, `app_settings` toggle table + `/settings` inline menu, command-gate middleware, dynamic `/help`, README/ONBOARDING rewrite for simple-mode default

## Phase 4 — Production polish (remaining)

### P2 — quality (Batch 6.2)
- [x] **DB-integration test infra** — aiosqlite-backed integration tests for app_settings / day_entries / advances services
- [x] **Doc cleanup** — moved phase-0 specs into `docs/archive/`
- [x] **Metrics endpoint** — `/metrics` in admin panel: Prometheus-style gauges (users, shifts, day-entries, toggles)

## Future (post-Phase 5)
- Geofence as activated feature (currently deferred)
- Multi-language UI (pl, uk) — strings table refactor
- Telegram inline mode
- Mobile app companion
- Integrations (1C, accounting systems)
- Billing / subscriptions
