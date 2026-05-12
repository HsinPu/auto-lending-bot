from fastapi import APIRouter, HTTPException

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings, sqlite_path_from_url, strategy_config_for
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
)
from auto_lending_bot.safety import SafetyError, validate_run_settings


def create_api_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    bot_runs = BotRunRepository(settings.database_url)
    loan_offers = LoanOfferRepository(settings.database_url)
    market_rates = MarketRateRepository(settings.database_url)
    active_loans = ActiveLoanRepository(settings.database_url)
    lending_history = LendingHistoryRepository(settings.database_url)
    open_offers = OpenLoanOfferRepository(settings.database_url)

    @router.get("/status")
    def status() -> dict[str, object]:
        return {
            "label": settings.bot_label,
            "database": str(sqlite_path_from_url(settings.database_url)),
            "exchange": settings.exchange,
            "dry_run": settings.dry_run,
            "live_trading_allowed": settings.allow_live_trading,
            "counts": {
                "bot_runs": bot_runs.count(),
                "loan_offers": loan_offers.count(),
                "open_loan_offers": open_offers.count(),
                "active_loans": active_loans.count(),
                "lending_history": lending_history.count(),
                "market_rates": market_rates.count(),
            },
            "latest_run": bot_runs.latest(),
        }

    @router.get("/runs")
    def runs() -> list[dict[str, object]]:
        return bot_runs.recent()

    @router.get("/offers")
    def offers() -> list[dict[str, object]]:
        return loan_offers.recent()

    @router.get("/open-offers")
    def open_loan_offers() -> list[dict[str, object]]:
        return open_offers.recent()

    @router.get("/active-loans")
    def active_loan_rows() -> list[dict[str, object]]:
        return active_loans.recent()

    @router.get("/lending-history")
    def lending_history_rows() -> list[dict[str, object]]:
        return lending_history.recent()

    @router.get("/earnings")
    def earnings() -> list[dict[str, object]]:
        return lending_history.earnings_summary_by_currency()

    @router.get("/market-rates")
    def market_rate_rows() -> list[dict[str, object]]:
        return market_rates.recent()

    @router.get("/settings")
    def settings_snapshot() -> dict[str, object]:
        strategy = strategy_config_for(settings, settings.smoke_test_currency)
        return {
            "label": settings.bot_label,
            "exchange": settings.exchange,
            "dry_run": settings.dry_run,
            "allow_live_trading": settings.allow_live_trading,
            "bitfinex_enable_live_offers": settings.bitfinex_enable_live_offers,
            "smoke_test_currency": settings.smoke_test_currency,
            "strategy_debug": settings.strategy_debug,
            "strategy": strategy.__dict__,
        }

    @router.post("/actions/smoke-exchange")
    def smoke_exchange() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        exchange = create_exchange_client(settings)
        balances = exchange.get_lending_balances()
        orders = exchange.get_loan_orders(settings.smoke_test_currency)
        best_rate = max((order.daily_rate for order in orders), default=0)
        return {
            "action": "smoke-exchange",
            "ok": True,
            "exchange": settings.exchange,
            "currency": settings.smoke_test_currency.upper(),
            "lending_balances": len(balances),
            "loan_orders": len(orders),
            "best_daily_rate": best_rate,
        }

    @router.post("/actions/sync-history")
    def sync_history() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        entries = create_exchange_client(settings).get_lending_history(settings.smoke_test_currency)
        changed_count = lending_history.upsert_many(entries)
        return {
            "action": "sync-history",
            "ok": True,
            "currency": settings.smoke_test_currency.upper(),
            "changed_count": changed_count,
        }

    @router.post("/actions/sync-open-offers")
    def sync_open_offers() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        offers = create_exchange_client(settings).get_open_loan_offers()
        open_offers.replace_all(offers)
        return {
            "action": "sync-open-offers",
            "ok": True,
            "changed_count": len(offers),
        }

    @router.post("/actions/cleanup")
    def cleanup() -> dict[str, object]:
        deleted_count = market_rates.delete_older_than_days(settings.market_rate_retention_days)
        return {
            "action": "cleanup",
            "ok": True,
            "deleted_count": deleted_count,
        }

    @router.post("/actions/run-once")
    def run_once(payload: dict[str, bool] | None = None) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live run requires confirm_live=true.")

        offers_before = loan_offers.count()
        runner = BotRunner(
            settings=settings,
            exchange=create_exchange_client(settings),
            bot_runs=bot_runs,
            loan_offers=loan_offers,
            active_loans=active_loans,
            market_recorder=MarketRecorder(market_rates),
            notifier=Notifier(settings=settings),
        )
        runner.run_once()
        offers_after = loan_offers.count()
        return {
            "action": "run-once",
            "ok": True,
            "dry_run": settings.dry_run,
            "created_count": offers_after - offers_before,
            "latest_run": bot_runs.latest(),
        }

    return router


def _validate_safe_action_settings(settings: Settings) -> None:
    try:
        validate_run_settings(settings)
    except SafetyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
