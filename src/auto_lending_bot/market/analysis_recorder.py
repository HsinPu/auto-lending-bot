from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.persistence.repository import MarketAnalysisRateRepository


class MarketAnalysisRecorder:
    def __init__(self, repository: MarketAnalysisRateRepository) -> None:
        self._repository = repository

    def record_currency(
        self,
        exchange: ExchangeClient,
        currency: str,
        levels: int,
    ) -> int:
        orders = exchange.get_loan_orders(currency.upper())[:levels]
        return self._repository.add_many(orders)
