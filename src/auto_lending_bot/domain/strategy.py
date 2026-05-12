from dataclasses import dataclass

from auto_lending_bot.domain.models import CurrencyBalance, LendingDecision, LoanOffer, LoanOrder


@dataclass(frozen=True)
class StrategyConfig:
    min_daily_rate: float
    max_daily_rate: float
    min_loan_size: float
    spread_lend: int
    max_percent_to_lend: float
    max_amount_to_lend: float | None
    hide_coins: bool


def build_lending_decision(
    balance: CurrencyBalance,
    order_book: list[LoanOrder],
    strategy: StrategyConfig,
) -> LendingDecision:
    lendable_amount = _lendable_amount(balance.amount, strategy)
    if lendable_amount < strategy.min_loan_size:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Available balance is below the minimum loan size.",
        )

    best_order = _best_order(order_book)
    if best_order is None:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="No loan orders are available.",
        )

    if best_order.daily_rate < strategy.min_daily_rate and strategy.hide_coins:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Best daily rate is below the configured minimum.",
        )

    offer_rate = min(max(best_order.daily_rate, strategy.min_daily_rate), strategy.max_daily_rate)
    split_count = _split_count(lendable_amount, strategy.min_loan_size, strategy.spread_lend)
    offer_amounts = _split_amount(lendable_amount, split_count)
    offers = [
        LoanOffer(
            currency=balance.currency,
            amount=amount,
            daily_rate=offer_rate,
            duration_days=2,
        )
        for amount in offer_amounts
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


def _lendable_amount(amount: float, strategy: StrategyConfig) -> float:
    percent_amount = amount * (strategy.max_percent_to_lend / 100)
    if strategy.max_amount_to_lend is None:
        return round(percent_amount, 8)

    return round(min(percent_amount, strategy.max_amount_to_lend), 8)


def _split_count(amount: float, min_loan_size: float, spread_lend: int) -> int:
    requested_count = max(spread_lend, 1)
    affordable_count = int(amount // min_loan_size)
    return max(min(requested_count, affordable_count), 1)


def _split_amount(amount: float, split_count: int) -> list[float]:
    base_amount = round(amount / split_count, 8)
    amounts = [base_amount for _ in range(split_count)]
    remainder = round(amount - sum(amounts), 8)
    amounts[0] = round(amounts[0] + remainder, 8)
    return amounts
