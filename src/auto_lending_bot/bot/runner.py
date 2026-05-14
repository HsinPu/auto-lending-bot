import logging
import time

from auto_lending_bot.bot.run_steps import run_step_label
from auto_lending_bot.config import Settings, strategy_config_for
from auto_lending_bot.domain.models import ActiveLoan, CurrencyBalance, LoanOffer, LoanOrder
from auto_lending_bot.domain.strategy import build_lending_decision
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError
from auto_lending_bot.integrations.exchange import ExchangeClient
from auto_lending_bot.market.recorder import MarketRecorder
from auto_lending_bot.notifications.notifier import Notifier
from auto_lending_bot.persistence.repository import (
    ActiveLoanRepository,
    BotRunDecisionRepository,
    BotRunRepository,
    BotRunStepRepository,
    LendingHistoryRepository,
    LoanOfferRepository,
    MarketAnalysisRateRepository,
    NotificationStateRepository,
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
        lending_history: LendingHistoryRepository,
        notification_state: NotificationStateRepository,
        market_analysis_rates: MarketAnalysisRateRepository,
        market_recorder: MarketRecorder,
        notifier: Notifier,
        decision_snapshots: BotRunDecisionRepository | None = None,
        run_steps: BotRunStepRepository | None = None,
    ) -> None:
        self._settings = settings
        self._exchange = exchange
        self._bot_runs = bot_runs
        self._loan_offers = loan_offers
        self._active_loans = active_loans
        self._open_offers = open_offers
        self._lending_history = lending_history
        self._notification_state = notification_state
        self._market_analysis_rates = market_analysis_rates
        self._market_recorder = market_recorder
        self._notifier = notifier
        self._decision_snapshots = decision_snapshots
        self._run_steps = run_steps

    def run(self) -> None:
        loops_completed = 0
        try:
            while self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
                created_offers = self.run_once_with_retry()
                loops_completed += 1

                if self._settings.max_loops <= 0 or loops_completed < self._settings.max_loops:
                    time.sleep(self._sleep_seconds(created_offers))
        except KeyboardInterrupt:
            logger.info("Shutdown requested; stopping bot runner.")

    def run_once_with_retry(self) -> int:
        for attempt in range(1, self._settings.retry_attempts + 1):
            try:
                return self.run_once()
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
        return 0

    def run_once(self) -> int:
        bot_run_id = self._bot_runs.start(dry_run=self._settings.dry_run)
        created_offers = 0
        live_lend_amount = 0.0
        current_step_id: int | None = None

        try:
            self._record_completed_step(
                bot_run_id,
                "create-run",
                run_step_label("create-run"),
                f"Bot run #{bot_run_id} started.",
            )

            current_step_id = self._start_step(
                bot_run_id,
                "read-previous-active-loans",
                run_step_label("read-previous-active-loans"),
            )
            previous_active_loan_ids = {
                str(row["external_loan_id"]) for row in self._active_loans.recent(1000)
            }
            self._finish_step(
                current_step_id,
                message=f"讀取 {len(previous_active_loan_ids)} 筆本地舊放貸資料。",
            )
            current_step_id = None

            current_step_id = self._start_step(
                bot_run_id,
                "read-active-loans",
                run_step_label("read-active-loans"),
            )
            active_loans = self._exchange.get_active_loans()
            self._finish_step(
                current_step_id,
                message=f"讀取 {len(active_loans)} 筆交易所放貸中資料：{_active_loan_summary(active_loans)}",
            )
            current_step_id = None

            current_step_id = self._start_step(
                bot_run_id,
                "replace-active-loans",
                run_step_label("replace-active-loans"),
            )
            self._active_loans.replace_all(active_loans)
            self._finish_step(current_step_id, message=f"本地放貸中資料已更新為 {len(active_loans)} 筆。")
            current_step_id = None

            current_step_id = self._start_step(
                bot_run_id,
                "detect-new-active-loans",
                run_step_label("detect-new-active-loans"),
            )
            new_active_count = self._notify_new_active_loans(previous_active_loan_ids, active_loans)
            self._finish_step(current_step_id, message=f"檢查到 {new_active_count} 筆新成交放貸。")
            current_step_id = None

            current_step_id = self._start_step(
                bot_run_id,
                "read-lending-balances",
                run_step_label("read-lending-balances"),
            )
            balances = self._exchange.get_lending_balances()
            exchange_balances = _optional_exchange_balances(self._exchange, "get_exchange_balances")
            margin_balances = _optional_exchange_balances(self._exchange, "get_margin_balances")
            self._finish_step(
                current_step_id,
                message=(
                    "錢包餘額：\n"
                    f"- Funding/Lending wallet：{_balance_summary(balances)}\n"
                    f"- Exchange wallet：{_balance_summary(exchange_balances)}\n"
                    f"- Margin/Trading wallet：{_balance_summary(margin_balances)}"
                ),
            )
            current_step_id = None

            self._rebalance_open_offers(bot_run_id, balances)

            for balance in balances:
                current_step_id = self._start_step(
                    bot_run_id,
                    "load-market-orders",
                    run_step_label("load-market-orders"),
                )
                orders = self._exchange.get_loan_orders(balance.currency)
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：已讀取 {len(orders)} 筆市場利率。{_market_order_summary(orders)}",
                )
                current_step_id = None

                current_step_id = self._start_step(
                    bot_run_id,
                    "record-market-orders",
                    run_step_label("record-market-orders"),
                )
                self._market_recorder.record_orders(orders)
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：已記錄 {len(orders)} 筆市場資料。",
                )
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "load-strategy-config", run_step_label("load-strategy-config"))
                strategy = strategy_config_for(self._settings, balance.currency)
                self._finish_step(current_step_id, message=f"{balance.currency}：已載入策略設定。")
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "load-frr-rate", run_step_label("load-frr-rate"))
                frr_daily_rate = self._frr_daily_rate(balance.currency, strategy.frr_as_min)
                self._finish_step(
                    current_step_id,
                    status="completed" if strategy.frr_as_min else "skipped",
                    message=(
                        f"{balance.currency}：FRR 日利率 {frr_daily_rate}."
                        if strategy.frr_as_min
                        else f"{balance.currency}：略過 FRR，因為 FRR_AS_MIN=false。"
                    ),
                )
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "load-market-analysis-rate", run_step_label("load-market-analysis-rate"))
                suggested_min_daily_rate = self._suggested_min_daily_rate(balance.currency)
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：市場分析建議最低日利率 {suggested_min_daily_rate}。",
                )
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "calculate-active-amount", run_step_label("calculate-active-amount"))
                active_amount = self._active_amount(active_loans, balance.currency)
                self._finish_step(current_step_id, message=f"{balance.currency}：已放貸金額 {active_amount}。")
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "load-btc-price", run_step_label("load-btc-price"))
                btc_price = self._btc_price(balance.currency, strategy.gap_mode)
                self._finish_step(
                    current_step_id,
                    status="completed" if btc_price is not None else "skipped",
                    message=(
                        f"{balance.currency}：BTC 參考價格 {btc_price}。"
                        if btc_price is not None
                        else f"{balance.currency}：略過 BTC 價格，因為策略不需要。"
                    ),
                )
                current_step_id = None

                current_step_id = self._start_step(
                    bot_run_id,
                    "calculate-decisions",
                    run_step_label("calculate-decisions"),
                )
                decision = build_lending_decision(
                    balance=balance,
                    order_book=orders,
                    strategy=strategy,
                    frr_daily_rate=frr_daily_rate,
                    btc_price=btc_price,
                    suggested_min_daily_rate=suggested_min_daily_rate,
                    active_amount=active_amount,
                )
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：策略決策產生 {len(decision.offers)} 筆委託。",
                )
                current_step_id = None

                current_step_id = self._start_step(
                    bot_run_id,
                    "record-decisions",
                    run_step_label("record-decisions"),
                )
                self._record_decision_snapshot(
                    bot_run_id=bot_run_id,
                    balance=balance,
                    active_amount=active_amount,
                    open_offer_amount=self._open_offer_amount(balance.currency),
                    order_book=orders,
                    strategy=strategy,
                    frr_daily_rate=frr_daily_rate,
                    suggested_min_daily_rate=suggested_min_daily_rate,
                    decision=decision,
                )
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：已保存策略決策快照。",
                )
                current_step_id = None

                logger.info("%s: %s", decision.currency, decision.reason)
                if self._settings.strategy_debug:
                    self._log_strategy_debug(balance, orders, strategy, decision, frr_daily_rate)
                current_step_id = self._start_step(
                    bot_run_id,
                    "prepare-offers",
                    run_step_label("prepare-offers"),
                )
                self._finish_step(
                    current_step_id,
                    message=f"{balance.currency}：準備 {len(decision.offers)} 筆委託。",
                )
                current_step_id = None

                if self._settings.dry_run:
                    for offer in decision.offers:
                        current_step_id = self._start_step(
                            bot_run_id,
                            "record-dry-run-offer",
                            run_step_label("record-dry-run-offer"),
                        )
                        status = "dry_run"
                        self._loan_offers.add(
                            bot_run_id=bot_run_id,
                            offer=offer,
                            status=status,
                            dry_run=self._settings.dry_run,
                        )
                        self._record_xday_notification_step(bot_run_id, offer)
                        created_offers += 1
                        self._finish_step(
                            current_step_id,
                            message=(
                                f"{offer.currency}：已記錄模擬委託，金額 {offer.amount}，"
                                f"日利率 {offer.daily_rate}，天期 {offer.duration_days}。"
                            ),
                        )
                        current_step_id = None
                    continue

                for offer in decision.offers:
                    current_step_id = self._start_step(
                        bot_run_id,
                        "validate-live-offer",
                        run_step_label("validate-live-offer"),
                    )
                    self._assert_live_offer_allowed(offer, live_lend_amount)
                    self._finish_step(
                        current_step_id,
                        message=f"{offer.currency}：Live 委託金額通過安全檢查。",
                    )
                    current_step_id = None

                    current_step_id = self._start_step(
                        bot_run_id,
                        "record-live-intent",
                        run_step_label("record-live-intent"),
                    )
                    loan_offer_id = self._loan_offers.add(
                        bot_run_id=bot_run_id,
                        offer=offer,
                        status="intent",
                        dry_run=self._settings.dry_run,
                    )
                    self._finish_step(
                        current_step_id,
                        message=f"{offer.currency}：已建立 Live 委託意圖。",
                    )
                    current_step_id = None

                    current_step_id = self._start_step(
                        bot_run_id,
                        "submit-live-offer",
                        run_step_label("submit-live-offer"),
                    )
                    try:
                        external_offer_id = self._exchange.create_loan_offer(offer)
                        self._finish_step(
                            current_step_id,
                            message=f"{offer.currency}：已送出 Bitfinex 委託。",
                        )
                        current_step_id = None

                        current_step_id = self._start_step(
                            bot_run_id,
                            "update-offer-result",
                            run_step_label("update-offer-result"),
                        )
                        self._loan_offers.update_status(
                            loan_offer_id,
                            status="created",
                            external_offer_id=external_offer_id,
                        )
                        self._finish_step(
                            current_step_id,
                            message=f"{offer.currency}：委託已建立，交易所 ID {external_offer_id}。",
                        )
                        current_step_id = None
                        self._notifier.info(f"Created {offer.currency} loan offer {external_offer_id}.")
                        self._record_xday_notification_step(bot_run_id, offer)
                    except Exception as error:
                        self._finish_step(current_step_id, status="failed", message=str(error))
                        current_step_id = self._start_step(
                            bot_run_id,
                            "update-offer-result",
                            run_step_label("update-offer-result"),
                        )
                        self._loan_offers.update_status(
                            loan_offer_id,
                            status="failed",
                            message=str(error),
                        )
                        self._finish_step(
                            current_step_id,
                            status="failed",
                            message=f"{offer.currency}：委託建立失敗：{error}",
                        )
                        current_step_id = None
                        self._notify_caught_exception(
                            f"Failed to create {offer.currency} loan offer: {error}"
                        )
                        raise
                    live_lend_amount += offer.amount
                    created_offers += 1

            message = f"Completed with {created_offers} offer(s)."
            current_step_id = self._start_step(bot_run_id, "finish-run", run_step_label("finish-run"))
            self._bot_runs.finish(bot_run_id, status="completed", message=message)
            self._finish_step(current_step_id, message=message)
            current_step_id = None

            current_step_id = self._start_step(bot_run_id, "send-run-summary", run_step_label("send-run-summary"))
            self._notifier.run_summary(
                created_offers=created_offers,
                active_loans=len(active_loans),
                dry_run=self._settings.dry_run,
            )
            self._finish_step(current_step_id, message="已處理本輪摘要通知。")
            current_step_id = None

            current_step_id = self._start_step(
                bot_run_id,
                "send-periodic-summary",
                run_step_label("send-periodic-summary"),
            )
            periodic_sent = self._maybe_send_periodic_summary(active_loans)
            self._finish_step(
                current_step_id,
                status="completed" if periodic_sent else "skipped",
                message="已發送週期摘要通知。" if periodic_sent else "略過週期摘要通知。",
            )
            return created_offers
        except Exception as error:
            self._finish_step(current_step_id, status="failed", message=str(error))
            self._bot_runs.finish(bot_run_id, status="failed", message=str(error))
            error_notified = self._notify_caught_exception(str(error))
            self._record_completed_or_skipped_step(
                bot_run_id,
                "send-error-notification",
                error_notified,
                "已發送錯誤通知。" if error_notified else "略過錯誤通知。",
            )
            raise

    def _start_step(self, bot_run_id: int, step_key: str, label: str) -> int | None:
        if self._run_steps is None:
            return None

        return self._run_steps.start(bot_run_id, step_key, label)

    def _finish_step(
        self,
        step_id: int | None,
        status: str = "completed",
        message: str = "",
    ) -> None:
        if step_id is None or self._run_steps is None:
            return

        self._run_steps.finish(step_id, status=status, message=message)

    def _record_completed_step(
        self,
        bot_run_id: int,
        step_key: str,
        label: str,
        message: str = "",
    ) -> None:
        if self._run_steps is None:
            return

        self._run_steps.record_completed(bot_run_id, step_key, label, message=message)

    def _record_skipped_step(self, bot_run_id: int, step_key: str, message: str = "") -> None:
        step_id = self._start_step(bot_run_id, step_key, run_step_label(step_key))
        self._finish_step(step_id, status="skipped", message=message)

    def _record_completed_or_skipped_step(
        self,
        bot_run_id: int,
        step_key: str,
        completed: bool,
        message: str,
    ) -> None:
        step_id = self._start_step(bot_run_id, step_key, run_step_label(step_key))
        self._finish_step(step_id, status="completed" if completed else "skipped", message=message)

    def _record_xday_notification_step(self, bot_run_id: int, offer: LoanOffer) -> None:
        sent = self._notify_xday_offer(offer)
        self._record_completed_or_skipped_step(
            bot_run_id,
            "send-xday-notification",
            sent,
            f"{offer.currency}：已發送長天期委託通知。"
            if sent
            else f"{offer.currency}：略過長天期委託通知。",
        )

    def _sleep_seconds(self, created_offers: int) -> int:
        if created_offers > 0:
            return self._settings.bot_sleep_seconds

        return self._settings.bot_inactive_sleep_seconds

    def _assert_live_offer_allowed(self, offer: LoanOffer, live_lend_amount: float) -> None:
        if self._settings.max_single_offer_amount is not None:
            if offer.amount > self._settings.max_single_offer_amount:
                msg = "Offer amount exceeds MAX_SINGLE_OFFER_AMOUNT."
                raise ValueError(msg)

        if self._settings.max_total_lend_amount is not None:
            if live_lend_amount + offer.amount > self._settings.max_total_lend_amount:
                msg = "Run total exceeds MAX_TOTAL_LEND_AMOUNT."
                raise ValueError(msg)

    def _rebalance_open_offers(self, bot_run_id: int, balances: list[CurrencyBalance]) -> None:
        self._record_completed_step(
            bot_run_id,
            "check-open-offer-rebalance-setting",
            run_step_label("check-open-offer-rebalance-setting"),
            "AUTO_REBALANCE_OPEN_OFFERS=true."
            if self._settings.auto_rebalance_open_offers
            else "AUTO_REBALANCE_OPEN_OFFERS=false.",
        )
        if not self._settings.auto_rebalance_open_offers:
            self._record_skipped_step(
                bot_run_id,
                "sync-open-offers",
                "略過同步未成交委託，因為 AUTO_REBALANCE_OPEN_OFFERS=false。",
            )
            self._record_skipped_step(
                bot_run_id,
                "replace-open-offers",
                "略過更新本地未成交委託。",
            )
            self._record_skipped_step(
                bot_run_id,
                "check-open-offer-cancel-setting",
                "略過取消設定檢查，因為未同步 open offers。",
            )
            self._record_skipped_step(
                bot_run_id,
                "evaluate-open-offer-cancel",
                "略過舊委託取消評估。",
            )
            return

        step_id = self._start_step(bot_run_id, "sync-open-offers", run_step_label("sync-open-offers"))
        offers = self._exchange.get_open_loan_offers()
        self._finish_step(step_id, message=f"讀取 {len(offers)} 筆未成交委託。")

        step_id = self._start_step(bot_run_id, "replace-open-offers", run_step_label("replace-open-offers"))
        self._open_offers.replace_all(offers)
        self._finish_step(step_id, message=f"本地未成交委託已更新為 {len(offers)} 筆。")

        self._record_completed_step(
            bot_run_id,
            "check-open-offer-cancel-setting",
            run_step_label("check-open-offer-cancel-setting"),
            "允許取消舊委託。"
            if not self._settings.dry_run and self._settings.auto_cancel_open_offers
            else "略過取消舊委託：dry-run 或 AUTO_CANCEL_OPEN_OFFERS=false。",
        )
        if self._settings.dry_run or not self._settings.auto_cancel_open_offers:
            self._record_skipped_step(
                bot_run_id,
                "evaluate-open-offer-cancel",
                "略過舊委託取消評估：dry-run 或 AUTO_CANCEL_OPEN_OFFERS=false。",
            )
            return

        kept_offers = []
        for offer in offers:
            step_id = self._start_step(
                bot_run_id,
                "evaluate-open-offer-cancel",
                run_step_label("evaluate-open-offer-cancel"),
            )
            if self._keep_stuck_offer(offer, offers, balances):
                kept_offers.append(offer)
                self._finish_step(step_id, message=f"保留 {offer.currency} 舊委託，避免低於最小放貸量。")
                continue
            if offer.external_offer_id:
                self._finish_step(step_id, message=f"{offer.currency} 舊委託可取消。")
                step_id = self._start_step(
                    bot_run_id,
                    "cancel-open-offer",
                    run_step_label("cancel-open-offer"),
                )
                self._exchange.cancel_loan_offer(offer.external_offer_id)
                self._finish_step(step_id, message=f"已取消 {offer.currency} 舊委託 {offer.external_offer_id}。")
            else:
                self._finish_step(step_id, message=f"略過 {offer.currency} 舊委託：沒有交易所委託 ID。")
        self._open_offers.replace_all(kept_offers)

    def _keep_stuck_offer(
        self,
        offer: LoanOffer,
        offers: list[LoanOffer],
        balances: list[CurrencyBalance],
    ) -> bool:
        if not self._settings.keep_stuck_orders:
            return False

        currency = offer.currency.upper()
        total_available_after_cancel = sum(
            balance.amount for balance in balances if balance.currency.upper() == currency
        ) + sum(open_offer.amount for open_offer in offers if open_offer.currency.upper() == currency)
        strategy = strategy_config_for(self._settings, currency)
        return total_available_after_cancel < strategy.min_loan_size

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
                self._settings.market_analysis_min_samples,
                self._settings.market_analysis_max_age_seconds,
            )

        if self._settings.market_analysis_method == "macd":
            if (
                self._settings.market_analysis_macd_short_seconds > 0
                and self._settings.market_analysis_macd_long_seconds > 0
            ):
                return self._market_analysis_rates.macd_rate_by_seconds(
                    currency,
                    self._settings.market_analysis_macd_short_seconds,
                    self._settings.market_analysis_macd_long_seconds,
                    self._settings.market_analysis_multiplier,
                    self._settings.market_analysis_min_samples,
                    self._settings.market_analysis_max_age_seconds,
                )

            return self._market_analysis_rates.macd_rate(
                currency,
                self._settings.market_analysis_macd_short_samples,
                self._settings.market_analysis_macd_long_samples,
                self._settings.market_analysis_multiplier,
                self._settings.market_analysis_min_samples,
                self._settings.market_analysis_max_age_seconds,
            )

        return None

    @staticmethod
    def _active_amount(active_loans: list[ActiveLoan], currency: str) -> float:
        return sum(
            active_loan.amount
            for active_loan in active_loans
            if active_loan.currency.upper() == currency.upper()
        )

    def _open_offer_amount(self, currency: str) -> float:
        return sum(
            float(row["amount"])
            for row in self._open_offers.recent(1000)
            if str(row["currency"]).upper() == currency.upper()
        )

    def _record_decision_snapshot(
        self,
        bot_run_id: int,
        balance: CurrencyBalance,
        active_amount: float,
        open_offer_amount: float,
        order_book: list,
        strategy,
        frr_daily_rate: float | None,
        suggested_min_daily_rate: float | None,
        decision,
    ) -> None:
        if self._decision_snapshots is None:
            return

        self._decision_snapshots.add(
            {
                "bot_run_id": bot_run_id,
                "currency": balance.currency,
                "balance": balance.amount,
                "active_amount": active_amount,
                "open_offer_amount": open_offer_amount,
                "best_market_rate": max((order.daily_rate for order in order_book), default=0.0),
                "configured_min_daily_rate": strategy.min_daily_rate,
                "suggested_min_daily_rate": suggested_min_daily_rate,
                "effective_min_daily_rate": max(
                    strategy.min_daily_rate,
                    suggested_min_daily_rate or 0,
                    frr_daily_rate + strategy.frr_delta if frr_daily_rate is not None else 0,
                ),
                "max_daily_rate": strategy.max_daily_rate,
                "max_to_lend": strategy.max_amount_to_lend,
                "max_percent_to_lend": strategy.max_percent_to_lend,
                "max_active_amount": strategy.max_active_amount,
                "offer_count": len(decision.offers),
                "offers": [offer.__dict__ for offer in decision.offers],
                "reason": decision.reason,
            }
        )

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

    def _maybe_send_periodic_summary(self, active_loans: list[ActiveLoan]) -> bool:
        if self._settings.notify_summary_minutes <= 0:
            return False

        now = time.time()
        state_key = "telegram_summary_last_sent_at"
        last_sent_at = self._notification_state.get_float(state_key)
        interval_seconds = self._settings.notify_summary_minutes * 60
        if last_sent_at is not None and now - last_sent_at < interval_seconds:
            return False

        open_offers = self._open_offers.recent(1000)
        earnings = self._lending_history.earnings_summary_by_currency()
        self._notifier.periodic_summary(
            _summary_message(
                active_loans=active_loans,
                open_offers=open_offers,
                earnings=earnings,
            )
        )
        self._notification_state.set_float(state_key, now)
        return True

    def _notify_xday_offer(self, offer: LoanOffer) -> bool:
        if not self._settings.notify_xday_threshold:
            return False
        if offer.duration_days <= 2:
            return False

        self._notifier.xday_offer(offer, dry_run=self._settings.dry_run)
        return True

    def _notify_new_active_loans(
        self,
        previous_active_loan_ids: set[str],
        active_loans: list[ActiveLoan],
    ) -> int:
        if not previous_active_loan_ids:
            return 0

        new_count = 0
        for active_loan in active_loans:
            if active_loan.external_loan_id not in previous_active_loan_ids:
                self._notifier.loan_filled(active_loan)
                new_count += 1
        return new_count

    def _notify_caught_exception(self, message: str) -> bool:
        if self._settings.notify_caught_exception:
            self._notifier.error(message)
            return True
        return False


def _summary_message(
    active_loans: list[ActiveLoan],
    open_offers: list[dict[str, object]],
    earnings: list[dict[str, object]],
) -> str:
    active_amount = sum(active_loan.amount for active_loan in active_loans)
    open_offer_amount = sum(float(row["amount"]) for row in open_offers)
    today_earned = sum(float(row["today_earned"]) for row in earnings)
    total_earned = sum(float(row["total_earned"]) for row in earnings)
    lines = [
        "Lending summary: "
        f"active_loans={len(active_loans)}, active_amount={active_amount:.8f}, "
        f"open_offers={len(open_offers)}, open_offer_amount={open_offer_amount:.8f}, "
        f"today_earned={today_earned:.8f}, total_earned={total_earned:.8f}."
    ]
    if not earnings:
        lines.append("Earnings: no lending history yet.")
        return "\n".join(lines)

    lines.append("Earnings by currency:")
    for row in sorted(earnings, key=lambda item: str(item["currency"])):
        lines.append(
            f"{row['currency']}: today={float(row['today_earned']):.8f}, "
            f"yesterday={float(row['yesterday_earned']):.8f}, "
            f"total={float(row['total_earned']):.8f}."
        )
    return "\n".join(lines)


def _balance_summary(balances: list[CurrencyBalance]) -> str:
    if not balances:
        return "沒有可用餘額。"
    return "、".join(f"{balance.currency} {balance.amount:g}" for balance in balances) + "。"


def _active_loan_summary(active_loans: list[ActiveLoan]) -> str:
    if not active_loans:
        return "目前沒有放貸中資料。"
    return "、".join(
        f"{loan.currency} {loan.amount:g} @ {loan.daily_rate:g} / {loan.duration_days}天"
        for loan in active_loans
    ) + "。"


def _market_order_summary(orders: list[LoanOrder]) -> str:
    if not orders:
        return "沒有市場利率資料。"
    best_order = max(orders, key=lambda order: order.daily_rate)
    return f"最佳日利率 {best_order.daily_rate:g}，可用量 {best_order.amount:g}。"


def _optional_exchange_balances(exchange: ExchangeClient, method_name: str) -> list[CurrencyBalance]:
    method = getattr(exchange, method_name, None)
    if method is None:
        return []
    return method()
