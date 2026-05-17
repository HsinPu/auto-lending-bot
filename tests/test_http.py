import pytest

from auto_lending_bot.integrations.errors import (
    ExchangePermissionError,
    ExchangeRateLimitError,
    ExchangeRequestError,
)
from auto_lending_bot.integrations.http import HttpResponse, RetryingHttpClient, UrlLibHttpClient


def test_retrying_http_client_returns_successful_response() -> None:
    client = FakeHttpClient([HttpResponse(status_code=200, body="{}")])
    retrying_client = RetryingHttpClient(client)

    response = retrying_client.request("GET", "https://example.test")

    assert response.body == "{}"
    assert client.calls == 1


def test_retrying_http_client_retries_rate_limit_responses() -> None:
    client = FakeHttpClient(
        [
            HttpResponse(status_code=429, body="rate limited"),
            HttpResponse(status_code=200, body="{}"),
        ]
    )
    retrying_client = RetryingHttpClient(client)

    response = retrying_client.request("GET", "https://example.test")

    assert response.status_code == 200
    assert client.calls == 2


def test_retrying_http_client_raises_after_rate_limit_attempts() -> None:
    client = FakeHttpClient([HttpResponse(status_code=429, body="rate limited")])
    retrying_client = RetryingHttpClient(client, max_attempts=2)

    with pytest.raises(ExchangeRateLimitError):
        retrying_client.request("GET", "https://example.test")

    assert client.calls == 2


def test_retrying_http_client_raises_request_error_for_non_success() -> None:
    client = FakeHttpClient([HttpResponse(status_code=500, body='{"error":"server"}')])
    retrying_client = RetryingHttpClient(client)

    with pytest.raises(ExchangeRequestError) as error:
        retrying_client.request("GET", "https://example.test")

    assert error.value.status_code == 500
    assert error.value.response_body == '{"error":"server"}'
    assert str(error.value) == 'Exchange request failed with status 500: {"error":"server"}.'


def test_retrying_http_client_truncates_error_response_body() -> None:
    client = FakeHttpClient([HttpResponse(status_code=403, body="x" * 1100)])
    retrying_client = RetryingHttpClient(client)

    with pytest.raises(ExchangeRequestError) as error:
        retrying_client.request("GET", "https://example.test")

    assert len(error.value.response_body) == 1000


def test_retrying_http_client_maps_403_to_permission_error() -> None:
    client = FakeHttpClient([HttpResponse(status_code=403, body='{"message":"permission denied"}')])
    retrying_client = RetryingHttpClient(client)

    with pytest.raises(ExchangePermissionError) as error:
        retrying_client.request("GET", "https://example.test")

    assert error.value.status_code == 403

def test_url_lib_http_client_sets_default_user_agent(monkeypatch) -> None:
    seen_headers = {}

    def fake_urlopen(request, timeout):
        seen_headers["user_agent"] = request.get_header("User-agent")
        return FakeUrlOpenResponse()

    monkeypatch.setattr("auto_lending_bot.integrations.http.urlopen", fake_urlopen)

    response = UrlLibHttpClient().request("GET", "https://example.test")

    assert response.status_code == 200
    assert seen_headers["user_agent"] == "auto-lending-bot/0.1"


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        self.calls += 1
        if len(self._responses) == 1:
            return self._responses[0]

        return self._responses.pop(0)


class FakeUrlOpenResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return b"{}"
