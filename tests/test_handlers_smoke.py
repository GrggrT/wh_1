"""Smoke tests for handler registration and string formatting."""

from src.bot.strings import STRINGS, t


class TestStrings:
    def test_all_keys_format_without_error(self) -> None:
        """All string templates with no args should not crash."""
        for key, template in STRINGS["ru"].items():
            # Only test templates without format placeholders
            if "{" not in template:
                result = t(key)
                assert isinstance(result, str)

    def test_welcome_format(self) -> None:
        result = t("welcome", name="Иван")
        assert "Иван" in result

    def test_shift_started_format(self) -> None:
        result = t("shift_started", time="08:00", site="Стройка 1")
        assert "08:00" in result
        assert "Стройка 1" in result

    def test_missing_key_returns_key(self) -> None:
        assert t("nonexistent_key") == "nonexistent_key"


class TestRouterRegistration:
    def test_common_router_has_handlers(self) -> None:
        from src.bot.handlers.common import router
        # Router should have message handlers registered
        assert len(router.message.handlers) > 0

    def test_shifts_router_has_handlers(self) -> None:
        from src.bot.handlers.shifts import router
        assert len(router.message.handlers) > 0
        assert len(router.callback_query.handlers) > 0

    def test_reports_router_has_handlers(self) -> None:
        from src.bot.handlers.reports import router
        assert len(router.message.handlers) > 0

    def test_exports_router_has_handlers(self) -> None:
        from src.bot.handlers.exports import router
        assert len(router.message.handlers) > 0
