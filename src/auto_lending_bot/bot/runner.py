import logging
import time
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from auto_lending_bot.bot.run_steps import run_step_label
from auto_lending_bot.config import Settings, strategy_config_for
from auto_lending_bot.domain.models import (
    ActiveLoan,
    CurrencyBalance,
    FillOutcome,
    LendingDecision,
    LoanOffer,
    LoanOrder,
)
from auto_lending_bot.domain.strategy import build_lending_decision, detect_market_regime
from auto_lending_bot.integrations.errors import ExchangeAuthenticationError, ExchangePermissionError
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
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile

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
        bot_job_id: int | None = None,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
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
        self._bot_job_id = bot_job_id
        self._profile_context = profile_context

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
            except (ExchangeAuthenticationError, ExchangePermissionError):
                logger.exception("Exchange permission/authentication failed; not retrying bot run.")
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
        bot_run_id = self._bot_runs.start(
            dry_run=self._settings.dry_run,
            job_id=self._bot_job_id,
            profile_context=self._profile_context,
        )
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
                str(row["external_loan_id"])
                for row in self._active_loans.recent(
                    limit=1000,
                    profile_context=self._profile_context,
                )
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
            self._active_loans.replace_all(active_loans, profile_context=self._profile_context)
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

            if not balances:
                self._record_skipped_step(
                    bot_run_id,
                    "calculate-decisions",
                    (
                        "放貸日利率計算：無法計算\n"
                        "影響：Funding/Lending wallet 沒有可用餘額，所以本輪沒有幣種可進行利率、金額與委託計算。\n"
                        "設定鍵：需先把資金放在 Funding/Lending wallet，或執行轉帳後再跑一次。"
                    ),
                )

            for balance in balances:
                current_step_id = self._start_step(
                    bot_run_id,
                    "load-market-orders",
                    run_step_label("load-market-orders"),
                )
                orders = self._exchange.get_loan_orders(balance.currency)
                suggested_min_daily_rate = self._suggested_min_daily_rate(balance.currency)
                historical_daily_rates = self._historical_daily_rates(balance.currency)
                fill_outcomes = self._fill_outcomes(balance.currency)
                market_regime_rates = self._market_regime_daily_rates(balance.currency)
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
                analysis_changed_count = self._market_analysis_rates.add_many(
                    orders[: self._settings.market_analysis_levels],
                    profile_context=self._profile_context,
                )
                self._finish_step(
                    current_step_id,
                    message=(
                        f"{balance.currency}：已記錄 {len(orders)} 筆市場資料；"
                        f"同步記錄 {analysis_changed_count} 筆市場分析樣本。"
                    ),
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
                        else _setting_message(
                            f"{balance.currency} FRR 最低利率參考",
                            "關閉",
                            "不會讀取 FRR，也不會把 FRR 當成本輪最低放貸利率候選。",
                            "FRR_AS_MIN=false",
                        )
                    ),
                )
                current_step_id = None

                current_step_id = self._start_step(bot_run_id, "load-market-analysis-rate", run_step_label("load-market-analysis-rate"))
                self._finish_step(
                    current_step_id,
                    message=(
                        f"{balance.currency}：市場分析建議最低日利率 {suggested_min_daily_rate}；"
                        f"最佳化樣本 {len(historical_daily_rates)} 筆；"
                        f"實際成交回饋 {len(fill_outcomes)} 筆；"
                        f"市場狀態樣本 {len(market_regime_rates)} 筆。"
                    ),
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
                        else _setting_message(
                            f"{balance.currency} BTC 價格參考",
                            "不需要",
                            "目前策略不需要 BTC 參考價格；只有 GAP_MODE=raw_btc/rawbtc 時才會讀取。",
                            f"GAP_MODE={strategy.gap_mode}",
                        )
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
                    historical_daily_rates=historical_daily_rates,
                    fill_outcomes=fill_outcomes,
                    market_regime_daily_rates=market_regime_rates,
                )
                decision, min_value_message = self._filter_min_offer_value(
                    decision,
                    strategy.min_offer_value_usd,
                    btc_price,
                )
                self._finish_step(
                    current_step_id,
                    message=_decision_calculation_summary(
                        balance=balance,
                        active_amount=active_amount,
                        order_book=orders,
                        strategy=strategy,
                        frr_daily_rate=frr_daily_rate,
                        suggested_min_daily_rate=suggested_min_daily_rate,
                        decision=decision,
                        historical_daily_rates=historical_daily_rates,
                    ),
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
                prepare_message = f"{balance.currency}：準備 {len(decision.offers)} 筆委託。"
                if min_value_message:
                    prepare_message = f"{prepare_message} {min_value_message}"
                self._finish_step(
                    current_step_id,
                    message=prepare_message,
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
                            strategy_snapshot=_offer_strategy_snapshot(strategy),
                            rate_candidate_snapshot=[candidate.__dict__ for candidate in decision.rate_candidates],
                            profile_context=self._profile_context,
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
                        strategy_snapshot=_offer_strategy_snapshot(strategy),
                        rate_candidate_snapshot=[candidate.__dict__ for candidate in decision.rate_candidates],
                        profile_context=self._profile_context,
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
            periodic_sent, periodic_message = self._maybe_send_periodic_summary(active_loans)
            self._finish_step(
                current_step_id,
                status="completed" if periodic_sent else "skipped",
                message=periodic_message,
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
                "已發送錯誤通知。"
                if error_notified
                else _setting_message(
                    "錯誤通知",
                    "關閉",
                    "本輪失敗時不會發送 Telegram 錯誤通知。",
                    "NOTIFY_CAUGHT_EXCEPTION=false",
                ),
            )
            raise

    def _start_step(self, bot_run_id: int, step_key: str, label: str) -> int | None:
        if self._run_steps is None:
            return None

        return self._run_steps.start(
            bot_run_id,
            step_key,
            label,
            profile_context=self._profile_context,
        )

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

        self._run_steps.record_completed(
            bot_run_id,
            step_key,
            label,
            message=message,
            profile_context=self._profile_context,
        )

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
            else self._xday_notification_skip_message(offer),
        )

    def _sleep_seconds(self, created_offers: int) -> int:
        if created_offers > 0:
            return self._settings.bot_sleep_seconds

        return self._settings.bot_inactive_sleep_seconds

    def _assert_live_offer_allowed(self, offer: LoanOffer, live_lend_amount: float) -> None:
        if (
            self._settings.max_single_offer_amount is not None
            and self._settings.max_single_offer_amount > 0
        ):
            if offer.amount > self._settings.max_single_offer_amount:
                msg = "Offer amount exceeds MAX_SINGLE_OFFER_AMOUNT."
                raise ValueError(msg)

        if (
            self._settings.max_total_lend_amount is not None
            and self._settings.max_total_lend_amount > 0
        ):
            if live_lend_amount + offer.amount > self._settings.max_total_lend_amount:
                msg = "Run total exceeds MAX_TOTAL_LEND_AMOUNT."
                raise ValueError(msg)

    def _rebalance_open_offers(self, bot_run_id: int, balances: list[CurrencyBalance]) -> None:
        self._record_completed_step(
            bot_run_id,
            "check-open-offer-rebalance-setting",
            run_step_label("check-open-offer-rebalance-setting"),
            _setting_message(
                "未成交委託自動整理",
                "開啟",
                "會同步交易所未成交委託，並檢查是否需要保留、取消或重掛舊委託。",
                "AUTO_REBALANCE_OPEN_OFFERS=true",
            )
            if self._settings.auto_rebalance_open_offers
            else _setting_message(
                "未成交委託自動整理",
                "關閉",
                "不會同步交易所未成交委託，也不會取消或重掛舊委託。",
                "AUTO_REBALANCE_OPEN_OFFERS=false",
            ),
        )
        if not self._settings.auto_rebalance_open_offers:
            self._record_skipped_step(
                bot_run_id,
                "sync-open-offers",
                _setting_message(
                    "未成交委託同步",
                    "略過",
                    "不會讀取交易所目前還掛著的放貸委託，也不會更新本地未成交委託快照。",
                    "AUTO_REBALANCE_OPEN_OFFERS=false",
                ),
            )
            self._record_skipped_step(
                bot_run_id,
                "replace-open-offers",
                _setting_message(
                    "本地未成交委託快照",
                    "略過",
                    "因為沒有同步交易所未成交委託，所以不會更新本地快照。",
                    "AUTO_REBALANCE_OPEN_OFFERS=false",
                ),
            )
            self._record_skipped_step(
                bot_run_id,
                "check-open-offer-cancel-setting",
                _setting_message(
                    "舊委託取消設定檢查",
                    "略過",
                    "未同步交易所未成交委託，因此不會進一步檢查是否要取消舊委託。",
                    "AUTO_REBALANCE_OPEN_OFFERS=false",
                ),
            )
            self._record_skipped_step(
                bot_run_id,
                "evaluate-open-offer-cancel",
                _setting_message(
                    "舊委託取消評估",
                    "略過",
                    "未同步交易所未成交委託，因此不會逐筆評估舊委託是否要取消或重掛。",
                    "AUTO_REBALANCE_OPEN_OFFERS=false",
                ),
            )
            return

        step_id = self._start_step(bot_run_id, "sync-open-offers", run_step_label("sync-open-offers"))
        offers = self._exchange.get_open_loan_offers()
        self._finish_step(step_id, message=f"讀取 {len(offers)} 筆未成交委託。")

        step_id = self._start_step(bot_run_id, "replace-open-offers", run_step_label("replace-open-offers"))
        self._open_offers.replace_all(offers, profile_context=self._profile_context)
        self._finish_step(step_id, message=f"本地未成交委託已更新為 {len(offers)} 筆。")

        self._record_completed_step(
            bot_run_id,
            "check-open-offer-cancel-setting",
            run_step_label("check-open-offer-cancel-setting"),
            _setting_message(
                "舊委託自動取消",
                "開啟",
                "允許取消交易所上不符合目前策略的舊委託。",
                "BOT_DRY_RUN=false，AUTO_CANCEL_OPEN_OFFERS=true",
            )
            if not self._settings.dry_run and self._settings.auto_cancel_open_offers
            else _setting_message(
                "舊委託自動取消",
                "關閉",
                "不會取消交易所上的舊委託；模擬模式或未開啟自動取消時都只會保留。",
                (
                    f"BOT_DRY_RUN={str(self._settings.dry_run).lower()}，"
                    f"AUTO_CANCEL_OPEN_OFFERS={str(self._settings.auto_cancel_open_offers).lower()}"
                ),
            ),
        )
        if self._settings.dry_run or not self._settings.auto_cancel_open_offers:
            self._record_skipped_step(
                bot_run_id,
                "evaluate-open-offer-cancel",
                _setting_message(
                    "舊委託取消評估",
                    "略過",
                    "不會逐筆評估是否取消舊委託；模擬模式或未開啟自動取消時都只會保留。",
                    (
                        f"BOT_DRY_RUN={str(self._settings.dry_run).lower()}，"
                        f"AUTO_CANCEL_OPEN_OFFERS={str(self._settings.auto_cancel_open_offers).lower()}"
                    ),
                ),
            )
            return

        kept_offers = []
        repriced_count = 0
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
            stale_reprice_minutes = self._stale_offer_reprice_minutes(offer.currency)
            if self._settings.stale_offer_reprice_enabled and not self._is_stale_offer(offer):
                kept_offers.append(offer)
                self._finish_step(
                    step_id,
                    message=(
                        f"保留 {offer.currency} 舊委託，尚未超過 "
                        f"{stale_reprice_minutes} 分鐘重掛門檻。"
                    ),
                )
                continue
            if self._reprice_cancel_limit_reached(repriced_count):
                kept_offers.append(offer)
                self._finish_step(
                    step_id,
                    message=(
                        f"保留 {offer.currency} 舊委託，本輪已達 "
                        "STALE_OFFER_REPRICE_MAX_CANCELS_PER_RUN="
                        f"{self._settings.stale_offer_reprice_max_cancels_per_run}。"
                    ),
                )
                continue
            debounce_remaining_minutes = self._reprice_debounce_remaining_minutes(
                offer.currency
            )
            if debounce_remaining_minutes > 0:
                kept_offers.append(offer)
                self._finish_step(
                    step_id,
                    message=(
                        f"保留 {offer.currency} 舊委託，距離上次重掛取消仍需等待 "
                        f"{debounce_remaining_minutes:.1f} 分鐘。"
                    ),
                )
                continue
            if offer.external_offer_id:
                self._finish_step(step_id, message=f"{offer.currency} 舊委託可取消。")
                step_id = self._start_step(
                    bot_run_id,
                    "cancel-open-offer",
                    run_step_label("cancel-open-offer"),
                )
                self._exchange.cancel_loan_offer(offer.external_offer_id)
                self._loan_offers.mark_canceled_by_external_offer_id(
                    offer.external_offer_id,
                    profile_context=self._profile_context,
                )
                repriced_count += 1
                self._record_reprice_cancel(offer.currency)
                self._finish_step(
                    step_id,
                    message=f"已取消 {offer.currency} 舊委託 {offer.external_offer_id}。",
                )
            else:
                self._finish_step(step_id, message=f"略過 {offer.currency} 舊委託：沒有交易所委託 ID。")
        self._open_offers.replace_all(kept_offers, profile_context=self._profile_context)

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

    def _is_stale_offer(self, offer: LoanOffer) -> bool:
        if not offer.created_at:
            return False
        try:
            created_at = datetime.strptime(offer.created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return False
        age_minutes = (datetime.now(UTC) - created_at).total_seconds() / 60
        return age_minutes >= self._stale_offer_reprice_minutes(offer.currency)

    def _stale_offer_reprice_minutes(self, currency: str | None = None) -> int:
        if currency:
            regime_minutes = self._market_regime_stale_reprice_minutes(currency)
            if regime_minutes is not None:
                return regime_minutes

        risk_level = self._settings.lending_risk_level.lower()
        if risk_level == "fast":
            return max(self._settings.stale_offer_reprice_minutes_fast, 1)
        if risk_level == "yield":
            return max(self._settings.stale_offer_reprice_minutes_yield, 1)
        return max(self._settings.stale_offer_reprice_minutes_balanced, 1)

    def _market_regime_stale_reprice_minutes(self, currency: str) -> int | None:
        rates = self._market_regime_daily_rates(currency)
        if not rates:
            return None

        regime = detect_market_regime(rates[0], rates)
        return {
            "volatile_rising": 15,
            "rising": 30,
            "falling": 90,
            "volatile_falling": 120,
        }.get(regime.label)

    def _reprice_cancel_limit_reached(self, repriced_count: int) -> bool:
        limit = self._settings.stale_offer_reprice_max_cancels_per_run
        return limit > 0 and repriced_count >= limit

    def _reprice_debounce_remaining_minutes(self, currency: str) -> float:
        debounce_minutes = self._settings.stale_offer_reprice_debounce_minutes
        if debounce_minutes <= 0:
            return 0.0
        last_cancel_epoch = self._notification_state.get_float(
            self._reprice_debounce_key(currency),
            self._profile_context,
        )
        if last_cancel_epoch is None:
            return 0.0
        elapsed_seconds = datetime.now(UTC).timestamp() - last_cancel_epoch
        remaining_seconds = (debounce_minutes * 60) - elapsed_seconds
        return max(remaining_seconds / 60, 0.0)

    def _record_reprice_cancel(self, currency: str) -> None:
        if self._settings.stale_offer_reprice_debounce_minutes <= 0:
            return
        self._notification_state.set_float(
            self._reprice_debounce_key(currency),
            datetime.now(UTC).timestamp(),
            self._profile_context,
        )

    @staticmethod
    def _reprice_debounce_key(currency: str) -> str:
        return f"stale_offer_reprice_last_cancel:{currency.upper()}"

    def _frr_daily_rate(self, currency: str, frr_as_min: bool) -> float | None:
        if not frr_as_min:
            return None

        return self._exchange.get_frr_rate(currency)

    def _btc_price(self, currency: str, gap_mode: str) -> float | None:
        normalized_gap_mode = gap_mode.lower().replace("-", "_")
        if normalized_gap_mode not in {"raw_btc", "rawbtc"}:
            return None

        return self._exchange.get_btc_price(currency)

    def _filter_min_offer_value(
        self,
        decision: LendingDecision,
        min_offer_value_usd: float,
        btc_price: float | None,
    ) -> tuple[LendingDecision, str]:
        if min_offer_value_usd <= 0 or not decision.offers:
            return decision, ""

        needs_btc_conversion = decision.currency.upper() not in {"USD", "USDT", "UST"}
        usd_btc_price = self._currency_btc_price("USD") if needs_btc_conversion else None
        currency_btc_price = (
            btc_price or self._currency_btc_price(decision.currency)
            if needs_btc_conversion
            else None
        )
        kept_offers: list[LoanOffer] = []
        skipped_count = 0
        for offer in decision.offers:
            usd_value = _offer_usd_value(offer, currency_btc_price, usd_btc_price)
            if usd_value is not None and usd_value >= min_offer_value_usd:
                kept_offers.append(offer)
                continue
            skipped_count += 1

        if skipped_count == 0:
            return decision, ""

        reason = decision.reason
        if not kept_offers:
            reason = "Available balance is below the minimum offer USD value."
        message = f"略過 {skipped_count} 筆低於 MIN_OFFER_VALUE_USD={min_offer_value_usd:g} 的委託。"
        return replace(decision, offers=kept_offers, reason=reason), message

    def _currency_btc_price(self, currency: str) -> float | None:
        if currency.upper() in {"USD", "USDT", "UST"}:
            return self._exchange.get_btc_price("USD")
        return self._exchange.get_btc_price(currency)

    def _suggested_min_daily_rate(self, currency: str) -> float | None:
        if self._settings.market_analysis_method == "percentile":
            return self._market_analysis_rates.percentile_rate(
                currency,
                self._settings.market_analysis_percentile,
                self._settings.market_analysis_min_samples,
                self._settings.market_analysis_max_age_seconds,
                profile_context=self._profile_context,
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
                    profile_context=self._profile_context,
                )

            return self._market_analysis_rates.macd_rate(
                currency,
                self._settings.market_analysis_macd_short_samples,
                self._settings.market_analysis_macd_long_samples,
                self._settings.market_analysis_multiplier,
                self._settings.market_analysis_min_samples,
                self._settings.market_analysis_max_age_seconds,
                profile_context=self._profile_context,
            )

        return None

    def _historical_daily_rates(self, currency: str) -> list[float]:
        if self._settings.rate_optimization_mode != "fill_probability":
            return []

        return self._market_analysis_rates.recent_top_level_rates(
            currency,
            self._settings.rate_optimization_sample_size,
            self._settings.market_analysis_max_age_seconds,
            profile_context=self._profile_context,
        )

    def _fill_outcomes(self, currency: str) -> list[FillOutcome]:
        if self._settings.rate_optimization_mode != "fill_probability":
            return []

        return self._loan_offers.recent_fill_outcomes(
            currency,
            self._settings.rate_optimization_sample_size,
            profile_context=self._profile_context,
        )

    def _market_regime_daily_rates(self, currency: str) -> list[float]:
        return self._market_analysis_rates.recent_top_level_rates(
            currency,
            self._settings.rate_optimization_sample_size,
            self._settings.market_analysis_max_age_seconds,
            profile_context=self._profile_context,
        )

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
            for row in self._open_offers.recent(
                limit=1000,
                profile_context=self._profile_context,
            )
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
                "rate_candidates": [candidate.__dict__ for candidate in decision.rate_candidates],
                "market_regime": _market_regime_snapshot(decision),
                "allocation_mode": decision.allocation_mode,
                "allocation_reason": decision.allocation_reason,
                "stale_reprice_minutes": self._stale_offer_reprice_minutes(balance.currency),
                "reason": decision.reason,
            },
            profile_context=self._profile_context,
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

    def _maybe_send_periodic_summary(self, active_loans: list[ActiveLoan]) -> tuple[bool, str]:
        if self._settings.notify_summary_minutes <= 0:
            return False, _setting_message(
                "週期摘要通知",
                "關閉",
                "不會定時發送 Telegram 放貸與收益摘要。",
                "NOTIFY_SUMMARY_MINUTES=0",
            )

        now = time.time()
        state_key = "telegram_summary_last_sent_at"
        last_sent_at = self._notification_state.get_float(
            state_key,
            profile_context=self._profile_context,
        )
        interval_seconds = self._settings.notify_summary_minutes * 60
        if last_sent_at is not None and now - last_sent_at < interval_seconds:
            return (
                False,
                _setting_message(
                    "週期摘要通知",
                    "暫不發送",
                    "距離上次發送尚未達設定間隔，本輪不會重複發送摘要。",
                    f"NOTIFY_SUMMARY_MINUTES={self._settings.notify_summary_minutes}",
                ),
            )

        open_offers = self._open_offers.recent(
            limit=1000,
            profile_context=self._profile_context,
        )
        earnings = self._lending_history.earnings_summary_by_currency(self._profile_context)
        self._notifier.periodic_summary(
            _summary_message(
                active_loans=active_loans,
                open_offers=open_offers,
                earnings=earnings,
            )
        )
        self._notification_state.set_float(
            state_key,
            now,
            profile_context=self._profile_context,
        )
        return True, "已發送週期摘要通知。"

    def _notify_xday_offer(self, offer: LoanOffer) -> bool:
        if not self._settings.notify_xday_threshold:
            return False
        if offer.duration_days <= 2:
            return False

        self._notifier.xday_offer(offer, dry_run=self._settings.dry_run)
        return True

    def _xday_notification_skip_message(self, offer: LoanOffer) -> str:
        if not self._settings.notify_xday_threshold:
            return _setting_message(
                f"{offer.currency} 長天期委託通知",
                "關閉",
                "不會針對長天期委託發送 Telegram 提醒。",
                "NOTIFY_XDAY_THRESHOLD=false",
            )
        return _setting_message(
            f"{offer.currency} 長天期委託通知",
            "不需要",
            f"本筆委託天期是 {offer.duration_days} 天，未超過長天期通知門檻。",
            f"duration_days={offer.duration_days}",
        )

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
                self._loan_offers.mark_filled_by_active_loan(
                    active_loan,
                    profile_context=self._profile_context,
                )
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
    return "、".join(f"{balance.currency} {_format_decimal_amount(balance.amount)}" for balance in balances) + "。"


def _offer_usd_value(
    offer: LoanOffer,
    currency_btc_price: float | None,
    usd_btc_price: float | None,
) -> float | None:
    if offer.currency.upper() in {"USD", "USDT", "UST"}:
        return offer.amount
    if currency_btc_price is None or usd_btc_price is None or usd_btc_price <= 0:
        return None
    return offer.amount * currency_btc_price / usd_btc_price


def _format_decimal_amount(amount: float) -> str:
    value = format(Decimal(str(amount)), "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def _format_daily_and_annual_rate(daily_rate: float) -> str:
    return f"{_format_decimal_amount(daily_rate)}（年化 {_format_rate_percent(daily_rate * 365)}）"


def _setting_message(title: str, status: str, impact: str, setting: str) -> str:
    return f"{title}：{status}\n影響：{impact}\n設定鍵：{setting}"


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


def _decision_calculation_summary(
    balance: CurrencyBalance,
    active_amount: float,
    order_book: list[LoanOrder],
    strategy,
    frr_daily_rate: float | None,
    suggested_min_daily_rate: float | None,
    decision,
    historical_daily_rates: list[float],
) -> str:
    best_daily_rate = max((order.daily_rate for order in order_book), default=0)
    effective_min_daily_rate = _effective_min_daily_rate(
        strategy,
        frr_daily_rate,
        suggested_min_daily_rate,
    )
    percent_amount = round(balance.amount * (strategy.max_percent_to_lend / 100), 8)
    percent_limit_applies = _should_apply_lend_percent_limit(best_daily_rate, strategy)
    amount_after_percent = percent_amount if percent_limit_applies else round(balance.amount, 8)
    amount_after_max = amount_after_percent
    if percent_limit_applies and strategy.max_amount_to_lend is not None:
        amount_after_max = round(min(amount_after_percent, strategy.max_amount_to_lend), 8)

    active_remaining = None
    final_lendable_amount = amount_after_max
    if strategy.max_active_amount is not None:
        active_remaining = round(max(strategy.max_active_amount - active_amount, 0), 8)
        final_lendable_amount = round(min(amount_after_max, active_remaining), 8)

    prepared_amount = round(sum(offer.amount for offer in decision.offers), 8)
    will_create_offers = len(decision.offers) > 0
    lines = [
        f"{balance.currency}：{_decision_result_summary(decision, best_daily_rate, effective_min_daily_rate)}",
        (
            "利率比較："
            f"市場最佳 {_format_rate_percent(best_daily_rate * 365)} 年化；"
            f"最低要求 {_format_rate_percent(effective_min_daily_rate * 365)} 年化。"
        ),
        (
            "最低要求來源："
            f"設定 {_format_rate_percent(strategy.min_daily_rate * 365)}；"
            f"FRR {_optional_annual_rate(_frr_min_daily_rate(strategy, frr_daily_rate))}；"
            f"市場分析 {_optional_annual_rate(suggested_min_daily_rate)}。"
        ),
        (
            "定價方式："
            f"{_decision_pricing_mode_label(decision, strategy)}；"
            f"最佳化樣本 {len(historical_daily_rates)} 筆。"
        ),
        (
            "拆單方式："
            f"{_split_mode_label(strategy)}；"
            f"保留尾款 {_format_decimal_amount(round(max(final_lendable_amount - prepared_amount, 0), 8))}。"
        ),
    ]
    if will_create_offers:
        lines.append(
            "預計掛單："
            f"{len(decision.offers)} 筆；"
            f"年化 {_offer_annualized_rate_summary(decision.offers)}；"
            f"天期 {_offer_duration_summary(decision.offers)}。"
        )
    if decision.rate_candidates:
        lines.append(f"候選利率：{_rate_candidate_summary(decision.rate_candidates)}。")
    if decision.market_regime:
        lines.append(f"市場狀態：{_market_regime_summary(decision.market_regime)}。")
    lines.append(
        "金額："
        f"可用 {_format_decimal_amount(balance.amount)}，"
        f"本輪可放貸 {_format_decimal_amount(final_lendable_amount)}，"
        f"實際準備 {_format_decimal_amount(prepared_amount)}。"
    )
    if percent_limit_applies or strategy.max_amount_to_lend is not None or strategy.max_active_amount is not None:
        lines.append(
            "限制："
            f"比例後 {_format_decimal_amount(percent_amount)}，"
            f"金額上限後 {_format_decimal_amount(amount_after_max)}，"
            f"目前放貸中 {_format_decimal_amount(active_amount)}。"
        )
    return "\n".join(lines)


def _should_apply_lend_percent_limit(best_daily_rate: float, strategy) -> bool:
    if strategy.max_amount_to_lend is None and strategy.max_percent_to_lend >= 100:
        return False
    if best_daily_rate <= 0:
        return False
    return strategy.max_to_lend_rate == 0 or best_daily_rate <= strategy.max_to_lend_rate


def _optional_amount(amount: float | None) -> str:
    return "未設定" if amount is None else _format_decimal_amount(amount)


def _split_mode_label(strategy) -> str:
    if strategy.max_offer_amount is not None and strategy.max_offer_amount >= strategy.min_loan_size:
        return (
            f"每筆最多 {_format_decimal_amount(strategy.max_offer_amount)}，"
            f"尾款小於等於 {_format_decimal_amount(strategy.min_offer_remainder)} 不下單"
        )
    return f"固定拆成 {max(strategy.spread_lend, 1)} 筆"


def _decision_result_summary(decision, best_daily_rate: float, effective_min_daily_rate: float) -> str:
    if decision.offers:
        if best_daily_rate < effective_min_daily_rate:
            return f"會用有效最低利率先建立 {len(decision.offers)} 筆委託。"
        return f"會建立 {len(decision.offers)} 筆委託。"
    if best_daily_rate < effective_min_daily_rate:
        return "不掛單，因為市場利率低於最低要求。"
    return f"不掛單，原因：{decision.reason}"


def _optional_annual_rate(daily_rate: float | None) -> str:
    return "未使用" if daily_rate is None else _format_rate_percent(daily_rate * 365)


def _pricing_mode_label(rate_optimization_mode: str, gap_mode: str) -> str:
    if rate_optimization_mode == "fill_probability":
        return "用歷史樣本估算成交機率後選利率"
    if gap_mode.lower().replace("-", "_") in {"raw_btc", "rawbtc"}:
        return "用 BTC 深度尋找掛單利率"
    if gap_mode.lower() == "off":
        return "跟隨市場最佳利率"
    return f"使用 {gap_mode} 深度策略"


def _decision_pricing_mode_label(decision, strategy) -> str:
    if decision.reason == "Created minimum-rate offers while market is below the configured minimum.":
        return "市場低於最低要求，直接使用有效最低利率掛單"
    return _pricing_mode_label(strategy.rate_optimization_mode, strategy.gap_mode)


def _effective_min_daily_rate(
    strategy,
    frr_daily_rate: float | None,
    suggested_min_daily_rate: float | None,
) -> float:
    return max(
        strategy.min_daily_rate,
        suggested_min_daily_rate or 0,
        _frr_min_daily_rate(strategy, frr_daily_rate) or 0,
    )


def _frr_min_daily_rate(strategy, frr_daily_rate: float | None) -> float | None:
    if frr_daily_rate is None:
        return None
    return frr_daily_rate + strategy.frr_delta


def _optional_rate(rate: float | None) -> str:
    return "未使用" if rate is None else _format_decimal_amount(rate)


def _offer_rate_summary(offers: list[LoanOffer]) -> str:
    if not offers:
        return "無委託利率"
    return "、".join(_format_decimal_amount(offer.daily_rate) for offer in offers)


def _rate_candidate_summary(candidates) -> str:
    return "、".join(
        (
            f"{_format_rate_percent(candidate.daily_rate * 365)} "
            f"成交率 {_format_rate_percent(candidate.fill_probability)} "
            f"分數 {_format_decimal_amount(candidate.expected_score)}"
            f"{f'（{candidate.selection_role}）' if candidate.selection_role else ''}"
        )
        for candidate in candidates[:5]
    )


def _market_regime_snapshot(decision) -> dict[str, object]:
    if not decision.market_regime:
        return {}
    return decision.market_regime.__dict__


def _market_regime_summary(regime) -> str:
    label = {
        "rising": "升溫",
        "falling": "降溫",
        "stable": "穩定",
        "volatile_rising": "高波動升溫",
        "volatile_falling": "高波動降溫",
        "volatile_range": "高波動盤整",
        "insufficient_data": "樣本不足",
        "unknown": "未知",
    }.get(regime.label, regime.label)
    return f"{label}，樣本 {regime.sample_count} 筆"


def _offer_strategy_snapshot(strategy) -> dict[str, object]:
    return {
        "lending_risk_level": strategy.lending_risk_level,
        "rate_optimization_mode": strategy.rate_optimization_mode,
        "rate_optimization_min_probability": strategy.rate_optimization_min_probability,
        "rate_optimization_sample_size": strategy.rate_optimization_sample_size,
        "dynamic_duration_enabled": strategy.dynamic_duration_enabled,
        "min_offer_value_usd": strategy.min_offer_value_usd,
    }


def _offer_duration_summary(offers: list[LoanOffer]) -> str:
    if not offers:
        return "無委託天期"
    return "、".join(f"{offer.duration_days} 天" for offer in offers)


def _offer_annualized_rate_summary(offers: list[LoanOffer]) -> str:
    if not offers:
        return "無委託年化利率"
    return "、".join(_format_rate_percent(offer.daily_rate * 365) for offer in offers)


def _format_rate_percent(rate: float) -> str:
    return f"{_format_decimal_amount(round(rate * 100, 10))}%"


def _optional_exchange_balances(exchange: ExchangeClient, method_name: str) -> list[CurrencyBalance]:
    method = getattr(exchange, method_name, None)
    if method is None:
        return []
    return method()
