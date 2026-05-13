import logging
from urllib.parse import urlencode

from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import ActiveLoan, LoanOffer
from auto_lending_bot.integrations.http import HttpClient, UrlLibHttpClient


class Notifier:
    def __init__(self, settings: Settings | None = None, http_client: HttpClient | None = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._settings = settings
        self._http_client = http_client or UrlLibHttpClient()

    def info(self, message: str) -> None:
        self._logger.info(message)
        self._send_telegram(message)

    def error(self, message: str) -> None:
        self._logger.error(message)
        self._send_telegram(f"ERROR: {message}")

    def run_summary(self, created_offers: int, active_loans: int, dry_run: bool) -> None:
        mode = "dry-run" if dry_run else "live"
        self.info(
            f"Completed {mode} run with {created_offers} offer(s). "
            f"Active loans: {active_loans}."
        )

    def loan_filled(self, active_loan: ActiveLoan) -> None:
        self.info(
            f"Filled {active_loan.currency} loan {active_loan.external_loan_id}: "
            f"{active_loan.amount:g} at {active_loan.daily_rate:.8f} daily rate "
            f"for {active_loan.duration_days} day(s)."
        )

    def periodic_summary(self, message: str) -> None:
        self.info(message)

    def xday_offer(self, offer: LoanOffer, dry_run: bool) -> None:
        mode = "dry-run" if dry_run else "live"
        self.info(
            f"Long-duration {mode} {offer.currency} offer: {offer.amount:g} "
            f"at {offer.daily_rate:.8f} daily rate for {offer.duration_days} day(s)."
        )

    def _send_telegram(self, message: str) -> None:
        if self._settings is None:
            return
        if not self._settings.telegram_bot_token or not self._settings.telegram_chat_id:
            return

        body = urlencode(
            {"chat_id": self._settings.telegram_chat_id, "text": self._message(message)}
        )
        try:
            self._http_client.request(
                method="POST",
                url=f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body=body,
                timeout_seconds=self._settings.http_timeout_seconds,
            )
        except Exception:
            self._logger.exception("Failed to send Telegram notification.")

    def _message(self, message: str) -> str:
        if self._settings is None or not self._settings.notify_prefix:
            return message

        return f"{self._settings.notify_prefix} {message}"
