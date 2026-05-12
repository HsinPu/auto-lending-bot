from fastapi.testclient import TestClient

from auto_lending_bot.api.app import create_app
from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import ActiveLoan, LendingHistoryEntry, LoanOffer, LoanOrder
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
)


def test_api_status_returns_counts_and_latest_run(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    _seed_database(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "Auto Lending Bot"
    assert body["exchange"] == "mock"
    assert body["dry_run"] is True
    assert body["counts"] == {
        "bot_runs": 1,
        "loan_offers": 1,
        "open_loan_offers": 1,
        "active_loans": 1,
        "lending_history": 1,
        "market_rates": 1,
        "market_analysis_rates": 0,
    }
    assert body["latest_run"]["status"] == "completed"


def test_api_read_only_resource_endpoints(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    _seed_database(database_url)

    client = TestClient(create_app(settings))

    endpoints = [
        "/api/runs",
        "/api/offers",
        "/api/open-offers",
        "/api/active-loans",
        "/api/lending-history",
        "/api/earnings",
        "/api/converted-earnings",
        "/api/market-rates",
        "/api/market-analysis-rates",
        "/api/currency-details",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_api_currency_details_returns_aggregated_currency_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    _seed_database(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/currency-details")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "currency": "BTC",
            "active_amount": 0.1,
            "open_offer_amount": 0.1,
            "average_daily_rate": 0.00008,
            "latest_market_rate": 0.00008,
            "total_earned": 0.0000085,
            "active_loan_count": 1,
            "open_offer_count": 1,
        }
    ]


def test_api_settings_returns_strategy_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["output_currency"] == "BTC"
    assert body["smoke_test_currency"] == "BTC"
    assert body["strategy"]["min_daily_rate"] == 0.00005
    assert body["strategy"]["spread_lend"] == 3


def test_api_safe_actions_update_local_state(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    smoke_response = client.post("/api/actions/smoke-exchange")
    assert smoke_response.status_code == 200
    assert smoke_response.json()["action"] == "smoke-exchange"
    assert smoke_response.json()["loan_orders"] == 1

    history_response = client.post("/api/actions/sync-history")
    assert history_response.status_code == 200
    assert history_response.json()["changed_count"] == 1

    open_offers_response = client.post("/api/actions/sync-open-offers")
    assert open_offers_response.status_code == 200
    assert open_offers_response.json()["changed_count"] == 0

    market_analysis_response = client.post("/api/actions/record-market-analysis")
    assert market_analysis_response.status_code == 200
    assert market_analysis_response.json()["changed_count"] == 1

    cancel_response = client.post("/api/actions/cancel-open-offers")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["would_cancel_count"] == 0
    assert cancel_response.json()["canceled_count"] == 0

    cleanup_response = client.post("/api/actions/cleanup")
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["deleted_count"] == 0


def test_api_safe_action_returns_safety_error(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, dry_run=False, allow_live_trading=False)

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/smoke-exchange")

    assert response.status_code == 400
    assert "BOT_DRY_RUN=false requires ALLOW_LIVE_TRADING=true" in response.json()["detail"]


def test_api_run_once_creates_dry_run_offers(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/run-once")

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "run-once"
    assert body["dry_run"] is True
    assert body["created_count"] == 6
    assert body["latest_run"]["status"] == "completed"


def test_api_run_once_requires_live_confirmation(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(
        database_url,
        exchange="bitfinex",
        api_key="key",
        api_secret="secret",
        dry_run=False,
        allow_live_trading=True,
        bitfinex_enable_live_offers=True,
        max_total_lend_amount=1,
        max_single_offer_amount=1,
    )

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/run-once")

    assert response.status_code == 400
    assert response.json()["detail"] == "Live run requires confirm_live=true."


def test_api_cancel_open_offers_requires_live_confirmation(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(
        database_url,
        exchange="bitfinex",
        api_key="key",
        api_secret="secret",
        dry_run=False,
        allow_live_trading=True,
        bitfinex_enable_live_offers=True,
        max_total_lend_amount=1,
        max_single_offer_amount=1,
    )

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/cancel-open-offers")

    assert response.status_code == 400
    assert response.json()["detail"] == "Live cancel requires confirm_live=true."


def _seed_database(database_url: str) -> None:
    bot_runs = BotRunRepository(database_url)
    bot_run_id = bot_runs.start(dry_run=True)
    bot_runs.finish(bot_run_id, status="completed", message="ok")

    LoanOfferRepository(database_url).add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2),
        status="dry_run",
        dry_run=True,
    )
    MarketRateRepository(database_url).add(
        LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008)
    )
    ActiveLoanRepository(database_url).replace_all(
        [
            ActiveLoan(
                currency="BTC",
                amount=0.1,
                daily_rate=0.00008,
                duration_days=2,
                external_loan_id="loan-1",
            )
        ]
    )
    LendingHistoryRepository(database_url).upsert_many(
        [
            LendingHistoryEntry(
                currency="BTC",
                amount=0.1,
                daily_rate=0.00008,
                duration_days=2,
                interest=0.00001,
                fee=-0.0000015,
                earned=0.0000085,
                opened_at="2026-01-01 00:00:00",
                closed_at="2026-01-02 00:00:00",
                external_entry_id="history-1",
            )
        ]
    )
    OpenLoanOfferRepository(database_url).replace_all(
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


def _settings(
    database_url: str,
    dry_run: bool = True,
    allow_live_trading: bool = False,
    exchange: str = "mock",
    api_key: str = "",
    api_secret: str = "",
    bitfinex_enable_live_offers: bool = False,
    max_total_lend_amount: float | None = None,
    max_single_offer_amount: float | None = None,
) -> Settings:
    return Settings(
        allow_live_trading=allow_live_trading,
        api_key=api_key,
        api_secret=api_secret,
        bitfinex_enable_live_offers=bitfinex_enable_live_offers,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        auto_rebalance_open_offers=False,
        auto_cancel_open_offers=False,
        dry_run=dry_run,
        exchange=exchange,
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        market_analysis_levels=10,
        market_analysis_method="off",
        market_analysis_percentile=75,
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
        max_single_offer_amount=max_single_offer_amount,
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
