from auto_lending_bot.domain.models import CurrencyBalance, LoanOrder
from auto_lending_bot.domain.strategy import build_lending_decision


def test_strategy_rejects_balance_below_minimum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=0.001),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        min_daily_rate=0.00005,
        min_loan_size=0.01,
        spread_lend=3,
    )

    assert decision.should_lend is False
    assert decision.reason == "Available balance is below the minimum loan size."


def test_strategy_rejects_rate_below_minimum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USDT", amount=100.0),
        order_book=[LoanOrder(currency="USDT", amount=1000.0, daily_rate=0.00004)],
        min_daily_rate=0.00005,
        min_loan_size=0.01,
        spread_lend=3,
    )

    assert decision.should_lend is False
    assert decision.reason == "Best daily rate is below the configured minimum."


def test_strategy_splits_balance_into_offers() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="ETH", amount=2.0),
        order_book=[LoanOrder(currency="ETH", amount=4.0, daily_rate=0.00006)],
        min_daily_rate=0.00005,
        min_loan_size=0.01,
        spread_lend=3,
    )

    assert decision.should_lend is True
    assert len(decision.offers) == 3
    assert sum(offer.amount for offer in decision.offers) == 2.0
    assert {offer.daily_rate for offer in decision.offers} == {0.00006}
