from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from auto_lending_bot.integrations.errors import ExchangeRateLimitError, ExchangeRequestError


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: str


class HttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        pass


class RetryingHttpClient:
    def __init__(self, client: HttpClient, max_attempts: int = 3) -> None:
        self._client = client
        self._max_attempts = max(max_attempts, 1)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        last_response: HttpResponse | None = None
        for _ in range(self._max_attempts):
            response = self._client.request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=timeout_seconds,
            )
            last_response = response
            if response.status_code != 429:
                return _raise_for_status(response)

        raise ExchangeRateLimitError("Exchange rate limit exceeded.")


def _raise_for_status(response: HttpResponse) -> HttpResponse:
    if 200 <= response.status_code < 300:
        return response

    if response.status_code == 429:
        raise ExchangeRateLimitError("Exchange rate limit exceeded.")

    raise ExchangeRequestError(f"Exchange request failed with status {response.status_code}.")


class UrlLibHttpClient:
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_seconds: int = 30,
    ) -> HttpResponse:
        body_bytes = body.encode("utf-8") if body is not None else None
        request = Request(url=url, data=body_bytes, headers=headers or {}, method=method.upper())
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status_code=response.status,
                    body=response.read().decode("utf-8"),
                )
        except HTTPError as error:
            return HttpResponse(status_code=error.code, body=error.read().decode("utf-8"))
