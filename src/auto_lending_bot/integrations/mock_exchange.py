from auto_lending_bot.domain.models import CurrencyBalance, LoanOffer, LoanOrder


class MockExchangeClient:
    def __init__(self) -> None:
        self._created_offers: list[LoanOffer] = []

    def get_lending_balances(self) -> list[CurrencyBalance]:
        return [
            CurrencyBalance(currency="BTC", amount=0.25),
            CurrencyBalance(currency="ETH", amount=2.0),
            CurrencyBalance(currency="USDT", amount=500.0),
        ]

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        order_books = {
            "BTC": [LoanOrder(currency="BTC", amount=0.5, daily_rate=0.00008)],
            "ETH": [LoanOrder(currency="ETH", amount=4.0, daily_rate=0.00006)],
            "USDT": [LoanOrder(currency="USDT", amount=1000.0, daily_rate=0.00004)],
        }
        return order_books.get(currency, [])

    def get_open_loan_offers(self) -> list[LoanOffer]:
        return list(self._created_offers)

    def create_loan_offer(self, offer: LoanOffer) -> str:
        self._created_offers.append(offer)
        return f"mock-{len(self._created_offers)}"

    def cancel_loan_offer(self, offer_id: str) -> None:
        return None


def create_exchange_client(exchange: str) -> MockExchangeClient:
    if exchange != "mock":
        msg = "Only the mock exchange is supported in phase one."
        raise ValueError(msg)

    return MockExchangeClient()
