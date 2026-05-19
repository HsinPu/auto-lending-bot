import pytest
from fastapi.testclient import TestClient

from auto_lending_bot.api.app import create_app
from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import ActiveLoan, LendingHistoryEntry, LoanOffer, LoanOrder
from auto_lending_bot.integrations.errors import ExchangePermissionError
from auto_lending_bot.persistence.database import connect, initialize_database
from auto_lending_bot.persistence.factory import create_repository_bundle
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    AppSettingRepository,
    BotRunRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
    ProfileAppSettingRepository,
)
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT
from auto_lending_bot.settings_snapshot import settings_snapshot_json


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
    assert body["profile"] == {"id": "default", "name": "Default"}
    assert body["exchange"] == "mock"
    assert body["dry_run"] is True
    assert body["settings_runtime"] == {
        "hot_reload": True,
        "managed_override_count": 0,
        "last_updated_at": None,
    }
    assert body["bot_loop"] == {
        "running": False,
        "bot_job_id": None,
        "bot_job": None,
        "started_at": None,
        "restored_at": None,
        "last_run_at": None,
        "loops_completed": 0,
        "last_error": None,
    }
    assert body["market_analysis_collection"] == {
        "running": False,
        "started_at": None,
        "last_run_at": None,
        "loops_completed": 0,
        "last_changed_count": 0,
        "last_error": None,
    }
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
        "/api/market-analysis-status",
        "/api/currency-details",
        "/api/strategy-decisions",
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


def test_api_strategy_decisions_returns_per_currency_preview(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    _seed_database(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/strategy-decisions")

    assert response.status_code == 200
    body = response.json()
    btc = next(row for row in body if row["currency"] == "BTC")
    assert btc["balance"] == 0.25
    assert btc["active_amount"] == 0.05
    assert btc["open_offer_amount"] == 0.1
    assert btc["best_market_rate"] == 0.00008
    assert btc["effective_min_daily_rate"] == 0.00005
    assert btc["offer_count"] == 3
    assert btc["offers"][0]["currency"] == "BTC"


def test_api_strategy_decisions_use_live_fill_feedback(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, rate_optimization_mode="fill_probability")
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    loan_offers = LoanOfferRepository(database_url)
    filled_offer_id = loan_offers.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00005, duration_days=2),
        status="intent",
        dry_run=False,
    )
    loan_offers.update_status(
        filled_offer_id,
        status="created",
        external_offer_id="filled-1",
    )
    loan_offers.mark_filled_by_active_loan(
        ActiveLoan(
            currency="BTC",
            amount=0.1,
            daily_rate=0.00005,
            duration_days=2,
            external_loan_id="loan-1",
        )
    )
    canceled_offer_id = loan_offers.add(
        bot_run_id=bot_run_id,
        offer=LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2),
        status="intent",
        dry_run=False,
    )
    loan_offers.update_status(
        canceled_offer_id,
        status="created",
        external_offer_id="canceled-1",
    )
    loan_offers.mark_canceled_by_external_offer_id("canceled-1")
    client = TestClient(create_app(settings))

    response = client.get("/api/strategy-decisions")

    assert response.status_code == 200
    btc = next(row for row in response.json() if row["currency"] == "BTC")
    assert btc["offers"][0]["daily_rate"] == 0.00005
    assert btc["rate_candidates"][0]["source"] == "fill_outcome"
    assert btc["rate_candidates"][0]["selected"] is True


def test_api_strategy_performance_returns_live_offer_summary(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    loan_offers = LoanOfferRepository(database_url)
    offer_id = loan_offers.add(
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
    loan_offers.update_status(offer_id, status="created", external_offer_id="offer-1")
    loan_offers.mark_filled_by_active_loan(
        ActiveLoan(
            currency="BTC",
            amount=100,
            daily_rate=0.0002,
            duration_days=2,
            external_loan_id="loan-1",
        )
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/strategy-performance")

    assert response.status_code == 200
    body = response.json()
    assert body["overall"]["total_offers"] == 1
    assert body["overall"]["filled_offers"] == 1
    assert body["by_currency"][0]["label"] == "BTC"
    assert body["by_risk_level"][0]["label"] == "balanced"


def test_api_run_preview_returns_decisions_without_creating_records(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    client = TestClient(create_app(settings))

    response = client.post("/api/actions/run-preview")

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "run-preview"
    assert body["ok"] is True
    assert body["summary"]["total_offer_count"] > 0
    assert "rate_candidates" in body["decisions"][0]
    assert BotRunRepository(database_url).count() == 0
    assert LoanOfferRepository(database_url).count() == 0


def test_api_run_preview_reports_live_safety_blockers(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, dry_run=False)
    initialize_database(database_url)
    client = TestClient(create_app(settings))

    response = client.post("/api/actions/run-preview")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["mode"] == "live"
    assert body["safety_error"] is not None
    assert body["live_readiness"]["ready"] is False


def test_api_settings_returns_strategy_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["output_currency"] == "BTC"
    assert body["display_timezone"] == "UTC"
    assert body["smoke_test_currency"] == "BTC"
    assert body["market_analysis_suggested_min_daily_rate"] is None
    assert body["effective_min_daily_rate"] == 0.00005
    assert body["strategy"]["min_daily_rate"] == 0.00005
    assert body["strategy"]["spread_lend"] == 3


def test_api_live_readiness_reports_missing_live_settings(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    response = client.get("/api/live-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["live_offers"]["ready"] is False
    assert "EXCHANGE=bitfinex" in body["live_offers"]["missing"]
    assert "BOT_DRY_RUN=false" in body["live_offers"]["missing"]
    assert body["live_transfers"]["ready"] is False
    assert body["note"] == "API keys should not include withdrawal permissions."


def test_api_manages_database_settings(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", "test-key")
    client = TestClient(create_app())

    schema_response = client.get("/api/settings/schema")
    assert schema_response.status_code == 200
    assert any(row["key"] == "BOT_LABEL" for row in schema_response.json())
    schema_by_key = {row["key"]: row for row in schema_response.json()}
    assert schema_by_key["DISPLAY_TIMEZONE"]["scope"] == "global"
    assert schema_by_key["EXCHANGE_API_SECRET"]["scope"] == "profile_secret"
    assert schema_by_key["BOT_DRY_RUN"]["scope"] == "profile_safety"

    update_response = client.put(
        "/api/settings/values",
        headers=_admin_headers(),
        json={
            "values": {
                "BOT_LABEL": "Managed Bot",
                "DISPLAY_TIMEZONE": "Asia/Taipei",
                "EXCHANGE_API_SECRET": "secret",
            }
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["changed_count"] == 3

    values_response = client.get("/api/settings/values")
    assert values_response.status_code == 200
    assert values_response.json()["BOT_LABEL"]["value"] == "Managed Bot"
    assert values_response.json()["EXCHANGE_API_SECRET"]["value"] == "********cret"
    assert values_response.json()["BOT_LABEL"]["scope"] == "profile"
    assert values_response.json()["DISPLAY_TIMEZONE"]["scope"] == "global"

    global_values = AppSettingRepository(database_url).get_many()
    profile_values = ProfileAppSettingRepository(database_url, "test-key").get_many(
        DEFAULT_PROFILE_CONTEXT
    )
    assert "DISPLAY_TIMEZONE" in global_values
    assert "BOT_LABEL" not in global_values
    assert "BOT_LABEL" in profile_values
    assert "EXCHANGE_API_SECRET" in profile_values

    effective_response = client.get("/api/settings/effective")
    assert effective_response.status_code == 200
    assert effective_response.json()["label"] == "Managed Bot"
    assert effective_response.json()["display_timezone"] == "Asia/Taipei"

    audit_response = client.get("/api/settings/audit-log")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) >= 2

    export_response = client.get("/api/settings/export")
    assert export_response.status_code == 200
    assert export_response.json()["includes_secrets"] is False
    assert export_response.json()["values"]["BOT_LABEL"] == "Managed Bot"
    assert "EXCHANGE_API_SECRET" not in export_response.json()["values"]
    assert export_response.json()["excluded_secret_keys"] == ["EXCHANGE_API_SECRET"]

    reset_response = client.post(
        "/api/settings/reset",
        headers=_admin_headers(),
        json={"key": "BOT_LABEL"},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["reset_count"] == 1


def test_api_settings_write_requires_admin_token(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app(), client=("203.0.113.10", 50000))

    missing_response = client.put("/api/settings/values", json={"BOT_LABEL": "Managed Bot"})
    wrong_response = client.post(
        "/api/settings/reset",
        headers={"Authorization": "Bearer wrong-token"},
        json={"key": "BOT_LABEL"},
    )

    assert missing_response.status_code == 401
    assert wrong_response.status_code == 401


def test_api_settings_write_allows_localhost_without_admin_token(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.delenv("ADMIN_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app(), client=("127.0.0.1", 50000))

    response = client.put("/api/settings/values", json={"BOT_LABEL": "Local Bot"})

    assert response.status_code == 200
    assert client.get("/api/settings/values").json()["BOT_LABEL"]["value"] == "Local Bot"


def test_api_settings_write_allows_docker_gateway_for_localhost(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.delenv("ADMIN_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(
        create_app(),
        base_url="http://127.0.0.1:8000",
        client=("172.20.0.1", 50000),
    )

    response = client.put("/api/settings/values", json={"BOT_LABEL": "Local Docker Bot"})

    assert response.status_code == 200


def test_api_settings_write_requires_configured_admin_token(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.delenv("ADMIN_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app(), client=("203.0.113.10", 50000))

    response = client.put(
        "/api/settings/values",
        headers={"Authorization": "Bearer admin-token"},
        json={"BOT_LABEL": "Managed Bot"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "ADMIN_AUTH_TOKEN is not configured."


def test_api_settings_write_rejects_invalid_value(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())

    response = client.put(
        "/api/settings/values",
        headers=_admin_headers(),
        json={"values": {"BOT_DRY_RUN": "maybe"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "BOT_DRY_RUN must be a boolean value."


def test_api_settings_import_requires_admin_and_updates_values(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())

    missing_response = client.post(
        "/api/settings/import",
        json={"values": {"BOT_LABEL": "Imported Bot"}},
    )
    import_response = client.post(
        "/api/settings/import",
        headers=_admin_headers(),
        json={"values": {"BOT_LABEL": "Imported Bot"}},
    )

    assert missing_response.status_code == 401
    assert import_response.status_code == 200
    assert import_response.json()["changed_count"] == 1
    assert client.get("/api/settings/values").json()["BOT_LABEL"]["value"] == "Imported Bot"


def test_api_settings_uses_hot_reloaded_database_overrides(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    initialize_database(database_url)
    client = TestClient(create_app())
    AppSettingRepository(database_url).set_many({"BOT_LABEL": "DB Bot"})

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["label"] == "DB Bot"


def test_api_settings_returns_market_analysis_effective_rate(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, market_analysis_method="percentile")
    initialize_database(database_url)
    MarketAnalysisRateRepository(database_url).add_many(
        [LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00012)]
    )

    client = TestClient(create_app(settings))

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["market_analysis_suggested_min_daily_rate"] == 0.00012
    assert body["effective_min_daily_rate"] == 0.00012


def test_api_market_analysis_status_explains_suggestion_state(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(
        database_url,
        market_analysis_currencies=("BTC", "ETH"),
        market_analysis_method="percentile",
    )
    initialize_database(database_url)
    MarketAnalysisRateRepository(database_url).add_many(
        [LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00012)]
    )

    client = TestClient(create_app(settings))

    response = client.get("/api/market-analysis-status")

    assert response.status_code == 200
    body = response.json()
    btc = next(row for row in body if row["currency"] == "BTC")
    eth = next(row for row in body if row["currency"] == "ETH")
    assert btc["sample_count"] == 1
    assert btc["suggested_min_daily_rate"] == 0.00012
    assert btc["reason"] == "Market analysis suggestion is available."
    assert eth["sample_count"] == 0
    assert eth["reason"] == "No market analysis samples have been recorded."


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
    assert history_response.json()["dry_run"] is True
    assert history_response.json()["source"] == "mock"
    history_rows = client.get("/api/lending-history").json()
    assert history_rows[0]["dry_run"] == 1
    assert history_rows[0]["source"] == "mock"

    open_offers_response = client.post("/api/actions/sync-open-offers")
    assert open_offers_response.status_code == 200
    assert open_offers_response.json()["changed_count"] == 0

    transfer_preview_response = client.post("/api/actions/transfer-preview")
    assert transfer_preview_response.status_code == 200
    assert transfer_preview_response.json()["dry_run"] is True
    assert transfer_preview_response.json()["transfer_count"] == 0

    transfer_funds_response = client.post("/api/actions/transfer-funds")
    assert transfer_funds_response.status_code == 200
    assert transfer_funds_response.json()["dry_run"] is True
    assert transfer_funds_response.json()["transferred_count"] == 0

    market_analysis_response = client.post("/api/actions/record-market-analysis")
    assert market_analysis_response.status_code == 200
    assert market_analysis_response.json()["changed_count"] == 1
    assert market_analysis_response.json()["currencies"] == ["BTC"]

    cancel_response = client.post("/api/actions/cancel-open-offers")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["would_cancel_count"] == 0
    assert cancel_response.json()["canceled_count"] == 0

    cleanup_response = client.post("/api/actions/cleanup")
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["deleted_count"] == 0
    assert cleanup_response.json()["market_rate_deleted_count"] == 0
    assert cleanup_response.json()["market_analysis_deleted_count"] == 0


def test_api_safe_action_returns_safety_error(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, dry_run=False, allow_live_trading=False)

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/smoke-exchange")

    assert response.status_code == 400
    assert "BOT_DRY_RUN=false requires ALLOW_LIVE_TRADING=true" in response.json()["detail"]


def test_api_record_market_analysis_uses_configured_currencies(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url, market_analysis_currencies=("BTC", "ETH"))

    client = TestClient(create_app(settings))

    response = client.post("/api/actions/record-market-analysis", json={"levels": 1})

    assert response.status_code == 200
    assert response.json()["currencies"] == ["BTC", "ETH"]
    assert response.json()["changed_count"] == 2


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
    assert body["bot_run_id"] == body["latest_run"]["id"]
    assert body["status"] == "completed"
    assert body["message"] == "Completed with 6 offer(s)."
    assert body["started_at"] == body["latest_run"]["started_at"]
    assert body["finished_at"] == body["latest_run"]["finished_at"]
    assert body["latest_run"]["status"] == "completed"
    assert len(body["decisions"]) == 3
    assert body["decisions"][0]["bot_run_id"] == body["bot_run_id"]
    per_currency_steps = [
        "load-market-orders",
        "record-market-orders",
        "load-strategy-config",
        "load-frr-rate",
        "load-market-analysis-rate",
        "calculate-active-amount",
        "load-btc-price",
        "calculate-decisions",
        "record-decisions",
        "prepare-offers",
    ]
    assert [step["step_key"] for step in body["steps"]] == [
        "create-run",
        "read-previous-active-loans",
        "read-active-loans",
        "replace-active-loans",
        "detect-new-active-loans",
        "read-lending-balances",
        "check-open-offer-rebalance-setting",
        "sync-open-offers",
        "replace-open-offers",
        "check-open-offer-cancel-setting",
        "evaluate-open-offer-cancel",
        *per_currency_steps,
        "record-dry-run-offer",
        "send-xday-notification",
        "record-dry-run-offer",
        "send-xday-notification",
        "record-dry-run-offer",
        "send-xday-notification",
        *per_currency_steps,
        "record-dry-run-offer",
        "send-xday-notification",
        "record-dry-run-offer",
        "send-xday-notification",
        "record-dry-run-offer",
        "send-xday-notification",
        *per_currency_steps,
        "finish-run",
        "send-run-summary",
        "send-periodic-summary",
    ]
    assert {"completed", "skipped"}.issuperset({step["status"] for step in body["steps"]})
    step_messages = [step["message"] for step in body["steps"]]
    assert any(
        step["step_key"] == "read-lending-balances"
        and "BTC" in step["message"]
        and "0.25" in step["message"]
        and "- Exchange wallet" in step["message"]
        and "- Margin/Trading wallet" in step["message"]
        for step in body["steps"]
    )
    for currency in ("BTC", "ETH", "USDT"):
        assert any(
            step["step_key"] == "load-market-orders" and currency in step["message"]
            for step in body["steps"]
        )
        assert any(
            step["step_key"] == "record-market-orders" and currency in step["message"]
            for step in body["steps"]
        )
        assert any(
            step["step_key"] == "calculate-decisions" and currency in step["message"]
            for step in body["steps"]
        )
        assert any(
            step["step_key"] == "calculate-decisions"
            and currency in step["message"]
            and "利率比較" in step["message"]
            and "最低要求來源" in step["message"]
            and "定價方式" in step["message"]
            and "金額" in step["message"]
            for step in body["steps"]
        )
        assert any(
            step["step_key"] == "record-decisions" and currency in step["message"]
            for step in body["steps"]
        )
        assert any(
            step["step_key"] == "prepare-offers" and currency in step["message"]
            for step in body["steps"]
        )
    assert any("BTC" in message and "3" in message for message in step_messages)
    assert any("ETH" in message and "3" in message for message in step_messages)
    assert any("USDT" in message and "3" in message for message in step_messages)
    assert any(
        step["step_key"] == "replace-open-offers"
        and "AUTO_REBALANCE_OPEN_OFFERS=false" in step["message"]
        and "影響：" in step["message"]
        and "設定鍵：" in step["message"]
        for step in body["steps"]
    )
    assert any(
        step["step_key"] == "evaluate-open-offer-cancel"
        and "AUTO_REBALANCE_OPEN_OFFERS=false" in step["message"]
        and "影響：" in step["message"]
        and "設定鍵：" in step["message"]
        for step in body["steps"]
    )
    assert any(
        step["step_key"] == "load-btc-price"
        and "GAP_MODE=off" in step["message"]
        and "BTC 價格參考" in step["message"]
        and "設定鍵：" in step["message"]
        for step in body["steps"]
    )
    assert any(
        step["step_key"] == "send-xday-notification"
        and "NOTIFY_XDAY_THRESHOLD=false" in step["message"]
        and "長天期委託通知" in step["message"]
        and "設定鍵：" in step["message"]
        for step in body["steps"]
    )
    assert any(
        step["step_key"] == "send-periodic-summary"
        and "NOTIFY_SUMMARY_MINUTES=0" in step["message"]
        and "週期摘要通知" in step["message"]
        and "設定鍵：" in step["message"]
        for step in body["steps"]
    )
    assert sum(1 for step in body["steps"] if step["step_key"] == "record-dry-run-offer") == 6
    assert sum(1 for step in body["steps"] if step["step_key"] == "send-xday-notification") == 6
    decisions_response = client.get(f"/api/runs/{body['bot_run_id']}/decisions")
    assert decisions_response.status_code == 200
    assert decisions_response.json() == body["decisions"]
    steps_response = client.get(f"/api/runs/{body['bot_run_id']}/steps")
    assert steps_response.status_code == 200
    assert steps_response.json() == body["steps"]


def test_api_run_once_returns_exchange_permission_error(tmp_path, monkeypatch) -> None:
    class PermissionFailingRunner:
        def run_once(self) -> None:
            raise ExchangePermissionError(
                'Bitfinex private request failed: POST /v1/offer/new: '
                'Exchange request failed with status 403: {"message":"permission denied"}.',
                status_code=403,
                response_body='{"message":"permission denied"}',
            )

    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    monkeypatch.setattr(
        "auto_lending_bot.api.actions.create_bot_runner",
        lambda *args, **kwargs: PermissionFailingRunner(),
    )
    client = TestClient(create_app(settings))

    response = client.post("/api/actions/run-once")

    assert response.status_code == 403
    assert response.json()["detail"] == (
        'Bitfinex private request failed: POST /v1/offer/new: '
        'Exchange request failed with status 403: {"message":"permission denied"}.'
    )


def test_api_reset_dry_run_records_deletes_local_dry_run_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    run_response = client.post("/api/actions/run-once")
    assert run_response.status_code == 200
    assert run_response.json()["created_count"] == 6
    LendingHistoryRepository(database_url).upsert_many(
        [_lending_history_entry("mock-history-reset")],
        dry_run=True,
        source="mock",
    )

    reset_response = client.post("/api/actions/reset-dry-run-records", headers=_admin_headers())

    assert reset_response.status_code == 200
    body = reset_response.json()
    assert body["action"] == "reset-dry-run-records"
    assert body["deleted_dry_run_offers"] == 6
    assert body["deleted_dry_run_lending_history"] == 1
    assert body["deleted_runs"] == 1
    assert body["deleted_decisions"] == 3
    assert body["deleted_steps"] > 0
    status_response = client.get("/api/status")
    assert status_response.json()["counts"]["bot_runs"] == 0
    assert status_response.json()["counts"]["loan_offers"] == 0
    assert status_response.json()["counts"]["lending_history"] == 0


def test_api_reset_dry_run_records_preserves_live_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    run_response = client.post("/api/actions/run-once")
    assert run_response.status_code == 200
    LendingHistoryRepository(database_url).upsert_many(
        [_lending_history_entry("live-history-reset")],
        dry_run=False,
        source="bitfinex",
    )
    with connect(database_url) as connection:
        cursor = connection.execute(
            "INSERT INTO bot_runs (status, dry_run, message) VALUES (?, ?, ?)",
            ("completed", 0, "live run"),
        )
        live_run_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO loan_offers (
                bot_run_id, currency, amount, daily_rate, duration_days, status, dry_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (live_run_id, "USDT", 10, 0.0001, 2, "created", 0),
        )
        connection.execute(
            """
            INSERT INTO bot_run_steps (bot_run_id, step_key, label, status, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (live_run_id, "finish-run", "完成", "completed", "live step"),
        )

    reset_response = client.post("/api/actions/reset-dry-run-records", headers=_admin_headers())

    assert reset_response.status_code == 200
    with connect(database_url) as connection:
        live_runs = connection.execute("SELECT COUNT(*) AS count FROM bot_runs WHERE dry_run = 0").fetchone()
        live_offers = connection.execute("SELECT COUNT(*) AS count FROM loan_offers WHERE dry_run = 0").fetchone()
        live_steps = connection.execute(
            "SELECT COUNT(*) AS count FROM bot_run_steps WHERE bot_run_id = ?",
            (live_run_id,),
        ).fetchone()
        live_history = connection.execute(
            "SELECT COUNT(*) AS count FROM lending_history WHERE dry_run = 0 AND source = 'bitfinex'"
        ).fetchone()
    assert int(live_runs["count"]) == 1
    assert int(live_offers["count"]) == 1
    assert int(live_steps["count"]) == 1
    assert int(live_history["count"]) == 1


def test_api_reset_dry_run_records_rejects_running_loop(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    start_response = client.post("/api/actions/start-loop")
    reset_response = client.post("/api/actions/reset-dry-run-records", headers=_admin_headers())
    stop_response = client.post("/api/actions/stop-loop")

    assert start_response.status_code == 200
    assert reset_response.status_code == 409
    assert reset_response.json()["detail"] == "Stop the bot loop before resetting dry-run records."
    assert stop_response.status_code == 200


def test_api_can_start_and_stop_dry_run_loop(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    start_response = client.post("/api/actions/start-loop")
    status_response = client.get("/api/bot-loop")
    stop_response = client.post("/api/actions/stop-loop")

    assert start_response.status_code == 200
    assert start_response.json()["action"] == "start-loop"
    assert isinstance(start_response.json()["bot_job_id"], int)
    assert status_response.status_code == 200
    assert "running" in status_response.json()
    assert stop_response.status_code == 200
    assert stop_response.json()["action"] == "stop-loop"
    assert stop_response.json()["running"] is False

    with connect(database_url) as connection:
        job = connection.execute(
            """
            SELECT profile_id, status, loops_completed, last_run_id, settings_snapshot_json
            FROM bot_jobs
            """
        ).fetchone()
    assert job["profile_id"] == "default"
    assert job["status"] == "stopped"
    assert int(job["loops_completed"]) >= 1
    assert job["last_run_id"] is not None
    assert '"dry_run":true' in job["settings_snapshot_json"]


def test_api_can_stop_loop_by_job_id(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    start_response = client.post("/api/actions/start-loop")
    bot_job_id = start_response.json()["bot_job_id"]
    stop_response = client.post(f"/api/jobs/{bot_job_id}/stop")

    assert stop_response.status_code == 200
    assert stop_response.json()["action"] == "stop-job"
    assert stop_response.json()["running"] is False
    assert stop_response.json()["bot_job_id"] == bot_job_id


def test_api_stop_job_rejects_non_active_job(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    response = client.post("/api/jobs/999/stop")

    assert response.status_code == 409
    assert response.json()["detail"] == "Bot job is not running in this API process."


def test_api_startup_restores_running_jobs_and_stops_stopping_jobs(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    repositories = create_repository_bundle(settings)
    running_job_id = repositories.bot_jobs.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json=settings_snapshot_json(settings),
    )
    stopping_job_id = repositories.bot_jobs.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json=settings_snapshot_json(settings),
    )
    repositories.bot_jobs.mark_stopping(stopping_job_id)

    client = TestClient(create_app(settings))
    status_response = client.get("/api/bot-loop")
    stop_response = client.post("/api/actions/stop-loop")

    running_job = repositories.bot_jobs.get(running_job_id)
    stopping_job = repositories.bot_jobs.get(stopping_job_id)
    assert status_response.status_code == 200
    assert status_response.json()["running"] is True
    assert status_response.json()["bot_job_id"] == running_job_id
    assert status_response.json()["restored_at"] is not None
    assert stop_response.status_code == 200
    assert running_job is not None
    assert stopping_job is not None
    assert running_job["status"] == "stopped"
    assert stopping_job["status"] == "stopped"
    assert stopping_job["stop_reason"] == "stop requested"


def test_api_startup_restores_only_latest_running_job(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    repositories = create_repository_bundle(settings)
    older_job_id = repositories.bot_jobs.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json=settings_snapshot_json(settings),
    )
    newer_job_id = repositories.bot_jobs.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json=settings_snapshot_json(settings),
    )

    client = TestClient(create_app(settings))
    status_response = client.get("/api/bot-loop")
    stop_response = client.post("/api/actions/stop-loop")

    older_job = repositories.bot_jobs.get(older_job_id)
    newer_job = repositories.bot_jobs.get(newer_job_id)
    assert status_response.status_code == 200
    assert status_response.json()["running"] is True
    assert status_response.json()["bot_job_id"] == newer_job_id
    assert status_response.json()["restored_at"] is not None
    assert stop_response.status_code == 200
    assert older_job is not None
    assert newer_job is not None
    assert older_job["status"] == "failed"
    assert older_job["last_error"] == "Multiple running jobs cannot be restored by single-loop runtime."
    assert newer_job["status"] == "stopped"


def test_api_startup_fails_invalid_running_job_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    repositories = create_repository_bundle(settings)
    bot_job_id = repositories.bot_jobs.create(
        DEFAULT_PROFILE_CONTEXT,
        settings_snapshot_json='{"dry_run": true}',
    )

    client = TestClient(create_app(settings))
    status_response = client.get("/api/bot-loop")

    job = repositories.bot_jobs.get(bot_job_id)
    assert status_response.status_code == 200
    assert status_response.json()["running"] is False
    assert status_response.json()["restored_at"] is None
    assert job is not None
    assert job["status"] == "failed"
    assert "required positional argument" in str(job["last_error"])


def test_api_can_start_loop_with_effective_settings_proxy(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setenv("BOT_DRY_RUN", "true")
    client = TestClient(create_app())

    start_response = client.post("/api/actions/start-loop")
    stop_response = client.post("/api/actions/stop-loop")

    assert start_response.status_code == 200
    assert isinstance(start_response.json()["bot_job_id"], int)
    assert stop_response.status_code == 200


def test_api_jobs_returns_safe_snapshot_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EXCHANGE_API_SECRET", "secret-value")
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    client.post("/api/actions/start-loop")
    client.post("/api/actions/stop-loop")

    response = client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["profile_id"] == "default"
    assert "settings_snapshot_json" not in body[0]
    assert body[0]["snapshot_summary"]["exchange"] == "mock"
    assert body[0]["snapshot_summary"]["dry_run"] is True
    assert "secret-value" not in str(body)


def test_api_cancel_single_open_offer_dry_run_uses_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    initialize_database(database_url)
    repositories = create_repository_bundle(settings)
    repositories.open_offers.replace_all(
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
    client = TestClient(create_app(settings))

    response = client.post(
        "/api/actions/cancel-open-offer",
        json={"external_offer_id": "offer-1"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "cancel-open-offer"
    assert response.json()["dry_run"] is True
    assert response.json()["would_cancel_count"] == 1
    assert response.json()["canceled_count"] == 0
    assert repositories.open_offers.count() == 1


def test_api_cancel_single_open_offer_requires_id(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)
    client = TestClient(create_app(settings))

    response = client.post("/api/actions/cancel-open-offer", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "external_offer_id is required."


def test_api_can_start_and_stop_market_analysis_collection(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = _settings(database_url)

    client = TestClient(create_app(settings))

    start_response = client.post("/api/actions/start-market-analysis")
    status_response = client.get("/api/market-analysis-collection")
    stop_response = client.post("/api/actions/stop-market-analysis")

    assert start_response.status_code == 200
    assert start_response.json()["action"] == "start-market-analysis"
    assert status_response.status_code == 200
    assert "running" in status_response.json()
    assert stop_response.status_code == 200
    assert stop_response.json()["action"] == "stop-market-analysis"
    assert stop_response.json()["running"] is False


def test_api_run_once_requires_live_confirmation(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
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

    response = client.post("/api/actions/run-once", headers=_admin_headers())

    assert response.status_code == 400
    assert response.json()["detail"] == "Live run requires confirm_live=true."


def test_api_cancel_open_offers_requires_live_confirmation(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
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

    response = client.post("/api/actions/cancel-open-offers", headers=_admin_headers())

    assert response.status_code == 400
    assert response.json()["detail"] == "Live cancel requires confirm_live=true."


@pytest.mark.parametrize(
    ("endpoint", "settings_kwargs"),
    [
        (
            "/api/actions/run-once",
            {
                "bitfinex_enable_live_offers": True,
                "max_total_lend_amount": 1,
                "max_single_offer_amount": 1,
            },
        ),
        (
            "/api/actions/start-loop",
            {
                "bitfinex_enable_live_offers": True,
                "max_total_lend_amount": 1,
                "max_single_offer_amount": 1,
            },
        ),
        (
            "/api/actions/cancel-open-offers",
            {
                "bitfinex_enable_live_offers": True,
                "max_total_lend_amount": 1,
                "max_single_offer_amount": 1,
            },
        ),
        (
            "/api/actions/transfer-funds",
            {
                "allow_balance_transfers": True,
                "bitfinex_enable_live_transfers": True,
                "max_total_transfer_amount": 1,
                "max_single_transfer_amount": 1,
            },
        ),
    ],
)
def test_api_live_actions_require_admin_authorization(
    tmp_path,
    monkeypatch,
    endpoint: str,
    settings_kwargs: dict[str, object],
) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-token")
    settings = _settings(
        database_url,
        exchange="bitfinex",
        api_key="key",
        api_secret="secret",
        dry_run=False,
        allow_live_trading=True,
        **settings_kwargs,
    )

    client = TestClient(create_app(settings))

    missing_response = client.post(endpoint, json={"confirm_live": True})
    wrong_response = client.post(
        endpoint,
        headers={"Authorization": "Bearer wrong-token"},
        json={"confirm_live": True},
    )

    assert missing_response.status_code == 401
    assert wrong_response.status_code == 401


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


def _lending_history_entry(external_entry_id: str) -> LendingHistoryEntry:
    return LendingHistoryEntry(
        currency="BTC",
        amount=0.1,
        daily_rate=0.00008,
        duration_days=2,
        interest=0.00001,
        fee=-0.0000015,
        earned=0.0000085,
        opened_at="2026-01-01 00:00:00",
        closed_at="2026-01-02 00:00:00",
        external_entry_id=external_entry_id,
    )


def _settings(
    database_url: str,
    dry_run: bool = True,
    allow_live_trading: bool = False,
    allow_balance_transfers: bool = False,
    exchange: str = "mock",
    api_key: str = "",
    api_secret: str = "",
    bitfinex_enable_live_offers: bool = False,
    bitfinex_enable_live_transfers: bool = False,
    max_total_lend_amount: float | None = None,
    max_single_offer_amount: float | None = None,
    max_total_transfer_amount: float | None = None,
    max_single_transfer_amount: float | None = None,
    market_analysis_currencies: tuple[str, ...] = (),
    market_analysis_method: str = "off",
    rate_optimization_mode: str = "off",
) -> Settings:
    return Settings(
        allow_live_trading=allow_live_trading,
        allow_balance_transfers=allow_balance_transfers,
        api_key=api_key,
        api_secret=api_secret,
        bitfinex_enable_live_offers=bitfinex_enable_live_offers,
        bitfinex_enable_live_transfers=bitfinex_enable_live_transfers,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        bot_inactive_sleep_seconds=300,
        auto_rebalance_open_offers=False,
        auto_cancel_open_offers=False,
        keep_stuck_orders=True,
        dry_run=dry_run,
        exchange=exchange,
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        market_analysis_retention_days=30,
        market_analysis_currencies=market_analysis_currencies,
        market_analysis_levels=10,
        market_analysis_min_samples=0,
        market_analysis_max_age_seconds=0,
        market_analysis_method=market_analysis_method,
        market_analysis_percentile=75,
        market_analysis_macd_short_samples=3,
        market_analysis_macd_long_samples=10,
        market_analysis_macd_short_seconds=0,
        market_analysis_macd_long_seconds=0,
        market_analysis_multiplier=1.0,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
        transferable_currencies=(),
        smoke_test_currency="BTC",
        strategy_debug=False,
        telegram_bot_token="",
        telegram_chat_id="",
        notify_prefix="",
        notify_caught_exception=False,
        notify_summary_minutes=0,
        notify_xday_threshold=False,
        hide_coins=True,
        gap_mode="off",
        gap_bottom=0,
        gap_top=0,
        xday_threshold=0,
        xdays=2,
        xday_spread=0,
        frr_as_min=False,
        frr_delta=0,
        rate_optimization_mode=rate_optimization_mode,
        rate_optimization_min_probability=0.25,
        rate_optimization_sample_size=200,
        max_amount_to_lend=None,
        max_active_amount=None,
        max_single_transfer_amount=max_single_transfer_amount,
        max_single_offer_amount=max_single_offer_amount,
        max_total_transfer_amount=max_total_transfer_amount,
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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer admin-token"}
