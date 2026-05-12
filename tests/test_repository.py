from auto_lending_bot.domain.models import ActiveLoan, LoanOffer, LoanOrder
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
)


def test_repositories_write_bot_run_offer_and_market_rate(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)

    bot_runs = BotRunRepository(database_url)
    loan_offers = LoanOfferRepository(database_url)
    market_rates = MarketRateRepository(database_url)
    active_loans = ActiveLoanRepository(database_url)

    bot_run_id = bot_runs.start(dry_run=True)
    loan_offers.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2),
        status="dry_run",
        dry_run=True,
    )
    market_rates.add(LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008))
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
    bot_runs.finish(bot_run_id, status="completed", message="ok")

    assert bot_runs.count() == 1
    assert loan_offers.count() == 1
    assert market_rates.count() == 1
    assert active_loans.count() == 1


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


def test_bot_run_repository_recovers_running_runs(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_runs = BotRunRepository(database_url)

    bot_runs.start(dry_run=True)

    assert bot_runs.fail_running("recovered") == 1
    assert bot_runs.latest()["status"] == "failed"
