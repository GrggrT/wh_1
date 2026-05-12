"""Tests for the simple-mode reply keyboard (Phase 6.1)."""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup
from src.bot.keyboards import simple_menu
from src.bot.strings import t
from src.services.app_settings import SettingsSnapshot


def _snap(
    *,
    sites: bool = False,
    crews: bool = False,
    geofence: bool = False,
    legacy: bool = False,
) -> SettingsSnapshot:
    return SettingsSnapshot(
        sites_enabled=sites,
        crews_enabled=crews,
        geofence_enabled=geofence,
        legacy_clock_inout_enabled=legacy,
    )


def _labels(markup: ReplyKeyboardMarkup) -> list[str]:
    return [btn.text for row in markup.keyboard for btn in row]


def test_simple_menu_default_worker_has_only_core_buttons() -> None:
    markup = simple_menu(_snap(), role="worker")
    labels = _labels(markup)
    assert t("menu_btn_hours") in labels
    assert t("menu_btn_calendar") in labels
    assert t("menu_btn_period") in labels
    assert t("menu_btn_cash") in labels
    assert t("menu_btn_reports") in labels
    assert t("menu_btn_profile") in labels
    # Phase 6.11a: «Мои дни» button removed.
    assert "Мои дни" not in " ".join(labels)
    # Legacy + crew buttons are hidden by default.
    assert not any("смену" in label.lower() for label in labels)
    assert not any("бригад" in label.lower() for label in labels)


def test_simple_menu_legacy_toggle_does_not_add_shift_buttons() -> None:
    """Phase 6.9: legacy shift buttons are permanently removed from simple_menu."""
    markup = simple_menu(_snap(legacy=True), role="worker")
    labels = _labels(markup)
    assert not any("Начать смену" in label for label in labels)
    assert not any("Закончить смену" in label for label in labels)


def test_simple_menu_foreman_with_crews_adds_crew_buttons() -> None:
    markup = simple_menu(_snap(crews=True), role="foreman")
    labels = _labels(markup)
    assert any("Бригада сегодня" in label for label in labels)
    assert any("Пригласить" in label for label in labels)


def test_simple_menu_worker_does_not_get_crew_buttons_even_when_enabled() -> None:
    markup = simple_menu(_snap(crews=True), role="worker")
    labels = _labels(markup)
    assert not any("Бригада сегодня" in label for label in labels)


def test_simple_menu_owner_with_crews_has_crew_row() -> None:
    markup = simple_menu(_snap(crews=True), role="owner")
    labels = _labels(markup)
    assert any("Бригада сегодня" in label for label in labels)
    assert not any("Начать смену" in label for label in labels)
