from collections.abc import Callable
from dataclasses import dataclass
from inspect import Parameter, signature

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
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


ExchangeFactory = (
    Callable[[Settings], ExchangeClient]
    | Callable[[Settings, BotProfileContext], ExchangeClient]
)


@dataclass(frozen=True)
class RunnerRepositories:
    bot_runs: BotRunRepository
    loan_offers: LoanOfferRepository
    active_loans: ActiveLoanRepository
    open_offers: OpenLoanOfferRepository
    lending_history: LendingHistoryRepository
    notification_state: NotificationStateRepository
    market_analysis_rates: MarketAnalysisRateRepository
    market_rates: MarketRateRepository
    decision_snapshots: BotRunDecisionRepository
    run_steps: BotRunStepRepository


def create_bot_runner(
    settings: Settings,
    repositories: RunnerRepositories,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    exchange_factory: ExchangeFactory = create_exchange_client,
) -> BotRunner:
    return BotRunner(
        settings=settings,
        exchange=_create_exchange(exchange_factory, settings, profile_context),
        bot_runs=repositories.bot_runs,
        loan_offers=repositories.loan_offers,
        active_loans=repositories.active_loans,
        open_offers=repositories.open_offers,
        lending_history=repositories.lending_history,
        notification_state=repositories.notification_state,
        market_analysis_rates=repositories.market_analysis_rates,
        market_recorder=MarketRecorder(repositories.market_rates),
        notifier=Notifier(settings=settings),
        decision_snapshots=repositories.decision_snapshots,
        run_steps=repositories.run_steps,
    )


def create_default_bot_runner(
    settings: Settings,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    exchange_factory: ExchangeFactory = create_exchange_client,
) -> BotRunner:
    return create_bot_runner(
        settings,
        default_runner_repositories(settings),
        profile_context=profile_context,
        exchange_factory=exchange_factory,
    )


def default_runner_repositories(settings: Settings) -> RunnerRepositories:
    database_url = settings.database_url
    return RunnerRepositories(
        bot_runs=BotRunRepository(database_url),
        loan_offers=LoanOfferRepository(database_url),
        active_loans=ActiveLoanRepository(database_url),
        open_offers=OpenLoanOfferRepository(database_url),
        lending_history=LendingHistoryRepository(database_url),
        notification_state=NotificationStateRepository(database_url),
        market_analysis_rates=MarketAnalysisRateRepository(database_url),
        market_rates=MarketRateRepository(database_url),
        decision_snapshots=BotRunDecisionRepository(database_url),
        run_steps=BotRunStepRepository(database_url),
    )


def _create_exchange(
    exchange_factory: ExchangeFactory,
    settings: Settings,
    profile_context: BotProfileContext,
) -> ExchangeClient:
    parameters = list(signature(exchange_factory).parameters.values())
    accepts_profile_context = any(
        parameter.kind == Parameter.VAR_POSITIONAL for parameter in parameters
    ) or sum(
        1
        for parameter in parameters
        if parameter.kind
        in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}
    ) > 1
    if accepts_profile_context:
        return exchange_factory(settings, profile_context)  # type: ignore[misc]
    return exchange_factory(settings)  # type: ignore[misc]
