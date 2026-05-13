from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import TransferPreview


class SafetyError(ValueError):
    pass


def validate_run_settings(settings: Settings) -> None:
    if settings.exchange not in {"mock", "bitfinex"}:
        msg = "Only EXCHANGE=mock or EXCHANGE=bitfinex are supported."
        raise SafetyError(msg)

    if not settings.dry_run and not settings.allow_live_trading:
        msg = "BOT_DRY_RUN=false requires ALLOW_LIVE_TRADING=true."
        raise SafetyError(msg)

    if settings.exchange == "bitfinex" and (not settings.api_key or not settings.api_secret):
        msg = "EXCHANGE=bitfinex requires EXCHANGE_API_KEY and EXCHANGE_API_SECRET."
        raise SafetyError(msg)

    if not settings.dry_run:
        if settings.exchange != "bitfinex":
            msg = "Live lending beta only supports EXCHANGE=bitfinex."
            raise SafetyError(msg)
        if settings.max_total_lend_amount is None:
            msg = "BOT_DRY_RUN=false requires MAX_TOTAL_LEND_AMOUNT."
            raise SafetyError(msg)
        if settings.max_single_offer_amount is None:
            msg = "BOT_DRY_RUN=false requires MAX_SINGLE_OFFER_AMOUNT."
            raise SafetyError(msg)
        if not settings.bitfinex_enable_live_offers:
            msg = "EXCHANGE=bitfinex live mode requires BITFINEX_ENABLE_LIVE_OFFERS=true."
            raise SafetyError(msg)


def validate_transfer_settings(settings: Settings) -> None:
    if settings.exchange not in {"mock", "bitfinex"}:
        msg = "Only EXCHANGE=mock or EXCHANGE=bitfinex are supported."
        raise SafetyError(msg)

    if settings.exchange == "bitfinex" and (not settings.api_key or not settings.api_secret):
        msg = "EXCHANGE=bitfinex requires EXCHANGE_API_KEY and EXCHANGE_API_SECRET."
        raise SafetyError(msg)

    if settings.dry_run:
        return

    if not settings.allow_live_trading:
        msg = "BOT_DRY_RUN=false requires ALLOW_LIVE_TRADING=true."
        raise SafetyError(msg)
    if settings.exchange != "bitfinex":
        msg = "Live transfers only support EXCHANGE=bitfinex."
        raise SafetyError(msg)
    if not settings.allow_balance_transfers:
        msg = "Live transfers require ALLOW_BALANCE_TRANSFERS=true."
        raise SafetyError(msg)
    if not settings.bitfinex_enable_live_transfers:
        msg = "EXCHANGE=bitfinex live transfers require BITFINEX_ENABLE_LIVE_TRANSFERS=true."
        raise SafetyError(msg)
    if settings.max_total_transfer_amount is None:
        msg = "Live transfers require MAX_TOTAL_TRANSFER_AMOUNT."
        raise SafetyError(msg)
    if settings.max_single_transfer_amount is None:
        msg = "Live transfers require MAX_SINGLE_TRANSFER_AMOUNT."
        raise SafetyError(msg)


def validate_transfer_limits(settings: Settings, transfers: list[TransferPreview]) -> None:
    if settings.dry_run:
        return

    if settings.max_single_transfer_amount is not None:
        for transfer in transfers:
            if transfer.amount > settings.max_single_transfer_amount:
                msg = "Transfer amount exceeds MAX_SINGLE_TRANSFER_AMOUNT."
                raise SafetyError(msg)

    if settings.max_total_transfer_amount is not None:
        total_amount = sum(transfer.amount for transfer in transfers)
        if total_amount > settings.max_total_transfer_amount:
            msg = "Transfer total exceeds MAX_TOTAL_TRANSFER_AMOUNT."
            raise SafetyError(msg)
