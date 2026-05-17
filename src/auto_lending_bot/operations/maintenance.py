from auto_lending_bot.config import Settings
from auto_lending_bot.market.analysis_recorder import MarketAnalysisRecorder
from auto_lending_bot.persistence.factory import RepositoryBundle
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile


class MaintenanceActionService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryBundle,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        self._settings = settings
        self._repositories = repositories
        self._profile_context = profile_context

    def cleanup_market_data(self) -> dict[str, object]:
        market_rate_deleted_count = self._repositories.market_rates.delete_older_than_days(
            self._settings.market_rate_retention_days,
            profile_context=self._profile_context,
        )
        market_analysis_deleted_count = (
            self._repositories.market_analysis_rates.delete_older_than_days(
                self._settings.market_analysis_retention_days,
                profile_context=self._profile_context,
            )
        )
        return {
            "action": "cleanup",
            "ok": True,
            "deleted_count": market_rate_deleted_count + market_analysis_deleted_count,
            "market_rate_deleted_count": market_rate_deleted_count,
            "market_analysis_deleted_count": market_analysis_deleted_count,
        }

    def sync_history(self, exchange) -> dict[str, object]:
        entries = exchange.get_lending_history(self._settings.smoke_test_currency)
        history_source = self._settings.exchange.lower()
        history_dry_run = history_source == "mock"
        changed_count = self._repositories.lending_history.upsert_many(
            entries,
            dry_run=history_dry_run,
            source=history_source,
            profile_context=self._profile_context,
        )
        return {
            "action": "sync-history",
            "ok": True,
            "currency": self._settings.smoke_test_currency.upper(),
            "dry_run": history_dry_run,
            "source": history_source,
            "changed_count": changed_count,
        }

    def sync_open_offers(self, exchange) -> dict[str, object]:
        offers = exchange.get_open_loan_offers()
        self._repositories.open_offers.replace_all(offers, profile_context=self._profile_context)
        return {
            "action": "sync-open-offers",
            "ok": True,
            "changed_count": len(offers),
        }

    def record_market_analysis(
        self,
        exchange,
        currency: str | None = None,
        levels: int | None = None,
    ) -> dict[str, object]:
        currencies = self._market_analysis_currencies(currency)
        resolved_levels = levels or self._settings.market_analysis_levels
        recorder = MarketAnalysisRecorder(
            self._repositories.market_analysis_rates,
            profile_context=self._profile_context,
        )
        changed_count = sum(
            recorder.record_currency(
                exchange=exchange,
                currency=currency,
                levels=resolved_levels,
            )
            for currency in currencies
        )
        return {
            "action": "record-market-analysis",
            "ok": True,
            "currency": currencies[0],
            "currencies": list(currencies),
            "changed_count": changed_count,
        }

    def _market_analysis_currencies(self, currency: str | None = None) -> tuple[str, ...]:
        if currency:
            return (currency.upper(),)
        if self._settings.market_analysis_currencies:
            return self._settings.market_analysis_currencies
        return (self._settings.smoke_test_currency.upper(),)
