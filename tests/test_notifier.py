from auto_lending_bot.config import Settings
from auto_lending_bot.integrations.http import HttpResponse
from auto_lending_bot.notifications.notifier import Notifier


def test_notifier_skips_telegram_without_credentials() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(settings=_settings(), http_client=http_client)

    notifier.info("hello")

    assert http_client.requests == []


def test_notifier_sends_telegram_message() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(
        settings=_settings(telegram_bot_token="token", telegram_chat_id="chat"),
        http_client=http_client,
    )

    notifier.info("hello world")

    assert len(http_client.requests) == 1
    request = http_client.requests[0]
    assert request["url"] == "https://api.telegram.org/bottoken/sendMessage"
    assert request["body"] == "chat_id=chat&text=hello+world"


class FakeHttpClient:
    def __init__(self) -> None:
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
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return HttpResponse(status_code=200, body='{"ok":true}')


def _settings(telegram_bot_token: str = "", telegram_chat_id: str = "") -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="",
        api_secret="",
        bitfinex_enable_live_offers=False,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        auto_rebalance_open_offers=False,
        auto_cancel_open_offers=False,
        dry_run=True,
        exchange="mock",
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
        smoke_test_currency="BTC",
        strategy_debug=False,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        hide_coins=True,
        gap_mode="off",
        gap_bottom=0,
        gap_top=0,
        xday_threshold=0,
        xdays=2,
        xday_spread=0,
        frr_as_min=False,
        frr_delta=0,
        max_amount_to_lend=None,
        max_single_offer_amount=None,
        max_total_lend_amount=None,
        min_daily_rate=0.00005,
        max_daily_rate=0.05,
        min_loan_size=0.01,
        max_percent_to_lend=100,
        max_to_lend_rate=0,
        end_date=None,
        spread_lend=3,
        database_url="sqlite:///data/test.db",
        log_level="INFO",
    )
