import pytest

from auto_lending_bot.integrations.errors import ExchangeRateLimitError, ExchangeRequestError
from auto_lending_bot.integrations.http import HttpResponse, RetryingHttpClient


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
    client = FakeHttpClient([HttpResponse(status_code=500, body="error")])
    retrying_client = RetryingHttpClient(client)

    with pytest.raises(ExchangeRequestError):
        retrying_client.request("GET", "https://example.test")


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
