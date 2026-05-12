import argparse
import sys

import uvicorn

from auto_lending_bot.api.app import create_app
from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings, load_settings, sqlite_path_from_url
from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.logging import configure_logging
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketRateRepository,
    OpenLoanOfferRepository,
)
from auto_lending_bot.safety import SafetyError, validate_run_settings


def main() -> None:
    raise SystemExit(run_cli())


def run_cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "init-db":
        initialize_database(settings.database_url)
        print(f"Initialized database: {sqlite_path_from_url(settings.database_url)}")
        return 0

    if args.command == "status":
        initialize_database(settings.database_url)
        print(_format_status(settings))
        return 0

    if args.command == "cleanup":
        initialize_database(settings.database_url)
        deleted_count = MarketRateRepository(settings.database_url).delete_older_than_days(
            settings.market_rate_retention_days
        )
        print(f"Deleted {deleted_count} old market rate row(s).")
        return 0

    if args.command == "sync-history":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        entries = create_exchange_client(settings).get_lending_history(settings.smoke_test_currency)
        changed_count = LendingHistoryRepository(settings.database_url).upsert_many(entries)
        print(
            f"Synced {changed_count} lending history row(s) "
            f"for {settings.smoke_test_currency.upper()}."
        )
        return 0

    if args.command == "sync-open-offers":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        offers = create_exchange_client(settings).get_open_loan_offers()
        OpenLoanOfferRepository(settings.database_url).replace_all(offers)
        print(f"Synced {len(offers)} open loan offer row(s).")
        return 0

    if args.command == "cancel-open-offers":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        if not settings.dry_run and not args.confirm_live:
            print("Live cancel requires --confirm-live.", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        exchange = create_exchange_client(settings)
        offers = exchange.get_open_loan_offers()
        if settings.dry_run:
            print(f"Dry run: would cancel {len(offers)} open loan offer(s).")
            return 0

        canceled_count = _cancel_open_offers(exchange, offers)
        OpenLoanOfferRepository(settings.database_url).replace_all([])
        print(f"Canceled {canceled_count} open loan offer(s).")
        return 0

    if args.command == "smoke-exchange":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        print(_smoke_exchange(settings))
        return 0

    if args.command == "serve-api":
        uvicorn.run(
            create_app(settings),
            host=args.host,
            port=args.port,
            log_level=settings.log_level.lower(),
        )
        return 0

    if args.command == "run":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        configure_logging(settings.log_level)
        initialize_database(settings.database_url)
        recovered_count = BotRunRepository(settings.database_url).fail_running(
            "Recovered interrupted run before startup."
        )
        if recovered_count:
            print(f"Recovered {recovered_count} interrupted run(s).")
        if not settings.dry_run:
            print("WARNING: live lending is enabled. Real loan offers may be created.")
        _create_runner(settings).run()
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-lending-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Initialize the SQLite database.")
    subparsers.add_parser("cleanup", help="Delete old market-rate rows.")
    subparsers.add_parser("run", help="Run the lending bot.")
    serve_api_parser = subparsers.add_parser("serve-api", help="Run the read-only HTTP API.")
    serve_api_parser.add_argument("--host", default="127.0.0.1", help="API bind host.")
    serve_api_parser.add_argument("--port", type=int, default=8000, help="API bind port.")
    subparsers.add_parser("smoke-exchange", help="Read balances and lendbook without lending.")
    subparsers.add_parser("status", help="Show bot status from SQLite.")
    subparsers.add_parser("sync-history", help="Sync lending history from the exchange.")
    subparsers.add_parser("sync-open-offers", help="Sync open loan offers from the exchange.")
    cancel_parser = subparsers.add_parser(
        "cancel-open-offers", help="Cancel open loan offers after safety confirmation."
    )
    cancel_parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required when BOT_DRY_RUN=false because real exchange offers will be canceled.",
    )
    return parser


def _cancel_open_offers(exchange, offers: list[LoanOffer]) -> int:
    canceled_count = 0
    for offer in offers:
        if not offer.external_offer_id:
            continue
        exchange.cancel_loan_offer(offer.external_offer_id)
        canceled_count += 1
    return canceled_count


def _create_runner(settings: Settings) -> BotRunner:
    return BotRunner(
        settings=settings,
        exchange=create_exchange_client(settings),
        bot_runs=BotRunRepository(settings.database_url),
        loan_offers=LoanOfferRepository(settings.database_url),
        active_loans=ActiveLoanRepository(settings.database_url),
        open_offers=OpenLoanOfferRepository(settings.database_url),
        market_recorder=MarketRecorder(MarketRateRepository(settings.database_url)),
        notifier=Notifier(settings=settings),
    )


def _format_status(settings: Settings) -> str:
    bot_runs = BotRunRepository(settings.database_url)
    loan_offers = LoanOfferRepository(settings.database_url)
    market_rates = MarketRateRepository(settings.database_url)
    active_loans = ActiveLoanRepository(settings.database_url)
    lending_history = LendingHistoryRepository(settings.database_url)
    open_offers = OpenLoanOfferRepository(settings.database_url)
    latest_run = bot_runs.latest()

    lines = [
        f"Label: {settings.bot_label}",
        f"Database: {sqlite_path_from_url(settings.database_url)}",
        f"Exchange: {settings.exchange}",
        f"Dry run: {settings.dry_run}",
        f"Live trading allowed: {settings.allow_live_trading}",
        f"Bot runs: {bot_runs.count()}",
        f"Loan offers: {loan_offers.count()}",
        f"Open loan offers: {open_offers.count()}",
        f"Active loans: {active_loans.count()}",
        f"Lending history: {lending_history.count()}",
        f"Market rates: {market_rates.count()}",
    ]

    if latest_run is None:
        lines.append("Latest run: none")
    else:
        lines.append(
            "Latest run: "
            f"#{latest_run['id']} {latest_run['status']} "
            f"started={latest_run['started_at']} finished={latest_run['finished_at']}"
        )

    return "\n".join(lines)


def _smoke_exchange(settings: Settings) -> str:
    exchange = create_exchange_client(settings)
    balances = exchange.get_lending_balances()
    orders = exchange.get_loan_orders(settings.smoke_test_currency)
    best_rate = max((order.daily_rate for order in orders), default=0)

    return "\n".join(
        [
            f"Exchange: {settings.exchange}",
            f"Currency: {settings.smoke_test_currency.upper()}",
            f"Lending balances: {len(balances)}",
            f"Loan orders: {len(orders)}",
            f"Best daily rate: {best_rate:.8f}",
        ]
    )
