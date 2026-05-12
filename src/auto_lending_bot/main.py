from auto_lending_bot.config import load_settings
from auto_lending_bot.bot.runner import BotRunner
from auto_lending_bot.integrations.mock_exchange import create_exchange_client
from auto_lending_bot.logging import configure_logging
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import (
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
)


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    initialize_database(settings.database_url)

    runner = BotRunner(
        settings=settings,
        exchange=create_exchange_client(settings.exchange),
        bot_runs=BotRunRepository(settings.database_url),
        loan_offers=LoanOfferRepository(settings.database_url),
        market_recorder=MarketRecorder(MarketRateRepository(settings.database_url)),
        notifier=Notifier(),
    )
    runner.run()


if __name__ == "__main__":
    main()
