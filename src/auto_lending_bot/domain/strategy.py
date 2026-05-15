from dataclasses import dataclass
from dataclasses import replace
from datetime import date

from auto_lending_bot.domain.models import CurrencyBalance, LendingDecision, LoanOffer, LoanOrder


@dataclass(frozen=True)
class StrategyConfig:
    min_daily_rate: float
    max_daily_rate: float
    min_loan_size: float
    spread_lend: int
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


def build_lending_decision(
    balance: CurrencyBalance,
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    frr_daily_rate: float | None = None,
    btc_price: float | None = None,
    suggested_min_daily_rate: float | None = None,
    active_amount: float = 0.0,
    historical_daily_rates: list[float] | None = None,
) -> LendingDecision:
    strategy = _strategy_with_frr_minimum(strategy, frr_daily_rate)
    strategy = _strategy_with_suggested_minimum(strategy, suggested_min_daily_rate)
    best_order = _best_order(order_book)
    if best_order is None:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="No loan orders are available.",
        )

    lendable_amount = _lendable_amount(balance.amount, best_order.daily_rate, strategy)
    lendable_amount = _lendable_amount_with_active_cap(lendable_amount, active_amount, strategy)
    if lendable_amount < strategy.min_loan_size:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason=_below_minimum_reason(active_amount, strategy),
        )

    if best_order.daily_rate < strategy.min_daily_rate and strategy.hide_coins:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Best daily rate is below the configured minimum.",
        )

    if strategy.end_date is not None and _days_until_end(strategy) <= 2:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="End date is too close to create new lending offers.",
        )

    split_count = _split_count(lendable_amount, strategy.min_loan_size, strategy.spread_lend)
    offer_amounts = _split_amount(lendable_amount, split_count, strategy.min_loan_size)
    offer_rates = _offer_rates(
        order_book,
        strategy,
        lendable_amount,
        split_count,
        btc_price,
        historical_daily_rates or [],
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

    return LendingDecision(
        currency=balance.currency,
        offers=offers,
        reason="Created lending offers from available balance.",
    )


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


def _offer_rates(
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    lendable_amount: float,
    split_count: int,
    btc_price: float | None,
    historical_daily_rates: list[float],
) -> list[float]:
    optimized_rates = _optimized_offer_rates(order_book, strategy, split_count, historical_daily_rates)
    if optimized_rates:
        return optimized_rates

    gap_mode = strategy.gap_mode.lower().replace("-", "_")
    if gap_mode == "rawbtc":
        gap_mode = "raw_btc"
    if gap_mode not in {"raw", "relative", "raw_btc"}:
        best_order = _best_order(order_book)
        rate = _clamp_rate(best_order.daily_rate if best_order else 0, strategy)
        return [rate for _ in range(split_count)]

    bottom_rate = _gap_rate(
        order_book, strategy.gap_bottom, lendable_amount, gap_mode, strategy, btc_price
    )
    top_rate = _gap_rate(order_book, strategy.gap_top, lendable_amount, gap_mode, strategy, btc_price)
    if split_count == 1:
        return [_clamp_rate(bottom_rate, strategy)]

    rate_step = (top_rate - bottom_rate) / (split_count - 1)
    return [_clamp_rate(bottom_rate + (rate_step * index), strategy) for index in range(split_count)]


def _optimized_offer_rates(
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    split_count: int,
    historical_daily_rates: list[float],
) -> list[float]:
    if strategy.rate_optimization_mode.lower() != "fill_probability":
        return []

    sample_size = max(strategy.rate_optimization_sample_size, 1)
    samples = [rate for rate in historical_daily_rates[:sample_size] if rate > 0]
    if not samples:
        return []

    candidates = sorted(
        {
            _clamp_rate(order.daily_rate, strategy)
            for order in order_book
            if order.daily_rate > 0
        }
        | {_clamp_rate(rate, strategy) for rate in samples},
    )
    if not candidates:
        return []

    minimum_probability = min(max(strategy.rate_optimization_min_probability, 0), 1)
    scored_rates = []
    for candidate in candidates:
        probability = sum(1 for sample in samples if sample >= candidate) / len(samples)
        if probability >= minimum_probability:
            scored_rates.append((candidate * probability, candidate))

    if not scored_rates:
        return []

    selected_rates = [rate for _, rate in sorted(scored_rates, reverse=True)[:split_count]]
    selected_rates.sort()
    while len(selected_rates) < split_count:
        selected_rates.append(selected_rates[-1])
    return selected_rates


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


def _days_until_end(strategy: StrategyConfig) -> int:
    if strategy.end_date is None:
        return 0

    return (strategy.end_date - date.today()).days
