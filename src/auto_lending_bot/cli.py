import argparse
import sys

from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings, load_settings, sqlite_path_from_url
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.logging import configure_logging
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
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
    subparsers.add_parser("status", help="Show bot status from SQLite.")
    return parser


def _create_runner(settings: Settings) -> BotRunner:
    return BotRunner(
        settings=settings,
        exchange=create_exchange_client(settings),
        bot_runs=BotRunRepository(settings.database_url),
        loan_offers=LoanOfferRepository(settings.database_url),
        market_recorder=MarketRecorder(MarketRateRepository(settings.database_url)),
        notifier=Notifier(),
    )


def _format_status(settings: Settings) -> str:
    bot_runs = BotRunRepository(settings.database_url)
    loan_offers = LoanOfferRepository(settings.database_url)
    market_rates = MarketRateRepository(settings.database_url)
    latest_run = bot_runs.latest()

    lines = [
        f"Label: {settings.bot_label}",
        f"Database: {sqlite_path_from_url(settings.database_url)}",
        f"Exchange: {settings.exchange}",
        f"Dry run: {settings.dry_run}",
        f"Live trading allowed: {settings.allow_live_trading}",
        f"Bot runs: {bot_runs.count()}",
        f"Loan offers: {loan_offers.count()}",
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
