from auto_lending_bot.domain.models import CurrencyBalance, LendingDecision, LoanOffer, LoanOrder


def build_lending_decision(
    balance: CurrencyBalance,
    order_book: list[LoanOrder],
    min_daily_rate: float,
    min_loan_size: float,
    spread_lend: int,
) -> LendingDecision:
    if balance.amount < min_loan_size:
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

    if best_order.daily_rate < min_daily_rate:
        return LendingDecision(
            currency=balance.currency,
            offers=[],
            reason="Best daily rate is below the configured minimum.",
        )

    split_count = _split_count(balance.amount, min_loan_size, spread_lend)
    offer_amounts = _split_amount(balance.amount, split_count)
    offers = [
        LoanOffer(
            currency=balance.currency,
            amount=amount,
            daily_rate=best_order.daily_rate,
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
