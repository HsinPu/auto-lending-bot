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


def test_poloniex_client_reads_lending_balances() -> None:
    client = PoloniexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"lending": {"BTC": "0.25", "ETH": "0"}}'),
    )

    balances = client.get_lending_balances()

    assert len(balances) == 1
    assert balances[0].currency == "BTC"
    assert balances[0].amount == 0.25


def test_poloniex_client_reads_loan_orders() -> None:
    client = PoloniexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"offers": [{"amount": "1.5", "rate": "0.00008"}]}'),
    )

    orders = client.get_loan_orders("BTC")

    assert len(orders) == 1
    assert orders[0].currency == "BTC"
    assert orders[0].amount == 1.5
    assert orders[0].daily_rate == 0.00008


def test_poloniex_client_reads_open_loan_offers() -> None:
    client = PoloniexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '{"BTC": [{"amount": "0.5", "rate": "0.00008", "duration": "2"}]}'
        ),
    )

    offers = client.get_open_loan_offers()

    assert len(offers) == 1
    assert offers[0].currency == "BTC"
    assert offers[0].amount == 0.5


def test_parse_json_response() -> None:
    assert parse_json_response('{"ok": true}') == {"ok": True}


class FakeHttpClient:
    def __init__(self, body: str = "{}") -> None:
        self._body = body

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        return HttpResponse(status_code=200, body=self._body)
