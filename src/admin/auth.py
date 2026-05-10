"""HTTP Basic auth for the admin panel using a single shared owner password."""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.core.config import Settings, get_settings

_security = HTTPBasic()


def require_admin(
    credentials: HTTPBasicCredentials = Depends(_security),
    settings: Settings = Depends(get_settings),
) -> str:
    """Dependency that enforces HTTP Basic with the configured admin creds."""
    if not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_disabled",
        )
    user_ok = secrets.compare_digest(
        credentials.username, settings.admin_username,
    )
    pass_ok = secrets.compare_digest(
        credentials.password, settings.admin_password,
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad_credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
