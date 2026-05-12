import pytest

from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.http import HttpResponse
from auto_lending_bot.integrations.poloniex import PoloniexClient, parse_json_response


def test_poloniex_client_requires_credentials() -> None:
    with pytest.raises(ExchangeAuthenticationError):
        PoloniexClient(api_key="", api_secret="", http_client=FakeHttpClient())


def test_poloniex_client_builds_signed_headers() -> None:
    client = PoloniexClient(api_key="key", api_secret="secret", http_client=FakeHttpClient())

    headers = client.build_signed_headers({"command": "returnBalances", "nonce": "1"})

    assert headers["Key"] == "key"
    assert len(headers["Sign"]) == 128


def test_parse_json_response() -> None:
    assert parse_json_response('{"ok": true}') == {"ok": True}


class FakeHttpClient:
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        return HttpResponse(status_code=200, body="{}")
