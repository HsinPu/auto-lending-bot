from auto_lending_bot.bot.run_steps import RUN_STEP_DEFINITIONS, RUN_STEPS_BY_KEY, run_step_label


def test_run_step_catalog_has_stable_unique_keys() -> None:
    keys = [step.key for step in RUN_STEP_DEFINITIONS]

    assert keys == [
        "create-run",
        "sync-active-loans",
        "detect-new-active-loans",
        "sync-balances",
        "sync-open-offers",
        "rebalance-open-offers",
        "load-market-orders",
        "record-market-orders",
        "load-strategy-inputs",
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
