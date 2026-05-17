from auto_lending_bot.domain.models import LoanOrder
from auto_lending_bot.persistence.repository import MarketRateRepository
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext


class MarketRecorder:
    def __init__(
        self,
        repository: MarketRateRepository,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        self._repository = repository
        self._profile_context = profile_context

    def record_orders(self, orders: list[LoanOrder]) -> None:
        for order in orders:
            self._repository.add(order, profile_context=self._profile_context)
