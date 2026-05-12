import pytest

from auto_lending_bot.config import Settings
from auto_lending_bot.safety import SafetyError, validate_run_settings


def test_validate_run_settings_allows_mock_dry_run() -> None:
    validate_run_settings(_settings(exchange="mock", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_non_mock_exchange() -> None:
    with pytest.raises(SafetyError, match="Only EXCHANGE=mock or EXCHANGE=poloniex"):
        validate_run_settings(_settings(exchange="bitfinex", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_live_mode_without_explicit_allowance() -> None:
    with pytest.raises(SafetyError, match="ALLOW_LIVE_TRADING=true"):
        validate_run_settings(_settings(exchange="mock", dry_run=False, allow_live_trading=False))


def test_validate_run_settings_allows_explicit_live_mode() -> None:
    validate_run_settings(_settings(exchange="mock", dry_run=False, allow_live_trading=True))


def test_validate_run_settings_rejects_poloniex_without_credentials() -> None:
    with pytest.raises(SafetyError, match="EXCHANGE_API_KEY"):
        validate_run_settings(_settings(exchange="poloniex", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_poloniex_live_mode() -> None:
    with pytest.raises(SafetyError, match="read-only"):
        validate_run_settings(
            _settings(
                exchange="poloniex",
                dry_run=False,
                allow_live_trading=True,
                api_key="key",
                api_secret="secret",
            )
        )


def test_validate_run_settings_allows_poloniex_dry_run_with_credentials() -> None:
    validate_run_settings(
        _settings(
            exchange="poloniex",
            dry_run=True,
            allow_live_trading=False,
            api_key="key",
            api_secret="secret",
        )
    )


def _settings(
    exchange: str,
    dry_run: bool,
    allow_live_trading: bool,
    api_key: str = "",
    api_secret: str = "",
) -> Settings:
    return Settings(
        allow_live_trading=allow_live_trading,
        api_key=api_key,
        api_secret=api_secret,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        dry_run=dry_run,
        exchange=exchange,
        http_timeout_seconds=30,
        max_loops=1,
        hide_coins=True,
        max_amount_to_lend=None,
        min_daily_rate=0.00005,
        max_daily_rate=0.05,
        min_loan_size=0.01,
        max_percent_to_lend=100,
        spread_lend=3,
        database_url="sqlite:///data/test.db",
        log_level="INFO",
    )
