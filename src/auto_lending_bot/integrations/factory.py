from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.bitfinex import BitfinexClient
from auto_lending_bot.integrations.credentials import ExchangeCredentialProvider
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.integrations.http import RetryingHttpClient, UrlLibHttpClient
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile


def create_exchange_client(
    settings: Settings,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    credential_provider: ExchangeCredentialProvider | None = None,
) -> ExchangeClient:
    ensure_default_profile(profile_context)
    if settings.exchange == "mock":
        return MockExchangeClient()

    if settings.exchange == "bitfinex":
        credentials = (credential_provider or ExchangeCredentialProvider()).credentials_for(
            settings,
            profile_context,
        )
        return BitfinexClient(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            http_client=RetryingHttpClient(UrlLibHttpClient()),
            timeout_seconds=settings.http_timeout_seconds,
        )

    msg = f"Unsupported exchange: {settings.exchange}"
    raise ValueError(msg)
