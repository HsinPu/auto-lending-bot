from auto_lending_bot.domain.models import LoanOrder
from auto_lending_bot.persistence.repository import MarketRateRepository


class MarketRecorder:
    def __init__(self, repository: MarketRateRepository) -> None:
        self._repository = repository

    def record_orders(self, orders: list[LoanOrder]) -> None:
        for order in orders:
            self._repository.add(order)
