import logging

import pytest

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import ActiveLoan, LendingHistoryEntry, LoanOffer, LoanOrder
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    MarketRateRepository,
    NotificationStateRepository,
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
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
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
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
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
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
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


def test_runner_uses_inactive_sleep_when_no_offers_are_created(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    sleep_calls: list[int] = []
    monkeypatch.setattr("auto_lending_bot.bot.runner.time.sleep", sleep_calls.append)

    runner = BotRunner(
        settings=_settings(
            database_url,
            max_loops=2,
            bot_sleep_seconds=60,
            bot_inactive_sleep_seconds=300,
        ),
        exchange=NoOfferExchange(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run()

    assert sleep_calls == [300]


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
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    assert open_offers.count() == 1


def test_runner_keeps_stuck_open_offers_during_live_rebalance(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    exchange = StuckOfferExchange()
    open_offers = OpenLoanOfferRepository(database_url)

    runner = BotRunner(
        settings=_settings(
            database_url,
            dry_run=False,
            auto_rebalance_open_offers=True,
            auto_cancel_open_offers=True,
            keep_stuck_orders=True,
        ),
        exchange=exchange,
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=open_offers,
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=SpyNotifier(),
    )

    runner.run_once()

    assert exchange.canceled_offer_ids == []
    assert open_offers.count() == 1


def test_runner_uses_percentile_market_analysis_minimum(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(database_url, market_analysis_method="percentile", hide_coins=False)
    market_analysis_rates = MarketAnalysisRateRepository(database_url)
    market_analysis_rates.add_many(
        [
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00012),
        ]
    )
    loan_offers = LoanOfferRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=market_analysis_rates,
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    btc_offer = next(row for row in loan_offers.recent() if row["currency"] == "BTC")
    assert btc_offer["daily_rate"] == 0.00012


def test_runner_uses_macd_market_analysis_minimum(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(
        database_url,
        market_analysis_method="macd",
        hide_coins=False,
        market_analysis_macd_short_samples=2,
        market_analysis_macd_long_samples=5,
    )
    market_analysis_rates = MarketAnalysisRateRepository(database_url)
    for daily_rate in [0.00005, 0.00006, 0.00007, 0.00008, 0.00015]:
        market_analysis_rates.add_many(
            [LoanOrder(currency="BTC", amount=1.0, daily_rate=daily_rate)]
        )
    loan_offers = LoanOfferRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=market_analysis_rates,
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    btc_offer = next(row for row in loan_offers.recent() if row["currency"] == "BTC")
    assert btc_offer["daily_rate"] == pytest.approx(0.000115)


def test_runner_uses_seconds_macd_market_analysis_minimum(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    settings = _settings(
        database_url,
        market_analysis_method="macd",
        hide_coins=False,
        market_analysis_macd_short_seconds=60,
        market_analysis_macd_long_seconds=3600,
        market_analysis_multiplier=1.05,
    )
    market_analysis_rates = MarketAnalysisRateRepository(database_url)
    for daily_rate in [0.00008, 0.0001]:
        market_analysis_rates.add_many(
            [LoanOrder(currency="BTC", amount=1.0, daily_rate=daily_rate)]
        )
    loan_offers = LoanOfferRepository(database_url)

    runner = BotRunner(
        settings=settings,
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=market_analysis_rates,
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    btc_offer = next(row for row in loan_offers.recent() if row["currency"] == "BTC")
    assert btc_offer["daily_rate"] == pytest.approx(0.0000945)


def test_runner_passes_active_amount_to_strategy_cap(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    monkeypatch.setenv("BTC_MAX_ACTIVE_AMOUNT", "0.06")
    loan_offers = LoanOfferRepository(database_url)

    runner = BotRunner(
        settings=_settings(database_url),
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=loan_offers,
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=Notifier(),
    )

    runner.run_once()

    btc_offers = [row for row in loan_offers.recent(20) if row["currency"] == "BTC"]
    assert sum(float(row["amount"]) for row in btc_offers) == pytest.approx(0.01)


def test_runner_notifies_new_active_loans_after_initial_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    active_loans = ActiveLoanRepository(database_url)
    active_loans.replace_all(
        [
            ActiveLoan(
                currency="BTC",
                amount=0.01,
                daily_rate=0.00007,
                duration_days=2,
                external_loan_id="loan-old",
            )
        ]
    )
    notifier = SpyNotifier()

    runner = BotRunner(
        settings=_settings(database_url),
        exchange=NewActiveLoanExchange(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=active_loans,
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=notifier,
    )

    runner.run_once()

    assert notifier.filled_loan_ids == ["loan-new"]
    assert notifier.summaries == [(0, 2, True)]


def test_runner_sends_periodic_summary_when_interval_is_due(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    notification_state = NotificationStateRepository(database_url)
    lending_history = LendingHistoryRepository(database_url)
    lending_history.upsert_many(
        [
            LendingHistoryEntry(
                currency="BTC",
                amount=0.05,
                daily_rate=0.00008,
                duration_days=2,
                interest=0.00001,
                fee=-0.0000015,
                earned=0.0000085,
                opened_at="2026-05-11 00:00:00",
                closed_at="2026-05-12 00:00:00",
                external_entry_id="history-1",
            )
        ]
    )
    notifier = SpyNotifier()

    runner = BotRunner(
        settings=_settings(database_url, notify_summary_minutes=60),
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=lending_history,
        notification_state=notification_state,
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=notifier,
    )

    runner.run_once()
    runner.run_once()

    assert len(notifier.periodic_summaries) == 1
    assert "active_loans=1" in notifier.periodic_summaries[0]
    assert "Earnings by currency:" in notifier.periodic_summaries[0]
    assert "BTC: today=" in notifier.periodic_summaries[0]
    assert "total=0.00000850" in notifier.periodic_summaries[0]


def test_runner_skips_exception_notification_by_default(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    notifier = SpyNotifier()

    runner = BotRunner(
        settings=_settings(database_url),
        exchange=AuthFailingExchange(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=notifier,
    )

    with pytest.raises(ExchangeAuthenticationError):
        runner.run_once()

    assert notifier.errors == []


def test_runner_sends_exception_notification_when_enabled(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    notifier = SpyNotifier()

    runner = BotRunner(
        settings=_settings(database_url, notify_caught_exception=True),
        exchange=AuthFailingExchange(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=notifier,
    )

    with pytest.raises(ExchangeAuthenticationError):
        runner.run_once()

    assert notifier.errors == ["invalid key"]


def test_runner_notifies_xday_offers_when_enabled(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    notifier = SpyNotifier()

    runner = BotRunner(
        settings=_settings(
            database_url,
            notify_xday_threshold=True,
            xday_threshold=0.00007,
            xdays=30,
        ),
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=notifier,
    )

    runner.run_once()

    assert notifier.xday_offers == [("BTC", 30), ("BTC", 30), ("BTC", 30)]


def test_runner_enforces_live_run_total_limit(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)

    runner = BotRunner(
        settings=_settings(database_url, dry_run=False, max_total_lend_amount=0.02),
        exchange=MockExchangeClient(),
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_recorder=MarketRecorder(MarketRateRepository(database_url)),
        notifier=SpyNotifier(),
    )

    with pytest.raises(ValueError, match="MAX_TOTAL_LEND_AMOUNT"):
        runner.run_once()


def _settings(
    database_url: str,
    strategy_debug: bool = False,
    auto_rebalance_open_offers: bool = False,
    auto_cancel_open_offers: bool = False,
    keep_stuck_orders: bool = True,
    market_analysis_method: str = "off",
    hide_coins: bool = True,
    market_analysis_macd_short_samples: int = 3,
    market_analysis_macd_long_samples: int = 10,
    market_analysis_macd_short_seconds: int = 0,
    market_analysis_macd_long_seconds: int = 0,
    market_analysis_multiplier: float = 1.0,
    dry_run: bool = True,
    max_total_lend_amount: float | None = None,
    max_active_amount: float | None = None,
    notify_summary_minutes: int = 0,
    notify_xday_threshold: bool = False,
    notify_caught_exception: bool = False,
    xday_threshold: float = 0,
    xdays: int = 2,
    max_loops: int = 1,
    bot_sleep_seconds: int = 60,
    bot_inactive_sleep_seconds: int = 300,
) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="",
        api_secret="",
        bitfinex_enable_live_offers=False,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=bot_sleep_seconds,
        bot_inactive_sleep_seconds=bot_inactive_sleep_seconds,
        auto_rebalance_open_offers=auto_rebalance_open_offers,
        auto_cancel_open_offers=auto_cancel_open_offers,
        keep_stuck_orders=keep_stuck_orders,
        dry_run=dry_run,
        exchange="mock",
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        market_analysis_levels=10,
        market_analysis_method=market_analysis_method,
        market_analysis_percentile=75,
        market_analysis_macd_short_samples=market_analysis_macd_short_samples,
        market_analysis_macd_long_samples=market_analysis_macd_long_samples,
        market_analysis_macd_short_seconds=market_analysis_macd_short_seconds,
        market_analysis_macd_long_seconds=market_analysis_macd_long_seconds,
        market_analysis_multiplier=market_analysis_multiplier,
        max_loops=max_loops,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
        smoke_test_currency="BTC",
        strategy_debug=strategy_debug,
        telegram_bot_token="",
        telegram_chat_id="",
        notify_prefix="",
        notify_caught_exception=notify_caught_exception,
        notify_summary_minutes=notify_summary_minutes,
        notify_xday_threshold=notify_xday_threshold,
        hide_coins=hide_coins,
        gap_mode="off",
        gap_bottom=0,
        gap_top=0,
        xday_threshold=xday_threshold,
        xdays=xdays,
        xday_spread=0,
        frr_as_min=False,
        frr_delta=0,
        max_amount_to_lend=None,
        max_active_amount=max_active_amount,
        max_single_offer_amount=None,
        max_total_lend_amount=max_total_lend_amount,
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


class SpyNotifier:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.filled_loan_ids: list[str] = []
        self.infos: list[str] = []
        self.periodic_summaries: list[str] = []
        self.summaries: list[tuple[int, int, bool]] = []
        self.xday_offers: list[tuple[str, int]] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def run_summary(self, created_offers: int, active_loans: int, dry_run: bool) -> None:
        self.summaries.append((created_offers, active_loans, dry_run))

    def loan_filled(self, active_loan: ActiveLoan) -> None:
        self.filled_loan_ids.append(active_loan.external_loan_id)

    def periodic_summary(self, message: str) -> None:
        self.periodic_summaries.append(message)

    def xday_offer(self, offer: LoanOffer, dry_run: bool) -> None:
        self.xday_offers.append((offer.currency, offer.duration_days))


class NewActiveLoanExchange:
    def get_active_loans(self):
        return [
            ActiveLoan(
                currency="BTC",
                amount=0.01,
                daily_rate=0.00007,
                duration_days=2,
                external_loan_id="loan-old",
            ),
            ActiveLoan(
                currency="BTC",
                amount=0.02,
                daily_rate=0.00008,
                duration_days=2,
                external_loan_id="loan-new",
            ),
        ]

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


class NoOfferExchange:
    def get_active_loans(self):
        return []

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


class StuckOfferExchange:
    def __init__(self) -> None:
        self.canceled_offer_ids: list[str] = []

    def get_active_loans(self):
        return []

    def get_lending_balances(self):
        return []

    def get_loan_orders(self, currency: str):
        return []

    def get_open_loan_offers(self):
        return [
            LoanOffer(
                currency="BTC",
                amount=0.005,
                daily_rate=0.00008,
                duration_days=2,
                external_offer_id="offer-stuck",
            )
        ]

    def create_loan_offer(self, offer):
        return ""

    def cancel_loan_offer(self, offer_id: str):
        self.canceled_offer_ids.append(offer_id)
