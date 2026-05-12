import logging

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
)


def test_runner_records_dry_run_offers_without_creating_exchange_offers(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(database_url)
    exchange = MockExchangeClient()
    loan_offers = LoanOfferRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=exchange,
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    assert loan_offers.count() == 6
    assert exchange.get_open_loan_offers() == []


def test_runner_logs_strategy_debug_details(tmp_path, caplog) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(database_url, strategy_debug=True)

    runner = BotRunner(
        settings=settings,
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    with caplog.at_level(logging.INFO):
        runner.run_once()

    assert "strategy_debug currency=BTC" in caplog.text
    assert "best_daily_rate=0.00008000" in caplog.text


def _settings(database_url: str, strategy_debug: bool = False) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="",
        api_secret="",
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        dry_run=True,
        exchange="mock",
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        report_path="reports/dashboard.html",
        smoke_test_currency="BTC",
        strategy_debug=strategy_debug,
        hide_coins=True,
        max_amount_to_lend=None,
        max_single_offer_amount=None,
        max_total_lend_amount=None,
        min_daily_rate=0.00005,
        max_daily_rate=0.05,
        min_loan_size=0.01,
        max_percent_to_lend=100,
        spread_lend=3,
        database_url=database_url,
        log_level="INFO",
    )
