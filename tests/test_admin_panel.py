"""Smoke tests for the FastAPI admin panel: auth gating + healthcheck."""

import base64
import os

import pytest
from fastapi.testclient import TestClient
from src.admin.app import create_app
from src.core.config import Settings, get_settings


def _make_settings(password: str) -> Settings:
    os.environ.setdefault("BOT_TOKEN", "test")
    os.environ.setdefault("OWNER_TG_ID", "1")
    return Settings(  # type: ignore[call-arg]
        bot_token="test",
        owner_tg_id=1,
        admin_password=password,
        admin_username="owner",
    )


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
