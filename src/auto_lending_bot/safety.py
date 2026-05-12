from auto_lending_bot.config import Settings


class SafetyError(ValueError):
    pass


def validate_run_settings(settings: Settings) -> None:
    if settings.exchange not in {"mock", "poloniex"}:
        msg = "Only EXCHANGE=mock or EXCHANGE=poloniex are supported."
        raise SafetyError(msg)

    if not settings.dry_run and not settings.allow_live_trading:
        msg = "BOT_DRY_RUN=false requires ALLOW_LIVE_TRADING=true."
        raise SafetyError(msg)

    if settings.exchange == "poloniex" and (not settings.api_key or not settings.api_secret):
        msg = "EXCHANGE=poloniex requires EXCHANGE_API_KEY and EXCHANGE_API_SECRET."
        raise SafetyError(msg)

    if not settings.dry_run:
        if settings.exchange != "poloniex":
            msg = "Live lending beta only supports EXCHANGE=poloniex."
            raise SafetyError(msg)
        if settings.max_total_lend_amount is None:
            msg = "BOT_DRY_RUN=false requires MAX_TOTAL_LEND_AMOUNT."
            raise SafetyError(msg)
        if settings.max_single_offer_amount is None:
            msg = "BOT_DRY_RUN=false requires MAX_SINGLE_OFFER_AMOUNT."
            raise SafetyError(msg)
