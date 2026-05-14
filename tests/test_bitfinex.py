import base64
import json

import pytest

from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.integrations.bitfinex import BitfinexClient, parse_json_response
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.errors import ExchangeRequestError
from auto_lending_bot.integrations.http import HttpResponse


def test_bitfinex_client_requires_credentials() -> None:
    with pytest.raises(ExchangeAuthenticationError):
        BitfinexClient(api_key="", api_secret="", http_client=FakeHttpClient())


def test_bitfinex_client_builds_signed_headers() -> None:
    client = BitfinexClient(api_key="key", api_secret="secret", http_client=FakeHttpClient())

    headers = client.build_signed_headers({"request": "/v1/balances"})

    assert headers["X-BFX-APIKEY"] == "key"
    assert len(headers["X-BFX-PAYLOAD"]) > 0
    assert len(headers["X-BFX-SIGNATURE"]) == 96


def test_bitfinex_client_adds_nonce_to_private_payload() -> None:
    http_client = RecordingHttpClient('[{"type":"deposit","currency":"btc","available":"0.25"}]')
    client = BitfinexClient(api_key="key", api_secret="secret", http_client=http_client)

    client.get_lending_balances()

    payload = json.loads(base64.b64decode(http_client.requests[0]["headers"]["X-BFX-PAYLOAD"]))
    assert payload["request"] == "/v1/balances"
    assert int(payload["nonce"]) > 0


def test_bitfinex_client_reads_lending_balances() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"type":"deposit","currency":"btc","available":"0.25"},'
            '{"type":"exchange","currency":"eth","available":"2.0"}]'
        ),
    )

    balances = client.get_lending_balances()

    assert len(balances) == 1
    assert balances[0].currency == "BTC"
    assert balances[0].amount == 0.25


def test_bitfinex_client_reads_exchange_balances() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"type":"deposit","currency":"btc","available":"0.25"},'
            '{"type":"exchange","currency":"eth","available":"2.0"}]'
        ),
    )

    balances = client.get_exchange_balances()

    assert len(balances) == 1
    assert balances[0].currency == "ETH"
    assert balances[0].amount == 2.0


def test_bitfinex_client_reads_margin_balances() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"type":"deposit","currency":"btc","available":"0.25"},'
            '{"type":"trading","currency":"ust","available":"100.0"}]'
        ),
    )

    balances = client.get_margin_balances()

    assert len(balances) == 1
    assert balances[0].currency == "USDT"
    assert balances[0].amount == 100.0


def test_bitfinex_client_skips_invalid_lending_balances() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"type":"deposit","currency":"btc","available":"bad"},'
            '{"type":"deposit","currency":"eth","available":"0"}]'
        ),
    )

    assert client.get_lending_balances() == []


def test_bitfinex_client_reads_loan_orders() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"asks":[{"amount":"1.5","rate":"2.92"}]}'),
    )

    orders = client.get_loan_orders("BTC")

    assert len(orders) == 1
    assert orders[0].currency == "BTC"
    assert orders[0].amount == 1.5
    assert round(orders[0].daily_rate, 8) == 0.00008


@pytest.mark.parametrize(
    ("currency", "expected_path"),
    [
        ("DASH", "/v1/lendbook/dsh"),
        ("IOTA", "/v1/lendbook/iot"),
        ("USDT", "/v1/lendbook/ust"),
    ],
)
def test_bitfinex_client_maps_display_currency_to_bitfinex_lendbook_symbol(
    currency: str,
    expected_path: str,
) -> None:
    http_client = RecordingHttpClient('{"asks":[{"amount":"1.5","rate":"2.92"}]}')
    client = BitfinexClient(api_key="key", api_secret="secret", http_client=http_client)

    orders = client.get_loan_orders(currency)

    assert http_client.requests[0]["url"].endswith(expected_path)
    assert orders[0].currency == currency


def test_bitfinex_client_maps_api_currency_to_display_currency() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[{"type":"deposit","currency":"ust","available":"10"}]'),
    )

    balances = client.get_lending_balances()

    assert balances[0].currency == "USDT"


def test_bitfinex_client_reads_frr_rate() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[["fBTC",0.00011]]'),
    )

    assert client.get_frr_rate("BTC") == 0.00011


def test_bitfinex_client_returns_none_for_invalid_frr_rate() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[["fBTC","bad"]]'),
    )

    assert client.get_frr_rate("BTC") is None


def test_bitfinex_client_reads_direct_btc_price() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[0,0,0,0,0,0,0.05]'),
    )

    assert client.get_btc_price("ETH") == 0.05


def test_bitfinex_client_reads_inverse_btc_price() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClientSequence(['{"message":"not found"}', '[0,0,0,0,0,0,50000]']),
    )

    assert client.get_btc_price("USD") == 0.00002


def test_bitfinex_client_skips_invalid_loan_orders() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"asks":[{"amount":"bad","rate":"2.92"},{}]}'),
    )

    assert client.get_loan_orders("BTC") == []


def test_bitfinex_client_reads_open_loan_offers() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"direction":"lend","currency":"btc","remaining_amount":"0.5",'
            '"amount":"1.0","rate":"2.92","period":"2"}]'
        ),
    )

    offers = client.get_open_loan_offers()

    assert len(offers) == 1
    assert offers[0].currency == "BTC"
    assert offers[0].amount == 0.5
    assert round(offers[0].daily_rate, 8) == 0.00008
    assert offers[0].external_offer_id == ""


def test_bitfinex_client_reads_active_loans() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"id":123,"currency":"btc","amount":"0.5","rate":"2.92","period":"2"}]'
        ),
    )

    active_loans = client.get_active_loans()

    assert len(active_loans) == 1
    assert active_loans[0].currency == "BTC"
    assert active_loans[0].amount == 0.5
    assert round(active_loans[0].daily_rate, 8) == 0.00008
    assert active_loans[0].duration_days == 2
    assert active_loans[0].external_loan_id == "123"


def test_bitfinex_client_reads_lending_history() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient(
            '[{"id":123,"currency":"btc","amount":"0.000085",'
            '"timestamp":"1704067200","description":"Margin Funding Payment"}]'
        ),
    )

    entries = client.get_lending_history("BTC")

    assert len(entries) == 1
    assert entries[0].currency == "BTC"
    assert entries[0].earned == 0.000085
    assert entries[0].external_entry_id == "123"
    assert entries[0].closed_at == "2024-01-01 00:00:00"


def test_bitfinex_client_ignores_non_funding_history() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[{"amount":"1","description":"Exchange Wallet Deposit"}]'),
    )

    assert client.get_lending_history("BTC") == []


def test_bitfinex_client_skips_invalid_active_loans() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[{"currency":"btc","amount":"bad","rate":"2.92"}]'),
    )

    assert client.get_active_loans() == []


def test_bitfinex_client_skips_invalid_open_loan_offers() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('[{"direction":"lend","currency":"btc","amount":"bad"}]'),
    )

    assert client.get_open_loan_offers() == []


def test_bitfinex_client_creates_loan_offer() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"id": 123}'),
    )

    offer_id = client.create_loan_offer(
        LoanOffer(currency="BTC", amount=0.1, daily_rate=0.00008, duration_days=2)
    )

    assert offer_id == "123"


def test_bitfinex_client_maps_usdt_to_bitfinex_ust_for_private_payloads() -> None:
    http_client = RecordingHttpClient('{"id": 123}')
    client = BitfinexClient(api_key="key", api_secret="secret", http_client=http_client)

    client.create_loan_offer(LoanOffer(currency="USDT", amount=0.1, daily_rate=0.00008, duration_days=2))

    payload = json.loads(base64.b64decode(http_client.requests[0]["headers"]["X-BFX-PAYLOAD"]))
    assert payload["currency"] == "UST"


def test_bitfinex_client_maps_dash_and_iota_private_payloads() -> None:
    http_client = RecordingHttpClient('{"id": 123}')
    client = BitfinexClient(api_key="key", api_secret="secret", http_client=http_client)

    client.create_loan_offer(LoanOffer(currency="DASH", amount=0.1, daily_rate=0.00008, duration_days=2))
    client.transfer_to_lending("IOTA", 0.1)

    offer_payload = json.loads(base64.b64decode(http_client.requests[0]["headers"]["X-BFX-PAYLOAD"]))
    transfer_payload = json.loads(base64.b64decode(http_client.requests[1]["headers"]["X-BFX-PAYLOAD"]))
    assert offer_payload["currency"] == "DSH"
    assert transfer_payload["currency"] == "IOT"


def test_bitfinex_client_cancels_loan_offer() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"id": 123}'),
    )

    client.cancel_loan_offer("123")


def test_bitfinex_client_transfers_to_lending() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"id": 456}'),
    )

    transfer_id = client.transfer_to_lending("BTC", 0.1)

    assert transfer_id == "456"


def test_bitfinex_client_raises_exchange_error_for_api_message() -> None:
    client = BitfinexClient(
        api_key="key",
        api_secret="secret",
        http_client=FakeHttpClient('{"message":"invalid api key"}'),
    )

    with pytest.raises(ExchangeRequestError, match="invalid api key"):
        client.get_lending_balances()


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


class RecordingHttpClient(FakeHttpClient):
    def __init__(self, body: str = "{}") -> None:
        super().__init__(body)
        self.requests: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return super().request(method, url, headers, body, timeout_seconds)


class FakeHttpClientSequence:
    def __init__(self, bodies: list[str]) -> None:
        self._bodies = bodies
        self._index = 0

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        body = self._bodies[self._index]
        self._index += 1
        return HttpResponse(status_code=200, body=body)
