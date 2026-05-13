from auto_lending_bot.domain.models import CurrencyBalance
from auto_lending_bot.operations.transfers import build_transfer_preview


def test_build_transfer_preview_uses_explicit_currencies() -> None:
    previews = build_transfer_preview(
        exchange_balances=[
            CurrencyBalance(currency="BTC", amount=0.1),
            CurrencyBalance(currency="ETH", amount=1.0),
        ],
        lending_balances=[],
        transferable_currencies=("BTC",),
    )

    assert [(preview.currency, preview.amount) for preview in previews] == [("BTC", 0.1)]


def test_build_transfer_preview_supports_all_and_active() -> None:
    previews = build_transfer_preview(
        exchange_balances=[
            CurrencyBalance(currency="BTC", amount=0.1),
            CurrencyBalance(currency="ETH", amount=1.0),
        ],
        lending_balances=[CurrencyBalance(currency="ETH", amount=0.5)],
        transferable_currencies=("ACTIVE",),
    )

    assert [(preview.currency, preview.amount) for preview in previews] == [("ETH", 1.0)]
