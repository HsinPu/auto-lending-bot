import pytest

from auto_lending_bot.domain.models import (
    ActiveLoan,
    FillOutcome,
    LendingHistoryEntry,
    LoanOffer,
    LoanOrder,
)
from auto_lending_bot.persistence.database import connect, initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    AppSettingRepository,
    BotJobRepository,
    BotRunDecisionRepository,
    BotRunRepository,
    BotRunStepRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    MarketRateRepository,
    NotificationStateRepository,
    OpenLoanOfferRepository,
    ProfileAppSettingRepository,
)
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT
from auto_lending_bot.settings_registry import SETTING_DEFINITIONS_BY_KEY, setting_schema


def test_initialize_database_seeds_default_profile_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    initialize_database(database_url)

    with connect(database_url) as connection:
        profile = connection.execute(
            "SELECT id, name FROM bot_profiles WHERE id = 'default'"
        ).fetchone()
        setting_columns = connection.execute(
            "PRAGMA table_info(profile_app_settings)"
        ).fetchall()

    assert dict(profile) == {"id": "default", "name": "Default"}
    assert {column[1] for column in setting_columns} >= {"profile_id", "key", "value"}


def test_initialize_database_adds_profile_scope_to_runtime_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    initialize_database(database_url)

    runtime_tables = [
        "bot_runs",
        "loan_offers",
        "bot_run_decisions",
        "bot_run_steps",
        "active_loans",
        "open_loan_offers",
        "lending_history",
        "market_rates",
        "market_analysis_rates",
        "notification_state",
    ]
    with connect(database_url) as connection:
        table_columns = {
            table: {column[1] for column in connection.execute(f"PRAGMA table_info({table})")}
            for table in runtime_tables
        }

    assert all("profile_id" in columns for columns in table_columns.values())


def test_initialize_database_uses_profile_scoped_runtime_constraints(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    initialize_database(database_url)

    with connect(database_url) as connection:
        history_unique_indexes = [
            tuple(
                row[2]
                for row in connection.execute(f"PRAGMA index_info({index[1]})").fetchall()
            )
            for index in connection.execute("PRAGMA index_list(lending_history)").fetchall()
            if int(index[2])
        ]
        notification_pk = tuple(
            row[1]
            for row in sorted(
                connection.execute("PRAGMA table_info(notification_state)").fetchall(),
                key=lambda row: row[5],
            )
            if int(row[5])
        )

    assert ("profile_id", "external_entry_id", "currency") in history_unique_indexes
    assert notification_pk == ("profile_id", "key")


def test_profile_app_setting_repository_manages_default_profile_settings(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = ProfileAppSettingRepository(database_url, encryption_key="test-key")

    repository.set_many(
        DEFAULT_PROFILE_CONTEXT,
        {"BOT_LABEL": "Profile Bot", "EXCHANGE_API_SECRET": "secret"},
        source="test",
    )

    values = repository.get_many(DEFAULT_PROFILE_CONTEXT)
    plain_values = repository.plain_values(DEFAULT_PROFILE_CONTEXT)
    audit_log = repository.audit_log(DEFAULT_PROFILE_CONTEXT)

    assert values["BOT_LABEL"]["value"] == "Profile Bot"
    assert values["EXCHANGE_API_SECRET"]["value"] == "********cret"
    assert plain_values["EXCHANGE_API_SECRET"] == "secret"
    assert audit_log[0]["profile_id"] == "default"

    repository.reset(DEFAULT_PROFILE_CONTEXT, "BOT_LABEL", source="test")

    assert "BOT_LABEL" not in repository.get_many(DEFAULT_PROFILE_CONTEXT)


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

    with connect(database_url) as connection:
        profile_ids = {
            table: connection.execute(f"SELECT DISTINCT profile_id FROM {table}").fetchall()
            for table in [
                "bot_runs",
                "loan_offers",
                "market_rates",
                "market_analysis_rates",
                "active_loans",
                "lending_history",
                "open_loan_offers",
            ]
        }
    assert all([row["profile_id"] for row in rows] == ["default"] for rows in profile_ids.values())


def test_bot_run_repository_links_runs_to_jobs(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_runs = BotRunRepository(database_url)
    bot_job_id = BotJobRepository(database_url).create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json='{"dry_run": true}',
    )

    bot_run_id = bot_runs.start(dry_run=True, job_id=bot_job_id)

    assert bot_runs.latest()["id"] == bot_run_id
    assert bot_runs.latest()["job_id"] == bot_job_id


def test_loan_offer_repository_tracks_live_offer_lifecycle(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    repository = LoanOfferRepository(database_url)
    offer = LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2)

    offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=offer,
        status="intent",
        dry_run=False,
        strategy_snapshot={"lending_risk_level": "balanced"},
        rate_candidate_snapshot=[{"daily_rate": 0.00008, "selected": True}],
    )
    repository.update_status(offer_id, status="created", external_offer_id="offer-1")
    marked = repository.mark_filled_by_active_loan(
        ActiveLoan(
            currency="BTC",
            amount=0.1,
            daily_rate=0.00008,
            duration_days=2,
            external_loan_id="credit-1",
        )
    )
    rows = repository.recent()

    assert marked is True
    assert rows[0]["status"] == "filled"
    assert rows[0]["final_status"] == "filled"
    assert rows[0]["submitted_at"] is not None
    assert rows[0]["filled_at"] is not None
    assert rows[0]["time_to_fill_seconds"] is not None
    assert rows[0]["initial_daily_rate"] == 0.00008
    assert rows[0]["strategy_snapshot_json"] == '{"lending_risk_level":"balanced"}'
    assert rows[0]["rate_candidate_snapshot_json"] == '[{"daily_rate":8e-05,"selected":true}]'


def test_loan_offer_repository_marks_canceled_offer(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    repository = LoanOfferRepository(database_url)
    offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2),
        status="intent",
        dry_run=False,
    )
    repository.update_status(offer_id, status="created", external_offer_id="offer-1")

    changed_count = repository.mark_canceled_by_external_offer_id("offer-1")
    rows = repository.recent()

    assert changed_count == 1
    assert rows[0]["status"] == "canceled"
    assert rows[0]["final_status"] == "canceled"
    assert rows[0]["canceled_at"] is not None
    assert rows[0]["reprice_count"] == 1


def test_loan_offer_repository_returns_recent_fill_outcomes(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    repository = LoanOfferRepository(database_url)

    filled_offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.0002, duration_days=2),
        status="intent",
        dry_run=False,
    )
    repository.update_status(
        filled_offer_id,
        status="created",
        external_offer_id="filled-1",
    )
    repository.mark_filled_by_active_loan(
        ActiveLoan(
            currency="BTC",
            amount=0.1,
            daily_rate=0.0002,
            duration_days=2,
            external_loan_id="loan-1",
        )
    )
    canceled_offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.0003, duration_days=2),
        status="intent",
        dry_run=False,
    )
    repository.update_status(
        canceled_offer_id,
        status="created",
        external_offer_id="canceled-1",
    )
    repository.mark_canceled_by_external_offer_id("canceled-1")
    repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.0004, duration_days=2),
        status="dry_run",
        dry_run=True,
    )
    repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="ETH", amount=0.1, daily_rate=0.0005, duration_days=2),
        status="created",
        dry_run=False,
    )

    assert repository.recent_fill_outcomes("BTC") == [
        FillOutcome(daily_rate=0.0003, filled=False),
        FillOutcome(daily_rate=0.0002, filled=True),
    ]


def test_loan_offer_repository_summarizes_live_offer_performance(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    repository = LoanOfferRepository(database_url)

    filled_offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=100, daily_rate=0.0002, duration_days=2),
        status="intent",
        dry_run=False,
        strategy_snapshot={"lending_risk_level": "balanced"},
        rate_candidate_snapshot=[
            {
                "daily_rate": 0.0002,
                "fill_probability": 0.6,
                "expected_score": 0.00012,
                "selected": True,
            }
        ],
    )
    repository.update_status(filled_offer_id, status="created", external_offer_id="filled-1")
    repository.mark_filled_by_active_loan(
        ActiveLoan(
            currency="BTC",
            amount=100,
            daily_rate=0.0002,
            duration_days=2,
            external_loan_id="loan-1",
        )
    )
    canceled_offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=50, daily_rate=0.0003, duration_days=7),
        status="intent",
        dry_run=False,
        strategy_snapshot={"lending_risk_level": "balanced"},
        rate_candidate_snapshot=[
            {
                "daily_rate": 0.0003,
                "fill_probability": 0.2,
                "expected_score": 0.00006,
                "selected": True,
            }
        ],
    )
    repository.update_status(canceled_offer_id, status="created", external_offer_id="canceled-1")
    repository.mark_canceled_by_external_offer_id("canceled-1")
    open_offer_id = repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="ETH", amount=25, daily_rate=0.0001, duration_days=2),
        status="intent",
        dry_run=False,
        strategy_snapshot={"lending_risk_level": "yield"},
        rate_candidate_snapshot=[
            {
                "daily_rate": 0.0001,
                "fill_probability": 0.1,
                "expected_score": 0.00001,
                "selected": True,
            }
        ],
    )
    repository.update_status(open_offer_id, status="created", external_offer_id="open-1")
    repository.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=999, daily_rate=0.001, duration_days=2),
        status="dry_run",
        dry_run=True,
    )
    with connect(database_url) as connection:
        connection.execute(
            "UPDATE loan_offers SET time_to_fill_seconds = 120 WHERE id = ?",
            (filled_offer_id,),
        )

    summary = repository.performance_summary()
    overall = summary["overall"]
    by_currency = {row["label"]: row for row in summary["by_currency"]}
    by_risk_level = {row["label"]: row for row in summary["by_risk_level"]}

    assert overall["total_offers"] == 3
    assert overall["filled_offers"] == 1
    assert overall["canceled_offers"] == 1
    assert overall["open_offers"] == 1
    assert overall["total_amount"] == 175
    assert overall["amount_fill_rate"] == pytest.approx(100 / 175)
    assert overall["average_daily_rate"] == pytest.approx(0.00021428571428571427)
    assert overall["average_expected_fill_probability"] == pytest.approx(72.5 / 175)
    assert overall["actual_vs_expected_fill_delta"] == pytest.approx(
        (100 / 175) - (72.5 / 175)
    )
    assert overall["average_time_to_fill_seconds"] == 120
    assert by_currency["BTC"]["total_offers"] == 2
    assert by_risk_level["balanced"]["total_offers"] == 2
    assert by_risk_level["yield"]["open_offers"] == 1


def test_bot_job_repository_stores_settings_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = BotJobRepository(database_url)

    bot_job_id = repository.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json='{"dry_run": true}',
    )

    job = repository.get(bot_job_id)
    latest_running = repository.latest_running(DEFAULT_PROFILE_CONTEXT)
    recent = repository.recent(DEFAULT_PROFILE_CONTEXT)

    assert job is not None
    assert job["profile_id"] == "default"
    assert job["status"] == "running"
    assert job["mode"] == "loop"
    assert job["settings_snapshot_json"] == '{"dry_run": true}'
    assert latest_running is not None
    assert latest_running["id"] == bot_job_id
    assert recent[0]["id"] == bot_job_id


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


def test_bot_run_decision_repository_stores_run_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=True)
    decisions = BotRunDecisionRepository(database_url)

    decisions.add(
        {
            "bot_run_id": bot_run_id,
            "currency": "BTC",
            "balance": 0.1,
            "active_amount": 0.0,
            "open_offer_amount": 0.0,
            "best_market_rate": 0.00008,
            "configured_min_daily_rate": 0.00005,
            "suggested_min_daily_rate": None,
            "effective_min_daily_rate": 0.00005,
            "max_daily_rate": 0.05,
            "max_to_lend": None,
            "max_percent_to_lend": 100.0,
            "max_active_amount": None,
            "offer_count": 1,
            "offers": [{"currency": "BTC", "amount": 0.1}],
            "rate_candidates": [
                {
                    "daily_rate": 0.00008,
                    "fill_probability": 0.8,
                    "expected_score": 0.000064,
                    "selected": True,
                }
            ],
            "reason": "Created lending offers from available balance.",
        }
    )

    rows = decisions.for_run(bot_run_id)

    assert rows[0]["currency"] == "BTC"
    assert rows[0]["profile_id"] == "default"
    assert rows[0]["offer_count"] == 1
    assert rows[0]["offers"] == [{"currency": "BTC", "amount": 0.1}]
    assert rows[0]["rate_candidates"] == [
        {
            "daily_rate": 0.00008,
            "fill_probability": 0.8,
            "expected_score": 0.000064,
            "selected": True,
        }
    ]


def test_bot_run_step_repository_stores_progress_steps(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=True)
    steps = BotRunStepRepository(database_url)

    running_step_id = steps.start(bot_run_id, "sync-balances", "讀取可用 Lending 餘額")
    steps.finish(running_step_id, message="Loaded 3 lending balance(s).")
    steps.record_completed(bot_run_id, "finish-run", "完成本次執行", "Completed with 6 offer(s).")

    rows = steps.for_run(bot_run_id)

    assert [row["step_key"] for row in rows] == ["sync-balances", "finish-run"]
    assert {row["profile_id"] for row in rows} == {"default"}
    assert rows[0]["status"] == "completed"
    assert rows[0]["message"] == "Loaded 3 lending balance(s)."
    assert rows[0]["finished_at"] is not None


def test_lending_history_repository_upserts_entries(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    lending_history = LendingHistoryRepository(database_url)

    assert lending_history.upsert_many([_history_entry("history-1")], dry_run=True, source="mock") == 1
    assert lending_history.upsert_many([_history_entry("history-1")], dry_run=True, source="mock") == 1

    assert lending_history.count() == 1
    recent = lending_history.recent()[0]
    assert recent["external_entry_id"] == "history-1"
    assert recent["dry_run"] == 1
    assert recent["source"] == "mock"
    earnings = lending_history.earnings_summary_by_currency()[0]
    assert earnings["total_earned"] == 0.0000085
    assert earnings["dry_run"] == 1
    assert earnings["source"] == "mock"


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
    assert repository.percentile_rate("BTC", 75, min_samples=3) is None


def test_market_analysis_rate_repository_calculates_macd_rate(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)

    for daily_rate in [0.00005, 0.00007, 0.00009, 0.00011, 0.00013]:
        repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=daily_rate)])

    assert repository.macd_rate("BTC", short_samples=2, long_samples=5) == pytest.approx(0.00012)
    assert repository.macd_rate("BTC", short_samples=2, long_samples=5, min_samples=6) is None


def test_market_analysis_rate_repository_returns_recent_top_level_rates(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)

    repository.add_many(
        [
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00009),
        ]
    )
    repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)])

    assert repository.recent_top_level_rates("BTC", 2) == [0.0001, 0.00008]


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
    assert (
        repository.macd_rate_by_seconds(
            "BTC",
            short_seconds=60,
            long_seconds=3600,
            min_samples=3,
        )
        is None
    )


def test_market_analysis_rate_repository_ignores_stale_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)
    repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008)])
    with connect(database_url) as connection:
        connection.execute(
            """
            UPDATE market_analysis_rates
            SET captured_at = datetime('now', '-2 hours')
            """
        )

    assert repository.percentile_rate("BTC", 75, max_age_seconds=60) is None
    assert repository.macd_rate("BTC", 1, 1, max_age_seconds=60) is None


def test_market_analysis_rate_repository_deletes_old_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = MarketAnalysisRateRepository(database_url)
    repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008)])
    repository.add_many([LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00009)])
    with connect(database_url) as connection:
        connection.execute(
            """
            UPDATE market_analysis_rates
            SET captured_at = datetime('now', '-31 days')
            WHERE id = 1
            """
        )

    assert repository.delete_older_than_days(30) == 1

    rows = repository.recent()
    assert len(rows) == 1
    assert rows[0]["daily_rate"] == 0.00009


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


def test_app_setting_repository_stores_values_and_audit_log(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = AppSettingRepository(database_url)

    repository.set_many({"BOT_LABEL": "Desk Bot", "BOT_DRY_RUN": "true"}, source="test")

    settings = repository.get_many()
    assert settings["BOT_LABEL"]["value"] == "Desk Bot"
    assert settings["BOT_LABEL"]["value_type"] == "string"
    assert settings["BOT_DRY_RUN"]["value_type"] == "bool"
    assert repository.audit_log()[0]["source"] == "test"


def test_app_setting_repository_rejects_unknown_setting(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = AppSettingRepository(database_url)

    with pytest.raises(ValueError, match="Unknown setting"):
        repository.set_many({"UNKNOWN": "value"})


def test_app_setting_repository_rejects_invalid_setting_values(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = AppSettingRepository(database_url)

    with pytest.raises(ValueError, match="BOT_DRY_RUN must be a boolean"):
        repository.set_many({"BOT_DRY_RUN": "maybe"})
    with pytest.raises(ValueError, match="BOT_SLEEP_SECONDS must be an integer"):
        repository.set_many({"BOT_SLEEP_SECONDS": "1.5"})
    with pytest.raises(ValueError, match="MIN_DAILY_RATE must be a number"):
        repository.set_many({"MIN_DAILY_RATE": "fast"})
    with pytest.raises(ValueError, match="EXCHANGE must be one of"):
        repository.set_many({"EXCHANGE": "kraken"})
    with pytest.raises(ValueError, match="DISPLAY_TIMEZONE must be a valid IANA timezone"):
        repository.set_many({"DISPLAY_TIMEZONE": "Taipei"})


def test_app_setting_repository_resets_values(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = AppSettingRepository(database_url)
    repository.set_many({"BOT_LABEL": "Desk Bot"})

    repository.reset("BOT_LABEL")

    assert "BOT_LABEL" not in repository.get_many()
    assert repository.audit_log()[0]["new_value"] is None


def test_app_setting_repository_encrypts_secret_values(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    initialize_database(database_url)
    repository = AppSettingRepository(database_url, encryption_key="test-key")

    repository.set_many({"EXCHANGE_API_SECRET": "super-secret"}, source="test")

    public_settings = repository.get_many()
    assert public_settings["EXCHANGE_API_SECRET"]["value"] == "********cret"
    assert public_settings["EXCHANGE_API_SECRET"]["is_set"] is True
    assert repository.plain_values()["EXCHANGE_API_SECRET"] == "super-secret"
    audit_row = repository.audit_log()[0]
    assert audit_row["new_value"] == "<secret updated>"
    assert "super-secret" not in str(audit_row)


def test_setting_registry_contains_secret_metadata() -> None:
    assert SETTING_DEFINITIONS_BY_KEY["EXCHANGE_API_SECRET"].secret is True
    assert SETTING_DEFINITIONS_BY_KEY["BOT_DRY_RUN"].category == "Safety"
    assert any(row["key"] == "TELEGRAM_BOT_TOKEN" for row in setting_schema())


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
