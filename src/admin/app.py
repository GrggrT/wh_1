"""FastAPI admin panel app factory."""

import secrets as _secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select

from src.admin.auth import require_admin
from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.models import AuditLog, Crew, Shift, Site, User
from src.services.breaks import get_breaks_for_shifts, total_break_hours
from src.services.reports import compute_hours

logger = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def create_app(
    *,
    bot: Bot | None = None,
    dispatcher: Dispatcher | None = None,
    webhook_path: str | None = None,
    webhook_secret: str | None = None,
) -> FastAPI:
    """Build the admin FastAPI instance.

    If `bot`, `dispatcher`, `webhook_path`, and `webhook_secret` are all
    provided, a Telegram webhook endpoint is mounted at `webhook_path` that
    validates the X-Telegram-Bot-Api-Secret-Token header before dispatching.
    """
    app = FastAPI(title="wh1 admin", docs_url=None, redoc_url=None)

    if (
        bot is not None
        and dispatcher is not None
        and webhook_path
        and webhook_secret
    ):
        @app.post(webhook_path)
        async def telegram_webhook(request: Request) -> Response:
            header_secret = request.headers.get(
                "X-Telegram-Bot-Api-Secret-Token", "",
            )
            if not _secrets.compare_digest(header_secret, webhook_secret):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            data = await request.json()
            update = Update.model_validate(data, context={"bot": bot})
            await dispatcher.feed_update(bot, update)
            return Response(status_code=200)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
        _user: str = Depends(require_admin),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        tz = ZoneInfo(settings.timezone)
        now_local = datetime.now(tz=tz)
        today_local = now_local.date()
        day_start = datetime.combine(today_local, datetime.min.time(), tzinfo=tz)
        day_end = day_start + timedelta(days=1)
        week_start_date = today_local - timedelta(days=today_local.weekday())
        week_start = datetime.combine(
            week_start_date, datetime.min.time(), tzinfo=tz,
        )
        month_start = datetime.combine(
            today_local.replace(day=1), datetime.min.time(), tzinfo=tz,
        )
        chart_window_days = 30
        chart_window_start_date = today_local - timedelta(days=chart_window_days - 1)
        chart_window_start = datetime.combine(
            chart_window_start_date, datetime.min.time(), tzinfo=tz,
        )

        async for session in get_session():
            open_count = (
                await session.execute(
                    select(func.count(Shift.id)).where(Shift.end_at.is_(None)),
                )
            ).scalar_one()
            today_count = (
                await session.execute(
                    select(func.count(Shift.id)).where(
                        Shift.start_at >= day_start, Shift.start_at < day_end,
                    ),
                )
            ).scalar_one()
            users_count = (
                await session.execute(select(func.count(User.id)))
            ).scalar_one()
            sites_count = (
                await session.execute(
                    select(func.count(Site.id)).where(Site.archived_at.is_(None)),
                )
            ).scalar_one()
            window_shifts = list(
                (
                    await session.execute(
                        select(Shift).where(
                            Shift.end_at.is_not(None),
                            Shift.end_at >= chart_window_start,
                        ),
                    )
                ).scalars().all(),
            )

        def _shift_net_hours(s: Shift) -> Decimal:
            if s.end_at is None:
                return Decimal(0)
            return compute_hours(s.start_at, s.end_at)

        week_hours = sum(
            (_shift_net_hours(s) for s in window_shifts if s.end_at and s.end_at >= week_start),
            Decimal(0),
        ).quantize(Decimal("0.01"))
        month_hours = sum(
            (_shift_net_hours(s) for s in window_shifts if s.end_at and s.end_at >= month_start),
            Decimal(0),
        ).quantize(Decimal("0.01"))

        # Build day-bucket series (last 30 days, ending today, in local tz)
        buckets: dict[str, Decimal] = {}
        for offset in range(chart_window_days):
            d = chart_window_start_date + timedelta(days=offset)
            buckets[d.isoformat()] = Decimal(0)
        for s in window_shifts:
            if s.end_at is None:
                continue
            local_day = s.end_at.astimezone(tz).date().isoformat()
            if local_day in buckets:
                buckets[local_day] += _shift_net_hours(s)
        chart_labels = list(buckets.keys())
        chart_values = [float(v.quantize(Decimal("0.01"))) for v in buckets.values()]

        ctx: dict[str, object] = {
            "request": request,
            "title": "Сводка",
            "open_count": open_count,
            "today_count": today_count,
            "users_count": users_count,
            "sites_count": sites_count,
            "week_hours": str(week_hours),
            "month_hours": str(month_hours),
            "now_local": now_local.strftime("%Y-%m-%d %H:%M %Z"),
            "chart_labels": chart_labels,
            "chart_values": chart_values,
        }
        return templates.TemplateResponse(request, "dashboard.html", ctx)

    @app.get("/calendar", response_class=HTMLResponse)
    async def calendar_view(
        request: Request,
        month: str | None = None,
        _user: str = Depends(require_admin),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        tz = ZoneInfo(settings.timezone)
        today_local = datetime.now(tz=tz).date()
        if month:
            try:
                year_int, month_int = (int(p) for p in month.split("-", 1))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bad_month",
                ) from exc
            if not 1 <= month_int <= 12:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bad_month",
                )
        else:
            year_int, month_int = today_local.year, today_local.month

        first_day = datetime(year_int, month_int, 1, tzinfo=tz).date()
        if month_int == 12:
            next_first = datetime(year_int + 1, 1, 1, tzinfo=tz).date()
        else:
            next_first = datetime(year_int, month_int + 1, 1, tzinfo=tz).date()
        period_start = datetime.combine(first_day, datetime.min.time(), tzinfo=tz)
        period_end = datetime.combine(next_first, datetime.min.time(), tzinfo=tz)

        async for session in get_session():
            shifts = list(
                (
                    await session.execute(
                        select(Shift).where(
                            Shift.end_at.is_not(None),
                            Shift.end_at >= period_start,
                            Shift.end_at < period_end,
                        ),
                    )
                ).scalars().all(),
            )

        # Aggregate per-day hours and shift count
        day_hours: dict[str, Decimal] = {}
        day_count: dict[str, int] = {}
        for s in shifts:
            if s.end_at is None:
                continue
            key = s.end_at.astimezone(tz).date().isoformat()
            day_hours[key] = day_hours.get(key, Decimal(0)) + compute_hours(
                s.start_at, s.end_at,
            )
            day_count[key] = day_count.get(key, 0) + 1

        # Build week-aligned grid (Mon..Sun)
        leading_blanks = first_day.weekday()  # Monday=0
        days_in_month = (next_first - first_day).days
        cells: list[dict[str, object]] = []
        for _ in range(leading_blanks):
            cells.append({"empty": True})
        for d in range(1, days_in_month + 1):
            key = first_day.replace(day=d).isoformat()
            cells.append({
                "empty": False,
                "day": d,
                "hours": str(day_hours.get(key, Decimal(0)).quantize(Decimal("0.01"))),
                "count": day_count.get(key, 0),
                "today": first_day.replace(day=d) == today_local,
            })
        # pad trailing to fill last week row
        while len(cells) % 7 != 0:
            cells.append({"empty": True})

        prev_month = (
            f"{year_int - 1}-12" if month_int == 1
            else f"{year_int}-{month_int - 1:02d}"
        )
        next_month = (
            f"{year_int + 1}-01" if month_int == 12
            else f"{year_int}-{month_int + 1:02d}"
        )

        return templates.TemplateResponse(
            request,
            "calendar.html",
            {
                "request": request,
                "title": f"Календарь {year_int}-{month_int:02d}",
                "year": year_int,
                "month": month_int,
                "month_label": f"{year_int:04d}-{month_int:02d}",
                "cells": cells,
                "prev_month": prev_month,
                "next_month": next_month,
            },
        )

    @app.get("/users", response_class=HTMLResponse)
    async def users_list(
        request: Request,
        _user: str = Depends(require_admin),
    ) -> HTMLResponse:
        async for session in get_session():
            rows = list(
                (
                    await session.execute(
                        select(User).order_by(User.role.desc(), User.name),
                    )
                ).scalars().all(),
            )
            crew_ids = {u.crew_id for u in rows if u.crew_id is not None}
            crews_map: dict[int, str] = {}
            if crew_ids:
                cres = await session.execute(
                    select(Crew).where(Crew.id.in_(crew_ids)),
                )
                crews_map = {c.id: c.name for c in cres.scalars().all()}
        users_view = [
            {
                "id": u.id,
                "name": u.name,
                "tg_id": u.tg_id,
                "role": u.role,
                "crew": crews_map.get(u.crew_id, "—") if u.crew_id else "—",
                "rate": str(u.hourly_rate) if u.hourly_rate is not None else "—",
            }
            for u in rows
        ]
        return templates.TemplateResponse(
            request,
            "users.html",
            {"request": request, "title": "Работники", "users": users_view},
        )

    @app.get("/sites", response_class=HTMLResponse)
    async def sites_list(
        request: Request,
        _user: str = Depends(require_admin),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        tz = ZoneInfo(settings.timezone)
        async for session in get_session():
            rows = list(
                (
                    await session.execute(
                        select(Site).order_by(Site.archived_at.is_(None).desc(), Site.name),
                    )
                ).scalars().all(),
            )
        sites_view = [
            {
                "id": s.id,
                "name": s.name,
                "rate": str(s.hourly_rate) if s.hourly_rate is not None else "—",
                "polygon": "да" if s.polygon is not None else "нет",
                "archived": (
                    s.archived_at.astimezone(tz).strftime("%Y-%m-%d")
                    if s.archived_at is not None
                    else "—"
                ),
            }
            for s in rows
        ]
        return templates.TemplateResponse(
            request,
            "sites.html",
            {"request": request, "title": "Объекты", "sites": sites_view},
        )

    @app.get("/shifts", response_class=HTMLResponse)
    async def shifts_list(
        request: Request,
        days: int = 14,
        q: str = "",
        site: int | None = None,
        _user: str = Depends(require_admin),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        tz = ZoneInfo(settings.timezone)
        days_clamped = max(1, min(days, 90))
        cutoff = datetime.now(tz=UTC) - timedelta(days=days_clamped)
        q_norm = q.strip()
        async for session in get_session():
            stmt = (
                select(Shift)
                .where(Shift.start_at >= cutoff)
                .order_by(desc(Shift.start_at))
                .limit(500)
            )
            if site is not None:
                stmt = stmt.where(Shift.site_id == site)
            if q_norm:
                stmt = stmt.join(User, Shift.user_id == User.id).where(
                    User.name.ilike(f"%{q_norm}%"),
                )
            rows = list((await session.execute(stmt)).scalars().all())
            uids = {s.user_id for s in rows}
            sids = {s.site_id for s in rows if s.site_id is not None}
            users_map: dict[int, str] = {}
            sites_map: dict[int, str] = {}
            if uids:
                ures = await session.execute(
                    select(User).where(User.id.in_(uids)),
                )
                users_map = {u.id: u.name for u in ures.scalars().all()}
            if sids:
                sres = await session.execute(
                    select(Site).where(Site.id.in_(sids)),
                )
                sites_map = {s.id: s.name for s in sres.scalars().all()}
            all_sites = list(
                (
                    await session.execute(
                        select(Site).order_by(Site.name),
                    )
                ).scalars().all(),
            )
            breaks_by_shift = await get_breaks_for_shifts(
                session, [s.id for s in rows],
            )

        shifts_view: list[dict[str, object]] = []
        for s in rows:
            start_local = s.start_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            end_local = (
                s.end_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                if s.end_at is not None
                else "—"
            )
            gross = (
                Decimal(0) if s.end_at is None
                else compute_hours(s.start_at, s.end_at)
            )
            br_hours = total_break_hours(
                breaks_by_shift.get(s.id, []), s.start_at, s.end_at,
            ) if s.end_at is not None else Decimal(0)
            net = max(gross - br_hours, Decimal(0))
            shifts_view.append({
                "id": s.id,
                "user": users_map.get(s.user_id, "—"),
                "site": sites_map.get(s.site_id, "—") if s.site_id else "—",
                "start": start_local,
                "end": end_local,
                "hours": str(net.quantize(Decimal("0.01"))),
                "auto": "да" if s.auto_closed else "нет",
            })
        site_options = [
            {"id": s.id, "name": s.name, "selected": s.id == site}
            for s in all_sites
        ]
        return templates.TemplateResponse(
            request,
            "shifts.html",
            {
                "request": request,
                "title": f"Смены за {days_clamped} дн",
                "shifts": shifts_view,
                "days": days_clamped,
                "q": q_norm,
                "site_id": site,
                "site_options": site_options,
            },
        )

    @app.get("/audit", response_class=HTMLResponse)
    async def audit_list(
        request: Request,
        limit: int = 100,
        entity: str = "",
        actor: int | None = None,
        _user: str = Depends(require_admin),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        tz = ZoneInfo(settings.timezone)
        limit_clamped = max(1, min(limit, 500))
        entity_norm = entity.strip()
        async for session in get_session():
            stmt = (
                select(AuditLog)
                .order_by(desc(AuditLog.created_at))
                .limit(limit_clamped)
            )
            if entity_norm:
                stmt = stmt.where(AuditLog.entity_type == entity_norm)
            if actor is not None:
                actor_user = (
                    await session.execute(
                        select(User).where(User.tg_id == actor),
                    )
                ).scalar_one_or_none()
                if actor_user is not None:
                    stmt = stmt.where(AuditLog.user_id == actor_user.id)
                else:
                    stmt = stmt.where(AuditLog.user_id == -1)
            rows = list((await session.execute(stmt)).scalars().all())
            actor_ids = {r.user_id for r in rows}
            actors_map: dict[int, str] = {}
            if actor_ids:
                ares = await session.execute(
                    select(User).where(User.id.in_(actor_ids)),
                )
                actors_map = {u.id: u.name for u in ares.scalars().all()}
        audit_view = [
            {
                "id": r.id,
                "when": r.created_at.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                "actor": actors_map.get(r.user_id, f"id={r.user_id}"),
                "entity": f"{r.entity_type}#{r.entity_id}",
                "action": r.action,
                "diff": str(r.diff)[:200],
            }
            for r in rows
        ]
        return templates.TemplateResponse(
            request,
            "audit.html",
            {
                "request": request,
                "title": "Журнал изменений",
                "rows": audit_view,
                "limit": limit_clamped,
                "entity": entity_norm,
                "actor": actor or "",
            },
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
