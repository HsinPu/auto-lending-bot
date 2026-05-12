import pytest

from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient, create_exchange_client


def test_mock_exchange_returns_balances() -> None:
    exchange = MockExchangeClient()

    balances = exchange.get_lending_balances()

    assert [balance.currency for balance in balances] == ["BTC", "ETH", "USDT"]


def test_mock_exchange_records_created_offers() -> None:
    exchange = MockExchangeClient()
    offer = LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2)

    offer_id = exchange.create_loan_offer(offer)

    assert offer_id == "mock-1"
    assert exchange.get_open_loan_offers() == [offer]


def test_create_exchange_client_rejects_non_mock_exchange() -> None:
    with pytest.raises(ValueError, match="Only the mock exchange"):
        create_exchange_client("poloniex")
