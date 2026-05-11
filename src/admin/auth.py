"""HTTP Basic auth for the admin panel using a single shared owner password."""

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.admin.rate_limit import tracker
from src.core.config import Settings, get_settings

_security = HTTPBasic()


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(_security),
    settings: Settings = Depends(get_settings),
) -> str:
    """Dependency that enforces HTTP Basic with the configured admin creds.

    Failed attempts are counted per client IP; when a client exceeds
    ``admin_auth_max_failures`` within ``admin_auth_window_seconds`` it is
    blocked with ``429 Too Many Requests`` for ``admin_auth_block_seconds``.
    """
    if not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_disabled",
        )
    ip = _client_ip(request)
    if tracker.is_blocked(
        ip,
        max_failures=settings.admin_auth_max_failures,
        window_seconds=settings.admin_auth_window_seconds,
        block_seconds=settings.admin_auth_block_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too_many_attempts",
        )
    user_ok = secrets.compare_digest(
        credentials.username, settings.admin_username,
    )
    pass_ok = secrets.compare_digest(
        credentials.password, settings.admin_password,
    )
    if not (user_ok and pass_ok):
        tracker.record_failure(
            ip, window_seconds=settings.admin_auth_window_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad_credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    tracker.clear_failures(ip)
    return credentials.username
