import logging
import time

from auto_lending_bot.config import Settings
from auto_lending_bot.domain.strategy import build_lending_decision
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.repository import BotRunRepository, LoanOfferRepository

logger = logging.getLogger(__name__)


class BotRunner:
    def __init__(
        self,
        settings: Settings,
        exchange: ExchangeClient,
        bot_runs: BotRunRepository,
        loan_offers: LoanOfferRepository,
        market_recorder: MarketRecorder,
        notifier: Notifier,
    ) -> None:
        self._settings = settings
        self._exchange = exchange
        self._bot_runs = bot_runs
        self._loan_offers = loan_offers
        self._market_recorder = market_recorder
        self._notifier = notifier

    def run(self) -> None:
        loops_completed = 0
        while self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
            self.run_once()
            loops_completed += 1

            if self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
                time.sleep(self._settings.bot_sleep_seconds)

    def run_once(self) -> None:
        bot_run_id = self._bot_runs.start(dry_run=self._settings.dry_run)
        created_offers = 0

        try:
            balances = self._exchange.get_lending_balances()
            for balance in balances:
                orders = self._exchange.get_loan_orders(balance.currency)
                self._market_recorder.record_orders(orders)
                decision = build_lending_decision(
                    balance=balance,
                    order_book=orders,
                    min_daily_rate=self._settings.min_daily_rate,
                    min_loan_size=self._settings.min_loan_size,
                    spread_lend=self._settings.spread_lend,
                )

                logger.info("%s: %s", decision.currency, decision.reason)
                for offer in decision.offers:
                    if self._settings.dry_run:
                        status = "dry_run"
                    else:
                        self._exchange.create_loan_offer(offer)
                        status = "created"

                    self._loan_offers.add(
                        bot_run_id=bot_run_id,
                        offer=offer,
                        status=status,
                        dry_run=self._settings.dry_run,
                    )
                    created_offers += 1

            message = f"Completed with {created_offers} offer(s)."
            self._bot_runs.finish(bot_run_id, status="completed", message=message)
            self._notifier.info(message)
        except Exception as error:
            self._bot_runs.finish(bot_run_id, status="failed", message=str(error))
            self._notifier.error(str(error))
            raise
