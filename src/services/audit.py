"""Audit log helper — single point for writing audit_log rows."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import AuditLog


async def write_audit(
    session: AsyncSession,
    actor_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    diff: dict[str, object],
) -> None:
    """Append an audit_log row. Caller is responsible for committing the session."""
    session.add(
        AuditLog(
            user_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            diff=diff,
        ),
    )
    await session.flush()
