# Operator Runbook

This is the on-call guide for the owner of the Telegram bot. Each section starts with the symptom you see and walks through the fix.

## Quick reference

| Resource | Where |
| --- | --- |
| GitHub repo | https://github.com/GrggrT/wh_1 |
| Railway project | https://railway.com — project `valiant-clarity`, service `worker` |
| Public URL | https://worker-production-171e.up.railway.app |
| Supabase project | `wh1` (eu-central-1) — Dashboard → Project Settings |
| Telegram bot | DM owner account; `/start` for the keyboard menu |

Railway env vars to know about: `BOT_TOKEN`, `DATABASE_URL`, `OWNER_TG_ID`, `TIMEZONE`, `ADMIN_PASSWORD`, `WEBHOOK_URL`, `WEBHOOK_SECRET`, optionally `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `SENTRY_DSN`. Full list with defaults in `.env.example`.

## 1. The bot is silent

**Symptom:** sending `/start` or buttons produces no reply.

1. **Check the public health endpoint** — `curl https://worker-production-171e.up.railway.app/healthz`. Should return `200`.
2. **If health is down** — open Railway service. If status is anything other than `Active`, look at the latest deployment: View logs → Deploy logs. The healthcheck is wired so Railway will auto-restart on crashes; if it's stuck restarting, the latest commit broke something.
3. **If health is up** — check that webhook is registered. With production `BOT_TOKEN`:
   ```bash
   curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
   ```
   `url` should point to `worker-production-171e.up.railway.app/tg/webhook`, `last_error_message` should be empty. If empty `url`, the bot never set the webhook — restart the Railway service (Deployments → Restart).
4. **If webhook is registered but updates are not flowing** — check `pending_update_count`. If it climbs, the bot crashed mid-request and Telegram is queuing updates. Restart Railway service; the next deploy resumes from the queue.

## 2. A migration failed on deploy

**Symptom:** deploy is `Crashed`; deploy logs show `alembic` errors.

1. Open the deploy logs and copy the exact error.
2. Common causes:
   - `Can't find revision 'XXX'` — Railway is deploying a stale commit. Confirm Settings → Source shows `GrggrT/wh_1` and the latest commit hash matches `git rev-parse main` locally.
   - `DuplicateTableError` — schema was pre-applied via Supabase MCP but `alembic_version` is missing. Fix by stamping:
     ```sql
     CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY);
     INSERT INTO alembic_version VALUES ('<latest revision id>');
     ```
     Then redeploy.
   - `DuplicatePreparedStatementError` — `DATABASE_URL` uses the Supabase transaction pooler (port 6543). Switch to the session pooler (port 5432, same hostname) or set `statement_cache_size=0`.
3. Worst case: revert the offending commit and `git push`. Railway will redeploy from the previous head.

## 3. Backup and restore

Daily backups run at 03:00 UTC via `.github/workflows/backup.yml`. Artifacts retain for 30 days.

**Activate backups** (one-time):
1. GitHub → Settings → Secrets and variables → Actions
2. Add **Secret** `DATABASE_URL` (full Supabase connection URL, the same one used by Railway).
3. Add **Variable** `BACKUP_ENABLED` = `true`.
4. Trigger once manually: Actions → DB Backup → Run workflow → Run.

**Restore from a backup**:
1. Actions → DB Backup → pick a successful run → download the `wh1-YYYYMMDD-HHMMSS.sql.gz` artifact.
2. From a workstation:
   ```bash
   gunzip wh1-*.sql.gz
   psql "$RESTORE_TARGET_URL" < wh1-*.sql
   ```
   Use a **scratch** Postgres first to verify the dump opens cleanly. Only point at the live Supabase DB after verification.
3. If restoring over the live DB, expect downtime: stop Railway service, drop+recreate the `public` schema, replay the dump, restart Railway.

## 4. Kicking off, transferring, or removing a worker

All admin operations are bot commands, no SQL required.

- **New worker joins:** foreman runs `/invite`, sends the 6-char code, worker DMs `/join <code>` to the bot.
- **Move worker between crews:** owner runs `/transfer_crew <tg_id> <crew_id>`. Refuses to move foremen.
- **Remove worker from a crew:** foreman or owner runs `/remove_member <tg_id>`. Refuses if the worker has an open shift; close it first with `/stop_for <tg_id>`.
- **Worker leaves on their own:** worker runs `/leave_crew`.

All changes are audited; `/admin_audit` shows the last 20 admin actions.

## 5. Rotating the webhook secret

If `WEBHOOK_SECRET` leaks:

1. Generate a new random value, e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Update `WEBHOOK_SECRET` in Railway service env vars (Variables tab → Edit → Save).
3. Railway redeploys automatically; on startup `bot.set_webhook(secret_token=…)` re-registers the new secret with Telegram.
4. Verify: `curl -i -X POST -H "X-Telegram-Bot-Api-Secret-Token: OLD" https://worker-production-171e.up.railway.app/tg/webhook -d '{}'` must return `403`.

The webhook URL itself only needs changing if the Railway domain changes — set `WEBHOOK_URL` to the new public base URL.

## 6. Sentry alerts

Enable by setting `SENTRY_DSN` in Railway service env vars (Sentry → Settings → Client Keys → DSN). Restart the service so `init_sentry` runs.

When an alert fires:
1. Open the issue in Sentry — it carries the structlog event name (`handler_error`, `webhook_starting`, etc.) and the update id.
2. Cross-reference the update id with Railway logs to see the surrounding context.
3. The owner already received a DM via the aiogram error handler (`owner_error_alert`).
4. Mark the Sentry issue resolved once a fix is deployed.

## 7. Manual fixes via SQL (last resort)

Use Supabase Dashboard → SQL Editor with a read-only session first. Only switch to a write session after verifying the query.

Common surgical queries:
```sql
-- Force-close a stuck open shift:
UPDATE shifts SET end_at = now() WHERE id = <shift_id> AND end_at IS NULL;

-- Inspect the latest audit rows:
SELECT created_at, actor_id, entity_type, entity_id, action, diff
FROM audit_log
ORDER BY id DESC
LIMIT 50;
```

Every direct-SQL change should be paired with an `audit_log` row inserted by hand for traceability.

## 8. Restarting / rolling back

- **Restart only:** Railway → Deployments → ⋯ next to active deploy → Restart.
- **Roll back a bad release:** Railway → Deployments → find the previous green deploy → ⋯ → Redeploy.
- **Local rollback:** `git revert <bad-sha> && git push origin main`. CI must stay green; Railway redeploys automatically.
