import pytest

from auto_lending_bot.config import Settings
from auto_lending_bot.safety import SafetyError, validate_run_settings


def test_validate_run_settings_allows_mock_dry_run() -> None:
    validate_run_settings(_settings(exchange="mock", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_non_mock_exchange() -> None:
    with pytest.raises(SafetyError, match="Only EXCHANGE=mock"):
        validate_run_settings(_settings(exchange="poloniex", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_live_mode_without_explicit_allowance() -> None:
    with pytest.raises(SafetyError, match="ALLOW_LIVE_TRADING=true"):
        validate_run_settings(_settings(exchange="mock", dry_run=False, allow_live_trading=False))


def test_validate_run_settings_allows_explicit_live_mode() -> None:
    validate_run_settings(_settings(exchange="mock", dry_run=False, allow_live_trading=True))


def _settings(exchange: str, dry_run: bool, allow_live_trading: bool) -> Settings:
    return Settings(
        allow_live_trading=allow_live_trading,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        dry_run=dry_run,
        exchange=exchange,
        max_loops=1,
        min_daily_rate=0.00005,
        min_loan_size=0.01,
        spread_lend=3,
        database_url="sqlite:///data/test.db",
        log_level="INFO",
    )
