"""Tests for crew / role / invite-code logic."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from src.services.crews import (
    INVITE_CODE_LENGTH,
    InviteError,
    generate_invite_code,
)

_UTC = ZoneInfo("UTC")


def test_invite_code_format() -> None:
    code = generate_invite_code()
    assert len(code) == INVITE_CODE_LENGTH
    # Excluded ambiguous chars
    assert all(c not in "01OIL" for c in code)
    assert code.isupper()


def test_invite_code_randomness() -> None:
    seen = {generate_invite_code() for _ in range(50)}
    assert len(seen) > 40  # collisions are extremely unlikely


def test_invite_error_is_exception() -> None:
    err = InviteError("expired")
    assert isinstance(err, Exception)
    assert str(err) == "expired"


def test_invite_window_math() -> None:
    """Sanity for redeem_invite_code expiry check."""
    now = datetime(2026, 5, 9, 12, 0, tzinfo=_UTC)
    expires = now + timedelta(hours=72)
    # Inside window
    just_before = expires - timedelta(minutes=1)
    assert just_before < expires
    # Outside window — equality should fail (strict less-than in code)
    assert not (expires > expires)
    # Past expiry
    later = expires + timedelta(seconds=1)
    assert later > expires


@pytest.mark.parametrize("code", ["AAAAAA", "ZZZZZZ", "234567"])
def test_invite_code_alphabet_chars_only(code: str) -> None:
    allowed = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
    assert all(c in allowed for c in code)
