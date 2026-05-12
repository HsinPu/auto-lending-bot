import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from auto_lending_bot.domain.models import (
    ActiveLoan,
    CurrencyBalance,
    LendingHistoryEntry,
    LoanOffer,
    LoanOrder,
)
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.errors import ExchangeRequestError
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

        balances = []
        for item in response:
            if not isinstance(item, dict) or item.get("type") != "deposit":
                continue

            amount = _optional_float(item.get("available"))
            currency = item.get("currency")
            if amount is None or amount <= 0 or not currency:
                continue

            balances.append(CurrencyBalance(currency=str(currency).upper(), amount=amount))

        return balances

    def get_loan_orders(self, currency: str) -> list[LoanOrder]:
        response = self._public_query(f"/v1/lendbook/{currency.lower()}")
        asks = response.get("asks", []) if isinstance(response, dict) else []
        if not isinstance(asks, list):
            return []

        orders = []
        for item in asks:
            if not isinstance(item, dict):
                continue

            amount = _optional_float(item.get("amount"))
            rate = _optional_bitfinex_rate_to_daily_rate(item.get("rate"))
            if amount is None or rate is None:
                continue

            orders.append(LoanOrder(currency=currency.upper(), amount=amount, daily_rate=rate))

        return orders

    def get_open_loan_offers(self) -> list[LoanOffer]:
        response = self._private_query("/v1/offers", {})
        if not isinstance(response, list):
            return []

        offers = []
        for item in response:
            if not isinstance(item, dict) or item.get("direction") != "lend":
                continue

            amount = _optional_float(item.get("remaining_amount", item.get("amount")))
            rate = _optional_bitfinex_rate_to_daily_rate(item.get("rate"))
            duration_days = _optional_int(item.get("period", 2))
            currency = item.get("currency")
            if amount is None or amount <= 0 or rate is None or duration_days is None or not currency:
                continue

            offers.append(
                LoanOffer(
                    currency=str(currency).upper(),
                    amount=amount,
                    daily_rate=rate,
                    duration_days=duration_days,
                    external_offer_id=str(item.get("id", "")),
                )
            )

        return offers

    def get_active_loans(self) -> list[ActiveLoan]:
        response = self._private_query("/v1/credits", {})
        if not isinstance(response, list):
            return []

        active_loans = []
        for item in response:
            if not isinstance(item, dict):
                continue

            amount = _optional_float(item.get("amount"))
            rate = _optional_bitfinex_rate_to_daily_rate(item.get("rate"))
            duration_days = _optional_int(item.get("period", item.get("duration", 2)))
            currency = item.get("currency")
            external_loan_id = item.get("id")
            if amount is None or rate is None or duration_days is None or not currency:
                continue

            active_loans.append(
                ActiveLoan(
                    currency=str(currency).upper(),
                    amount=amount,
                    daily_rate=rate,
                    duration_days=duration_days,
                    external_loan_id=str(external_loan_id or ""),
                )
            )

        return active_loans

    def get_lending_history(self, currency: str, limit: int = 500) -> list[LendingHistoryEntry]:
        response = self._private_query(
            "/v1/history",
            {
                "currency": currency.upper(),
                "wallet": "deposit",
                "limit": limit,
            },
        )
        if not isinstance(response, list):
            return []

        entries = []
        for item in response:
            if not isinstance(item, dict):
                continue
            if "Margin Funding Payment" not in str(item.get("description", "")):
                continue

            earned = _optional_float(item.get("amount"))
            if earned is None:
                continue

            interest = earned / 0.85
            fee = earned - interest
            timestamp = _format_bitfinex_timestamp(item.get("timestamp"))
            entries.append(
                LendingHistoryEntry(
                    currency=currency.upper(),
                    amount=0.0,
                    daily_rate=0.0,
                    duration_days=0.0,
                    interest=interest,
                    fee=fee,
                    earned=earned,
                    opened_at=timestamp,
                    closed_at=timestamp,
                    external_entry_id=str(item.get("id", item.get("timestamp", ""))),
                )
            )

        return entries

    def create_loan_offer(self, offer: LoanOffer) -> str:
        response = self._private_query(
            "/v1/offer/new",
            {
                "currency": offer.currency,
                "amount": str(offer.amount),
                "rate": str(round(offer.daily_rate, 10) * 36500),
                "period": offer.duration_days,
                "direction": "lend",
            },
        )
        if not isinstance(response, dict):
            return ""

        return str(response.get("id", ""))

    def cancel_loan_offer(self, offer_id: str) -> None:
        self._private_query("/v1/offer/cancel", {"offer_id": offer_id})

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
        return _raise_for_api_error(parse_json_response(response.body))

    def _private_query(self, path: str, payload: dict[str, object]) -> object:
        request_payload = {"request": path, **payload}
        response = self._http_client.request(
            method="POST",
            url=f"https://api.bitfinex.com{path}",
            headers=self.build_signed_headers(request_payload),
            timeout_seconds=self._timeout_seconds,
        )
        return _raise_for_api_error(json.loads(response.body))


def _encode_payload(payload: dict[str, object]) -> str:
    raw_payload = json.dumps(payload, separators=(",", ":"))
    return base64.standard_b64encode(raw_payload.encode("utf-8")).decode("utf-8")


def _bitfinex_rate_to_daily_rate(rate: object) -> float:
    return float(rate) / 36500


def _optional_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_bitfinex_rate_to_daily_rate(rate: object) -> float | None:
    raw_rate = _optional_float(rate)
    if raw_rate is None:
        return None

    return raw_rate / 36500


def _format_bitfinex_timestamp(value: object) -> str:
    raw_timestamp = _optional_float(value)
    if raw_timestamp is None:
        return ""

    return datetime.fromtimestamp(raw_timestamp, UTC).strftime("%Y-%m-%d %H:%M:%S")


def _raise_for_api_error(response: object):
    if isinstance(response, dict) and "message" in response:
        raise ExchangeRequestError(str(response["message"]))

    return response


def parse_json_response(body: str) -> dict[str, object]:
    return json.loads(body)
