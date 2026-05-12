from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.bitfinex import BitfinexClient
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient


def test_create_exchange_client_returns_mock_client() -> None:
    assert isinstance(create_exchange_client(_settings("mock")), MockExchangeClient)


def test_create_exchange_client_returns_bitfinex_client() -> None:
    assert isinstance(create_exchange_client(_settings("bitfinex")), BitfinexClient)


def _settings(exchange: str) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="key",
        api_secret="secret",
        bitfinex_enable_live_offers=False,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        auto_rebalance_open_offers=False,
        auto_cancel_open_offers=False,
        dry_run=True,
        exchange=exchange,
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        market_analysis_levels=10,
        market_analysis_method="off",
        market_analysis_percentile=75,
        market_analysis_macd_short_samples=3,
        market_analysis_macd_long_samples=10,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
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
        max_single_offer_amount=None,
        max_total_lend_amount=None,
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
