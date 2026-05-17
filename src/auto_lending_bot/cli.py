import argparse
from inspect import Parameter, signature
import sys
import time

import uvicorn

from auto_lending_bot.api.app import create_app
from auto_lending_bot.bot.factory import create_default_bot_runner
from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.config import Settings, load_effective_settings, load_settings, sqlite_path_from_url
from auto_lending_bot.integrations.factory import create_exchange_client
from auto_lending_bot.logging import configure_logging
from auto_lending_bot.operations.exchange_actions import ExchangeActionService
from auto_lending_bot.operations.maintenance import MaintenanceActionService
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.factory import RepositoryBundle, create_repository_bundle
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT
from auto_lending_bot.safety import (
    SafetyError,
    validate_run_settings,
    validate_transfer_limits,
    validate_transfer_settings,
)


def main() -> None:
    raise SystemExit(run_cli())


def run_cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    base_settings = load_settings()
    settings = load_effective_settings(
        base_settings.database_url,
        profile_context=DEFAULT_PROFILE_CONTEXT,
    )
    repositories = create_repository_bundle(settings)
    maintenance_actions = MaintenanceActionService(
        settings=settings,
        repositories=repositories,
        profile_context=DEFAULT_PROFILE_CONTEXT,
    )
    exchange_actions = ExchangeActionService(
        settings=settings,
        repositories=repositories,
        profile_context=DEFAULT_PROFILE_CONTEXT,
    )

    if args.command == "init-db":
        initialize_database(settings.database_url)
        print(f"Initialized database: {sqlite_path_from_url(settings.database_url)}")
        return 0

    if args.command == "status":
        initialize_database(settings.database_url)
        print(_format_status(settings, repositories))
        return 0

    if args.command == "cleanup":
        initialize_database(settings.database_url)
        result = maintenance_actions.cleanup_market_data()
        print(
            f"Deleted {result['deleted_count']} old market data row(s) "
            f"({result['market_rate_deleted_count']} market rate, "
            f"{result['market_analysis_deleted_count']} market analysis)."
        )
        return 0

    if args.command == "sync-history":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        result = maintenance_actions.sync_history(_exchange_client(settings))
        print(
            f"Synced {result['changed_count']} lending history row(s) "
            f"for {result['currency']}."
        )
        return 0

    if args.command == "sync-open-offers":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        result = maintenance_actions.sync_open_offers(_exchange_client(settings))
        print(f"Synced {result['changed_count']} open loan offer row(s).")
        return 0

    if args.command == "transfer-preview":
        try:
            validate_transfer_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        exchange = _exchange_client(settings)
        previews = exchange_actions.transfer_previews(exchange)
        if not previews:
            print("No exchange balances match TRANSFERABLE_CURRENCIES.")
            return 0
        for preview in previews:
            print(
                f"Would transfer {preview.amount:g} {preview.currency} "
                f"from {preview.source} to {preview.destination}."
            )
        return 0

    if args.command == "transfer-funds":
        try:
            validate_transfer_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        if not settings.dry_run and not args.confirm_live:
            print("Live transfer requires --confirm-live.", file=sys.stderr)
            return 2

        exchange = _exchange_client(settings)
        previews = exchange_actions.transfer_previews(exchange)
        try:
            validate_transfer_limits(settings, previews)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        if settings.dry_run:
            print(f"Dry run: would transfer {len(previews)} balance(s).")
            return 0

        result = exchange_actions.transfer_funds_response(exchange, previews)
        print(f"Transferred {result['transferred_count']} balance(s) to lending wallet.")
        return 0

    if args.command == "record-market-analysis":
        try:
            validate_run_settings(settings)
        except SafetyError as error:
            print(f"Safety check failed: {error}", file=sys.stderr)
            return 2

        initialize_database(settings.database_url)
        exchange = _exchange_client(settings)
        result = maintenance_actions.record_market_analysis(
            exchange=exchange,
            currency=args.currency,
            levels=args.levels,
        )
        print(
            f"Recorded {result['changed_count']} market analysis rate row(s) "
            f"for {', '.join(result['currencies'])}."
        )
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
        exchange = _exchange_client(settings)
        result = exchange_actions.cancel_open_offers_response(exchange)
        if result["dry_run"]:
            print(f"Dry run: would cancel {result['would_cancel_count']} open loan offer(s).")
            return 0

        print(f"Canceled {result['canceled_count']} open loan offer(s).")
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
            create_app(),
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
        recovered_count = repositories.bot_runs.fail_running(
            "Recovered interrupted run before startup."
        )
        if recovered_count:
            print(f"Recovered {recovered_count} interrupted run(s).")
        if not settings.dry_run:
            print("WARNING: live lending is enabled. Real loan offers may be created.")
        _run_bot_with_reloaded_settings(settings)
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
    subparsers.add_parser("transfer-preview", help="Preview exchange-to-lending transfers.")
    transfer_parser = subparsers.add_parser(
        "transfer-funds", help="Transfer exchange balances to lending after safety confirmation."
    )
    transfer_parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required when BOT_DRY_RUN=false because real balances will be transferred.",
    )
    market_analysis_parser = subparsers.add_parser(
        "record-market-analysis", help="Record lendbook levels for market analysis."
    )
    market_analysis_parser.add_argument("--currency", help="Currency to record.")
    market_analysis_parser.add_argument("--levels", type=int, help="Number of lendbook levels.")
    cancel_parser = subparsers.add_parser(
        "cancel-open-offers", help="Cancel open loan offers after safety confirmation."
    )
    cancel_parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required when BOT_DRY_RUN=false because real exchange offers will be canceled.",
    )
    return parser


def _create_runner(settings: Settings) -> BotRunner:
    return create_default_bot_runner(settings, exchange_factory=create_exchange_client)


def _exchange_client(settings: Settings) -> object:
    parameters = list(signature(create_exchange_client).parameters.values())
    accepts_profile_context = any(
        parameter.kind == Parameter.VAR_POSITIONAL for parameter in parameters
    ) or sum(
        1
        for parameter in parameters
        if parameter.kind
        in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}
    ) > 1
    if accepts_profile_context:
        return create_exchange_client(settings, DEFAULT_PROFILE_CONTEXT)
    return create_exchange_client(settings)


def _run_bot_with_reloaded_settings(initial_settings: Settings) -> None:
    loops_completed = 0
    settings = initial_settings
    database_url = initial_settings.database_url
    try:
        while settings.max_loops <= 0 or loops_completed < settings.max_loops:
            validate_run_settings(settings)
            created_offers = _create_runner(settings).run_once_with_retry()
            loops_completed += 1

            settings = load_effective_settings(
                database_url,
                profile_context=DEFAULT_PROFILE_CONTEXT,
            )
            if settings.max_loops <= 0 or loops_completed < settings.max_loops:
                time.sleep(_sleep_seconds(settings, created_offers))
    except KeyboardInterrupt:
        return


def _sleep_seconds(settings: Settings, created_offers: int) -> int:
    if created_offers > 0:
        return settings.bot_sleep_seconds

    return settings.bot_inactive_sleep_seconds


def _format_status(settings: Settings, repositories: RepositoryBundle) -> str:
    bot_runs = repositories.bot_runs
    loan_offers = repositories.loan_offers
    market_rates = repositories.market_rates
    active_loans = repositories.active_loans
    lending_history = repositories.lending_history
    open_offers = repositories.open_offers
    profile_context = DEFAULT_PROFILE_CONTEXT
    latest_run = bot_runs.latest(profile_context)

    lines = [
        f"Label: {settings.bot_label}",
        f"Database: {sqlite_path_from_url(settings.database_url)}",
        f"Exchange: {settings.exchange}",
        f"Dry run: {settings.dry_run}",
        f"Live trading allowed: {settings.allow_live_trading}",
        f"Bot runs: {bot_runs.count(profile_context)}",
        f"Loan offers: {loan_offers.count(profile_context)}",
        f"Open loan offers: {open_offers.count(profile_context)}",
        f"Active loans: {active_loans.count(profile_context)}",
        f"Lending history: {lending_history.count(profile_context)}",
        f"Market rates: {market_rates.count(profile_context)}",
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
    exchange = _exchange_client(settings)
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
