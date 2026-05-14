from auto_lending_bot.bot.run_steps import RUN_STEP_DEFINITIONS, RUN_STEPS_BY_KEY, run_step_label


def test_run_step_catalog_has_stable_unique_keys() -> None:
    keys = [step.key for step in RUN_STEP_DEFINITIONS]

    assert keys == [
        "create-run",
        "read-previous-active-loans",
        "read-active-loans",
        "replace-active-loans",
        "detect-new-active-loans",
        "read-lending-balances",
        "check-open-offer-rebalance-setting",
        "sync-open-offers",
        "replace-open-offers",
        "check-open-offer-cancel-setting",
        "rebalance-open-offers",
        "evaluate-open-offer-cancel",
        "cancel-open-offer",
        "load-market-orders",
        "record-market-orders",
        "load-strategy-config",
        "load-frr-rate",
        "load-btc-price",
        "load-market-analysis-rate",
        "calculate-active-amount",
        "calculate-decisions",
        "record-decisions",
        "prepare-offers",
        "record-dry-run-offers",
        "validate-live-offers",
        "record-live-intents",
        "submit-live-offers",
        "update-offer-results",
        "finish-run",
        "send-notifications",
    ]
    assert len(RUN_STEPS_BY_KEY) == len(keys)
    assert run_step_label("submit-live-offers") == "送出 Bitfinex 委託"
