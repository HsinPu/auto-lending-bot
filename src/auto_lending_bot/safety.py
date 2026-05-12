from auto_lending_bot.config import Settings


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
