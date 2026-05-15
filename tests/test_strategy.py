from datetime import date, timedelta

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


def test_strategy_does_not_limit_lendable_amount_above_max_to_lend_rate() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_percent_to_lend=50, max_to_lend_rate=0.00008),
    )

    assert sum(offer.amount for offer in decision.offers) == 10.0


def test_strategy_limits_lendable_amount_at_or_below_max_to_lend_rate() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008)],
        strategy=_strategy(max_percent_to_lend=50, max_to_lend_rate=0.00008),
    )

    assert sum(offer.amount for offer in decision.offers) == 5.0


def test_strategy_limits_lendable_amount_by_max_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_amount_to_lend=2.0),
    )

    assert sum(offer.amount for offer in decision.offers) == 2.0


def test_strategy_limits_lendable_amount_by_active_amount_cap() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_active_amount=2.0),
        active_amount=1.25,
    )

    assert sum(offer.amount for offer in decision.offers) == 0.75


def test_strategy_stops_when_active_amount_reaches_cap() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(max_active_amount=2.0),
        active_amount=2.0,
    )

    assert decision.should_lend is False
    assert decision.reason == "Active lending amount is at or above the configured maximum."


def test_strategy_does_not_create_split_offers_below_min_loan_size() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=0.02999999),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(min_loan_size=0.01, spread_lend=3),
    )

    assert decision.should_lend is True
    assert len(decision.offers) == 2
    assert all(offer.amount >= 0.01 for offer in decision.offers)


def test_strategy_uses_currency_specific_min_loan_size() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=0.015),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001)],
        strategy=_strategy(min_loan_size=0.02),
    )

    assert decision.should_lend is False
    assert decision.reason == "Available balance is below the minimum loan size."


def test_strategy_uses_min_rate_when_hide_coins_is_disabled() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00004)],
        strategy=_strategy(hide_coins=False),
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00005}


def test_strategy_uses_frr_as_effective_minimum() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00008)],
        strategy=_strategy(hide_coins=False, frr_as_min=True, frr_delta=0.00001),
        frr_daily_rate=0.0001,
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00011}


def test_strategy_uses_suggested_minimum_when_higher() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00012)],
        strategy=_strategy(hide_coins=False),
        suggested_min_daily_rate=0.0001,
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00012}


def test_strategy_keeps_configured_minimum_when_frr_is_lower() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00004)],
        strategy=_strategy(hide_coins=False, frr_as_min=True),
        frr_daily_rate=0.00003,
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00005}


def test_strategy_spreads_rates_by_raw_gap_depth() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=3.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00005),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00007),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00009),
        ],
        strategy=_strategy(gap_mode="raw", gap_bottom=1, gap_top=3),
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.00005, 0.00007, 0.00009]


def test_strategy_spreads_rates_by_relative_gap_depth() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=10.0),
        order_book=[
            LoanOrder(currency="BTC", amount=2.0, daily_rate=0.00005),
            LoanOrder(currency="BTC", amount=3.0, daily_rate=0.00008),
        ],
        strategy=_strategy(spread_lend=2, gap_mode="relative", gap_bottom=20, gap_top=50),
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.00005, 0.00008]


def test_strategy_spreads_rates_by_raw_btc_gap_depth() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="ETH", amount=3.0),
        order_book=[
            LoanOrder(currency="ETH", amount=1.0, daily_rate=0.00005),
            LoanOrder(currency="ETH", amount=1.0, daily_rate=0.00007),
            LoanOrder(currency="ETH", amount=1.0, daily_rate=0.00009),
        ],
        strategy=_strategy(gap_mode="raw_btc", gap_bottom=1, gap_top=1.5),
        btc_price=0.5,
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.00007, 0.00008, 0.00009]


def test_strategy_optimizes_rate_by_fill_probability() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0002),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=1,
            rate_optimization_mode="fill_probability",
            rate_optimization_min_probability=0.25,
        ),
        historical_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0003]


def test_strategy_falls_back_to_gap_rates_without_probability_samples() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=2.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00005),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00009),
        ],
        strategy=_strategy(spread_lend=2, gap_mode="raw", gap_bottom=1, gap_top=2, rate_optimization_mode="fill_probability"),
        historical_daily_rates=[],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.00005, 0.00009]


def test_strategy_uses_long_duration_above_xday_threshold() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.001)],
        strategy=_strategy(xday_threshold=0.001, xdays=30),
    )

    assert {offer.duration_days for offer in decision.offers} == {30}


def test_strategy_linearly_increases_duration_with_xday_spread() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00075)],
        strategy=_strategy(xday_threshold=0.001, xdays=30, xday_spread=2),
    )

    assert {offer.duration_days for offer in decision.offers} == {16}


def test_strategy_caps_duration_at_end_date() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.001)],
        strategy=_strategy(xday_threshold=0.001, xdays=30, end_date=date.today() + timedelta(days=10)),
    )

    assert {offer.duration_days for offer in decision.offers} == {10}


def test_strategy_stops_when_end_date_is_too_close() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.001)],
        strategy=_strategy(end_date=date.today() + timedelta(days=2)),
    )

    assert decision.should_lend is False
    assert decision.reason == "End date is too close to create new lending offers."


def _strategy(
    min_daily_rate: float = 0.00005,
    max_daily_rate: float = 0.05,
    min_loan_size: float = 0.01,
    spread_lend: int = 3,
    gap_mode: str = "off",
    gap_bottom: float = 0,
    gap_top: float = 0,
    xday_threshold: float = 0,
    xdays: int = 2,
    xday_spread: float = 0,
    frr_as_min: bool = False,
    frr_delta: float = 0,
    rate_optimization_mode: str = "off",
    rate_optimization_min_probability: float = 0.25,
    rate_optimization_sample_size: int = 200,
    max_percent_to_lend: float = 100,
    max_amount_to_lend: float | None = None,
    max_active_amount: float | None = None,
    max_to_lend_rate: float = 0,
    end_date: date | None = None,
    hide_coins: bool = True,
) -> StrategyConfig:
    return StrategyConfig(
        min_daily_rate=min_daily_rate,
        max_daily_rate=max_daily_rate,
        min_loan_size=min_loan_size,
        spread_lend=spread_lend,
        gap_mode=gap_mode,
        gap_bottom=gap_bottom,
        gap_top=gap_top,
        xday_threshold=xday_threshold,
        xdays=xdays,
        xday_spread=xday_spread,
        frr_as_min=frr_as_min,
        frr_delta=frr_delta,
        rate_optimization_mode=rate_optimization_mode,
        rate_optimization_min_probability=rate_optimization_min_probability,
        rate_optimization_sample_size=rate_optimization_sample_size,
        max_percent_to_lend=max_percent_to_lend,
        max_amount_to_lend=max_amount_to_lend,
        max_active_amount=max_active_amount,
        max_to_lend_rate=max_to_lend_rate,
        end_date=end_date,
        hide_coins=hide_coins,
    )
