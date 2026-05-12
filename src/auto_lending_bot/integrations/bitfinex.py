import base64
import hashlib
import hmac
import json

from auto_lending_bot.domain.models import CurrencyBalance, LoanOffer, LoanOrder
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.http import HttpClient


class BitfinexClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        http_client: HttpClient,
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key or not api_secret:
            msg = "Bitfinex API key and secret are required."
            raise ExchangeAuthenticationError(msg)

        self._api_key = api_key
        self._api_secret = api_secret
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds

    def get_lending_balances(self) -> list[CurrencyBalance]:
        response = self._private_query("/v1/balances", {})
        if not isinstance(response, list):
            return []

        return [
            CurrencyBalance(currency=item["currency"].upper(), amount=float(item["available"]))
            for item in response
            if item.get("type") == "deposit" and float(item.get("available", 0)) > 0
        ]

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        response = self._public_query(f"/v1/lendbook/{currency.lower()}")
        asks = response.get("asks", []) if isinstance(response, dict) else []
        if not isinstance(asks, list):
            return []

        return [
            LoanOrder(
                currency=currency.upper(),
                amount=float(item["amount"]),
                daily_rate=_bitfinex_rate_to_daily_rate(item["rate"]),
            )
            for item in asks
        ]

    def get_open_loan_offers(self) -> list[LoanOffer]:
        response = self._private_query("/v1/offers", {})
        if not isinstance(response, list):
            return []

        return [
            LoanOffer(
                currency=item["currency"].upper(),
                amount=float(item.get("remaining_amount", item["amount"])),
                daily_rate=_bitfinex_rate_to_daily_rate(item["rate"]),
                duration_days=int(float(item.get("period", 2))),
            )
            for item in response
            if item.get("direction") == "lend" and float(item.get("remaining_amount", 0)) > 0
        ]

    def create_loan_offer(self, offer: LoanOffer) -> str:
        raise NotImplementedError("Live Bitfinex lending is not enabled yet.")

    def cancel_loan_offer(self, offer_id: str) -> None:
        raise NotImplementedError("Live Bitfinex lending is not enabled yet.")

    def build_signed_headers(self, payload: dict[str, object]) -> dict[str, str]:
        encoded_payload = _encode_payload(payload)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha384,
        ).hexdigest()
        return {
            "X-BFX-APIKEY": self._api_key,
            "X-BFX-PAYLOAD": encoded_payload,
            "X-BFX-SIGNATURE": signature,
        }

    def _public_query(self, path: str) -> dict[str, object]:
        response = self._http_client.request(
            method="GET",
            url=f"https://api.bitfinex.com{path}",
            timeout_seconds=self._timeout_seconds,
        )
        return parse_json_response(response.body)

    def _private_query(self, path: str, payload: dict[str, object]) -> object:
        request_payload = {"request": path, **payload}
        response = self._http_client.request(
            method="POST",
            url=f"https://api.bitfinex.com{path}",
            headers=self.build_signed_headers(request_payload),
            timeout_seconds=self._timeout_seconds,
        )
        return json.loads(response.body)


def _encode_payload(payload: dict[str, object]) -> str:
    raw_payload = json.dumps(payload, separators=(",", ":"))
    return base64.standard_b64encode(raw_payload.encode("utf-8")).decode("utf-8")


def _bitfinex_rate_to_daily_rate(rate: object) -> float:
    return float(rate) / 36500


def parse_json_response(body: str) -> dict[str, object]:
    return json.loads(body)
