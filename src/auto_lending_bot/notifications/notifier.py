import logging
from urllib.parse import urlencode

from auto_lending_bot.config import Settings
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

    def _send_telegram(self, message: str) -> None:
        if self._settings is None:
            return
        if not self._settings.telegram_bot_token or not self._settings.telegram_chat_id:
            return

        body = urlencode({"chat_id": self._settings.telegram_chat_id, "text": message})
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
