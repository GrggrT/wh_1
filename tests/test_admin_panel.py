"""Smoke tests for the FastAPI admin panel: auth gating + healthcheck."""

import base64
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.admin.app import create_app
from src.admin.rate_limit import tracker
from src.core.config import Settings, get_settings


def _make_settings(password: str, **overrides: object) -> Settings:
    os.environ.setdefault("BOT_TOKEN", "test")
    os.environ.setdefault("OWNER_TG_ID", "1")
    kwargs: dict[str, object] = {
        "bot_token": "test",
        "owner_tg_id": 1,
        "admin_password": password,
        "admin_username": "owner",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[call-arg,arg-type]


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    tracker.reset()


def _basic(user: str, password: str) -> dict[str, str]:
    raw = f"{user}:{password}".encode()
    token = base64.b64encode(raw).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client_with_password() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _make_settings("secret")
    return TestClient(app)


@pytest.fixture
def client_without_password() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _make_settings("")
    return TestClient(app)


def test_healthz_is_open(client_with_password: TestClient) -> None:
    resp = client_with_password.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unauthenticated_dashboard_returns_401(
    client_with_password: TestClient,
) -> None:
    resp = client_with_password.get("/")
    assert resp.status_code == 401


def test_wrong_password_returns_401(client_with_password: TestClient) -> None:
    resp = client_with_password.get("/", headers=_basic("owner", "wrong"))
    assert resp.status_code == 401


def test_disabled_admin_returns_503(
    client_without_password: TestClient,
) -> None:
    resp = client_without_password.get(
        "/", headers=_basic("owner", "anything"),
    )
    assert resp.status_code == 503


def test_webhook_route_absent_when_not_configured(
    client_with_password: TestClient,
) -> None:
    resp = client_with_password.post("/tg/webhook", json={})
    assert resp.status_code == 404


def test_metrics_requires_auth(client_with_password: TestClient) -> None:
    resp = client_with_password.get("/metrics")
    assert resp.status_code == 401


def test_metrics_disabled_admin_returns_503(
    client_without_password: TestClient,
) -> None:
    resp = client_without_password.get(
        "/metrics", headers=_basic("owner", "anything"),
    )
    assert resp.status_code == 503


def test_rate_limit_blocks_after_max_failures() -> None:
    """After admin_auth_max_failures bad attempts, even correct creds get 429."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _make_settings(
        "secret",
        admin_auth_max_failures=3,
        admin_auth_window_seconds=60,
        admin_auth_block_seconds=300,
    )
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/", headers=_basic("owner", "wrong")).status_code == 401
    # Next request: even with correct password, the IP is blocked.
    resp = client.get("/", headers=_basic("owner", "secret"))
    assert resp.status_code == 429
    assert resp.json()["detail"] == "too_many_attempts"


def test_rate_limit_clears_on_successful_auth() -> None:
    """A successful auth resets the per-IP failure counter."""
    from unittest.mock import MagicMock

    from fastapi.security import HTTPBasicCredentials
    from src.admin.auth import require_admin

    settings = _make_settings(
        "secret",
        admin_auth_max_failures=3,
        admin_auth_window_seconds=60,
        admin_auth_block_seconds=300,
    )
    request = MagicMock()
    request.client.host = "1.2.3.4"

    # 2 failures (one below threshold).
    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            require_admin(
                request,
                credentials=HTTPBasicCredentials(username="owner", password="x"),
                settings=settings,
            )
        assert exc.value.status_code == 401

    # Successful auth clears the counter.
    user = require_admin(
        request,
        credentials=HTTPBasicCredentials(username="owner", password="secret"),
        settings=settings,
    )
    assert user == "owner"

    # Three more bad attempts: all return 401, none get blocked early.
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            require_admin(
                request,
                credentials=HTTPBasicCredentials(username="owner", password="x"),
                settings=settings,
            )
        assert exc.value.status_code == 401


def test_webhook_rejects_wrong_secret() -> None:
    """Webhook route returns 403 if X-Telegram-Bot-Api-Secret-Token mismatches."""
    from unittest.mock import MagicMock

    app = create_app(
        bot=MagicMock(),
        dispatcher=MagicMock(),
        webhook_path="/tg/webhook",
        webhook_secret="correct",
    )
    app.dependency_overrides[get_settings] = lambda: _make_settings("secret")
    client = TestClient(app)
    resp = client.post(
        "/tg/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403
