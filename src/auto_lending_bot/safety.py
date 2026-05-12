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

    if settings.exchange == "poloniex" and not settings.dry_run:
        msg = "EXCHANGE=poloniex is read-only and requires BOT_DRY_RUN=true."
        raise SafetyError(msg)

    if settings.exchange == "poloniex" and (not settings.api_key or not settings.api_secret):
        msg = "EXCHANGE=poloniex requires EXCHANGE_API_KEY and EXCHANGE_API_SECRET."
        raise SafetyError(msg)
