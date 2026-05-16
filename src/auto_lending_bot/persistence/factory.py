from dataclasses import dataclass

from auto_lending_bot.config import Settings
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    AppSettingRepository,
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
from auto_lending_bot.profiles import (
    DEFAULT_PROFILE_CONTEXT,
    BotProfileContext,
    ensure_default_profile,
)


@dataclass(frozen=True)
class RepositoryBundle:
    bot_runs: BotRunRepository
    loan_offers: LoanOfferRepository
    active_loans: ActiveLoanRepository
    open_offers: OpenLoanOfferRepository
    lending_history: LendingHistoryRepository
    notification_state: NotificationStateRepository
    market_analysis_rates: MarketAnalysisRateRepository
    market_rates: MarketRateRepository
    bot_run_decisions: BotRunDecisionRepository
    bot_run_steps: BotRunStepRepository
    app_settings: AppSettingRepository
    profile_app_settings: ProfileAppSettingRepository


def create_repository_bundle(
    settings: Settings,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    settings_encryption_key: str = "",
) -> RepositoryBundle:
    ensure_default_profile(profile_context)
    database_url = settings.database_url
    return RepositoryBundle(
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_rates=MarketRateRepository(database_url),
        bot_run_decisions=BotRunDecisionRepository(database_url),
        bot_run_steps=BotRunStepRepository(database_url),
        app_settings=AppSettingRepository(
            database_url,
            encryption_key=settings_encryption_key,
        ),
        profile_app_settings=ProfileAppSettingRepository(
            database_url,
            encryption_key=settings_encryption_key,
        ),
    )
