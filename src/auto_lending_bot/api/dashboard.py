from dataclasses import dataclass

from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunDecisionRepository,
    BotRunRepository,
    BotRunStepRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
)
from auto_lending_bot.profiles import (
    DEFAULT_PROFILE_CONTEXT,
    BotProfileContext,
    ensure_default_profile,
)


@dataclass(frozen=True)
class DashboardRepositories:
    bot_runs: BotRunRepository
    loan_offers: LoanOfferRepository
    open_offers: OpenLoanOfferRepository
    active_loans: ActiveLoanRepository
    lending_history: LendingHistoryRepository
    market_rates: MarketRateRepository
    market_analysis_rates: MarketAnalysisRateRepository
    run_decisions: BotRunDecisionRepository
    run_steps: BotRunStepRepository


class DashboardReadService:
    def __init__(
        self,
        repositories: DashboardRepositories,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        self._repositories = repositories
        self._profile_context = profile_context

    @property
    def profile_context(self) -> BotProfileContext:
        return self._profile_context

    def counts(self) -> dict[str, int]:
        return {
            "bot_runs": self._repositories.bot_runs.count(),
            "loan_offers": self._repositories.loan_offers.count(),
            "open_loan_offers": self._repositories.open_offers.count(),
            "active_loans": self._repositories.active_loans.count(),
            "lending_history": self._repositories.lending_history.count(),
            "market_rates": self._repositories.market_rates.count(),
            "market_analysis_rates": self._repositories.market_analysis_rates.count(),
        }

    def latest_run(self) -> dict[str, object] | None:
        return self._repositories.bot_runs.latest()

    def recent_runs(self) -> list[dict[str, object]]:
        return self._repositories.bot_runs.recent()

    def run_decisions(self, bot_run_id: int) -> list[dict[str, object]]:
        return self._repositories.run_decisions.for_run(bot_run_id)

    def run_steps(self, bot_run_id: int) -> list[dict[str, object]]:
        return self._repositories.run_steps.for_run(bot_run_id)

    def recent_offers(self) -> list[dict[str, object]]:
        return self._repositories.loan_offers.recent()

    def recent_open_offers(self, limit: int | None = None) -> list[dict[str, object]]:
        if limit is None:
            return self._repositories.open_offers.recent()
        return self._repositories.open_offers.recent(limit)

    def recent_active_loans(self, limit: int | None = None) -> list[dict[str, object]]:
        if limit is None:
            return self._repositories.active_loans.recent()
        return self._repositories.active_loans.recent(limit)

    def recent_lending_history(self) -> list[dict[str, object]]:
        return self._repositories.lending_history.recent()

    def earnings_summary_by_currency(self) -> list[dict[str, object]]:
        return self._repositories.lending_history.earnings_summary_by_currency()

    def recent_market_rates(self, limit: int | None = None) -> list[dict[str, object]]:
        if limit is None:
            return self._repositories.market_rates.recent()
        return self._repositories.market_rates.recent(limit)

    def recent_market_analysis_rates(self) -> list[dict[str, object]]:
        return self._repositories.market_analysis_rates.recent()
