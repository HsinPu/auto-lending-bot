from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.integrations.http import RetryingHttpClient, UrlLibHttpClient
from auto_lending_bot.integrations.mock_exchange import MockExchangeClient
from auto_lending_bot.integrations.poloniex import PoloniexClient


def create_exchange_client(settings: Settings) -> ExchangeClient:
    if settings.exchange == "mock":
        return MockExchangeClient()

    if settings.exchange == "poloniex":
        return PoloniexClient(
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            http_client=RetryingHttpClient(UrlLibHttpClient()),
            timeout_seconds=settings.http_timeout_seconds,
        )

    msg = f"Unsupported exchange: {settings.exchange}"
    raise ValueError(msg)
