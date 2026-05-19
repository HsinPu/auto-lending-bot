from datetime import date, timedelta

from auto_lending_bot.domain.models import CurrencyBalance, FillOutcome, LoanOrder
from auto_lending_bot.domain.strategy import (
    StrategyConfig,
    _regime_adjusted_duration_days,
    build_lending_decision,
    detect_market_regime,
)


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
        strategy=_strategy(allow_above_market_offers=False),
    )

    assert decision.should_lend is False
    assert decision.reason == "Best daily rate is below the configured minimum."


def test_strategy_creates_minimum_rate_offers_below_market_by_default() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USDT", amount=100.0),
        order_book=[LoanOrder(currency="USDT", amount=1000.0, daily_rate=0.00004)],
        strategy=_strategy(min_daily_rate=0.00005),
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00005}
    assert decision.reason == "Created minimum-rate offers while market is below the configured minimum."


def test_strategy_uses_minimum_rate_below_market_even_with_high_historical_samples() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USDT", amount=100.0),
        order_book=[LoanOrder(currency="USDT", amount=1000.0, daily_rate=0.00004)],
        strategy=_strategy(
            min_daily_rate=0.00005,
            rate_optimization_mode="fill_probability",
            max_daily_rate=0.05,
        ),
        historical_daily_rates=[0.2],
    )

    assert decision.should_lend is True
    assert {offer.daily_rate for offer in decision.offers} == {0.00005}


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


def test_strategy_splits_by_max_offer_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USD", amount=10000.0),
        order_book=[LoanOrder(currency="USD", amount=10000.0, daily_rate=0.0001)],
        strategy=_strategy(max_offer_amount=500, min_offer_remainder=100),
    )

    assert len(decision.offers) == 20
    assert {offer.amount for offer in decision.offers} == {500}


def test_strategy_drops_small_remainder_when_splitting_by_max_offer_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USD", amount=1095.75),
        order_book=[LoanOrder(currency="USD", amount=10000.0, daily_rate=0.0001)],
        strategy=_strategy(max_offer_amount=500, min_offer_remainder=100),
    )

    assert [offer.amount for offer in decision.offers] == [500, 500]


def test_strategy_keeps_large_remainder_when_splitting_by_max_offer_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USD", amount=1150.0),
        order_book=[LoanOrder(currency="USD", amount=10000.0, daily_rate=0.0001)],
        strategy=_strategy(max_offer_amount=500, min_offer_remainder=100),
    )

    assert [offer.amount for offer in decision.offers] == [500, 500, 150]


def test_strategy_keeps_single_offer_below_max_offer_amount() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USD", amount=480.0),
        order_book=[LoanOrder(currency="USD", amount=10000.0, daily_rate=0.0001)],
        strategy=_strategy(max_offer_amount=500, min_offer_remainder=100),
    )

    assert [offer.amount for offer in decision.offers] == [480]


def test_strategy_uses_spread_lend_when_max_offer_amount_is_disabled() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="USD", amount=10000.0),
        order_book=[LoanOrder(currency="USD", amount=10000.0, daily_rate=0.0001)],
        strategy=_strategy(spread_lend=3, max_offer_amount=None),
    )

    assert len(decision.offers) == 3
    assert sum(offer.amount for offer in decision.offers) == 10000.0


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
    assert [candidate.daily_rate for candidate in decision.rate_candidates] == [0.0001, 0.0002, 0.0003]
    assert [candidate.fill_probability for candidate in decision.rate_candidates] == [1.0, 0.6, 0.6]
    assert [candidate.selected for candidate in decision.rate_candidates] == [False, False, True]
    assert [candidate.selection_role for candidate in decision.rate_candidates] == ["", "", "expected"]


def test_strategy_blends_actual_fill_outcomes_into_probability() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=1,
            rate_optimization_mode="fill_probability",
            rate_optimization_min_probability=0.10,
        ),
        historical_daily_rates=[0.0003, 0.0003],
        fill_outcomes=[
            *[FillOutcome(daily_rate=0.0001, filled=True) for _ in range(8)],
            *[FillOutcome(daily_rate=0.0003, filled=False) for _ in range(8)],
        ],
    )

    candidates = {candidate.daily_rate: candidate for candidate in decision.rate_candidates}
    assert [offer.daily_rate for offer in decision.offers] == [0.0001]
    assert candidates[0.0001].fill_probability == 1.0
    assert candidates[0.0003].fill_probability == 0.2
    assert candidates[0.0003].meets_min_probability is False


def test_strategy_can_optimize_from_fill_outcomes_without_market_samples() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=1,
            rate_optimization_mode="fill_probability",
            rate_optimization_min_probability=0.10,
        ),
        historical_daily_rates=[],
        fill_outcomes=[
            FillOutcome(daily_rate=0.0001, filled=True),
            FillOutcome(daily_rate=0.0003, filled=False),
        ],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0001]
    assert [candidate.source for candidate in decision.rate_candidates] == [
        "fill_outcome+order_book",
        "fill_outcome+order_book",
    ]


def test_strategy_allocates_rates_across_fast_expected_and_yield_tiers() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=3.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0002),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=3,
            rate_optimization_mode="fill_probability",
            lending_risk_level="balanced",
        ),
        historical_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0001, 0.0003, 0.0003]
    assert [candidate.selection_role for candidate in decision.rate_candidates] == ["fast", "", "expected+yield"]


def test_strategy_uses_market_regime_to_reduce_fast_allocation_when_rates_rise() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=4.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0002),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=4,
            rate_optimization_mode="fill_probability",
            lending_risk_level="balanced",
        ),
        historical_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001],
        market_regime_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001, 0.0001],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0001, 0.0003, 0.0003, 0.0003]
    assert [candidate.selection_role for candidate in decision.rate_candidates] == ["fast", "", "expected+yield"]


def test_strategy_uses_market_regime_to_prefer_fast_allocation_when_rates_fall() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=4.0),
        order_book=[
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0001),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0002),
            LoanOrder(currency="BTC", amount=1.0, daily_rate=0.0003),
        ],
        strategy=_strategy(
            spread_lend=4,
            rate_optimization_mode="fill_probability",
            lending_risk_level="balanced",
        ),
        historical_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001],
        market_regime_daily_rates=[0.0001, 0.0001, 0.0001, 0.0003, 0.0003, 0.0003],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0001, 0.0001, 0.0001, 0.0003]
    assert [candidate.selection_role for candidate in decision.rate_candidates] == ["fast", "", "expected"]


def test_strategy_fast_risk_level_prefers_higher_fill_probability() -> None:
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
            rate_optimization_min_probability=0.10,
            lending_risk_level="fast",
        ),
        historical_daily_rates=[0.0003, 0.0003, 0.0003, 0.0001, 0.0001],
    )

    assert [offer.daily_rate for offer in decision.offers] == [0.0001]


def test_strategy_yield_risk_level_accepts_lower_fill_probability() -> None:
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
            rate_optimization_min_probability=0.10,
            lending_risk_level="yield",
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


def test_strategy_detects_volatile_rising_market_regime() -> None:
    regime = detect_market_regime(
        current_daily_rate=0.00022,
        historical_daily_rates=[0.00022, 0.00021, 0.0002, 0.0001, 0.0001, 0.0001],
    )

    assert regime.label == "volatile_rising"
    assert regime.trend == "rising"
    assert regime.volatility == "volatile"
    assert regime.sample_count == 6
    assert regime.short_average_daily_rate == 0.000215
    assert regime.long_average_daily_rate == 0.000155


def test_strategy_detects_stable_market_regime() -> None:
    regime = detect_market_regime(
        current_daily_rate=0.0001,
        historical_daily_rates=[0.0001, 0.000101, 0.000099, 0.0001],
    )

    assert regime.label == "stable"
    assert regime.trend == "stable"
    assert regime.volatility == "calm"


def test_strategy_uses_long_duration_above_xday_threshold() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.001)],
        strategy=_strategy(xday_threshold=0.001, xdays=30),
    )

    assert {offer.duration_days for offer in decision.offers} == {30}


def test_strategy_uses_dynamic_duration_tiers() -> None:
    decisions = [
        build_lending_decision(
            balance=CurrencyBalance(currency="BTC", amount=1.0),
            order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=rate)],
            strategy=_strategy(dynamic_duration_enabled=True),
        )
        for rate in (0.0001, 0.00022, 0.00042, 0.00069)
    ]

    assert [decision.offers[0].duration_days for decision in decisions] == [2, 7, 30, 120]


def test_strategy_duration_policy_caps_rising_market_terms() -> None:
    strategy = _strategy(dynamic_duration_enabled=True)
    rising = detect_market_regime(
        current_daily_rate=0.00042,
        historical_daily_rates=[0.000125, 0.000125, 0.000125, 0.0001, 0.0001, 0.0001],
    )
    volatile_rising = detect_market_regime(
        current_daily_rate=0.00069,
        historical_daily_rates=[0.0005, 0.0004, 0.00025, 0.0001, 0.00008, 0.00005],
    )

    assert _regime_adjusted_duration_days(30, 0.00042, strategy, rising) == 14
    assert _regime_adjusted_duration_days(120, 0.00069, strategy, volatile_rising) == 7


def test_strategy_duration_policy_extends_falling_market_terms() -> None:
    strategy = _strategy(dynamic_duration_enabled=True)
    falling = detect_market_regime(
        current_daily_rate=0.00022,
        historical_daily_rates=[0.0001, 0.0001, 0.0001, 0.000125, 0.000125, 0.000125],
    )
    volatile_falling = detect_market_regime(
        current_daily_rate=0.00042,
        historical_daily_rates=[0.00005, 0.00008, 0.0001, 0.00025, 0.0004, 0.0005],
    )

    assert _regime_adjusted_duration_days(7, 0.00022, strategy, falling) == 14
    assert _regime_adjusted_duration_days(30, 0.00042, strategy, volatile_falling) == 60


def test_strategy_caps_offer_duration_when_market_regime_is_rising() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00069)],
        strategy=_strategy(dynamic_duration_enabled=True),
        market_regime_daily_rates=[0.0005, 0.0004, 0.00025, 0.0001, 0.00008, 0.00005],
    )

    assert decision.market_regime is not None
    assert decision.market_regime.label == "volatile_rising"
    assert {offer.duration_days for offer in decision.offers} == {7}


def test_strategy_extends_offer_duration_when_market_regime_is_falling() -> None:
    decision = build_lending_decision(
        balance=CurrencyBalance(currency="BTC", amount=1.0),
        order_book=[LoanOrder(currency="BTC", amount=1.0, daily_rate=0.00042)],
        strategy=_strategy(dynamic_duration_enabled=True),
        market_regime_daily_rates=[0.00005, 0.00008, 0.0001, 0.00025, 0.0004, 0.0005],
    )

    assert decision.market_regime is not None
    assert decision.market_regime.label == "volatile_falling"
    assert {offer.duration_days for offer in decision.offers} == {60}


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
    max_offer_amount: float | None = None,
    min_offer_remainder: float = 0,
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
    allow_above_market_offers: bool = True,
    lending_risk_level: str = "balanced",
    dynamic_duration_enabled: bool = False,
) -> StrategyConfig:
    return StrategyConfig(
        min_daily_rate=min_daily_rate,
        max_daily_rate=max_daily_rate,
        min_loan_size=min_loan_size,
        spread_lend=spread_lend,
        max_offer_amount=max_offer_amount,
        min_offer_remainder=min_offer_remainder,
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
        allow_above_market_offers=allow_above_market_offers,
        lending_risk_level=lending_risk_level,
        dynamic_duration_enabled=dynamic_duration_enabled,
    )
