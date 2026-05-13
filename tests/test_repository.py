import pytest

from auto_lending_bot.domain.models import ActiveLoan, LendingHistoryEntry, LoanOffer, LoanOrder
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


def test_repositories_write_bot_run_offer_and_market_rate(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)

    bot_runs = BotRunRepository(database_url)
    loan_offers = LoanOfferRepository(database_url)
    market_rates = MarketRateRepository(database_url)
    active_loans = ActiveLoanRepository(database_url)
    lending_history = LendingHistoryRepository(database_url)
    open_offers = OpenLoanOfferRepository(database_url)
    market_analysis_rates = MarketAnalysisRateRepository(database_url)

    bot_run_id = bot_runs.start(dry_run=True)
    loan_offers.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2),
        status="dry_run",
        dry_run=True,
    )
    market_rates.add(LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008))
    market_analysis_rates.add_many(
        [
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008),
            LoanOrder(currency="BTC", amount=2.0, daily_rate=0.00009),
        ]
    )
    active_loans.replace_all(
        [
            ActiveLoan(
                currency="BTC",
                amount=0.05,
                daily_rate=0.00008,
                duration_days=2,
                external_loan_id="loan-1",
            )
        ]
    )
    lending_history.upsert_many([_history_entry("history-1")])
    open_offers.replace_all(
        [
            LoanOffer(
                currency="BTC",
                amount=0.1,
                daily_rate=0.00008,
                duration_days=2,
                external_offer_id="offer-1",
            )
        ]
    )
    bot_runs.finish(bot_run_id, status="completed", message="ok")

    assert bot_runs.count() == 1
    assert loan_offers.count() == 1
    assert market_rates.count() == 1
    assert market_analysis_rates.count() == 2
    assert active_loans.count() == 1
    assert lending_history.count() == 1
    assert open_offers.count() == 1


def test_active_loan_repository_replaces_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    active_loans = ActiveLoanRepository(database_url)

    active_loans.replace_all(
        [
            ActiveLoan(
                currency="BTC",
                amount=0.05,
                daily_rate=0.00008,
                duration_days=2,
                external_loan_id="loan-1",
            )
        ]
    )
    active_loans.replace_all([])

    assert active_loans.count() == 0


def test_lending_history_repository_upserts_entries(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    lending_history = LendingHistoryRepository(database_url)

    assert lending_history.upsert_many([_history_entry("history-1")]) == 1
    assert lending_history.upsert_many([_history_entry("history-1")]) == 1

    assert lending_history.count() == 1
    assert lending_history.recent()[0]["external_entry_id"] == "history-1"
    assert lending_history.earnings_summary_by_currency()[0]["total_earned"] == 0.0000085


def test_open_loan_offer_repository_replaces_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    open_offers = OpenLoanOfferRepository(database_url)

    open_offers.replace_all(
        [
            LoanOffer(
                currency="BTC",
                amount=0.1,
                daily_rate=0.00008,
                duration_days=2,
                external_offer_id="offer-1",
            )
        ]
    )
    open_offers.replace_all([])

    assert open_offers.count() == 0


def test_market_analysis_rate_repository_records_levels(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)

    changed_count = repository.add_many(
        [
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008),
            LoanOrder(currency="BTC", amount=2.0, daily_rate=0.00009),
        ]
    )

    assert changed_count == 2
    assert repository.recent(1)[0]["level"] == 1
    assert repository.percentile_rate("BTC", 75) == 0.00009


def test_market_analysis_rate_repository_calculates_macd_rate(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)

    for daily_rate in [0.00005, 0.00007, 0.00009, 0.00011, 0.00013]:
        repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=daily_rate)])

    assert repository.macd_rate("BTC", short_samples=2, long_samples=5) == pytest.approx(0.00012)


def test_market_analysis_rate_repository_calculates_macd_rate_by_seconds(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)

    for daily_rate in [0.00008, 0.0001]:
        repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=daily_rate)])

    assert repository.macd_rate_by_seconds(
        "BTC",
        short_seconds=60,
        long_seconds=3600,
        multiplier=1.05,
    ) == pytest.approx(0.0000945)


def test_notification_state_repository_stores_float_values(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = NotificationStateRepository(database_url)

    assert repository.get_float("summary") is None

    repository.set_float("summary", 123.5)

    assert repository.get_float("summary") == 123.5


def test_bot_run_repository_recovers_running_runs(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_runs = BotRunRepository(database_url)

    bot_runs.start(dry_run=True)

    assert bot_runs.fail_running("recovered") == 1
    assert bot_runs.latest()["status"] == "failed"


def _history_entry(external_entry_id: str) -> LendingHistoryEntry:
    return LendingHistoryEntry(
        currency="BTC",
        amount=0.05,
        daily_rate=0.00008,
        duration_days=2,
        interest=0.00001,
        fee=-0.0000015,
        earned=0.0000085,
        opened_at="2026-01-01 00:00:00",
        closed_at="2026-01-02 00:00:00",
        external_entry_id=external_entry_id,
    )
