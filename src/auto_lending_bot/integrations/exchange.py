from typing import Protocol

from auto_lending_bot.domain.models import ActiveLoan, CurrencyBalance, LoanOffer, LoanOrder


class ExchangeClient(Protocol):
    def get_lending_balances(self) -> list[CurrencyBalance]:
        pass

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        pass

    def get_open_loan_offers(self) -> list[LoanOffer]:
        pass

    def get_active_loans(self) -> list[ActiveLoan]:
        pass

    def create_loan_offer(self, offer: LoanOffer) -> str:
        pass

    def cancel_loan_offer(self, offer_id: str) -> None:
        pass
