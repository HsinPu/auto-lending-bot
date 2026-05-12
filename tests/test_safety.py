import pytest

from auto_lending_bot.config import Settings
from auto_lending_bot.safety import SafetyError, validate_run_settings


def test_validate_run_settings_allows_mock_dry_run() -> None:
    validate_run_settings(_settings(exchange="mock", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_non_mock_exchange() -> None:
    with pytest.raises(SafetyError, match="Only EXCHANGE=mock"):
        validate_run_settings(_settings(exchange="kraken", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_live_mode_without_explicit_allowance() -> None:
    with pytest.raises(SafetyError, match="ALLOW_LIVE_TRADING=true"):
        validate_run_settings(_settings(exchange="mock", dry_run=False, allow_live_trading=False))


def test_validate_run_settings_allows_explicit_live_mode() -> None:
    validate_run_settings(
        _settings(
            exchange="bitfinex",
            dry_run=False,
            allow_live_trading=True,
            api_key="key",
            api_secret="secret",
            bitfinex_enable_live_offers=True,
            max_single_offer_amount=0.1,
            max_total_lend_amount=1.0,
        )
    )


def test_validate_run_settings_rejects_live_mode_without_amount_limits() -> None:
    with pytest.raises(SafetyError, match="MAX_TOTAL_LEND_AMOUNT"):
        validate_run_settings(
            _settings(
                exchange="bitfinex",
                dry_run=False,
                allow_live_trading=True,
                api_key="key",
                api_secret="secret",
                bitfinex_enable_live_offers=True,
            )
        )


def test_validate_run_settings_rejects_bitfinex_without_credentials() -> None:
    with pytest.raises(SafetyError, match="EXCHANGE_API_KEY"):
        validate_run_settings(_settings(exchange="bitfinex", dry_run=True, allow_live_trading=False))


def test_validate_run_settings_rejects_bitfinex_live_mode_without_live_flag() -> None:
    with pytest.raises(SafetyError, match="BITFINEX_ENABLE_LIVE_OFFERS"):
        validate_run_settings(
            _settings(
                exchange="bitfinex",
                dry_run=False,
                allow_live_trading=True,
                api_key="key",
                api_secret="secret",
                max_single_offer_amount=0.1,
                max_total_lend_amount=1.0,
            )
        )


def test_validate_run_settings_allows_bitfinex_live_mode_with_all_guards() -> None:
    validate_run_settings(
        _settings(
            exchange="bitfinex",
            dry_run=False,
            allow_live_trading=True,
            api_key="key",
            api_secret="secret",
            bitfinex_enable_live_offers=True,
            max_single_offer_amount=0.1,
            max_total_lend_amount=1.0,
        )
    )


def test_validate_run_settings_allows_bitfinex_dry_run_with_credentials() -> None:
    validate_run_settings(
        _settings(
            exchange="bitfinex",
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
    bitfinex_enable_live_offers: bool = False,
    max_single_offer_amount: float | None = None,
    max_total_lend_amount: float | None = None,
) -> Settings:
    return Settings(
        allow_live_trading=allow_live_trading,
        api_key=api_key,
        api_secret=api_secret,
        bitfinex_enable_live_offers=bitfinex_enable_live_offers,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        dry_run=dry_run,
        exchange=exchange,
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        smoke_test_currency="BTC",
        strategy_debug=False,
        telegram_bot_token="",
        telegram_chat_id="",
        hide_coins=True,
        gap_mode="off",
        gap_bottom=0,
        gap_top=0,
        xday_threshold=0,
        xdays=2,
        xday_spread=0,
        frr_as_min=False,
        frr_delta=0,
        max_amount_to_lend=None,
        max_single_offer_amount=max_single_offer_amount,
        max_total_lend_amount=max_total_lend_amount,
        min_daily_rate=0.00005,
        max_daily_rate=0.05,
        min_loan_size=0.01,
        max_percent_to_lend=100,
        max_to_lend_rate=0,
        end_date=None,
        spread_lend=3,
        database_url="sqlite:///data/test.db",
        log_level="INFO",
    )
