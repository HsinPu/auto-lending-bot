from dataclasses import dataclass
from dataclasses import replace

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
    max_percent_to_lend: float
    max_amount_to_lend: float | None
    max_to_lend_rate: float
    hide_coins: bool


def build_lending_decision(
    balance: CurrencyBalance,
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
    frr_daily_rate: float | None = None,
) -> LendingDecision:
    strategy = _strategy_with_frr_minimum(strategy, frr_daily_rate)
    best_order = _best_order(order_book)
    if best_order is None:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="No loan orders are available.",
        )

    lendable_amount = _lendable_amount(balance.amount, best_order.daily_rate, strategy)
    if lendable_amount < strategy.min_loan_size:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Available balance is below the minimum loan size.",
        )

    if best_order.daily_rate < strategy.min_daily_rate and strategy.hide_coins:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Best daily rate is below the configured minimum.",
        )

    split_count = _split_count(lendable_amount, strategy.min_loan_size, strategy.spread_lend)
    offer_amounts = _split_amount(lendable_amount, split_count, strategy.min_loan_size)
    offer_rates = _offer_rates(order_book, strategy, lendable_amount, split_count)
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
) -> list[float]:
    gap_mode = strategy.gap_mode.lower()
    if gap_mode not in {"raw", "relative"}:
        best_order = _best_order(order_book)
        rate = _clamp_rate(best_order.daily_rate if best_order else 0, strategy)
        return [rate for _ in range(split_count)]

    bottom_rate = _gap_rate(order_book, strategy.gap_bottom, lendable_amount, gap_mode, strategy)
    top_rate = _gap_rate(order_book, strategy.gap_top, lendable_amount, gap_mode, strategy)
    if split_count == 1:
        return [_clamp_rate(bottom_rate, strategy)]

    rate_step = (top_rate - bottom_rate) / (split_count - 1)
    return [_clamp_rate(bottom_rate + (rate_step * index), strategy) for index in range(split_count)]


def _gap_rate(
    order_book: list[LoanOrder],
    gap: float,
    lendable_amount: float,
    gap_mode: str,
    strategy: StrategyConfig,
) -> float:
    sorted_orders = sorted(order_book, key=lambda order: order.daily_rate)
    if not sorted_orders:
        return strategy.min_daily_rate

    target_depth = gap if gap_mode == "raw" else lendable_amount * gap / 100
    if target_depth <= 0:
        return sorted_orders[0].daily_rate

    depth = 0.0
    for order in sorted_orders:
        depth += order.amount
        if depth >= target_depth:
            return order.daily_rate

    return strategy.max_daily_rate


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


def _duration_days(rate: float, strategy: StrategyConfig) -> int:
    if strategy.xday_threshold <= 0:
        return 2

    max_days = min(max(strategy.xdays, 2), 120)
    if rate >= strategy.xday_threshold:
        return max_days

    if strategy.xday_spread <= 0:
        return 2

    threshold_min = strategy.xday_threshold / strategy.xday_spread
    if rate <= threshold_min:
        return 2

    slope = (max_days - 2) / (strategy.xday_threshold - threshold_min)
    return min(max(round(slope * (rate - threshold_min) + 2), 2), max_days)
