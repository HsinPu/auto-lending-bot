import logging

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
)


def test_runner_records_dry_run_offers_without_creating_exchange_offers(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(database_url)
    exchange = MockExchangeClient()
    loan_offers = LoanOfferRepository(database_url)
    active_loans = ActiveLoanRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=exchange,
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        active_loans=active_loans,
        open_offers=OpenLoanOfferRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    assert loan_offers.count() == 6
    assert active_loans.count() == 1
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
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    with caplog.at_level(logging.INFO):
        runner.run_once()

    assert "strategy_debug currency=BTC" in caplog.text
    assert "best_daily_rate=0.00008000" in caplog.text


def test_runner_does_not_retry_authentication_errors(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    exchange = AuthFailingExchange()
    settings = _settings(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=exchange,
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    try:
        runner.run()
    except ExchangeAuthenticationError:
        pass
    else:
        raise AssertionError("Expected ExchangeAuthenticationError")

    assert exchange.calls == 1


def test_runner_rebalances_open_offers_without_canceling_in_dry_run(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(database_url, auto_rebalance_open_offers=True, auto_cancel_open_offers=True)
    exchange = MockExchangeClient()
    exchange.create_loan_offer(LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2))
    open_offers = OpenLoanOfferRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=exchange,
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=open_offers,
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    assert open_offers.count() == 1


def _settings(
    database_url: str,
    strategy_debug: bool = False,
    auto_rebalance_open_offers: bool = False,
    auto_cancel_open_offers: bool = False,
) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="",
        api_secret="",
        bitfinex_enable_live_offers=False,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        auto_rebalance_open_offers=auto_rebalance_open_offers,
        auto_cancel_open_offers=auto_cancel_open_offers,
        dry_run=True,
        exchange="mock",
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
        smoke_test_currency="BTC",
        strategy_debug=strategy_debug,
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
        database_url=database_url,
        log_level="INFO",
    )


class AuthFailingExchange:
    def __init__(self) -> None:
        self.calls = 0

    def get_active_loans(self):
        self.calls += 1
        raise ExchangeAuthenticationError("invalid key")

    def get_lending_balances(self):
        return []

    def get_loan_orders(self, currency: str):
        return []

    def get_open_loan_offers(self):
        return []

    def create_loan_offer(self, offer):
        return ""

    def cancel_loan_offer(self, offer_id: str):
        return None
