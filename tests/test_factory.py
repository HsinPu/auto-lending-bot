from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.integrations.poloniex import PoloniexClient


def test_create_exchange_client_returns_mock_client() -> None:
    assert isinstance(create_exchange_client(_settings("mock")), MockExchangeClient)


def test_create_exchange_client_returns_poloniex_client() -> None:
    assert isinstance(create_exchange_client(_settings("poloniex")), PoloniexClient)


def _settings(exchange: str) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="key",
        api_secret="secret",
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        dry_run=True,
        exchange=exchange,
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        report_path="reports/dashboard.html",
        hide_coins=True,
        max_amount_to_lend=None,
        max_single_offer_amount=None,
        max_total_lend_amount=None,
        min_daily_rate=0.00005,
        max_daily_rate=0.05,
        min_loan_size=0.01,
        max_percent_to_lend=100,
        spread_lend=3,
        database_url="sqlite:///data/test.db",
        log_level="INFO",
    )
