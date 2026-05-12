import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from auto_lending_bot.domain.models import CurrencyBalance, LoanOffer, LoanOrder
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.http import HttpClient


class PoloniexClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        http_client: HttpClient,
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key or not api_secret:
            msg = "Poloniex API key and secret are required."
            raise ExchangeAuthenticationError(msg)

        self._api_key = api_key
        self._api_secret = api_secret
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds

    def get_lending_balances(self) -> list[CurrencyBalance]:
        response = self._private_query(
            command="returnAvailableAccountBalances",
            payload={"account": "lending"},
        )
        lending_balances = response.get("lending", {})
        if not isinstance(lending_balances, dict):
            return []

        return [
            CurrencyBalance(currency=currency, amount=float(amount))
            for currency, amount in lending_balances.items()
            if float(amount) > 0
        ]

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        response = self._public_query("returnLoanOrders", {"currency": currency})
        offers = response.get("offers", [])
        if not isinstance(offers, list):
            return []

        return [
            LoanOrder(
                currency=currency,
                amount=float(item["amount"]),
                daily_rate=float(item["rate"]),
            )
            for item in offers
        ]

    def get_open_loan_offers(self) -> list[LoanOffer]:
        response = self._private_query(command="returnOpenLoanOffers", payload={})
        if not isinstance(response, dict):
            return []

        offers = []
        for currency, currency_offers in response.items():
            if not isinstance(currency_offers, list):
                continue

            for item in currency_offers:
                offers.append(
                    LoanOffer(
                        currency=currency,
                        amount=float(item["amount"]),
                        daily_rate=float(item["rate"]),
                        duration_days=int(float(item.get("duration", 2))),
                    )
                )

        return offers

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

    def _public_query(self, command: str, payload: dict[str, str]) -> dict[str, object]:
        query = urlencode({"command": command, **payload})
        response = self._http_client.request(
            method="GET",
            url=f"https://poloniex.com/public?{query}",
            timeout_seconds=self._timeout_seconds,
        )
        return parse_json_response(response.body)

    def _private_query(self, command: str, payload: dict[str, str]) -> dict[str, object]:
        request_payload = {**self.build_private_payload(command), **payload}
        body = _encode_payload(request_payload)
        response = self._http_client.request(
            method="POST",
            url="https://poloniex.com/tradingApi",
            headers=self.build_signed_headers(request_payload),
            body=body,
            timeout_seconds=self._timeout_seconds,
        )
        return parse_json_response(response.body)


def _encode_payload(payload: dict[str, str]) -> str:
    return urlencode(sorted(payload.items()))


def parse_json_response(body: str) -> dict[str, object]:
    return json.loads(body)
