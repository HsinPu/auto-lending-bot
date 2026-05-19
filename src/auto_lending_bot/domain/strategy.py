from dataclasses import dataclass
from dataclasses import replace
from datetime import date

from auto_lending_bot.domain.models import (
    CurrencyBalance,
    FillOutcome,
    LendingDecision,
    LoanOffer,
    LoanOrder,
    MarketRegime,
    RateCandidate,
)


@dataclass(frozen=True)
class StrategyConfig:
    min_daily_rate: float
    max_daily_rate: float
    min_loan_size: float
    spread_lend: int
    max_offer_amount: float | None
    min_offer_remainder: float
    gap_mode: str
    gap_bottom: float
    gap_top: float
    xday_threshold: float
    xdays: int
    xday_spread: float
    frr_as_min: bool
    frr_delta: float
    rate_optimization_mode: str
    rate_optimization_min_probability: float
    rate_optimization_sample_size: int
    max_percent_to_lend: float
    max_amount_to_lend: float | None
    max_active_amount: float | None
    max_to_lend_rate: float
    end_date: date | None
    hide_coins: bool
    allow_above_market_offers: bool
    min_offer_value_usd: float = 150.0
    lending_risk_level: str = "balanced"
    dynamic_duration_enabled: bool = True
    duration_low_days: int = 2
    duration_medium_daily_rate: float = 0.0002191780821917808
    duration_medium_days: int = 7
    duration_high_daily_rate: float = 0.000410958904109589
    duration_high_days: int = 30
    duration_extreme_daily_rate: float = 0.0006849315068493151
    duration_extreme_days: int = 120


MARKET_REGIME_MIN_SAMPLES = 4
MARKET_REGIME_TREND_THRESHOLD = 0.10
MARKET_REGIME_VOLATILITY_THRESHOLD = 0.50


def build_lending_decision(
    balance: CurrencyBalance,
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    frr_daily_rate: float | None = None,
    btc_price: float | None = None,
    suggested_min_daily_rate: float | None = None,
    active_amount: float = 0.0,
    historical_daily_rates: list[float] | None = None,
    fill_outcomes: list[FillOutcome] | None = None,
    market_regime_daily_rates: list[float] | None = None,
) -> LendingDecision:
    strategy = _strategy_with_frr_minimum(strategy, frr_daily_rate)
    strategy = _strategy_with_suggested_minimum(strategy, suggested_min_daily_rate)
    best_order = _best_order(order_book)
    market_regime = detect_market_regime(
        current_daily_rate=best_order.daily_rate if best_order else 0.0,
        historical_daily_rates=market_regime_daily_rates or historical_daily_rates or [],
    )
    if best_order is None:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="No loan orders are available.",
            market_regime=market_regime,
        )

    lendable_amount = _lendable_amount(balance.amount, best_order.daily_rate, strategy)
    lendable_amount = _lendable_amount_with_active_cap(lendable_amount, active_amount, strategy)
    if lendable_amount < strategy.min_loan_size:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason=_below_minimum_reason(active_amount, strategy),
            market_regime=market_regime,
        )

    if (
        best_order.daily_rate < strategy.min_daily_rate
        and strategy.hide_coins
        and not strategy.allow_above_market_offers
    ):
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Best daily rate is below the configured minimum.",
            market_regime=market_regime,
        )

    if strategy.end_date is not None and _days_until_end(strategy) <= 2:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="End date is too close to create new lending offers.",
            market_regime=market_regime,
        )

    offer_amounts = _offer_amounts(lendable_amount, strategy)
    if not offer_amounts:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Available balance is below the minimum loan size.",
            market_regime=market_regime,
        )

    rate_candidates: list[RateCandidate] = []
    if best_order.daily_rate < strategy.min_daily_rate:
        offer_rates = [_clamp_rate(strategy.min_daily_rate, strategy) for _ in offer_amounts]
    else:
        offer_rates, rate_candidates = _offer_rates(
            order_book,
            strategy,
            lendable_amount,
            len(offer_amounts),
            btc_price,
            historical_daily_rates or [],
            fill_outcomes or [],
        )
    offers = [
        LoanOffer(
            currency=balance.currency,
            amount=amount,
            daily_rate=rate,
            duration_days=_duration_days(rate, strategy),
        )
        for amount, rate in zip(offer_amounts, offer_rates, strict=True)
    ]

    reason = "Created lending offers from available balance."
    if best_order.daily_rate < strategy.min_daily_rate:
        reason = "Created minimum-rate offers while market is below the configured minimum."

    return LendingDecision(
        currency=balance.currency,
        offers=offers,
        reason=reason,
        rate_candidates=rate_candidates,
        market_regime=market_regime,
    )


def detect_market_regime(
    current_daily_rate: float,
    historical_daily_rates: list[float],
) -> MarketRegime:
    samples = [rate for rate in historical_daily_rates if rate > 0]
    current_rate = round(max(current_daily_rate, 0.0), 10)
    if len(samples) < MARKET_REGIME_MIN_SAMPLES:
        average = _mean(samples)
        return MarketRegime(
            label="insufficient_data" if samples else "unknown",
            trend="unknown",
            volatility="unknown",
            current_daily_rate=current_rate,
            short_average_daily_rate=average,
            long_average_daily_rate=average,
            sample_count=len(samples),
            reason="Not enough market-analysis samples to detect a regime.",
        )

    short_count = max(2, min(5, len(samples) // 3))
    short_average = _mean(samples[:short_count]) or 0.0
    long_average = _mean(samples) or 0.0
    trend_ratio = _safe_ratio(short_average - long_average, long_average)
    volatility_ratio = _safe_ratio(max(samples) - min(samples), long_average)
    trend = _market_regime_trend(trend_ratio)
    volatility = (
        "volatile"
        if volatility_ratio >= MARKET_REGIME_VOLATILITY_THRESHOLD
        else "calm"
    )

    return MarketRegime(
        label=_market_regime_label(trend, volatility),
        trend=trend,
        volatility=volatility,
        current_daily_rate=current_rate,
        short_average_daily_rate=round(short_average, 10),
        long_average_daily_rate=round(long_average, 10),
        sample_count=len(samples),
        reason=(
            f"Short average is {trend_ratio:.2%} versus the long average; "
            f"sample range is {volatility_ratio:.2%}."
        ),
    )


def _market_regime_trend(trend_ratio: float) -> str:
    if trend_ratio >= MARKET_REGIME_TREND_THRESHOLD:
        return "rising"
    if trend_ratio <= -MARKET_REGIME_TREND_THRESHOLD:
        return "falling"
    return "stable"


def _market_regime_label(trend: str, volatility: str) -> str:
    if volatility == "volatile":
        return {
            "rising": "volatile_rising",
            "falling": "volatile_falling",
        }.get(trend, "volatile_range")
    return trend


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 10)


def _best_order(order_book: list[LoanOrder]) -> LoanOrder | None:
    if not order_book:
        return None

    return max(order_book, key=lambda order: order.daily_rate)


def _lendable_amount(amount: float, best_daily_rate: float, strategy: StrategyConfig) -> float:
    if not _should_restrict_lendable_amount(best_daily_rate, strategy):
        return round(amount, 8)

    percent_amount = amount * (strategy.max_percent_to_lend / 100)
    if strategy.max_amount_to_lend is None:
        return round(percent_amount, 8)

    return round(min(percent_amount, strategy.max_amount_to_lend), 8)


def _lendable_amount_with_active_cap(
    lendable_amount: float,
    active_amount: float,
    strategy: StrategyConfig,
) -> float:
    if strategy.max_active_amount is None:
        return lendable_amount

    remaining_amount = max(strategy.max_active_amount - active_amount, 0)
    return round(min(lendable_amount, remaining_amount), 8)


def _below_minimum_reason(active_amount: float, strategy: StrategyConfig) -> str:
    if strategy.max_active_amount is not None and active_amount >= strategy.max_active_amount:
        return "Active lending amount is at or above the configured maximum."

    return "Available balance is below the minimum loan size."


def _should_restrict_lendable_amount(best_daily_rate: float, strategy: StrategyConfig) -> bool:
    if strategy.max_amount_to_lend is None and strategy.max_percent_to_lend >= 100:
        return False

    if best_daily_rate <= 0:
        return False

    return strategy.max_to_lend_rate == 0 or best_daily_rate <= strategy.max_to_lend_rate


def _offer_amounts(amount: float, strategy: StrategyConfig) -> list[float]:
    if strategy.max_offer_amount is not None and strategy.max_offer_amount >= strategy.min_loan_size:
        return _split_amount_by_max_offer(
            amount,
            strategy.max_offer_amount,
            strategy.min_offer_remainder,
        )

    split_count = _split_count(amount, strategy.min_loan_size, strategy.spread_lend)
    return _split_amount(amount, split_count, strategy.min_loan_size)


def _split_count(amount: float, min_loan_size: float, spread_lend: int) -> int:
    requested_count = max(spread_lend, 1)
    affordable_count = int(amount // min_loan_size)
    return max(min(requested_count, affordable_count), 1)


def _split_amount(amount: float, split_count: int, min_loan_size: float) -> list[float]:
    while split_count > 1 and round(amount / split_count, 8) < min_loan_size:
        split_count -= 1

    base_amount = round(amount / split_count, 8)
    amounts = [base_amount for _ in range(split_count)]
    remainder = round(amount - sum(amounts), 8)
    amounts[0] = round(amounts[0] + remainder, 8)
    return amounts


def _split_amount_by_max_offer(
    amount: float,
    max_offer_amount: float,
    min_offer_remainder: float,
) -> list[float]:
    if amount <= max_offer_amount:
        return [round(amount, 8)]

    full_offer_count = int(amount // max_offer_amount)
    amounts = [round(max_offer_amount, 8) for _ in range(full_offer_count)]
    remainder = round(amount - sum(amounts), 8)
    if remainder > max(min_offer_remainder, 0):
        amounts.append(remainder)
    return amounts


def _offer_rates(
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    lendable_amount: float,
    split_count: int,
    btc_price: float | None,
    historical_daily_rates: list[float],
    fill_outcomes: list[FillOutcome],
) -> tuple[list[float], list[RateCandidate]]:
    optimized_rates, rate_candidates = _optimized_offer_rates(
        order_book,
        strategy,
        split_count,
        historical_daily_rates,
        fill_outcomes,
    )
    if optimized_rates:
        return optimized_rates, rate_candidates

    gap_mode = strategy.gap_mode.lower().replace("-", "_")
    if gap_mode == "rawbtc":
        gap_mode = "raw_btc"
    if gap_mode not in {"raw", "relative", "raw_btc"}:
        best_order = _best_order(order_book)
        rate = _clamp_rate(best_order.daily_rate if best_order else 0, strategy)
        return [rate for _ in range(split_count)], rate_candidates

    bottom_rate = _gap_rate(
        order_book, strategy.gap_bottom, lendable_amount, gap_mode, strategy, btc_price
    )
    top_rate = _gap_rate(order_book, strategy.gap_top, lendable_amount, gap_mode, strategy, btc_price)
    if split_count == 1:
        return [_clamp_rate(bottom_rate, strategy)], rate_candidates

    rate_step = (top_rate - bottom_rate) / (split_count - 1)
    return [
        _clamp_rate(bottom_rate + (rate_step * index), strategy)
        for index in range(split_count)
    ], rate_candidates


def _optimized_offer_rates(
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    split_count: int,
    historical_daily_rates: list[float],
    fill_outcomes: list[FillOutcome],
) -> tuple[list[float], list[RateCandidate]]:
    if strategy.rate_optimization_mode.lower() != "fill_probability":
        return [], []

    sample_size = max(strategy.rate_optimization_sample_size, 1)
    samples = [rate for rate in historical_daily_rates[:sample_size] if rate > 0]
    outcomes = [outcome for outcome in fill_outcomes[:sample_size] if outcome.daily_rate > 0]
    if not samples and not outcomes:
        return [], []

    candidate_sources: dict[float, set[str]] = {}
    for order in order_book:
        if order.daily_rate <= 0:
            continue
        candidate_sources.setdefault(
            _clamp_rate(order.daily_rate, strategy),
            set(),
        ).add("order_book")
    for rate in samples:
        candidate_sources.setdefault(_clamp_rate(rate, strategy), set()).add("history")
    for outcome in outcomes:
        candidate_sources.setdefault(
            _clamp_rate(outcome.daily_rate, strategy),
            set(),
        ).add("fill_outcome")
    if not candidate_sources:
        return [], []

    minimum_probability = _risk_minimum_probability(strategy)
    scored_rates = []
    rate_candidates: list[RateCandidate] = []
    for candidate in sorted(candidate_sources):
        probability = _fill_probability(candidate, samples, outcomes)
        expected_score = candidate * probability
        meets_min_probability = probability >= minimum_probability
        rate_candidates.append(
            RateCandidate(
                daily_rate=candidate,
                annual_rate=round(candidate * 365, 10),
                fill_probability=round(probability, 10),
                expected_score=round(expected_score, 12),
                meets_min_probability=meets_min_probability,
                source="+".join(sorted(candidate_sources[candidate])),
            )
        )
        if meets_min_probability:
            scored_rates.append((expected_score, candidate))

    if not scored_rates:
        return [], rate_candidates

    eligible_candidates = [candidate for candidate in rate_candidates if candidate.meets_min_probability]
    selected_rates, selected_roles = _allocated_candidate_rates(eligible_candidates, strategy, split_count)
    selected_rate_set = set(selected_rates)
    return selected_rates, [
        replace(
            candidate,
            selected=candidate.daily_rate in selected_rate_set,
            selection_role="+".join(sorted(selected_roles.get(candidate.daily_rate, set()))),
        )
        for candidate in rate_candidates
    ]


def _allocated_candidate_rates(
    candidates: list[RateCandidate],
    strategy: StrategyConfig,
    split_count: int,
) -> tuple[list[float], dict[float, set[str]]]:
    if not candidates:
        return [], {}

    selected: list[tuple[float, str]] = []
    if split_count == 1:
        role = _single_allocation_role(strategy)
        candidate = _candidate_for_role(candidates, role)
        selected.append((candidate.daily_rate, role))
    else:
        for role, count in _allocation_role_counts(strategy, split_count):
            candidate = _candidate_for_role(candidates, role)
            selected.extend((candidate.daily_rate, role) for _ in range(count))

    selected_rates = sorted(rate for rate, _ in selected)
    selected_roles: dict[float, set[str]] = {}
    for rate, role in selected:
        selected_roles.setdefault(rate, set()).add(role)
    return selected_rates, selected_roles


def _single_allocation_role(strategy: StrategyConfig) -> str:
    return {
        "fast": "fast",
        "balanced": "expected",
        "yield": "yield",
    }.get(strategy.lending_risk_level.lower(), "expected")


def _allocation_role_counts(strategy: StrategyConfig, split_count: int) -> list[tuple[str, int]]:
    plan = _allocation_plan(strategy)
    if split_count < len(plan):
        return [(role, 1) for role, _ in plan[:split_count]]

    counts = {role: 1 for role, _ in plan}
    remaining = split_count - len(plan)
    remainders = []
    allocated = 0
    for role, weight in plan:
        raw_count = remaining * weight
        extra_count = int(raw_count)
        counts[role] += extra_count
        allocated += extra_count
        remainders.append((raw_count - extra_count, role))
    for _, role in sorted(remainders, reverse=True)[: remaining - allocated]:
        counts[role] += 1
    return [(role, counts[role]) for role, _ in plan if counts[role] > 0]


def _allocation_plan(strategy: StrategyConfig) -> list[tuple[str, float]]:
    return {
        "fast": [("fast", 0.90), ("expected", 0.10)],
        "balanced": [("fast", 0.70), ("expected", 0.20), ("yield", 0.10)],
        "yield": [("fast", 0.50), ("expected", 0.30), ("yield", 0.20)],
    }.get(strategy.lending_risk_level.lower(), [("fast", 0.70), ("expected", 0.20), ("yield", 0.10)])


def _fill_probability(
    candidate: float,
    market_samples: list[float],
    fill_outcomes: list[FillOutcome],
) -> float:
    market_successes = sum(1 for sample in market_samples if sample >= candidate)
    outcome_successes = sum(
        1
        for outcome in fill_outcomes
        if outcome.filled and outcome.daily_rate >= candidate
    )
    outcome_failures = sum(
        1
        for outcome in fill_outcomes
        if not outcome.filled and outcome.daily_rate <= candidate
    )
    total_samples = len(market_samples) + outcome_successes + outcome_failures
    if total_samples <= 0:
        return 0.0

    return (market_successes + outcome_successes) / total_samples


def _candidate_for_role(candidates: list[RateCandidate], role: str) -> RateCandidate:
    if role == "fast":
        return max(candidates, key=lambda candidate: (candidate.fill_probability, -candidate.daily_rate))
    if role == "yield":
        return max(candidates, key=lambda candidate: (candidate.daily_rate, candidate.expected_score))
    return max(candidates, key=lambda candidate: (candidate.expected_score, candidate.daily_rate))


def _risk_minimum_probability(strategy: StrategyConfig) -> float:
    risk_level = strategy.lending_risk_level.lower()
    default_probability = {
        "fast": 0.70,
        "balanced": 0.40,
        "yield": 0.15,
    }.get(risk_level, 0.40)
    configured_probability = min(max(strategy.rate_optimization_min_probability, 0), 1)
    return max(configured_probability, default_probability)


def _gap_rate(
    order_book: list[LoanOrder],
    gap: float,
    lendable_amount: float,
    gap_mode: str,
    strategy: StrategyConfig,
    btc_price: float | None,
) -> float:
    sorted_orders = sorted(order_book, key=lambda order: order.daily_rate)
    if not sorted_orders:
        return strategy.min_daily_rate

    target_depth = _target_gap_depth(gap, lendable_amount, gap_mode, btc_price)
    if target_depth <= 0:
        return sorted_orders[0].daily_rate

    depth = 0.0
    for order in sorted_orders:
        depth += order.amount
        if depth >= target_depth:
            return order.daily_rate

    return strategy.max_daily_rate


def _target_gap_depth(
    gap: float,
    lendable_amount: float,
    gap_mode: str,
    btc_price: float | None,
) -> float:
    if gap_mode == "relative":
        return lendable_amount * gap / 100
    if gap_mode == "raw_btc" and btc_price is not None and btc_price > 0:
        return gap / btc_price
    return gap


def _clamp_rate(rate: float, strategy: StrategyConfig) -> float:
    return round(min(max(rate, strategy.min_daily_rate), strategy.max_daily_rate), 10)


def _strategy_with_frr_minimum(
    strategy: StrategyConfig,
    frr_daily_rate: float | None,
) -> StrategyConfig:
    if not strategy.frr_as_min or frr_daily_rate is None:
        return strategy

    frr_min_daily_rate = frr_daily_rate + strategy.frr_delta
    if frr_min_daily_rate <= strategy.min_daily_rate:
        return strategy

    return replace(strategy, min_daily_rate=frr_min_daily_rate)


def _strategy_with_suggested_minimum(
    strategy: StrategyConfig,
    suggested_min_daily_rate: float | None,
) -> StrategyConfig:
    if suggested_min_daily_rate is None or suggested_min_daily_rate <= strategy.min_daily_rate:
        return strategy

    return replace(strategy, min_daily_rate=suggested_min_daily_rate)


def _duration_days(rate: float, strategy: StrategyConfig) -> int:
    max_end_date_days = _days_until_end(strategy)
    if strategy.dynamic_duration_enabled:
        return _dynamic_duration_days(rate, strategy, max_end_date_days)

    if strategy.xday_threshold <= 0:
        return min(2, max_end_date_days) if max_end_date_days > 0 else 2

    max_days = min(max(strategy.xdays, 2), 120)
    if max_end_date_days > 0:
        max_days = min(max_days, max_end_date_days)
    if rate >= strategy.xday_threshold:
        return max_days

    if strategy.xday_spread <= 0:
        return 2

    threshold_min = strategy.xday_threshold / strategy.xday_spread
    if rate <= threshold_min:
        return 2

    slope = (max_days - 2) / (strategy.xday_threshold - threshold_min)
    return min(max(round(slope * (rate - threshold_min) + 2), 2), max_days)


def _dynamic_duration_days(rate: float, strategy: StrategyConfig, max_end_date_days: int) -> int:
    if rate >= strategy.duration_extreme_daily_rate:
        days = strategy.duration_extreme_days
    elif rate >= strategy.duration_high_daily_rate:
        days = strategy.duration_high_days
    elif rate >= strategy.duration_medium_daily_rate:
        days = strategy.duration_medium_days
    else:
        days = strategy.duration_low_days

    capped_days = min(max(days, 2), 120)
    if max_end_date_days > 0:
        capped_days = min(capped_days, max_end_date_days)
    return capped_days


def _days_until_end(strategy: StrategyConfig) -> int:
    if strategy.end_date is None:
        return 0

    return (strategy.end_date - date.today()).days
