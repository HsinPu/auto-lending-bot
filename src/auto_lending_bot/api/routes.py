from fastapi import APIRouter, HTTPException

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings, sqlite_path_from_url, strategy_config_for
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.market.analysis_recorder import MarketAnalysisRecorder
from auto_lending_bot.notifications.notifier import Notifier
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
from auto_lending_bot.safety import SafetyError, validate_run_settings


def create_api_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    bot_runs = BotRunRepository(settings.database_url)
    loan_offers = LoanOfferRepository(settings.database_url)
    market_rates = MarketRateRepository(settings.database_url)
    market_analysis_rates = MarketAnalysisRateRepository(settings.database_url)
    active_loans = ActiveLoanRepository(settings.database_url)
    lending_history = LendingHistoryRepository(settings.database_url)
    open_offers = OpenLoanOfferRepository(settings.database_url)
    notification_state = NotificationStateRepository(settings.database_url)

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
                "market_analysis_rates": market_analysis_rates.count(),
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

    @router.get("/converted-earnings")
    def converted_earnings() -> list[dict[str, object]]:
        return _converted_earnings(
            earnings_rows=lending_history.earnings_summary_by_currency(),
            output_currency=settings.output_currency,
            exchange=create_exchange_client(settings),
        )

    @router.get("/market-rates")
    def market_rate_rows() -> list[dict[str, object]]:
        return market_rates.recent()

    @router.get("/market-analysis-rates")
    def market_analysis_rate_rows() -> list[dict[str, object]]:
        return market_analysis_rates.recent()

    @router.get("/settings")
    def settings_snapshot() -> dict[str, object]:
        strategy = strategy_config_for(settings, settings.smoke_test_currency)
        return {
            "label": settings.bot_label,
            "exchange": settings.exchange,
            "dry_run": settings.dry_run,
            "allow_live_trading": settings.allow_live_trading,
            "bitfinex_enable_live_offers": settings.bitfinex_enable_live_offers,
            "output_currency": settings.output_currency,
            "market_analysis_levels": settings.market_analysis_levels,
            "smoke_test_currency": settings.smoke_test_currency,
            "strategy_debug": settings.strategy_debug,
            "strategy": strategy.__dict__,
        }

    @router.get("/currency-details")
    def currency_details() -> list[dict[str, object]]:
        return _currency_details(
            active_loans=active_loans.recent(1000),
            open_offer_rows=open_offers.recent(1000),
            earnings_rows=lending_history.earnings_summary_by_currency(),
            market_rate_rows=market_rates.recent(1000),
        )

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

    @router.post("/actions/record-market-analysis")
    def record_market_analysis(payload: dict[str, object] | None = None) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        payload = payload or {}
        currency = str(payload.get("currency") or settings.smoke_test_currency).upper()
        levels = int(payload.get("levels") or settings.market_analysis_levels)
        changed_count = MarketAnalysisRecorder(market_analysis_rates).record_currency(
            exchange=create_exchange_client(settings),
            currency=currency,
            levels=levels,
        )
        return {
            "action": "record-market-analysis",
            "ok": True,
            "currency": currency,
            "changed_count": changed_count,
        }

    @router.post("/actions/cancel-open-offers")
    def cancel_open_offers(payload: dict[str, bool] | None = None) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live cancel requires confirm_live=true.")

        exchange = create_exchange_client(settings)
        offers = exchange.get_open_loan_offers()
        if settings.dry_run:
            return {
                "action": "cancel-open-offers",
                "ok": True,
                "dry_run": True,
                "would_cancel_count": len(offers),
                "canceled_count": 0,
            }

        canceled_count = _cancel_open_offers(exchange, offers)
        open_offers.replace_all([])
        return {
            "action": "cancel-open-offers",
            "ok": True,
            "dry_run": False,
            "would_cancel_count": len(offers),
            "canceled_count": canceled_count,
        }

    @router.post("/actions/cleanup")
    def cleanup() -> dict[str, object]:
        market_rate_deleted_count = market_rates.delete_older_than_days(
            settings.market_rate_retention_days
        )
        market_analysis_deleted_count = market_analysis_rates.delete_older_than_days(
            settings.market_analysis_retention_days
        )
        return {
            "action": "cleanup",
            "ok": True,
            "deleted_count": market_rate_deleted_count + market_analysis_deleted_count,
            "market_rate_deleted_count": market_rate_deleted_count,
            "market_analysis_deleted_count": market_analysis_deleted_count,
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
            open_offers=open_offers,
            lending_history=lending_history,
            notification_state=notification_state,
            market_analysis_rates=market_analysis_rates,
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


def _cancel_open_offers(exchange, offers: list[object]) -> int:
    canceled_count = 0
    for offer in offers:
        external_offer_id = getattr(offer, "external_offer_id", None)
        if not external_offer_id:
            continue
        exchange.cancel_loan_offer(str(external_offer_id))
        canceled_count += 1
    return canceled_count


def _currency_details(
    active_loans: list[dict[str, object]],
    open_offer_rows: list[dict[str, object]],
    earnings_rows: list[dict[str, object]],
    market_rate_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    currencies = sorted(
        {
            *(str(row["currency"]) for row in active_loans),
            *(str(row["currency"]) for row in open_offer_rows),
            *(str(row["currency"]) for row in earnings_rows),
            *(str(row["currency"]) for row in market_rate_rows),
        }
    )
    details = []
    for currency in currencies:
        currency_active_loans = [row for row in active_loans if row["currency"] == currency]
        currency_open_offers = [row for row in open_offer_rows if row["currency"] == currency]
        latest_market_rate = next(
            (row for row in market_rate_rows if row["currency"] == currency),
            None,
        )
        earnings = next((row for row in earnings_rows if row["currency"] == currency), {})
        active_amount = sum(float(row["amount"]) for row in currency_active_loans)
        weighted_rate = sum(
            float(row["amount"]) * float(row["daily_rate"]) for row in currency_active_loans
        )
        details.append(
            {
                "currency": currency,
                "active_amount": active_amount,
                "open_offer_amount": sum(float(row["amount"]) for row in currency_open_offers),
                "average_daily_rate": weighted_rate / active_amount if active_amount else 0,
                "latest_market_rate": latest_market_rate["daily_rate"] if latest_market_rate else 0,
                "total_earned": earnings.get("total_earned", 0),
                "active_loan_count": len(currency_active_loans),
                "open_offer_count": len(currency_open_offers),
            }
        )
    return details


def _converted_earnings(
    earnings_rows: list[dict[str, object]],
    output_currency: str,
    exchange,
) -> list[dict[str, object]]:
    output_currency = output_currency.upper()
    output_btc_price = _safe_btc_price(exchange, output_currency)
    converted_rows = []
    for row in earnings_rows:
        currency = str(row["currency"]).upper()
        total_earned = float(row.get("total_earned", 0))
        currency_btc_price = _safe_btc_price(exchange, currency)
        converted_total = None
        conversion_available = False
        if currency_btc_price is not None and output_btc_price not in {None, 0}:
            converted_total = total_earned * currency_btc_price / output_btc_price
            conversion_available = True
        converted_rows.append(
            {
                "currency": currency,
                "output_currency": output_currency,
                "total_earned": total_earned,
                "converted_total_earned": converted_total,
                "conversion_available": conversion_available,
            }
        )
    return converted_rows


def _safe_btc_price(exchange, currency: str) -> float | None:
    try:
        return exchange.get_btc_price(currency)
    except Exception:
        return None
