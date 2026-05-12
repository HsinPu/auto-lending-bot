import logging
import time

from auto_lending_bot.config import Settings, strategy_config_for
from auto_lending_bot.domain.models import LoanOffer
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
        try:
            while self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
                self._run_once_with_retry()
                loops_completed += 1

                if self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
                    time.sleep(self._settings.bot_sleep_seconds)
        except KeyboardInterrupt:
            logger.info("Shutdown requested; stopping bot runner.")

    def _run_once_with_retry(self) -> None:
        for attempt in range(1, self._settings.retry_attempts + 1):
            try:
                self.run_once()
                return
            except Exception:
                if attempt >= self._settings.retry_attempts:
                    raise
                logger.exception(
                    "Bot run failed; retrying in %s seconds.",
                    self._settings.retry_backoff_seconds,
                )
                time.sleep(self._settings.retry_backoff_seconds)

    def run_once(self) -> None:
        bot_run_id = self._bot_runs.start(dry_run=self._settings.dry_run)
        created_offers = 0
        live_lend_amount = 0.0

        try:
            balances = self._exchange.get_lending_balances()
            for balance in balances:
                orders = self._exchange.get_loan_orders(balance.currency)
                self._market_recorder.record_orders(orders)
                strategy = strategy_config_for(self._settings, balance.currency)
                decision = build_lending_decision(
                    balance=balance,
                    order_book=orders,
                    strategy=strategy,
                )

                logger.info("%s: %s", decision.currency, decision.reason)
                if self._settings.strategy_debug:
                    self._log_strategy_debug(balance, orders, strategy, decision)
                for offer in decision.offers:
                    if self._settings.dry_run:
                        status = "dry_run"
                        self._loan_offers.add(
                            bot_run_id=bot_run_id,
                            offer=offer,
                            status=status,
                            dry_run=self._settings.dry_run,
                        )
                    else:
                        self._assert_live_offer_allowed(offer, live_lend_amount)
                        loan_offer_id = self._loan_offers.add(
                            bot_run_id=bot_run_id,
                            offer=offer,
                            status="intent",
                            dry_run=self._settings.dry_run,
                        )
                        try:
                            external_offer_id = self._exchange.create_loan_offer(offer)
                            self._loan_offers.update_status(
                                loan_offer_id,
                                status="created",
                                external_offer_id=external_offer_id,
                            )
                        except Exception as error:
                            self._loan_offers.update_status(
                                loan_offer_id,
                                status="failed",
                                message=str(error),
                            )
                            raise
                        live_lend_amount += offer.amount
                    created_offers += 1

            message = f"Completed with {created_offers} offer(s)."
            self._bot_runs.finish(bot_run_id, status="completed", message=message)
            self._notifier.info(message)
        except Exception as error:
            self._bot_runs.finish(bot_run_id, status="failed", message=str(error))
            self._notifier.error(str(error))
            raise

    def _assert_live_offer_allowed(self, offer: LoanOffer, live_lend_amount: float) -> None:
        if self._settings.max_single_offer_amount is not None:
            if offer.amount > self._settings.max_single_offer_amount:
                msg = "Offer amount exceeds MAX_SINGLE_OFFER_AMOUNT."
                raise ValueError(msg)

        if self._settings.max_total_lend_amount is not None:
            if live_lend_amount + offer.amount > self._settings.max_total_lend_amount:
                msg = "Run total exceeds MAX_TOTAL_LEND_AMOUNT."
                raise ValueError(msg)

    def _log_strategy_debug(self, balance, orders, strategy, decision) -> None:
        best_rate = max((order.daily_rate for order in orders), default=0)
        logger.info(
            "strategy_debug currency=%s balance=%s best_daily_rate=%.8f "
            "min_daily_rate=%.8f max_daily_rate=%.8f offers=%s reason=%s",
            balance.currency,
            balance.amount,
            best_rate,
            strategy.min_daily_rate,
            strategy.max_daily_rate,
            len(decision.offers),
            decision.reason,
        )
