import hashlib
import hmac
import json
import time

from auto_lending_bot.domain.models import CurrencyBalance, LoanOffer, LoanOrder
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.http import HttpClient


class PoloniexClient:
    def __init__(self, api_key: str, api_secret: str, http_client: HttpClient) -> None:
        if not api_key or not api_secret:
            msg = "Poloniex API key and secret are required."
            raise ExchangeAuthenticationError(msg)

        self._api_key = api_key
        self._api_secret = api_secret
        self._http_client = http_client

    def get_lending_balances(self) -> list[CurrencyBalance]:
        raise NotImplementedError("Read-only Poloniex balances are planned for phase five.")

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        raise NotImplementedError("Read-only Poloniex loan orders are planned for phase five.")

    def get_open_loan_offers(self) -> list[LoanOffer]:
        raise NotImplementedError("Read-only Poloniex loan offers are planned for phase five.")

    def create_loan_offer(self, offer: LoanOffer) -> str:
        raise NotImplementedError("Live Poloniex lending is planned for phase six.")

    def cancel_loan_offer(self, offer_id: str) -> None:
        raise NotImplementedError("Live Poloniex lending is planned for phase six.")

    def build_signed_headers(self, payload: dict[str, str]) -> dict[str, str]:
        body = _encode_payload(payload)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        return {"Key": self._api_key, "Sign": signature}

    def build_private_payload(self, command: str) -> dict[str, str]:
        return {"command": command, "nonce": str(int(time.time() * 1000))}


def _encode_payload(payload: dict[str, str]) -> str:
    return "&".join(f"{key}={value}" for key, value in sorted(payload.items()))


def parse_json_response(body: str) -> dict[str, object]:
    return json.loads(body)
