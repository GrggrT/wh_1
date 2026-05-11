# Roadmap

## Shipped
- **Phase 0** — MVP single-tenant shift tracking, location, photos, XLSX export
- **Phase 1.1–1.4** — auto clock-out + reminders, Supabase Storage photo archive, roles + crews + invite codes, foreman crew reports
- **Phase 1A/1B** — FastAPI admin panel + Telegram webhook (HTTP Basic, secret-token)
- **Phase 2.1–2.10** — period earnings, /shift_info, geofence editor, /active, /stats, stale-break auto-close, /quick_start, /me YYYY-MM, crew-scoped sites, /help sync, /sites for workers, /crew_shifts, rate-change notify, /unarchive_site, /rename_site
- **Phase 2A/2B/2C** — dashboard charts + calendar, Whisper voice→note, admin filters + bot stat breakdowns (/work_stats, /site_stats)
- **Phase 3.1–3.6** — admin audit trail (/admin_audit), retroactive break edit, /my_open + /leave_crew, /site_info + /sites_archive, /remove_member + crew details, weekly digest

## Phase 4 — Production polish (in progress)

### P0 — blocking
- [ ] **README rewrite** — current README lists 5 commands; project has 50+. Cover: setup, env vars, admin panel, webhook, bot command catalogue, deploy
- [ ] **CI workflow** — `.github/workflows/ci.yml` running ruff + mypy --strict + pytest on every push/PR
- [ ] **`.env` hygiene** — verify nothing real committed, ensure `.env` is in `.gitignore` (currently `.env.example` only)
- [ ] **Consolidate start command** — single source of truth (keep `railway.json`, drop `Procfile` + `nixpacks.toml [start]`)
- [ ] **Railway healthcheck** — wire `healthcheckPath: "/healthz"` into `railway.json` so Railway auto-restarts on crashes

### P1 — operational hardening
- [ ] **Sentry integration** — `sentry-sdk` with aiogram error handler + FastAPI middleware
- [ ] **Supabase backup strategy** — daily `pg_dump` to Supabase Storage or scheduled snapshot (free tier has no auto-backup)
- [ ] **Runbook** — `docs/RUNBOOK.md` for operator: bot silent / migration failed / kick worker / rotate webhook / restore from backup
- [ ] **Admin panel rate-limit** — slowapi or simple in-memory counter, 5 failed-auth per IP per minute
- [ ] **Onboarding doc** — `docs/ONBOARDING.md` how a foreman gets the bot, how a worker joins via /join

### P2 — quality
- [ ] **Phase 2C test coverage** — admin `/shifts?q=&site=` and `/audit?entity=&actor=` filter paths
- [ ] **Phase 3.x test coverage** — geofence editor, edit/delete break, leave_crew, remove_member, restore_shift, weekly digest
- [ ] **Doc cleanup** — update or archive `AGENT_SPEC_phase0.md`, `AUDIT.md`, `DECISIONS.md` (all reflect Phase 0 only)
- [ ] **Metrics endpoint** — `/metrics` in admin panel: shifts/day, active users, error rate
- [ ] **Multi-timezone** — if expanding beyond Europe/Warsaw, per-user `tz` column (out of Phase 0 scope, defer)

## Future (post-polish)
- Multi-language UI (pl, uk) — strings table refactor
- Telegram inline mode
- Mobile app companion
- Integrations (1C, accounting systems)
- Billing / subscriptions
