import logging
import time

from auto_lending_bot.config import Settings, strategy_config_for
from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.domain.strategy import build_lending_decision
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    OpenLoanOfferRepository,
)

logger = logging.getLogger(__name__)


class BotRunner:
    def __init__(
        self,
        settings: Settings,
        exchange: ExchangeClient,
        bot_runs: BotRunRepository,
        loan_offers: LoanOfferRepository,
        active_loans: ActiveLoanRepository,
        open_offers: OpenLoanOfferRepository,
        market_analysis_rates: MarketAnalysisRateRepository,
        market_recorder: MarketRecorder,
        notifier: Notifier,
    ) -> None:
        self._settings = settings
        self._exchange = exchange
        self._bot_runs = bot_runs
        self._loan_offers = loan_offers
        self._active_loans = active_loans
        self._open_offers = open_offers
        self._market_analysis_rates = market_analysis_rates
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
            except ExchangeAuthenticationError:
                logger.exception("Authentication failed; not retrying bot run.")
                raise
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
            self._active_loans.replace_all(self._exchange.get_active_loans())
            self._rebalance_open_offers()
            balances = self._exchange.get_lending_balances()
            for balance in balances:
                orders = self._exchange.get_loan_orders(balance.currency)
                self._market_recorder.record_orders(orders)
                strategy = strategy_config_for(self._settings, balance.currency)
                frr_daily_rate = self._frr_daily_rate(balance.currency, strategy.frr_as_min)
                decision = build_lending_decision(
                    balance=balance,
                    order_book=orders,
                    strategy=strategy,
                    frr_daily_rate=frr_daily_rate,
                    btc_price=self._btc_price(balance.currency, strategy.gap_mode),
                    suggested_min_daily_rate=self._suggested_min_daily_rate(balance.currency),
                )

                logger.info("%s: %s", decision.currency, decision.reason)
                if self._settings.strategy_debug:
                    self._log_strategy_debug(balance, orders, strategy, decision, frr_daily_rate)
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
                            self._notifier.info(
                                f"Created {offer.currency} loan offer {external_offer_id}."
                            )
                        except Exception as error:
                            self._loan_offers.update_status(
                                loan_offer_id,
                                status="failed",
                                message=str(error),
                            )
                            self._notifier.error(
                                f"Failed to create {offer.currency} loan offer: {error}"
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

    def _rebalance_open_offers(self) -> None:
        if not self._settings.auto_rebalance_open_offers:
            return

        offers = self._exchange.get_open_loan_offers()
        self._open_offers.replace_all(offers)
        if self._settings.dry_run or not self._settings.auto_cancel_open_offers:
            return

        for offer in offers:
            if offer.external_offer_id:
                self._exchange.cancel_loan_offer(offer.external_offer_id)
        self._open_offers.replace_all([])

        if self._settings.max_total_lend_amount is not None:
            if live_lend_amount + offer.amount > self._settings.max_total_lend_amount:
                msg = "Run total exceeds MAX_TOTAL_LEND_AMOUNT."
                raise ValueError(msg)

    def _frr_daily_rate(self, currency: str, frr_as_min: bool) -> float | None:
        if not frr_as_min:
            return None

        return self._exchange.get_frr_rate(currency)

    def _btc_price(self, currency: str, gap_mode: str) -> float | None:
        normalized_gap_mode = gap_mode.lower().replace("-", "_")
        if normalized_gap_mode not in {"raw_btc", "rawbtc"}:
            return None

        return self._exchange.get_btc_price(currency)

    def _suggested_min_daily_rate(self, currency: str) -> float | None:
        if self._settings.market_analysis_method == "percentile":
            return self._market_analysis_rates.percentile_rate(
                currency,
                self._settings.market_analysis_percentile,
            )

        if self._settings.market_analysis_method == "macd":
            return self._market_analysis_rates.macd_rate(
                currency,
                self._settings.market_analysis_macd_short_samples,
                self._settings.market_analysis_macd_long_samples,
            )

        return None

    def _log_strategy_debug(self, balance, orders, strategy, decision, frr_daily_rate) -> None:
        best_rate = max((order.daily_rate for order in orders), default=0)
        logger.info(
            "strategy_debug currency=%s balance=%s best_daily_rate=%.8f "
            "min_daily_rate=%.8f max_daily_rate=%.8f frr_daily_rate=%s offers=%s reason=%s",
            balance.currency,
            balance.amount,
            best_rate,
            strategy.min_daily_rate,
            strategy.max_daily_rate,
            f"{frr_daily_rate:.8f}" if frr_daily_rate is not None else "none",
            len(decision.offers),
            decision.reason,
        )
