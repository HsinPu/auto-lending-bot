from auto_lending_bot.config import Settings
from auto_lending_bot.domain.models import ActiveLoan
from auto_lending_bot.domain.models import LoanOffer
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


def test_notifier_prefixes_telegram_message() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(
        settings=_settings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
            notify_prefix="[Bot]",
        ),
        http_client=http_client,
    )

    notifier.info("hello world")

    assert http_client.requests[0]["body"] == "chat_id=chat&text=%5BBot%5D+hello+world"


def test_notifier_sends_run_summary() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(
        settings=_settings(telegram_bot_token="token", telegram_chat_id="chat"),
        http_client=http_client,
    )

    notifier.run_summary(created_offers=3, active_loans=2, dry_run=True)

    assert http_client.requests[0]["body"] == (
        "chat_id=chat&text=Completed+dry-run+run+with+3+offer%28s%29."
        "+Active+loans%3A+2."
    )


def test_notifier_sends_filled_loan_message() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(
        settings=_settings(telegram_bot_token="token", telegram_chat_id="chat"),
        http_client=http_client,
    )

    notifier.loan_filled(
        ActiveLoan(
            currency="BTC",
            amount=0.05,
            daily_rate=0.00008,
            duration_days=2,
            external_loan_id="loan-1",
        )
    )

    assert http_client.requests[0]["body"] == (
        "chat_id=chat&text=Filled+BTC+loan+loan-1%3A+0.05+at+0.00008000+daily+rate+"
        "for+2+day%28s%29."
    )


def test_notifier_sends_xday_offer_message() -> None:
    http_client = FakeHttpClient()
    notifier = Notifier(
        settings=_settings(telegram_bot_token="token", telegram_chat_id="chat"),
        http_client=http_client,
    )

    notifier.xday_offer(
        LoanOffer(currency="BTC", amount=0.05, daily_rate=0.00012, duration_days=30),
        dry_run=True,
    )

    assert http_client.requests[0]["body"] == (
        "chat_id=chat&text=Long-duration+dry-run+BTC+offer%3A+0.05+at+"
        "0.00012000+daily+rate+for+30+day%28s%29."
    )


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


def _settings(
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    notify_prefix: str = "",
) -> Settings:
    return Settings(
        allow_live_trading=False,
        api_key="",
        api_secret="",
        bitfinex_enable_live_offers=False,
        bot_label="Auto Lending Bot",
        bot_sleep_seconds=60,
        bot_inactive_sleep_seconds=300,
        auto_rebalance_open_offers=False,
        auto_cancel_open_offers=False,
        keep_stuck_orders=True,
        dry_run=True,
        exchange="mock",
        http_timeout_seconds=30,
        market_rate_retention_days=30,
        market_analysis_retention_days=30,
        market_analysis_currencies=(),
        market_analysis_levels=10,
        market_analysis_min_samples=0,
        market_analysis_max_age_seconds=0,
        market_analysis_method="off",
        market_analysis_percentile=75,
        market_analysis_macd_short_samples=3,
        market_analysis_macd_long_samples=10,
        market_analysis_macd_short_seconds=0,
        market_analysis_macd_long_seconds=0,
        market_analysis_multiplier=1.0,
        max_loops=1,
        retry_attempts=3,
        retry_backoff_seconds=30,
        output_currency="BTC",
        transferable_currencies=(),
        smoke_test_currency="BTC",
        strategy_debug=False,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        notify_prefix=notify_prefix,
        notify_caught_exception=False,
        notify_summary_minutes=0,
        notify_xday_threshold=False,
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
        max_active_amount=None,
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
