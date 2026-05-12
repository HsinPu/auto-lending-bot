from auto_lending_bot.domain.models import CurrencyBalance, LoanOrder
from auto_lending_bot.domain.strategy import StrategyConfig, build_lending_decision


def test_strategy_rejects_balance_below_minimum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=0.001),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(),
    )

    assert decision.should_lend is False
    assert decision.reason == "Available balance is below the minimum loan size."


def test_strategy_rejects_rate_below_minimum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USDT", amount=100.0),
        order_book=[LoanOrder(currency="USDT", amount=1000.0, daily_rate=0.00004)],
        strategy=_strategy(),
    )

    assert decision.should_lend is False
    assert decision.reason == "Best daily rate is below the configured minimum."


def test_strategy_splits_balance_into_offers() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="ETH", amount=2.0),
        order_book=[LoanOrder(currency="ETH", amount=4.0, daily_rate=0.00006)],
        strategy=_strategy(),
    )

    assert decision.should_lend is True
    assert len(decision.offers) == 3
    assert sum(offer.amount for offer in decision.offers) == 2.0
    assert {offer.daily_rate for offer in decision.offers} == {0.00006}


def test_strategy_caps_rate_at_configured_maximum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.1)],
        strategy=_strategy(max_daily_rate=0.05),
    )

    assert {offer.daily_rate for offer in decision.offers} == {0.05}


def test_strategy_limits_lendable_amount_by_percent() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_percent_to_lend=50),
    )

    assert sum(offer.amount for offer in decision.offers) == 5.0


def test_strategy_limits_lendable_amount_by_max_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_amount_to_lend=2.0),
    )

    assert sum(offer.amount for offer in decision.offers) == 2.0


def test_strategy_uses_min_rate_when_hide_coins_is_disabled() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00004)],
        strategy=_strategy(hide_coins=False),
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00005}


def _strategy(
    min_daily_rate: float = 0.00005,
    max_daily_rate: float = 0.05,
    min_loan_size: float = 0.01,
    spread_lend: int = 3,
    max_percent_to_lend: float = 100,
    max_amount_to_lend: float | None = None,
    hide_coins: bool = True,
) -> StrategyConfig:
    return StrategyConfig(
        min_daily_rate=min_daily_rate,
        max_daily_rate=max_daily_rate,
        min_loan_size=min_loan_size,
        spread_lend=spread_lend,
        max_percent_to_lend=max_percent_to_lend,
        max_amount_to_lend=max_amount_to_lend,
        hide_coins=hide_coins,
    )
