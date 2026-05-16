from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
import threading

from fastapi import APIRouter, Header, HTTPException, Request

from auto_lending_bot.api.actions import BotActionService
from auto_lending_bot.api.dashboard import DashboardReadService, DashboardRepositories
from auto_lending_bot.bot.factory import RunnerRepositories, create_bot_runner
from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import (
    Settings,
    admin_auth_token,
    settings_encryption_key,
    sqlite_path_from_url,
    strategy_config_for,
)
from auto_lending_bot.domain.models import ActiveLoan, CurrencyBalance, LoanOrder
from auto_lending_bot.domain.strategy import build_lending_decision
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.operations.exchange_actions import ExchangeActionService
from auto_lending_bot.operations.maintenance import MaintenanceActionService
from auto_lending_bot.persistence.factory import RepositoryBundle, create_repository_bundle
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
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
)
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext
from auto_lending_bot.safety import (
    SafetyError,
    validate_run_settings,
    validate_transfer_limits,
    validate_transfer_settings,
)
from auto_lending_bot.settings_registry import GLOBAL_SETTING_SCOPE, setting_schema, setting_scope
from auto_lending_bot.settings_snapshot import settings_from_snapshot_json


class _SettingsProxy:
    def __init__(self, provider: Callable[[], Settings]) -> None:
        self._provider = provider

    def __getattr__(self, name: str):
        return getattr(self._provider(), name)


@dataclass(frozen=True)
class _RuntimeControllers:
    profile_context: BotProfileContext
    bot_loop: "_BotLoopController"
    market_analysis_collection: "_MarketAnalysisCollectionController"


def create_api_router(settings: Settings | Callable[[], Settings]) -> APIRouter:
    settings = _SettingsProxy(settings) if callable(settings) else settings
    router = APIRouter()

    repositories = create_repository_bundle(
        settings,
        settings_encryption_key=settings_encryption_key(),
    )
    bot_jobs = repositories.bot_jobs
    bot_runs = repositories.bot_runs
    loan_offers = repositories.loan_offers
    market_rates = repositories.market_rates
    market_analysis_rates = repositories.market_analysis_rates
    active_loans = repositories.active_loans
    bot_run_decisions = repositories.bot_run_decisions
    bot_run_steps = repositories.bot_run_steps
    lending_history = repositories.lending_history
    open_offers = repositories.open_offers
    notification_state = repositories.notification_state
    maintenance_actions = MaintenanceActionService(settings=settings, repositories=repositories)
    exchange_actions = ExchangeActionService(settings=settings, repositories=repositories)
    dashboard_reads = DashboardReadService(
        DashboardRepositories(
            bot_runs=bot_runs,
            loan_offers=loan_offers,
            open_offers=open_offers,
            active_loans=active_loans,
            lending_history=lending_history,
            market_rates=market_rates,
            market_analysis_rates=market_analysis_rates,
            run_decisions=bot_run_decisions,
            run_steps=bot_run_steps,
        ),
        profile_context=DEFAULT_PROFILE_CONTEXT,
    )
    runtime = _create_runtime_controllers(
        settings=settings,
        bot_jobs=bot_jobs,
        bot_runs=bot_runs,
        loan_offers=loan_offers,
        active_loans=active_loans,
        open_offers=open_offers,
        lending_history=lending_history,
        notification_state=notification_state,
        market_analysis_rates=market_analysis_rates,
        market_rates=market_rates,
        bot_run_decisions=bot_run_decisions,
        bot_run_steps=bot_run_steps,
        maintenance_actions=maintenance_actions,
    )
    bot_actions = BotActionService(
        settings=settings,
        repositories=repositories,
        loop_controller=runtime.bot_loop,
        profile_context=runtime.profile_context,
    )

    @router.get("/settings/schema")
    def settings_schema() -> list[dict[str, object]]:
        return setting_schema()

    @router.get("/settings/effective")
    def settings_effective() -> dict[str, object]:
        return settings_snapshot()

    @router.get("/settings/values")
    def settings_values() -> dict[str, object]:
        return _settings_values(settings, runtime.profile_context)

    @router.put("/settings/values")
    def update_settings_values(
        payload: dict[str, object],
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _require_backend_admin(authorization, request)
        values = payload.get("values", payload)
        if not isinstance(values, dict):
            raise HTTPException(status_code=400, detail="Settings values must be an object.")
        try:
            _set_settings_values(
                settings,
                runtime.profile_context,
                {str(key): str(value) for key, value in values.items()},
                source="api",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"ok": True, "changed_count": len(values)}

    @router.post("/settings/reset")
    def reset_settings(
        request: Request,
        payload: dict[str, object] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _require_backend_admin(authorization, request)
        payload = payload or {}
        key = payload.get("key")
        if key:
            _reset_setting(settings, runtime.profile_context, str(key), source="api")
            return {"ok": True, "reset_count": 1}
        existing_count = len(_settings_values(settings, runtime.profile_context))
        _reset_all_settings(settings, runtime.profile_context, source="api")
        return {"ok": True, "reset_count": existing_count}

    @router.get("/settings/export")
    def export_settings() -> dict[str, object]:
        values = _settings_values(settings, runtime.profile_context)
        exported_values = {
            key: str(row["value"])
            for key, row in values.items()
            if not int(row.get("is_secret", 0))
        }
        excluded_secret_keys = [
            key for key, row in values.items() if int(row.get("is_secret", 0))
        ]
        return {
            "version": 1,
            "includes_secrets": False,
            "values": exported_values,
            "excluded_secret_keys": excluded_secret_keys,
        }

    @router.post("/settings/import")
    def import_settings(
        payload: dict[str, object],
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _require_backend_admin(authorization, request)
        values = payload.get("values", payload)
        if not isinstance(values, dict):
            raise HTTPException(status_code=400, detail="Settings import values must be an object.")
        try:
            _set_settings_values(
                settings,
                runtime.profile_context,
                {str(key): str(value) for key, value in values.items()},
                source="api_import",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"ok": True, "changed_count": len(values)}

    @router.get("/settings/audit-log")
    def settings_audit_log() -> list[dict[str, object]]:
        return _settings_audit_log(settings, runtime.profile_context)

    @router.get("/status")
    def status() -> dict[str, object]:
        return {
            "label": settings.bot_label,
            "profile": dashboard_reads.profile_context.as_dict(),
            "database": str(sqlite_path_from_url(settings.database_url)),
            "exchange": settings.exchange,
            "dry_run": settings.dry_run,
            "live_trading_allowed": settings.allow_live_trading,
            "settings_runtime": _settings_runtime(settings),
            "bot_loop": runtime.bot_loop.status(),
            "market_analysis_collection": runtime.market_analysis_collection.status(),
            "counts": dashboard_reads.counts(),
            "latest_run": dashboard_reads.latest_run(),
        }

    @router.get("/live-readiness")
    def live_readiness() -> dict[str, object]:
        return _live_readiness(settings)

    @router.get("/bot-loop")
    def bot_loop_status() -> dict[str, object]:
        return runtime.bot_loop.status()

    @router.get("/market-analysis-collection")
    def market_analysis_collection_status() -> dict[str, object]:
        return runtime.market_analysis_collection.status()

    @router.get("/runs")
    def runs() -> list[dict[str, object]]:
        return dashboard_reads.recent_runs()

    @router.get("/runs/{bot_run_id}/decisions")
    def run_decisions(bot_run_id: int) -> list[dict[str, object]]:
        return dashboard_reads.run_decisions(bot_run_id)

    @router.get("/runs/{bot_run_id}/steps")
    def run_steps(bot_run_id: int) -> list[dict[str, object]]:
        return dashboard_reads.run_steps(bot_run_id)

    @router.get("/offers")
    def offers() -> list[dict[str, object]]:
        return dashboard_reads.recent_offers()

    @router.get("/open-offers")
    def open_loan_offers() -> list[dict[str, object]]:
        return dashboard_reads.recent_open_offers()

    @router.get("/active-loans")
    def active_loan_rows() -> list[dict[str, object]]:
        return dashboard_reads.recent_active_loans()

    @router.get("/lending-history")
    def lending_history_rows() -> list[dict[str, object]]:
        return dashboard_reads.recent_lending_history()

    @router.get("/earnings")
    def earnings() -> list[dict[str, object]]:
        return dashboard_reads.earnings_summary_by_currency()

    @router.get("/converted-earnings")
    def converted_earnings() -> list[dict[str, object]]:
        return _converted_earnings(
            earnings_rows=dashboard_reads.earnings_summary_by_currency(),
            output_currency=settings.output_currency,
            exchange=_exchange_client(settings, runtime.profile_context),
        )

    @router.get("/market-rates")
    def market_rate_rows() -> list[dict[str, object]]:
        return dashboard_reads.recent_market_rates()

    @router.get("/market-analysis-rates")
    def market_analysis_rate_rows() -> list[dict[str, object]]:
        return dashboard_reads.recent_market_analysis_rates()

    @router.get("/market-analysis-status")
    def market_analysis_status() -> list[dict[str, object]]:
        return _market_analysis_status(settings, market_analysis_rates)

    @router.get("/settings")
    def settings_snapshot() -> dict[str, object]:
        strategy = strategy_config_for(settings, settings.smoke_test_currency)
        suggested_min_daily_rate = _suggested_min_daily_rate(
            settings,
            market_analysis_rates,
            settings.smoke_test_currency,
        )
        return {
            "label": settings.bot_label,
            "profile": runtime.profile_context.as_dict(),
            "exchange": settings.exchange,
            "dry_run": settings.dry_run,
            "allow_live_trading": settings.allow_live_trading,
            "bitfinex_enable_live_offers": settings.bitfinex_enable_live_offers,
            "output_currency": settings.output_currency,
            "display_timezone": settings.display_timezone,
            "market_analysis_currencies": settings.market_analysis_currencies,
            "market_analysis_interval_seconds": settings.market_analysis_interval_seconds,
            "market_analysis_levels": settings.market_analysis_levels,
            "market_analysis_suggested_min_daily_rate": suggested_min_daily_rate,
            "effective_min_daily_rate": max(
                strategy.min_daily_rate,
                suggested_min_daily_rate or 0,
            ),
            "smoke_test_currency": settings.smoke_test_currency,
            "strategy_debug": settings.strategy_debug,
            "strategy": strategy.__dict__,
        }

    @router.get("/currency-details")
    def currency_details() -> list[dict[str, object]]:
        return _currency_details(
            active_loans=dashboard_reads.recent_active_loans(1000),
            open_offer_rows=dashboard_reads.recent_open_offers(1000),
            earnings_rows=dashboard_reads.earnings_summary_by_currency(),
            market_rate_rows=dashboard_reads.recent_market_rates(1000),
        )

    @router.get("/strategy-decisions")
    def strategy_decisions() -> list[dict[str, object]]:
        return _strategy_decisions(settings, active_loans, open_offers, market_analysis_rates)

    @router.post("/actions/smoke-exchange")
    def smoke_exchange() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        exchange = _exchange_client(settings, runtime.profile_context)
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
        return maintenance_actions.sync_history(
            _exchange_client(settings, runtime.profile_context)
        )

    @router.post("/actions/sync-open-offers")
    def sync_open_offers() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        return maintenance_actions.sync_open_offers(
            _exchange_client(settings, runtime.profile_context)
        )

    @router.post("/actions/transfer-preview")
    def transfer_preview() -> dict[str, object]:
        _validate_transfer_action_settings(settings)
        exchange = _exchange_client(settings, runtime.profile_context)
        return exchange_actions.transfer_preview_response(
            exchange_actions.transfer_previews(exchange)
        )

    @router.post("/actions/transfer-funds")
    def transfer_funds(
        request: Request,
        payload: dict[str, bool] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _validate_transfer_action_settings(settings)
        if not settings.dry_run:
            _require_backend_admin(authorization, request)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live transfer requires confirm_live=true.")

        exchange = _exchange_client(settings, runtime.profile_context)
        previews = exchange_actions.transfer_previews(exchange)
        _validate_transfer_limits(settings, previews)
        return exchange_actions.transfer_funds_response(exchange, previews)

    @router.post("/actions/record-market-analysis")
    def record_market_analysis(payload: dict[str, object] | None = None) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        payload = payload or {}
        currency = payload.get("currency")
        levels = int(payload.get("levels") or settings.market_analysis_levels)
        return maintenance_actions.record_market_analysis(
            exchange=_exchange_client(settings, runtime.profile_context),
            currency=str(currency) if currency else None,
            levels=levels,
        )

    @router.post("/actions/start-market-analysis")
    def start_market_analysis() -> dict[str, object]:
        _validate_safe_action_settings(settings)
        return {
            "action": "start-market-analysis",
            "ok": True,
            **runtime.market_analysis_collection.start(),
        }

    @router.post("/actions/stop-market-analysis")
    def stop_market_analysis() -> dict[str, object]:
        return {
            "action": "stop-market-analysis",
            "ok": True,
            **runtime.market_analysis_collection.stop(),
        }

    @router.post("/actions/cancel-open-offers")
    def cancel_open_offers(
        request: Request,
        payload: dict[str, bool] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        if not settings.dry_run:
            _require_backend_admin(authorization, request)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live cancel requires confirm_live=true.")

        return exchange_actions.cancel_open_offers_response(
            _exchange_client(settings, runtime.profile_context)
        )

    @router.post("/actions/cleanup")
    def cleanup() -> dict[str, object]:
        return maintenance_actions.cleanup_market_data()

    @router.post("/actions/reset-dry-run-records")
    def reset_dry_run_records(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _require_backend_admin(authorization, request)
        if bot_actions.loop_status()["running"]:
            raise HTTPException(status_code=409, detail="Stop the bot loop before resetting dry-run records.")
        return bot_actions.reset_dry_run_records()

    @router.post("/actions/run-once")
    def run_once(
        request: Request,
        payload: dict[str, bool] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        if not settings.dry_run:
            _require_backend_admin(authorization, request)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live run requires confirm_live=true.")

        return bot_actions.run_once()

    @router.post("/actions/start-loop")
    def start_loop(
        request: Request,
        payload: dict[str, bool] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _validate_safe_action_settings(settings)
        if not settings.dry_run:
            _require_backend_admin(authorization, request)
        if not settings.dry_run and not (payload or {}).get("confirm_live", False):
            raise HTTPException(status_code=400, detail="Live loop requires confirm_live=true.")

        return bot_actions.start_loop()

    @router.post("/actions/stop-loop")
    def stop_loop() -> dict[str, object]:
        return bot_actions.stop_loop()

    return router


class _BotLoopController:
    def __init__(
        self,
        settings: Settings,
        profile_context: BotProfileContext,
        bot_jobs: BotJobRepository,
        bot_runs: BotRunRepository,
        loan_offers: LoanOfferRepository,
        active_loans: ActiveLoanRepository,
        open_offers: OpenLoanOfferRepository,
        lending_history: LendingHistoryRepository,
        notification_state: NotificationStateRepository,
        market_analysis_rates: MarketAnalysisRateRepository,
        market_rates: MarketRateRepository,
        bot_run_decisions: BotRunDecisionRepository,
        bot_run_steps: BotRunStepRepository,
    ) -> None:
        self._settings = settings
        self._profile_context = profile_context
        self._bot_jobs = bot_jobs
        self._bot_runs = bot_runs
        self._loan_offers = loan_offers
        self._active_loans = active_loans
        self._open_offers = open_offers
        self._lending_history = lending_history
        self._notification_state = notification_state
        self._market_analysis_rates = market_analysis_rates
        self._market_rates = market_rates
        self._bot_run_decisions = bot_run_decisions
        self._bot_run_steps = bot_run_steps
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._bot_job_id: int | None = None
        self._started_at: str | None = None
        self._last_run_at: str | None = None
        self._last_error: str | None = None
        self._loops_completed = 0

    def start(self, bot_job_id: int) -> dict[str, object]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._status_unlocked()

            self._stop_event = threading.Event()
            self._bot_job_id = bot_job_id
            self._started_at = _utc_now()
            self._last_error = None
            self._loops_completed = 0
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return self._status_unlocked()

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        return self.status()

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_unlocked()

    def _status_unlocked(self) -> dict[str, object]:
        running = self._thread is not None and self._thread.is_alive()
        return {
            "running": running,
            "started_at": self._started_at,
            "last_run_at": self._last_run_at,
            "loops_completed": self._loops_completed,
            "last_error": self._last_error,
        }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_settings = self._settings_for_current_job()
                validate_run_settings(job_settings)
                runner = _create_runner(
                    settings=job_settings,
                    bot_runs=self._bot_runs,
                    loan_offers=self._loan_offers,
                    active_loans=self._active_loans,
                    open_offers=self._open_offers,
                    lending_history=self._lending_history,
                    notification_state=self._notification_state,
                    market_analysis_rates=self._market_analysis_rates,
                    market_rates=self._market_rates,
                    bot_run_decisions=self._bot_run_decisions,
                    bot_run_steps=self._bot_run_steps,
                    profile_context=self._profile_context,
                    bot_job_id=self._bot_job_id,
                )
                created_offers = runner.run_once_with_retry()
                wait_seconds = self._sleep_seconds(job_settings, created_offers)
                with self._lock:
                    self._loops_completed += 1
                    self._last_run_at = _utc_now()
                    self._last_error = None
            except Exception as error:
                wait_seconds = max(self._settings.retry_backoff_seconds, 1)
                with self._lock:
                    self._last_error = str(error)
                    self._last_run_at = _utc_now()

            self._stop_event.wait(wait_seconds)

    def _settings_for_current_job(self) -> Settings:
        bot_job_id = self._bot_job_id
        if bot_job_id is None:
            msg = "Bot loop job is not initialized."
            raise RuntimeError(msg)
        job = self._bot_jobs.get(bot_job_id)
        if job is None:
            msg = f"Bot job {bot_job_id} was not found."
            raise RuntimeError(msg)
        return settings_from_snapshot_json(str(job["settings_snapshot_json"]))

    def _sleep_seconds(self, settings: Settings, created_offers: int) -> int:
        if created_offers > 0:
            return max(settings.bot_sleep_seconds, 1)
        return max(settings.bot_inactive_sleep_seconds, 1)


class _MarketAnalysisCollectionController:
    def __init__(
        self,
        settings: Settings,
        maintenance_actions: MaintenanceActionService,
    ) -> None:
        self._settings = settings
        self._maintenance_actions = maintenance_actions
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: str | None = None
        self._last_run_at: str | None = None
        self._last_error: str | None = None
        self._loops_completed = 0
        self._last_changed_count = 0

    def start(self) -> dict[str, object]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._status_unlocked()

            self._stop_event = threading.Event()
            self._started_at = _utc_now()
            self._last_error = None
            self._loops_completed = 0
            self._last_changed_count = 0
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return self._status_unlocked()

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        return self.status()

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_unlocked()

    def _status_unlocked(self) -> dict[str, object]:
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "started_at": self._started_at,
            "last_run_at": self._last_run_at,
            "loops_completed": self._loops_completed,
            "last_changed_count": self._last_changed_count,
            "last_error": self._last_error,
        }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self._maintenance_actions.record_market_analysis(
                    exchange=_exchange_client(self._settings, DEFAULT_PROFILE_CONTEXT),
                )
                wait_seconds = max(self._settings.market_analysis_interval_seconds, 1)
                with self._lock:
                    self._loops_completed += 1
                    self._last_changed_count = int(result["changed_count"])
                    self._last_run_at = _utc_now()
                    self._last_error = None
            except Exception as error:
                wait_seconds = max(self._settings.retry_backoff_seconds, 1)
                with self._lock:
                    self._last_error = str(error)
                    self._last_run_at = _utc_now()

            self._stop_event.wait(wait_seconds)


def _create_runtime_controllers(
    settings: Settings,
    bot_jobs: BotJobRepository,
    bot_runs: BotRunRepository,
    loan_offers: LoanOfferRepository,
    active_loans: ActiveLoanRepository,
    open_offers: OpenLoanOfferRepository,
    lending_history: LendingHistoryRepository,
    notification_state: NotificationStateRepository,
    market_analysis_rates: MarketAnalysisRateRepository,
    market_rates: MarketRateRepository,
    bot_run_decisions: BotRunDecisionRepository,
    bot_run_steps: BotRunStepRepository,
    maintenance_actions: MaintenanceActionService,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
) -> _RuntimeControllers:
    return _RuntimeControllers(
        profile_context=profile_context,
        bot_loop=_BotLoopController(
            settings=settings,
            profile_context=profile_context,
            bot_jobs=bot_jobs,
            bot_runs=bot_runs,
            loan_offers=loan_offers,
            active_loans=active_loans,
            open_offers=open_offers,
            lending_history=lending_history,
            notification_state=notification_state,
            market_analysis_rates=market_analysis_rates,
            market_rates=market_rates,
            bot_run_decisions=bot_run_decisions,
            bot_run_steps=bot_run_steps,
        ),
        market_analysis_collection=_MarketAnalysisCollectionController(
            settings=settings,
            maintenance_actions=maintenance_actions,
        ),
    )


def _validate_safe_action_settings(settings: Settings) -> None:
    try:
        validate_run_settings(settings)
    except SafetyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _exchange_client(
    settings: Settings,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
) -> object:
    return create_exchange_client(settings, profile_context)


def _create_runner(
    settings: Settings,
    bot_runs: BotRunRepository,
    loan_offers: LoanOfferRepository,
    active_loans: ActiveLoanRepository,
    open_offers: OpenLoanOfferRepository,
    lending_history: LendingHistoryRepository,
    notification_state: NotificationStateRepository,
    market_analysis_rates: MarketAnalysisRateRepository,
    market_rates: MarketRateRepository,
    bot_run_decisions: BotRunDecisionRepository,
    bot_run_steps: BotRunStepRepository,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    bot_job_id: int | None = None,
) -> BotRunner:
    return create_bot_runner(
        settings,
        RunnerRepositories(
            bot_runs=bot_runs,
            loan_offers=loan_offers,
            active_loans=active_loans,
            open_offers=open_offers,
            lending_history=lending_history,
            notification_state=notification_state,
            market_analysis_rates=market_analysis_rates,
            market_rates=market_rates,
            decision_snapshots=bot_run_decisions,
            run_steps=bot_run_steps,
        ),
        profile_context=profile_context,
        bot_job_id=bot_job_id,
    )


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _require_backend_admin(authorization: str | None, request: Request) -> None:
    if _is_local_request(request):
        return

    token = admin_auth_token()
    if not token:
        raise HTTPException(status_code=403, detail="ADMIN_AUTH_TOKEN is not configured.")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Backend admin authorization is required.")


def _is_local_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        client_ip = ip_address(request.client.host)
    except ValueError:
        return False
    if client_ip.is_loopback:
        return True

    host = request.headers.get("host", "").split(":", 1)[0].lower()
    return client_ip.is_private and host in {"127.0.0.1", "localhost", "::1"}


def _validate_transfer_action_settings(settings: Settings) -> None:
    try:
        validate_transfer_settings(settings)
    except SafetyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _validate_transfer_limits(settings: Settings, transfers: list[object]) -> None:
    try:
        validate_transfer_limits(settings, transfers)
    except SafetyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _settings_bundle(
    settings: Settings,
    profile_context: BotProfileContext,
) -> RepositoryBundle:
    return create_repository_bundle(
        settings,
        profile_context=profile_context,
        settings_encryption_key=settings_encryption_key(),
    )


def _settings_values(
    settings: Settings,
    profile_context: BotProfileContext,
) -> dict[str, dict[str, object]]:
    repositories = _settings_bundle(settings, profile_context)
    values = repositories.app_settings.get_many()
    values.update(repositories.profile_app_settings.get_many(profile_context))
    for key, row in values.items():
        row["scope"] = setting_scope(key)
    return values


def _set_settings_values(
    settings: Settings,
    profile_context: BotProfileContext,
    values: dict[str, str],
    source: str,
) -> None:
    global_values = {
        key: value
        for key, value in values.items()
        if setting_scope(key) == GLOBAL_SETTING_SCOPE
    }
    profile_values = {
        key: value
        for key, value in values.items()
        if setting_scope(key) != GLOBAL_SETTING_SCOPE
    }
    repositories = _settings_bundle(settings, profile_context)
    if global_values:
        repositories.app_settings.set_many(global_values, source=source)
    if profile_values:
        repositories.profile_app_settings.set_many(profile_context, profile_values, source=source)


def _reset_setting(
    settings: Settings,
    profile_context: BotProfileContext,
    key: str,
    source: str,
) -> None:
    repositories = _settings_bundle(settings, profile_context)
    if setting_scope(key) == GLOBAL_SETTING_SCOPE:
        repositories.app_settings.reset(key, source=source)
        return
    repositories.profile_app_settings.reset(profile_context, key, source=source)


def _reset_all_settings(
    settings: Settings,
    profile_context: BotProfileContext,
    source: str,
) -> None:
    repositories = _settings_bundle(settings, profile_context)
    repositories.app_settings.reset_all(source=source)
    repositories.profile_app_settings.reset_all(profile_context, source=source)


def _settings_audit_log(
    settings: Settings,
    profile_context: BotProfileContext,
) -> list[dict[str, object]]:
    repositories = _settings_bundle(settings, profile_context)
    return (
        repositories.app_settings.audit_log()
        + repositories.profile_app_settings.audit_log(profile_context)
    )


def _settings_runtime(settings: Settings) -> dict[str, object]:
    values = _settings_values(settings, DEFAULT_PROFILE_CONTEXT)
    updated_at_values = [str(row["updated_at"]) for row in values.values() if row.get("updated_at")]
    return {
        "hot_reload": True,
        "managed_override_count": len(values),
        "last_updated_at": max(updated_at_values) if updated_at_values else None,
    }


def _live_readiness(settings: Settings) -> dict[str, object]:
    offer_items = [
        _check_item("EXCHANGE=bitfinex", settings.exchange == "bitfinex"),
        _check_item("BOT_DRY_RUN=false", not settings.dry_run),
        _check_item("ALLOW_LIVE_TRADING=true", settings.allow_live_trading),
        _check_item(
            "BITFINEX_ENABLE_LIVE_OFFERS=true",
            settings.bitfinex_enable_live_offers,
        ),
        _check_item("EXCHANGE_API_KEY is set", bool(settings.api_key)),
        _check_item("EXCHANGE_API_SECRET is set", bool(settings.api_secret)),
        _check_item(
            "MAX_TOTAL_LEND_AMOUNT is set",
            settings.max_total_lend_amount is not None,
        ),
        _check_item(
            "MAX_SINGLE_OFFER_AMOUNT is set",
            settings.max_single_offer_amount is not None,
        ),
    ]
    transfer_items = [
        _check_item("EXCHANGE=bitfinex", settings.exchange == "bitfinex"),
        _check_item("BOT_DRY_RUN=false", not settings.dry_run),
        _check_item("ALLOW_LIVE_TRADING=true", settings.allow_live_trading),
        _check_item("ALLOW_BALANCE_TRANSFERS=true", settings.allow_balance_transfers),
        _check_item(
            "BITFINEX_ENABLE_LIVE_TRANSFERS=true",
            settings.bitfinex_enable_live_transfers,
        ),
        _check_item("EXCHANGE_API_KEY is set", bool(settings.api_key)),
        _check_item("EXCHANGE_API_SECRET is set", bool(settings.api_secret)),
        _check_item(
            "MAX_TOTAL_TRANSFER_AMOUNT is set",
            settings.max_total_transfer_amount is not None,
        ),
        _check_item(
            "MAX_SINGLE_TRANSFER_AMOUNT is set",
            settings.max_single_transfer_amount is not None,
        ),
    ]
    return {
        "live_offers": _readiness_section(offer_items),
        "live_transfers": _readiness_section(transfer_items),
        "note": "API keys should not include withdrawal permissions.",
    }


def _check_item(label: str, ok: bool) -> dict[str, object]:
    return {"label": label, "ok": ok}


def _readiness_section(items: list[dict[str, object]]) -> dict[str, object]:
    missing = [str(item["label"]) for item in items if not item["ok"]]
    return {
        "ready": not missing,
        "items": items,
        "missing": missing,
    }


def _suggested_min_daily_rate(
    settings: Settings,
    market_analysis_rates: MarketAnalysisRateRepository,
    currency: str,
) -> float | None:
    if settings.market_analysis_method == "percentile":
        return market_analysis_rates.percentile_rate(
            currency,
            settings.market_analysis_percentile,
            settings.market_analysis_min_samples,
            settings.market_analysis_max_age_seconds,
        )

    if settings.market_analysis_method == "macd":
        if (
            settings.market_analysis_macd_short_seconds > 0
            and settings.market_analysis_macd_long_seconds > 0
        ):
            return market_analysis_rates.macd_rate_by_seconds(
                currency,
                settings.market_analysis_macd_short_seconds,
                settings.market_analysis_macd_long_seconds,
                settings.market_analysis_multiplier,
                settings.market_analysis_min_samples,
                settings.market_analysis_max_age_seconds,
            )

        return market_analysis_rates.macd_rate(
            currency,
            settings.market_analysis_macd_short_samples,
            settings.market_analysis_macd_long_samples,
            settings.market_analysis_multiplier,
            settings.market_analysis_min_samples,
            settings.market_analysis_max_age_seconds,
        )

    return None


def _market_analysis_status(
    settings: Settings,
    market_analysis_rates: MarketAnalysisRateRepository,
) -> list[dict[str, object]]:
    stats_by_currency = market_analysis_rates.stats_by_currency(
        settings.market_analysis_max_age_seconds
    )
    currencies = sorted(
        {
            settings.smoke_test_currency.upper(),
            *settings.market_analysis_currencies,
            *(currency.upper() for currency in stats_by_currency),
        }
    )
    rows = []
    for currency in currencies:
        stats = stats_by_currency.get(currency, {})
        sample_count = int(stats.get("sample_count") or 0)
        top_level_sample_count = int(stats.get("top_level_sample_count") or 0)
        suggested_min_daily_rate = _suggested_min_daily_rate(
            settings,
            market_analysis_rates,
            currency,
        )
        has_enough_samples = sample_count >= max(settings.market_analysis_min_samples, 1)
        is_stale = bool(stats.get("is_stale")) if stats else False
        rows.append(
            {
                "currency": currency,
                "method": settings.market_analysis_method,
                "sample_count": sample_count,
                "top_level_sample_count": top_level_sample_count,
                "min_samples": settings.market_analysis_min_samples,
                "max_age_seconds": settings.market_analysis_max_age_seconds,
                "latest_captured_at": stats.get("latest_captured_at"),
                "is_stale": is_stale,
                "has_enough_samples": has_enough_samples,
                "suggested_min_daily_rate": suggested_min_daily_rate,
                "reason": _market_analysis_status_reason(
                    settings.market_analysis_method,
                    sample_count,
                    has_enough_samples,
                    is_stale,
                    suggested_min_daily_rate,
                ),
            }
        )
    return rows


def _market_analysis_status_reason(
    method: str,
    sample_count: int,
    has_enough_samples: bool,
    is_stale: bool,
    suggested_min_daily_rate: float | None,
) -> str:
    if method == "off":
        return "Market analysis is disabled."
    if sample_count == 0:
        return "No market analysis samples have been recorded."
    if is_stale:
        return "Latest market analysis sample is older than the configured max age."
    if not has_enough_samples:
        return "Not enough samples to calculate a suggestion."
    if suggested_min_daily_rate is None:
        return "No suggested rate is available for the configured method."
    return "Market analysis suggestion is available."


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


def _strategy_decisions(
    settings: Settings,
    active_loans: ActiveLoanRepository,
    open_offers: OpenLoanOfferRepository,
    market_analysis_rates: MarketAnalysisRateRepository,
) -> list[dict[str, object]]:
    exchange = _exchange_client(settings)
    errors: dict[str, str] = {}
    balances = _safe_lending_balances(exchange, errors)
    active = _safe_active_loans(exchange, active_loans, errors)
    open_offer_rows = open_offers.recent(1000)
    currencies = _strategy_decision_currencies(settings, balances, active, open_offer_rows)

    rows = []
    for currency in currencies:
        strategy = strategy_config_for(settings, currency)
        balance = next(
            (item for item in balances if item.currency.upper() == currency),
            CurrencyBalance(currency=currency, amount=0.0),
        )
        active_amount = sum(
            item.amount for item in active if item.currency.upper() == currency
        )
        open_offer_amount = sum(
            float(row["amount"])
            for row in open_offer_rows
            if str(row["currency"]).upper() == currency
        )
        order_book = _safe_loan_orders(exchange, currency, errors)
        best_market_rate = max((order.daily_rate for order in order_book), default=0.0)
        suggested_min_daily_rate = _suggested_min_daily_rate(
            settings,
            market_analysis_rates,
            currency,
        )
        frr_daily_rate = _safe_frr_rate(exchange, currency, strategy.frr_as_min, errors)
        btc_price = (
            _safe_btc_price(exchange, currency)
            if _uses_raw_btc_gap(strategy.gap_mode)
            else None
        )
        decision = build_lending_decision(
            balance=balance,
            order_book=order_book,
            strategy=strategy,
            frr_daily_rate=frr_daily_rate,
            btc_price=btc_price,
            suggested_min_daily_rate=suggested_min_daily_rate,
            active_amount=active_amount,
            historical_daily_rates=_historical_daily_rates(
                settings,
                market_analysis_rates,
                currency,
            ),
        )

        rows.append(
            {
                "currency": currency,
                "balance": balance.amount,
                "active_amount": active_amount,
                "open_offer_amount": open_offer_amount,
                "best_market_rate": best_market_rate,
                "configured_min_daily_rate": strategy.min_daily_rate,
                "suggested_min_daily_rate": suggested_min_daily_rate,
                "effective_min_daily_rate": max(
                    strategy.min_daily_rate,
                    suggested_min_daily_rate or 0,
                    frr_daily_rate + strategy.frr_delta if frr_daily_rate is not None else 0,
                ),
                "max_daily_rate": strategy.max_daily_rate,
                "max_to_lend": strategy.max_amount_to_lend,
                "max_percent_to_lend": strategy.max_percent_to_lend,
                "max_active_amount": strategy.max_active_amount,
                "offer_count": len(decision.offers),
                "offers": [offer.__dict__ for offer in decision.offers],
                "reason": errors.get(currency, errors.get("*", decision.reason)),
            }
        )

    return rows


def _safe_lending_balances(exchange, errors: dict[str, str]) -> list[CurrencyBalance]:
    try:
        return exchange.get_lending_balances()
    except Exception as error:
        errors["*"] = f"Unable to load lending balances: {error}"
        return []


def _safe_active_loans(
    exchange,
    active_loans: ActiveLoanRepository,
    errors: dict[str, str],
) -> list[ActiveLoan]:
    try:
        return exchange.get_active_loans()
    except Exception as error:
        errors["*"] = f"Unable to load active loans: {error}"
        rows = active_loans.recent(1000)
        return [
            ActiveLoan(
                currency=str(row["currency"]),
                amount=float(row["amount"]),
                daily_rate=float(row["daily_rate"]),
                duration_days=int(row["duration_days"]),
                external_loan_id=str(row["external_loan_id"] or ""),
            )
            for row in rows
        ]


def _safe_loan_orders(exchange, currency: str, errors: dict[str, str]) -> list[LoanOrder]:
    try:
        return exchange.get_loan_orders(currency)
    except Exception as error:
        errors[currency] = f"Unable to load loan orders: {error}"
        return []


def _safe_frr_rate(
    exchange,
    currency: str,
    frr_as_min: bool,
    errors: dict[str, str],
) -> float | None:
    if not frr_as_min:
        return None
    try:
        return exchange.get_frr_rate(currency)
    except Exception as error:
        errors[currency] = f"Unable to load FRR rate: {error}"
        return None


def _historical_daily_rates(
    settings: Settings,
    market_analysis_rates: MarketAnalysisRateRepository,
    currency: str,
) -> list[float]:
    if settings.rate_optimization_mode != "fill_probability":
        return []

    return market_analysis_rates.recent_top_level_rates(
        currency,
        settings.rate_optimization_sample_size,
        settings.market_analysis_max_age_seconds,
    )


def _strategy_decision_currencies(
    settings: Settings,
    balances: list[CurrencyBalance],
    active_loans: list[ActiveLoan],
    open_offer_rows: list[dict[str, object]],
) -> list[str]:
    currencies = {
        settings.smoke_test_currency.upper(),
        *(balance.currency.upper() for balance in balances),
        *(loan.currency.upper() for loan in active_loans),
        *(str(row["currency"]).upper() for row in open_offer_rows),
        *settings.market_analysis_currencies,
    }
    return sorted(currency for currency in currencies if currency)


def _uses_raw_btc_gap(gap_mode: str) -> bool:
    return gap_mode.lower().replace("-", "_") in {"raw_btc", "rawbtc"}


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
                "dry_run": int(row.get("dry_run", 0)),
                "source": row.get("source", "exchange"),
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
