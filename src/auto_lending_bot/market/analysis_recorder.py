from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.persistence.repository import MarketAnalysisRateRepository
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext


class MarketAnalysisRecorder:
    def __init__(
        self,
        repository: MarketAnalysisRateRepository,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        self._repository = repository
        self._profile_context = profile_context

    def record_currency(
        self,
        exchange: ExchangeClient,
        currency: str,
        levels: int,
    ) -> int:
        orders = exchange.get_loan_orders(currency.upper())[:levels]
        return self._repository.add_many(orders, profile_context=self._profile_context)
