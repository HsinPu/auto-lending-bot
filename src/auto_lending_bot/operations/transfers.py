from auto_lending_bot.domain.models import CurrencyBalance, TransferPreview


def build_transfer_preview(
    exchange_balances: list[CurrencyBalance],
    lending_balances: list[CurrencyBalance],
    transferable_currencies: tuple[str, ...],
) -> list[TransferPreview]:
    currencies = _target_currencies(exchange_balances, lending_balances, transferable_currencies)
    previews = []
    for balance in exchange_balances:
        currency = balance.currency.upper()
        if currency in currencies and balance.amount > 0:
            previews.append(TransferPreview(currency=currency, amount=balance.amount))
    return previews


def execute_transfers(exchange, previews: list[TransferPreview]) -> list[TransferPreview]:
    results = []
    for preview in previews:
        external_transfer_id = exchange.transfer_to_lending(preview.currency, preview.amount)
        results.append(
            TransferPreview(
                currency=preview.currency,
                amount=preview.amount,
                source=preview.source,
                destination=preview.destination,
                external_transfer_id=external_transfer_id,
            )
        )
    return results


def _target_currencies(
    exchange_balances: list[CurrencyBalance],
    lending_balances: list[CurrencyBalance],
    transferable_currencies: tuple[str, ...],
) -> set[str]:
    configured = {currency.upper() for currency in transferable_currencies}
    if not configured:
        return set()

    targets = set()
    if "ALL" in configured:
        targets.update(balance.currency.upper() for balance in exchange_balances)
    if "ACTIVE" in configured:
        targets.update(balance.currency.upper() for balance in lending_balances)
    targets.update(currency for currency in configured if currency not in {"ALL", "ACTIVE"})
    return targets
